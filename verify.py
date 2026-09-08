"""
Smoke test do pipeline (sem servidor). Corre: `python verify.py` ou `make verify`.

Verifica, ponta-a-ponta e sem rede:
  1. parsing do Excel de exemplo;
  2. geração do PDF B2C (com cláusulas de livre resolução + anexo);
  3. geração do PDF B2B (sem livre resolução);
  4. trilho de auditoria (hash determinístico) presente.

Sai com código 0 se tudo passar, 1 se algo falhar. Pensado para o Claude Code
poder validar rapidamente que nada partiu.

Verifica também a Basic Auth da zona de coordenação (require_admin em app.py),
chamando a função diretamente — sem servidor nem httpx: falha fechada (503 sem
ADMIN_USER/ADMIN_PASS; 401 sem credenciais ou com credenciais erradas), aceita
palavra-passe não-ASCII, e só as rotas de coordenação levam a dependência.
"""
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
