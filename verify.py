"""
Smoke test do pipeline (sem servidor). Corre: `python verify.py` ou `make verify`.

Verifica, ponta-a-ponta e sem rede:
  1. parsing do Excel de exemplo;
  2. geração do PDF B2C (com cláusulas de livre resolução + anexo);
  3. geração do PDF B2B (sem livre resolução);
  4. trilho de auditoria (hash determinístico) presente;
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
from core.clausulas import clausulas
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
    """Lê as colunas declaradas no supabase_schema.sql para a tabela dada."""
    sql = (BASE / "supabase_schema.sql").read_text(encoding="utf-8")
    corpo = re.search(rf"create table if not exists {tabela}\s*\((.*?)\n\);",
                      sql, re.S | re.I)
    if not corpo:
        return set()
    colunas = set()
    for linha in corpo.group(1).splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("--"):
            continue
        nome = linha.split()[0]
        if nome.lower() not in ("primary", "foreign", "constraint", "unique"):
            colunas.add(nome)
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
        check(set(lote) == {"curso", "criado_em", "formandos"},
              "obter_lote devolve {curso, criado_em, formandos}")
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
    finally:
        store.client = original


def main():
    curso = {"nome": "Goalkeeper Coaching Course",
             "modalidade": "Online (formação a distância)",
             "duracao": "12 horas", "data_inicio": "22/09/2026",
             "data_conclusao": "08/10/2026"}

    # Basic Auth da zona de coordenação (independente do pipeline de PDF)
    verificar_auth()

    # 1) Excel
    formandos = excel_parser.ler_formandos(BASE / "formandos_exemplo.xlsx")
    check(len(formandos) >= 2, f"Excel lido ({len(formandos)} formandos)")

    # 2) Cláusulas por variante
    n_b2c = len(clausulas(online=True, tipo="B2C"))
    n_b2b = len(clausulas(online=True, tipo="B2B"))
    check(n_b2c > n_b2b, f"B2C tem mais cláusulas que B2B ({n_b2c} vs {n_b2b})")

    f = formandos[0]
    sig = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1"
           "HAwCAAAAC0lEQVR42mNk+M8AAAMCAYAAAA0xZ0AAAAASUVORK5CYII=")

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

    # 5) Estado
    verificar_store()

    print()
    if falhas:
        print(f"❌ {len(falhas)} verificação(ões) falharam.")
        sys.exit(1)
    print("✅ Tudo OK.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Basic Auth da zona de coordenação
# ---------------------------------------------------------------------------
# require_admin tem de falhar FECHADO: sem ADMIN_USER/ADMIN_PASS a zona de
# coordenação (nome, NIF, morada, email dos formandos + links de assinatura)
# responde 503, nunca abre. Chamamos a função diretamente com credenciais
# falsas — sem subir servidor nem depender de httpx.

ROTAS_COORDENACAO = {("GET", "/"), ("POST", "/criar-lote"),
                     ("GET", "/lote/{lote_id}")}
ROTAS_ABERTAS = {("GET", "/assinar/{token}"), ("POST", "/assinar/{token}"),
                 ("GET", "/pdf/{token}"), ("GET", "/health"),
                 ("POST", "/api/gerar-contrato")}


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
