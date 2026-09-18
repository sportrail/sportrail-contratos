"""Hidrata o template do contrato e gera o PDF. Calcula trilho de auditoria."""
import hashlib
import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from weasyprint.urls import URLFetcher

from .clausulas import (ENTIDADE, VERSAO_MINUTA, FECHO_MINUTA, corpo_contrato,
                        adenda_livre_resolucao, precisa_adenda,
                        precisa_formulario_resolucao,
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
                auditoria=None, local_assinatura=None, data_assinatura=None):
    """Devolve o HTML do contrato hidratado para a variante B2C ou B2B.

    O corpo é a minuta aprovada pela DGERT, igual nas duas variantes. O que
    distingue o B2C é a ADENDA de livre resolução (mais o formulário anexo),
    acrescentada depois das assinaturas — nunca dentro do articulado aprovado.
    """
    tpl = _env.get_template("contrato.html")
    tipo = tipo.upper()
    return tpl.render(
        entidade=ENTIDADE,
        versao_minuta=VERSAO_MINUTA,
        curso=curso,
        formando=formando,
        tipo=tipo,
        corpo=corpo_contrato(curso),
        fecho=FECHO_MINUTA,
        adenda=[{"titulo": t, "texto": x} for t, x in adenda_livre_resolucao()]
               if precisa_adenda(tipo) else None,
        # Local e data do fecho da minuta. Sem assinatura ainda -> ficam os
        # tracejados, que é como a minuta em papel sai para assinar à mão.
        local_assinatura=local_assinatura or ENTIDADE["morada"].split(",")[0],
        data_assinatura=data_assinatura or (auditoria or {}).get("data", "").split(" ")[0],
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
