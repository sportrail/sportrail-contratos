"""
Smoke test do motor de contratos e de PDF. Corre: `python verify.py` ou `make verify`.

Verifica, sem servidor e sem rede:
  1. cláusulas por variante (B2C tem livre resolução, B2B não);
  2. geração do PDF B2C (com anexo de livre resolução) e B2B (sem);
  3. trilho de auditoria (hash determinístico) presente;
  4. nenhum marcador de andaime no texto extraído dos PDF;
  5. o texto de consentimento, que é o que dá valor jurídico à assinatura;
  6. o render genérico isolado (/api/render-pdf) e a sua paginação;
  7. juntar PDF (/api/juntar-pdf): páginas, marcadores e recusa de lixo;
  8. que todas as rotas exigem o PDF_API_TOKEN, exceto o /health.

Sai com código 0 se tudo passar, 1 se algo falhar.

NOTA HISTÓRICA, que vale a pena não repetir: este ficheiro testava também um
`core/store.py` contra um duplo em memória, e validava as colunas escritas
contra o `supabase_schema.sql` deste repo. Esse schema nunca chegou a ser
aplicado — a base de dados tinha (e tem) o do dashboard. Os testes passavam
todos contra o esquema errado, enquanto em produção nenhum formando conseguia
assinar. Um teste que valida código contra a sua própria suposição não prova
nada. O estado saiu daqui; ver `tasks/bug-assinatura.md` no dashboard.
"""
import io
import sys
import tempfile
from pathlib import Path

from core import contract
from core.clausulas import (ENTIDADE, PRAZO_LIVRE_RESOLUCAO_DIAS,
                            clausulas, texto_consentimento)
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
falhas = []


def check(cond, msg):
    estado = "OK " if cond else "FALHA"
    print(f"[{estado}] {msg}")
    if not cond:
        falhas.append(msg)


def main():
    # 0) Config da entidade que sai impressa no contrato
    check(bool(ENTIDADE.get("email")),
          "ENTIDADE['email'] preenchido (sai na Cláusula 6.ª e no anexo)")

    curso = {"nome": "Goalkeeper Coaching Course",
             "modalidade": "Online (formação a distância)",
             "duracao": "12 horas", "data_inicio": "22/09/2026",
             "data_conclusao": "08/10/2026"}

    # Autenticação dos endpoints (independente do pipeline de PDF)
    verificar_auth_api()

    # 1) Cláusulas por variante
    n_b2c = len(clausulas(online=True, tipo="B2C"))
    n_b2b = len(clausulas(online=True, tipo="B2B"))
    check(n_b2c > n_b2b, f"B2C tem mais cláusulas que B2B ({n_b2c} vs {n_b2b})")

    # Formando de referência. Era lido do formandos_exemplo.xlsx, que saiu com
    # o excel_parser: quem lê Excel agora é o dashboard. Aqui basta a forma que
    # o render_html espera.
    f = {"nome": "Ana Teste", "email": "ana@exemplo.pt", "nif": "123456789",
         "valor_pago": "47", "morada": "Rua do Exemplo, 1, Lisboa"}

    # PNG 1x1 real. O valor anterior tinha padding base64 errado (95 chars):
    # o WeasyPrint descartava a imagem em silêncio, por isso estes testes nunca
    # chegaram a exercitar a assinatura que dizem estar a testar.
    sig = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
           "AAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==")

    with tempfile.TemporaryDirectory() as tmp:
        # 3) B2C com auditoria
        doc_id = "VERIFY0001"
        aud = contract.construir_auditoria(curso, f, sig, doc_id, "127.0.0.1")
        check(len(aud["hash"]) == 64, "Hash SHA-256 de auditoria gerado")

        p_b2c = Path(tmp) / "b2c.pdf"
        contract.gerar_pdf(contract.render_html(
            curso, f, tipo="B2C", assinatura_formando=sig, auditoria=aud), str(p_b2c))
        n1 = len(PdfReader(str(p_b2c)).pages)
        check(n1 >= 3, f"PDF B2C gerado com anexo de livre resolução ({n1} págs)")

        # 4) B2B
        p_b2b = Path(tmp) / "b2b.pdf"
        contract.gerar_pdf(contract.render_html(
            curso, f, tipo="B2B", assinatura_formando=sig, auditoria=aud), str(p_b2b))
        n2 = len(PdfReader(str(p_b2b)).pages)
        check(n2 < n1, f"PDF B2B sem anexo, menos páginas que B2C ({n2} págs)")

        # 5) Nenhum marcador de andaime pode chegar ao documento do formando.
        # Lemos o texto extraído do PDF, não o código-fonte: dois dos marcadores
        # viviam no template do anexo, que só é renderizado em B2C — um grep aos
        # .py dava tudo limpo enquanto o documento saía sujo.
        for rotulo, caminho in (("B2C", p_b2c), ("B2B", p_b2b)):
            texto = "\n".join(pg.extract_text() or ""
                              for pg in PdfReader(str(caminho)).pages)
            sujos = [m for m in ("JURISTA", "[EMAIL", "RASCUNHO") if m in texto]
            check(not sujos,
                  f"PDF {rotulo} sem marcadores de andaime"
                  + (f" (encontrado: {', '.join(sujos)})" if sujos else ""))

        # O email da entidade tem de sair impresso: é o endereço para onde o
        # formando envia a declaração de livre resolução. Só aparece no B2C.
        texto_b2c = "\n".join(pg.extract_text() or ""
                              for pg in PdfReader(str(p_b2c)).pages)
        check(ENTIDADE["email"] in texto_b2c,
              f"PDF B2C indica o email da entidade ({ENTIDADE['email']})")
    # 6) Consentimento — é o que dá valor jurídico à assinatura eletrónica
    verificar_consentimento()

    # 7) Render genérico (motor de PDF do dossier)
    verificar_render_isolado()

    # 8) Juntar PDF (DTP compilado)
    verificar_juntar_pdfs()

    print()
    if falhas:
        print(f"❌ {len(falhas)} verificação(ões) falharam.")
        sys.exit(1)
    print("✅ Tudo OK.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Render genérico isolado (/api/render-pdf — documentos do dossier)
# ---------------------------------------------------------------------------
# Aqui o HTML vem do dashboard, não dos nossos templates. Duas coisas têm de se
# manter verdadeiras a cada commit:
#   (a) o render não toca no disco nem na rede — senão o endpoint é uma
#       primitiva de leitura de ficheiros do servidor;
#   (b) o CSS de paginação (@page, counter(page), cabeçalho corrido) funciona —
#       é aquilo de que os documentos do dossier dependem e que o contrato,
#       sendo de página única sem numeração, nunca exercitou.

def verificar_render_isolado():
    from weasyprint.urls import URLFetcher

    # (a) protocolos: só `data:` passa.
    fetcher = URLFetcher(allowed_protocols={"data"})
    bloqueados = []
    for url in ("file:///etc/passwd", "https://example.com/a.png",
                "http://169.254.169.254/latest/meta-data/"):
        try:
            fetcher.fetch(url)
        except Exception:
            bloqueados.append(url)
    check(len(bloqueados) == 3,
          "URLFetcher isolado bloqueia file://, https:// e http:// "
          f"({len(bloqueados)}/3)")

    # `data:` continua a passar — é assim que logótipos e assinaturas entram.
    px = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
          "AAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==")
    try:
        fetcher.fetch(px)
        passa_data = True
    except Exception:
        passa_data = False
    check(passa_data, "URLFetcher isolado deixa passar data: URI")

    # E o render completo: um documento hostil sai sem o conteúdo do ficheiro.
    hostil = ('<html><head><link rel="stylesheet" href="file:///etc/passwd">'
              '</head><body><p>corpo</p>'
              '<img src="file:///etc/passwd">'
              '<img src="static/assinatura_diretora.png">'
              '</body></html>')
    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "hostil.pdf"
        alvo.write_bytes(contract.gerar_pdf_bytes_isolado(hostil))
        texto = "\n".join(pg.extract_text() or "" for pg in PdfReader(str(alvo)).pages)
    check("root:" not in texto and "corpo" in texto,
          "Render isolado gera o PDF sem embeber ficheiros locais")

    # Limite de tamanho: um payload absurdo é recusado antes de chegar ao motor.
    gigante = "<p>x</p>" * (contract.LIMITE_HTML_BYTES // 4)
    try:
        contract.gerar_pdf_bytes_isolado(gigante)
        recusou = False
    except ValueError:
        recusou = True
    check(recusou, "HTML acima do limite é recusado (ValueError → 413)")

    # (b) paginação: numeração e cabeçalho corrido em duas páginas.
    paginado = ("<html><head><style>"
                "@page { size: A4; margin: 20mm;"
                "  @top-center { content: element(topo); }"
                "  @bottom-right { content: 'Pagina ' counter(page) ' de ' counter(pages); } }"
                ".topo { position: running(topo); }"
                ".p2 { break-before: page; }"
                "</style></head><body>"
                "<div class='topo'>CABECALHO SPORTRAIL</div>"
                "<p>primeira</p><p class='p2'>segunda</p>"
                "</body></html>")
    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "paginado.pdf"
        alvo.write_bytes(contract.gerar_pdf_bytes_isolado(paginado))
        paginas = [pg.extract_text() or "" for pg in PdfReader(str(alvo)).pages]
    check(len(paginas) == 2, f"Render isolado respeita break-before: page ({len(paginas)} págs)")
    texto = "\n".join(paginas)
    check("Pagina 1 de 2" in texto and "Pagina 2 de 2" in texto,
          "counter(page)/counter(pages) numeram as páginas")
    check(all("CABECALHO SPORTRAIL" in pg for pg in paginas),
          "Cabeçalho corrido (position: running) repete em todas as páginas")

    # Acentuação: o dossier é todo em português e a imagem só traz DejaVu.
    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "acentos.pdf"
        alvo.write_bytes(contract.gerar_pdf_bytes_isolado(
            "<p>Ação de formação — avaliação síncrona</p>"))
        texto = (PdfReader(str(alvo)).pages[0].extract_text() or "")
    check("Ação de formação" in texto and "avaliação síncrona" in texto,
          "Acentuação portuguesa sobrevive ao render")


# ---------------------------------------------------------------------------
# Consentimento
# ---------------------------------------------------------------------------
# É a declaração que o formando aceita ao assinar, e o que dá à assinatura
# eletrónica simples (eIDAS) o valor de uma manuscrita. Em B2C é também o
# pedido expresso do art. 4.º do DL 24/2014 para começar a formação antes de
# terminado o prazo de livre resolução — se esse texto desaparecer, começar a
# formação nesse prazo deixa de estar coberto.

def verificar_consentimento():
    b2c = texto_consentimento("B2C")
    b2b = texto_consentimento("B2B")
    check("assinatura eletrónica" in b2c and "assinatura eletrónica" in b2b,
          "Ambas as variantes declaram a assinatura eletrónica")
    check(f"{PRAZO_LIVRE_RESOLUCAO_DIAS} dias" in b2c,
          f"B2C cita o prazo de livre resolução ({PRAZO_LIVRE_RESOLUCAO_DIAS} dias)")
    check("Solicito expressamente" in b2c,
          "B2C traz o pedido expresso do art. 4.º (início antes dos 14 dias)")
    check("livre resolu" not in b2b.lower(),
          "B2B não menciona livre resolução")
    check("representação da entidade" in b2b,
          "B2B assina em representação da entidade adquirente")
    check(texto_consentimento("b2c") == b2c,
          "tipo em minúsculas dá o mesmo texto (normalização)")


# ---------------------------------------------------------------------------
# Juntar PDF (/api/juntar-pdf — o DTP compilado)
# ---------------------------------------------------------------------------
# O compilado junta documentos ARQUIVADOS. Se uma parte entrar corrompida e for
# ignorada em silêncio, o dossier sai com um documento a menos e ninguém repara
# até alguém o auditar. Por isso o que se verifica aqui não é só que junta: é
# que RECUSA, e que diz qual.

def verificar_juntar_pdfs():
    from core import contract

    def pdf_de(texto, paginas=1):
        corpo = "".join(
            f'<div style="{"break-before: page;" if i else ""}">{texto} {i + 1}</div>'
            for i in range(paginas))
        return contract.gerar_pdf_bytes_isolado(
            f"<!DOCTYPE html><html><body>{corpo}</body></html>")

    partes = [
        {"pdf": pdf_de("Programa", 2), "titulo": "02 · Programa de formação"},
        {"pdf": pdf_de("Cronograma", 1), "titulo": "03 · Cronograma"},
        {"pdf": pdf_de("Pauta", 3), "titulo": "10 · Pauta de avaliação"},
    ]

    junto = contract.juntar_pdfs(partes)
    leitor = PdfReader(io.BytesIO(junto))
    check(len(leitor.pages) == 6,
          f"Junta 2+1+3 páginas e dá 6 (deu {len(leitor.pages)})")

    titulos = [item.title for item in leitor.outline if hasattr(item, "title")]
    check(titulos == [p["titulo"] for p in partes],
          f"Marcadores pela ordem dada (deu {titulos})")

    # A ordem é a que vem. Quem sabe a ordem do referencial é o dashboard — um
    # motor que reordenasse por sua conta partia isso em silêncio.
    invertido = PdfReader(io.BytesIO(contract.juntar_pdfs(list(reversed(partes)))))
    primeiro = [i.title for i in invertido.outline if hasattr(i, "title")][0]
    check(primeiro == partes[-1]["titulo"],
          "A ordem dos documentos é a que vem, não uma escolhida aqui")

    def recusa(documentos, porque):
        try:
            contract.juntar_pdfs(documentos)
            return None
        except ValueError as e:
            return str(e)

    erro = recusa([partes[0], {"pdf": b"nao sou um pdf", "titulo": "Lixo"}], "lixo")
    check(erro is not None and "Lixo" in erro,
          f"PDF ilegível é recusado e a mensagem diz qual (deu {erro!r})")

    erro_vazio = recusa([{"pdf": b"", "titulo": "Vazio"}], "vazio")
    check(erro_vazio is not None and "Vazio" in erro_vazio,
          f"PDF vazio é recusado e a mensagem diz qual (deu {erro_vazio!r})")

    check(recusa([], "nada") is not None, "Lista vazia é recusada")

    demais = [{"pdf": partes[0]["pdf"], "titulo": f"D{i}"}
              for i in range(contract.LIMITE_JUNTAR_PARTES + 1)]
    check(recusa(demais, "demasiados") is not None,
          f"Acima de {contract.LIMITE_JUNTAR_PARTES} documentos é recusado")


# ---------------------------------------------------------------------------
# Autenticação dos endpoints
# ---------------------------------------------------------------------------
# Os três /api/* geram documentos com dados pessoais a partir do que lhes
# mandam. Têm de falhar FECHADOS: sem PDF_API_TOKEN configurado respondem 503,
# nunca abrem. O /health fica aberto de propósito (protegê-lo marcava o serviço
# como não saudável no Render).
#
# Antes daqui testava-se a Basic Auth da zona de coordenação. Essa zona saiu:
# o upload, o dashboard do lote e a página de assinatura vivem no
# sportrail-dashboard, que tem sessão a sério em vez de um user/password
# partilhado por env.

ROTAS_API = {("POST", "/api/contrato-preview"), ("POST", "/api/gerar-contrato"),
             ("POST", "/api/render-pdf"), ("POST", "/api/juntar-pdf")}
ROTAS_ABERTAS = {("GET", "/health")}


def verificar_auth_api():
    import os
    import app as webapp
    from fastapi.routing import APIRoute

    # Wiring: nenhuma rota a mais, nenhuma a menos.
    rotas = set()
    for rota in webapp.app.routes:
        if isinstance(rota, APIRoute):
            for metodo in rota.methods:
                rotas.add((metodo, rota.path))
    inesperadas = sorted(rotas - ROTAS_API - ROTAS_ABERTAS)
    check(not inesperadas,
          "Nenhuma rota por classificar"
          + (f" — inesperadas: {inesperadas}" if inesperadas else ""))
    em_falta = sorted((ROTAS_API | ROTAS_ABERTAS) - rotas)
    check(not em_falta,
          "Todas as rotas esperadas existem"
          + (f" — em falta: {em_falta}" if em_falta else ""))

    def com_token(valor, header):
        """Corre _exigir_token_api com este PDF_API_TOKEN; devolve a exceção ou None."""
        guardado = os.environ.pop("PDF_API_TOKEN", None)
        original = webapp._pdf_api_token
        webapp._pdf_api_token = valor
        try:
            webapp._exigir_token_api(header)
            return None
        except Exception as e:
            return e
        finally:
            webapp._pdf_api_token = original
            if guardado is not None:
                os.environ["PDF_API_TOKEN"] = guardado

    def status(e):
        return getattr(e, "status_code", None)

    check(status(com_token(None, "seja-o-que-for")) == 503,
          "Sem PDF_API_TOKEN configurado → 503 (falha fechada, nunca aberta)")
    check(status(com_token("", "seja-o-que-for")) == 503,
          "PDF_API_TOKEN vazio → 503")
    check(status(com_token("segredo", None)) == 401,
          "Com segredo configurado e sem header → 401")
    check(status(com_token("segredo", "errado")) == 401,
          "Header errado → 401")
    check(com_token("segredo", "segredo") is None,
          "Header certo → passa")


if __name__ == "__main__":
    main()
