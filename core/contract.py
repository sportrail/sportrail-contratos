"""Hidrata o template do contrato e gera o PDF. Calcula trilho de auditoria."""
import hashlib
import datetime
import io
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from weasyprint.urls import URLFetcher
from pypdf import PdfReader, PdfWriter

from .clausulas import (ENTIDADE, clausulas, precisa_formulario_resolucao,
                        PRAZO_LIVRE_RESOLUCAO_DIAS)

BASE = Path(__file__).resolve().parent.parent
_env = Environment(loader=FileSystemLoader(str(BASE / "templates")))


def _assinatura_diretora_data_uri():
    """Devolve a assinatura da Diretora como data-URI (ou None se não existir)."""
    p = BASE / "static" / "assinatura_diretora.png"
    if not p.exists():
        return None
    import base64
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:image/png;base64,{b64}"


def _logo():
    """Logótipo Sportrail para o cabeçalho do contrato, se existir em static/.

    Prefere SVG (vetorial, nítido em qualquer ampliação do PDF); cai para PNG
    embutido em data-URI. Devolve None se não houver ficheiro — nesse caso o
    template usa a wordmark tipográfica.
    """
    svg = BASE / "static" / "logo_sportrail.svg"
    if svg.exists():
        return {"formato": "svg", "conteudo": svg.read_text(encoding="utf-8")}
    png = BASE / "static" / "logo_sportrail.png"
    if png.exists():
        import base64
        b64 = base64.b64encode(png.read_bytes()).decode()
        return {"formato": "png", "conteudo": f"data:image/png;base64,{b64}"}
    return None


def render_html(curso, formando, *, tipo="B2C", assinatura_formando=None,
                auditoria=None):
    """Devolve o HTML do contrato hidratado para a variante B2C ou B2B."""
    tpl = _env.get_template("contrato.html")
    online = curso.get("modalidade", "").lower().startswith("online") \
        or curso.get("modalidade", "").lower().startswith("dist")
    return tpl.render(
        entidade=ENTIDADE,
        curso=curso,
        formando=formando,
        tipo=tipo.upper(),
        clausulas=clausulas(online=online, tipo=tipo),
        assinatura_diretora=_assinatura_diretora_data_uri(),
        logo=_logo(),
        assinatura_formando=assinatura_formando,
        auditoria=auditoria,
        formulario_resolucao=precisa_formulario_resolucao(tipo),
        prazo_resolucao=PRAZO_LIVRE_RESOLUCAO_DIAS,
    )


def gerar_pdf(html, destino):
    """Renderiza HTML -> PDF no caminho destino."""
    HTML(string=html, base_url=str(BASE)).write_pdf(destino)
    return destino


def gerar_pdf_bytes(html):
    """Renderiza HTML -> PDF e devolve os bytes (sem escrever em disco).

    Usado pelo endpoint /api/gerar-contrato (motor de PDF para o dashboard)."""
    return HTML(string=html, base_url=str(BASE)).write_pdf()


# Tamanho máximo do HTML aceite pelo render genérico. Os documentos do dossier
# trazem imagens embutidas como data-URI, por isso a folga; o limite existe para
# que um payload absurdo não prenda o worker.
LIMITE_HTML_BYTES = 2 * 1024 * 1024


def gerar_pdf_bytes_isolado(html):
    """Renderiza HTML ARBITRÁRIO -> PDF, sem acesso ao disco nem à rede.

    Usado pelo endpoint /api/render-pdf, o motor de PDF dos documentos do dossier
    técnico-pedagógico (os templates vivem no dashboard, não aqui).

    Ao contrário de gerar_pdf_bytes, este render não pode confiar no HTML que
    recebe. Sem isolamento, um `<img src="file:///etc/passwd">` ou um
    `<link href="http://169.254.169.254/...">` transformavam o endpoint numa
    primitiva de leitura de ficheiros do servidor e de pedidos de saída:
      - base_url=None      -> caminhos relativos não resolvem para o repo;
      - allowed_protocols  -> só `data:` passa; file/http/https levantam ValueError.
    Tudo o que o documento precisar (logótipos, assinaturas) vai embutido em
    data-URI, que é como o contrato já embute a assinatura da Diretora.
    """
    if len(html.encode("utf-8")) > LIMITE_HTML_BYTES:
        raise ValueError(
            f"HTML acima do limite de {LIMITE_HTML_BYTES // (1024 * 1024)} MB.")
    fetcher = URLFetcher(allowed_protocols={"data"})
    return HTML(string=html, base_url=None, url_fetcher=fetcher).write_pdf()


# --- Juntar PDF (DTP compilado) --------------------------------------------
# Um dossier técnico-pedagógico acaba num PDF único, ordenado pelas secções do
# referencial. As partes chegam já geradas e ARQUIVADAS — não se regeram aqui.
# É esse o ponto: o compilado é o dossier tal como foi datado e arquivado, e o
# hash de cada parte já está registado no dashboard.

LIMITE_JUNTAR_BYTES = 40 * 1024 * 1024
LIMITE_JUNTAR_PARTES = 40


def juntar_pdfs(documentos):
    """Junta PDF já gerados num só, com marcadores por documento.

    `documentos` é uma lista de {"pdf": bytes, "titulo": str}. A ordem é a que
    vem — quem sabe a ordem do referencial é o dashboard, não este motor.

    Os marcadores (outline) não são enfeite: um DTP compilado tem para cima de
    cinquenta páginas, e sem eles quem o audita percorre-o à roda do rato.

    Falha FECHADO e a dizer qual: um PDF corrompido ou cifrado no meio de quinze
    não se pode ignorar em silêncio, senão o compilado sai com um documento a
    menos e ninguém repara.
    """
    if not documentos:
        raise ValueError("Sem documentos para juntar.")
    if len(documentos) > LIMITE_JUNTAR_PARTES:
        raise ValueError(
            f"Demasiados documentos ({len(documentos)}); o limite é "
            f"{LIMITE_JUNTAR_PARTES}.")

    total = sum(len(d.get("pdf") or b"") for d in documentos)
    if total > LIMITE_JUNTAR_BYTES:
        raise ValueError(
            f"Conjunto acima do limite de "
            f"{LIMITE_JUNTAR_BYTES // (1024 * 1024)} MB.")

    escritor = PdfWriter()
    for indice, doc in enumerate(documentos, start=1):
        titulo = (doc.get("titulo") or f"Documento {indice}").strip()
        bytes_pdf = doc.get("pdf") or b""
        if not bytes_pdf:
            raise ValueError(f"{titulo}: PDF vazio.")
        try:
            leitor = PdfReader(io.BytesIO(bytes_pdf))
            if leitor.is_encrypted:
                raise ValueError(f"{titulo}: PDF cifrado.")
            primeira = len(escritor.pages)
            for pagina in leitor.pages:
                escritor.add_page(pagina)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"{titulo}: PDF ilegível ({e.__class__.__name__}).")

        if len(escritor.pages) == primeira:
            raise ValueError(f"{titulo}: PDF sem páginas.")
        escritor.add_outline_item(titulo, primeira)

    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def hash_pdf(pdf_bytes, doc_id):
    """SHA-256 do PDF compilado (vincula doc_id + os bytes exatos)."""
    h = hashlib.sha256()
    h.update(f"{doc_id}|".encode("utf-8"))
    h.update(pdf_bytes)
    return h.hexdigest()


def construir_auditoria_compilado(doc_id, pdf_bytes):
    """Trilho de auditoria de um PDF compilado a partir de outros já gerados."""
    agora = datetime.datetime.now(datetime.timezone.utc).astimezone()
    return {
        "data": agora.strftime("%d/%m/%Y %H:%M:%S"),
        "tz": agora.strftime("%Z") or "UTC",
        "doc_id": doc_id,
        "hash": hash_pdf(pdf_bytes, doc_id),
    }


def hash_html(html, doc_id):
    """SHA-256 do documento renderizado (vincula doc_id + conteúdo exato)."""
    return hashlib.sha256(f"{doc_id}|{html}".encode("utf-8")).hexdigest()


def construir_auditoria_documento(doc_id, html):
    """Trilho de auditoria de um documento do dossier (sem partes nem assinatura)."""
    agora = datetime.datetime.now(datetime.timezone.utc).astimezone()
    return {
        "data": agora.strftime("%d/%m/%Y %H:%M:%S"),
        "tz": agora.strftime("%Z") or "UTC",
        "doc_id": doc_id,
        "hash": hash_html(html, doc_id),
    }


def hash_conteudo(curso, formando, assinatura_formando, doc_id):
    """SHA-256 do conteúdo lógico do contrato (vincula dados+assinatura)."""
    blob = "|".join([
        doc_id,
        curso.get("nome", ""), curso.get("duracao", ""),
        curso.get("data_inicio", ""), curso.get("data_conclusao", ""),
        formando.get("nome", ""), formando.get("nif", ""),
        formando.get("valor_pago", ""),
        (assinatura_formando or "")[:120],
    ])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def construir_auditoria(curso, formando, assinatura_formando, doc_id, ip):
    agora = datetime.datetime.now(datetime.timezone.utc).astimezone()
    return {
        "data": agora.strftime("%d/%m/%Y %H:%M:%S"),
        "tz": agora.strftime("%Z") or "UTC",
        "ip": ip or "—",
        "doc_id": doc_id,
        "hash": hash_conteudo(curso, formando, assinatura_formando, doc_id),
    }
