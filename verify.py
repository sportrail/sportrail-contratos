"""
Smoke test do pipeline (sem servidor). Corre: `python verify.py` ou `make verify`.

Verifica, ponta-a-ponta e sem rede:
  1. parsing do Excel de exemplo;
  2. geração do PDF B2C (com cláusulas de livre resolução + anexo);
  3. geração do PDF B2B (sem livre resolução);
  4. trilho de auditoria (hash determinístico) presente;
  5. nenhum marcador de andaime no texto extraído dos PDFs.
  5. o store contra um duplo em memória do Supabase, sem rede nem credenciais.

Sai com código 0 se tudo passar, 1 se algo falhar. Pensado para o Claude Code
poder validar rapidamente que nada partiu.

Verifica também a Basic Auth da zona de coordenação (require_admin em app.py),
chamando a função diretamente — sem servidor nem httpx: falha fechada (503 sem
ADMIN_USER/ADMIN_PASS; 401 sem credenciais ou com credenciais erradas), aceita
palavra-passe não-ASCII, e só as rotas de coordenação levam a dependência.
"""
import re
import sys
import tempfile
from pathlib import Path

from core import excel_parser, contract
from core.clausulas import ENTIDADE, MINUTA_APROVADA, VERSAO_MINUTA, corpo_contrato
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
falhas = []


def check(cond, msg):
    estado = "OK " if cond else "FALHA"
    print(f"[{estado}] {msg}")
    if not cond:
        falhas.append(msg)


# ---------------------------------------------------------------------------
# Duplo em memória do supabase-py
# ---------------------------------------------------------------------------
# Implementa só o que o core/store.py usa. Existe para o store ser testável
# sem rede nem credenciais: o que interessa verificar aqui é que as formas de
# retorno continuam a ser as que o app.py e os templates esperam, e que as
# colunas escritas existem mesmo no supabase_schema.sql.

class _Resposta:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, linhas):
        self._linhas = linhas          # lista partilhada = a "tabela"
        self._predicados = []
        self._ordem = None
        self._single = False
        self._op = "select"
        self._payload = None

    def select(self, *_args, **_kw):
        return self

    def insert(self, dados):
        self._op, self._payload = "insert", dados
        return self

    def update(self, dados):
        self._op, self._payload = "update", dados
        return self

    def eq(self, campo, valor):
        self._predicados.append(lambda l: l.get(campo) == valor)
        return self

    def in_(self, campo, valores):
        conjunto = set(valores)
        self._predicados.append(lambda l: l.get(campo) in conjunto)
        return self

    def order(self, campo, desc=False):
        self._ordem = (campo, desc)
        return self

    def maybe_single(self):
        self._single = True
        return self

    def _correspondentes(self):
        return [l for l in self._linhas if all(p(l) for p in self._predicados)]

    def execute(self):
        if self._op == "insert":
            novas = (self._payload if isinstance(self._payload, list)
                     else [self._payload])
            self._linhas.extend(dict(n) for n in novas)
            return _Resposta([dict(n) for n in novas])
        if self._op == "update":
            alteradas = self._correspondentes()
            for linha in alteradas:
                linha.update(self._payload)
            return _Resposta([dict(l) for l in alteradas])

        encontradas = self._correspondentes()
        if self._ordem:
            campo, desc = self._ordem
            encontradas = sorted(encontradas, key=lambda l: l.get(campo),
                                 reverse=desc)
        if self._single:
            return _Resposta(dict(encontradas[0]) if encontradas else None)
        return _Resposta([dict(l) for l in encontradas])


class FakeSupabase:
    def __init__(self):
        self.tabelas = {}

    def table(self, nome):
        return _Query(self.tabelas.setdefault(nome, []))


def _colunas_do_schema(tabela):
    """Lê as colunas declaradas no supabase_schema.sql para a tabela dada.

    Duas origens, porque o schema tem as duas: o `create table` inicial e os
    `alter table ... add column if not exists` das migrações que vieram depois.
    Ler só a primeira dava "coluna a mais" para tudo o que uma migração
    acrescentou — um falso alarme que ensinava a ignorar este teste.
    """
    sql = (BASE / "supabase_schema.sql").read_text(encoding="utf-8")
    colunas = set()

    corpo = re.search(rf"create table if not exists {tabela}\s*\((.*?)\n\);",
                      sql, re.S | re.I)
    if corpo:
        for linha in corpo.group(1).splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("--"):
                continue
            nome = linha.split()[0]
            if nome.lower() not in ("primary", "foreign", "constraint", "unique"):
                colunas.add(nome)

    for bloco in re.findall(rf"alter table {tabela}\s(.*?);", sql, re.S | re.I):
        for m in re.finditer(r"add column(?:\s+if not exists)?\s+(\w+)",
                             bloco, re.I):
            colunas.add(m.group(1))

    return colunas


def verificar_store():
    """O store contra o duplo: formas de retorno e colunas alinhadas ao schema."""
    from core import store

    fake = FakeSupabase()
    original = store.client
    store.client = lambda: fake
    try:
        curso = {"nome": "Curso X", "modalidade": "Online", "duracao": "12 horas",
                 "data_inicio": "22/09/2026", "data_conclusao": "08/10/2026"}
        formandos = [
            {"nome": "Ana", "email": "ana@x.pt", "nif": "111"},
            {"nome": "Bruno", "email": "bruno@x.pt", "tipo_contrato": "b2b"},
        ]
        lote_id = store.criar_lote(curso, formandos, tipo_default="B2C")

        # As colunas escritas têm de existir no schema, senão o insert só
        # rebenta em produção, contra o Postgres a sério.
        for tabela in ("contract_batches", "contract_signers"):
            declaradas = _colunas_do_schema(tabela)
            escritas = set().union(*(set(l) for l in fake.tabelas[tabela]))
            check(escritas <= declaradas,
                  f"{tabela}: colunas escritas existem no schema"
                  + (f" (a mais: {sorted(escritas - declaradas)})"
                     if escritas - declaradas else ""))

        lote = store.obter_lote(lote_id)
        check(set(lote) == {"curso", "criado_em", "origem", "formandos"},
              "obter_lote devolve {curso, criado_em, origem, formandos}")
        tokens = list(lote["formandos"])
        check([lote["formandos"][t]["nome"] for t in tokens] == ["Ana", "Bruno"],
              "ordem do Excel preservada")
        check(lote["formandos"][tokens[0]]["tipo_contrato"] == "B2C",
              "tipo_default do lote aplicado a quem não o traz do Excel")
        check(lote["formandos"][tokens[1]]["tipo_contrato"] == "B2B",
              "tipo do Excel tem precedência e é normalizado para maiúsculas")
        check(store.obter_lote("nao-existe") is None,
              "lote inexistente devolve None")

        lote_id2, _, f = store.obter_formando(tokens[0])
        check(lote_id2 == lote_id and f["nome"] == "Ana",
              "obter_formando devolve (lote_id, lote, formando)")
        check(store.obter_formando("token-invalido") == (None, None, None),
              "token inválido devolve (None, None, None)")

        store.marcar_assinado(tokens[0], assinado_em="2026-09-08", ip="1.2.3.4",
                              hash="a" * 64, doc_id="DOC1",
                              pdf_path=f"{lote_id}/contrato.pdf",
                              drive_file_id="supabase::x")
        _, _, assinado = store.obter_formando(tokens[0])
        check(assinado["estado"] == "assinado"
              and assinado["pdf_path"] == f"{lote_id}/contrato.pdf",
              "marcar_assinado persiste estado e caminho do PDF")

        lotes = store.todos_os_lotes()
        check(list(lotes) == [lote_id] and set(lotes[lote_id]["formandos"]) == set(tokens),
              "todos_os_lotes agrupa os formandos pelo lote certo")

        # --- Backfill -------------------------------------------------------
        # Um lote importado do histórico, com os campos que o export do
        # WooCommerce traz e o formato antigo não tinha.
        historico = [{"nome": "Carla", "email": "c@x.pt", "nif": "111111111",
                      "doc_identificacao": "12345678", "cedula": "999",
                      "clube": "SC Exemplo", "concelho": "Oeiras",
                      "distrito": "Lisboa", "valor_pago": "€ 150,00",
                      "tipo_contrato": ""}]
        lote_bf = store.criar_lote(
            {"nome": "Curso de 2024", "modalidade": "Online (formação a distância)",
             "duracao": "30 horas", "data_inicio": "09/09/2024",
             "data_conclusao": "31/10/2024"},
            historico, tipo_default="B2C", origem="backfill")
        lote = store.obter_lote(lote_bf)
        check(lote["origem"] == "backfill", "lote de backfill marcado como tal")
        token_bf = list(lote["formandos"])[0]
        carla = lote["formandos"][token_bf]
        check(carla["doc_identificacao"] == "12345678"
              and carla["cedula"] == "999" and carla["clube"] == "SC Exemplo"
              and carla["distrito"] == "Lisboa",
              "campos novos do WooCommerce persistidos no formando")

        # Quem já assinou em papel fecha-se SEM assinatura e SEM PDF. Se isto
        # alguma vez passar a gerar um PDF, está a fabricar-se um documento
        # assinado que ninguém assinou aqui.
        store.marcar_arquivado_papel(token_bf, "contrato em papel, arquivo 2024")
        _, _, carla = store.obter_formando(token_bf)
        check(carla["estado"] == "arquivado_papel" and not carla["pdf_path"]
              and not carla["hash"],
              "arquivado_papel não fabrica assinatura, PDF nem hash")
    finally:
        store.client = original


def main():
    # 0) Config da entidade que sai impressa no contrato
    check(bool(ENTIDADE.get("email")),
          "ENTIDADE['email'] preenchido (sai na Cláusula 6.ª e no anexo)")

    curso = {"nome": "Goalkeeper Coaching Course",
             "modalidade": "Online (formação a distância)",
             "duracao": "12 horas", "data_inicio": "22/09/2026",
             "data_conclusao": "08/10/2026"}

    # Basic Auth da zona de coordenação (independente do pipeline de PDF)
    verificar_auth()

    # 1) Excel — folha manual e export do WooCommerce
    formandos = excel_parser.ler_formandos(BASE / "formandos_exemplo.xlsx")
    check(len(formandos) >= 2, f"Excel lido ({len(formandos)} formandos)")
    verificar_woocommerce()

    # 2) Corpo do contrato = minuta aprovada, igual nas duas variantes
    verificar_minuta(curso)

    f = formandos[0]
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

        # O corpo aprovado tem de chegar INTEIRO aos dois PDFs. Isto é o teste
        # que interessa: um `{campo}` mal escrito ou uma cláusula que o template
        # deixa cair passam por todos os outros e só se veem no documento.
        texto_b2b = "\n".join(pg.extract_text() or ""
                              for pg in PdfReader(str(p_b2b)).pages)
        for rotulo, texto in (("B2C", texto_b2c), ("B2B", texto_b2b)):
            verificar_fidelidade_pdf(rotulo, texto)

        # A adenda de consumidor é o que separa as variantes — e vive FORA do
        # corpo aprovado. Se aparecesse no B2B, o contrato da empresa dava um
        # direito de consumidor que ela não tem.
        check("Livre Resolução" in texto_b2c or "livre resolução" in texto_b2c,
              "PDF B2C traz a adenda de livre resolução")
        check("livre resolução" not in texto_b2b.lower(),
              "PDF B2B sem qualquer menção a livre resolução")

        # Rodapé com a versão da minuta, em todas as páginas do corpo.
        check(VERSAO_MINUTA in texto_b2b,
              f"PDF traz o rodapé da versão da minuta ({VERSAO_MINUTA})")
    # 6) Render genérico (motor de PDF do dossier)
    verificar_render_isolado()

    # 7) Estado
    verificar_store()

    print()
    if falhas:
        print(f"❌ {len(falhas)} verificação(ões) falharam.")
        sys.exit(1)
    print("✅ Tudo OK.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Export do WooCommerce + agrupamento para o backfill
# ---------------------------------------------------------------------------
# O ficheiro que a loja produz desde 2024 não tem coluna `nome` nenhuma: o nome
# vem partido em `First Name (Billing)` / `Last Name (Billing)`, e o parser
# antigo rejeitava-o com "tem de ter as colunas nome e email". Constrói-se aqui
# um export com a forma exata do real, para isso não voltar a acontecer em
# silêncio. Duas ações de formação, para exercitar o agrupamento do backfill.

def _export_woocommerce(caminho):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["First Name (Billing)", "Last Name (Billing)", "Email (Billing)",
               "CC", "NIF", "cedula", "clube", "Product Name",
               "Order Total Amount"])
    ws.append(["Afonso", "Silva", "afonso@exemplo.pt", "15558282", "233385169",
               None, None, "Curso Online de Análise no Futebol", 150])
    ws.append(["Francisco", "Barros", "francisco@exemplo.pt", "31094292",
               "274050064", 184239, "CIF", "Curso Online de Análise no Futebol",
               150])
    ws.append(["Marco André", "Teixeira", "marco@exemplo.pt", "14301434",
               "210309024", None, "FC Luzern", "Curso de Scouting", 99.5])
    wb.save(caminho)


def verificar_woocommerce():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "woo.xlsx"
        _export_woocommerce(caminho)
        fs = excel_parser.ler_formandos(caminho)

    check(len(fs) == 3, f"Export do WooCommerce lido ({len(fs)} formandos)")
    check(fs[0]["nome"] == "Afonso Silva",
          "Nome composto de First Name + Last Name")
    # O CC é o que a minuta pede no preâmbulo; lido como número saía '15558282.0'.
    check(fs[0]["doc_identificacao"] == "15558282",
          "CC lido como documento de identificação, sem '.0'")
    check(fs[0]["nif"] == "233385169", "NIF lido sem notação de float")
    check(fs[1]["cedula"] == "184239" and fs[1]["clube"] == "CIF",
          "Cédula e clube lidos")
    # 150 -> '€ 150,00' e 99.5 -> '€ 99,50'. Um valor monetário num contrato não
    # sai com um decimal só nem sem decimais.
    check(fs[0]["valor_pago"] == "€ 150,00" and fs[2]["valor_pago"] == "€ 99,50",
          f"Valor formatado como moeda ({fs[0]['valor_pago']}, {fs[2]['valor_pago']})")
    # Clube preenchido NÃO decide B2B — é decisão do jurista.
    check(all(f["tipo_contrato"] == "" for f in fs),
          "Clube preenchido não decide B2B (tipo fica a herdar o do lote)")

    grupos = excel_parser.agrupar_por_curso(fs)
    check(len(grupos) == 2 and len(grupos["Curso Online de Análise no Futebol"]) == 2,
          f"Backfill agrupa por Product Name ({len(grupos)} ações)")


# ---------------------------------------------------------------------------
# Fidelidade à minuta aprovada pela DGERT
# ---------------------------------------------------------------------------
# O corpo do contrato não é texto nosso: é a minuta que a DGERT aprovou no
# pedido de certificação. Se o documento gerado deixar de coincidir com ela, a
# certificação deixa de cobrir o que a Sportrail faz assinar. Por isso:
#   (a) a estrutura em `clausulas.py` tem de ter as cláusulas todas, com os
#       rótulos tal como estão na minuta (incluindo a 10.ª sem 9.ª);
#   (b) o texto tem de sair INTEIRO no PDF, nas duas variantes.

# Uma frase-âncora por cláusula, copiada da minuta aprovada. Escolhidas por
# serem inconfundíveis: se uma destas desaparece do PDF, faltou uma cláusula.
ANCORAS_MINUTA = [
    "não gera nem titula relações de trabalho subordinado",
    "decorre de acordo com os horários que vierem a ser fixados",
    "Caderneta Individual de Competências",
    "Tratar com urbanidade a primeira outorgante",
    "acompanhamento técnico-pedagógico dos formandos",
    "Regulamento da Formação em vigor à data de início da formação",
    "não confere ao formando direito a qualquer indemnização",
    "impossibilidade superveniente, absoluta e definitiva",
    "Decreto-Lei n.º 242/88, de 7 de julho e demais legislação",
]


def verificar_minuta(curso):
    rotulos = [c["numero"] for c in MINUTA_APROVADA]
    check(len(MINUTA_APROVADA) == 9,
          f"Minuta aprovada com as 9 cláusulas ({len(MINUTA_APROVADA)})")
    # A minuta aprovada salta da 8.ª para a 10.ª. É um erro DELA, e reproduzi-lo
    # é o comportamento correto: corrigir a numeração é alterar um documento
    # aprovado, decisão do jurista. Se alguém "arrumar" isto, este teste avisa.
    check("CLÁUSULA 10.ª" in rotulos and "CLÁUSULA 9.ª" not in rotulos,
          "Numeração preservada tal como na minuta (10.ª existe, 9.ª não)")
    cl3 = next(c for c in MINUTA_APROVADA if c["numero"] == "CLÁUSULA 3.ª")
    check([p.get("n") for p in cl3["pontos"]] == ["3.", "4."],
          "Cláusula 3.ª mantém os pontos numerados 3. e 4. (como na minuta)")

    # Nenhum campo pode ficar por interpolar: um "{horas}" impresso num contrato
    # é pior do que um tracejado — parece um dado e não é.
    corpo = corpo_contrato(curso)
    texto = " ".join(p["texto"] for c in corpo for p in c["pontos"])
    check("{" not in texto and "}" not in texto,
          "Campos do curso todos interpolados (sem chavetas no texto)")
    check(curso["nome"] in texto and curso["data_inicio"] in texto,
          "Ação e datas do curso presentes no articulado")


def verificar_fidelidade_pdf(rotulo, texto):
    # O extract_text do pypdf parte linhas onde o PDF as parte; comparar por
    # frase exige normalizar os espaços primeiro.
    normalizado = re.sub(r"\s+", " ", texto)
    em_falta = [a for a in ANCORAS_MINUTA
                if re.sub(r"\s+", " ", a) not in normalizado]
    check(not em_falta,
          f"PDF {rotulo} reproduz as 9 cláusulas da minuta aprovada"
          + (f" (falta: {em_falta[0][:40]}...)" if em_falta else ""))


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
# Basic Auth da zona de coordenação
# ---------------------------------------------------------------------------
# require_admin tem de falhar FECHADO: sem ADMIN_USER/ADMIN_PASS a zona de
# coordenação (nome, NIF, morada, email dos formandos + links de assinatura)
# responde 503, nunca abre. Chamamos a função diretamente com credenciais
# falsas — sem subir servidor nem depender de httpx.

ROTAS_COORDENACAO = {("GET", "/"), ("POST", "/criar-lote"),
                     ("GET", "/lote/{lote_id}"),
                     # Backfill: o preview lista nomes, emails, NIF e CC de toda
                     # a gente que alguma vez comprou uma formação.
                     ("POST", "/backfill/preview"), ("POST", "/backfill/criar"),
                     ("POST", "/formando/{token}/arquivar-papel")}
ROTAS_ABERTAS = {("GET", "/assinar/{token}"), ("POST", "/assinar/{token}"),
                 ("GET", "/pdf/{token}"), ("GET", "/health"),
                 ("POST", "/api/gerar-contrato"), ("POST", "/api/render-pdf")}


def verificar_auth():
    import os
    from fastapi import HTTPException
    from fastapi.routing import APIRoute
    from fastapi.security import HTTPBasicCredentials
    import app as webapp

    def chamar(user, password, env):
        """Corre require_admin com este ambiente; devolve a exceção ou None."""
        guardado = {k: os.environ.pop(k, None) for k in ("ADMIN_USER", "ADMIN_PASS")}
        os.environ.update(env)
        creds = (None if user is None
                 else HTTPBasicCredentials(username=user, password=password))
        try:
            webapp.require_admin(creds)
            return None
        except Exception as e:      # HTTPException esperada; TypeError seria bug
            return e
        finally:
            for k, v in guardado.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def status(e):
        return getattr(e, "status_code", None)

    # Palavra-passe com não-ASCII de propósito: compare_digest(str, str) rebenta
    # com TypeError nestes casos — a comparação tem de ser em bytes.
    user, password = "sportrail", "pálavra-çã€"
    env = {"ADMIN_USER": user, "ADMIN_PASS": password}

    e = chamar(user, password, {})
    check(status(e) == 503, "Sem ADMIN_USER/ADMIN_PASS → 503 (falha fechada, nunca aberta)")
    e = chamar(user, password, {"ADMIN_USER": user})
    check(status(e) == 503, "Só ADMIN_USER definido → 503")

    e = chamar(None, None, env)
    challenge = getattr(e, "headers", None) or {}
    check(status(e) == 401 and challenge.get("WWW-Authenticate", "").startswith('Basic realm="'),
          "Com env vars e sem credenciais → 401 + WWW-Authenticate: Basic realm=...")
    e = chamar(user, "errada", env)
    check(status(e) == 401 and isinstance(e, HTTPException),
          "Palavra-passe errada → 401")
    e = chamar("outro", password, env)
    check(status(e) == 401 and isinstance(e, HTTPException),
          "Utilizador errado → 401")
    e = chamar(user, password, env)
    check(e is None, "Credenciais certas (com não-ASCII) → passa")

    # Wiring: quais rotas levam mesmo a dependência. Uma rota em falta dá None,
    # por isso o teste acusa também se alguém a renomear.
    rotas = {}
    for rota in webapp.app.routes:
        if isinstance(rota, APIRoute):
            protegida = any(d.call is webapp.require_admin
                            for d in rota.dependant.dependencies)
            for metodo in rota.methods:
                rotas[(metodo, rota.path)] = protegida
    for metodo, caminho in sorted(ROTAS_COORDENACAO):
        check(rotas.get((metodo, caminho)) is True,
              f"{metodo} {caminho} exige require_admin")
    for metodo, caminho in sorted(ROTAS_ABERTAS):
        check(rotas.get((metodo, caminho)) is False,
              f"{metodo} {caminho} aberta (sem require_admin)")
    por_classificar = sorted(set(rotas) - ROTAS_COORDENACAO - ROTAS_ABERTAS)
    check(not por_classificar,
          "Todas as rotas classificadas (coordenação ou aberta)"
          + (f" — por classificar: {por_classificar}" if por_classificar else ""))


if __name__ == "__main__":
    main()
