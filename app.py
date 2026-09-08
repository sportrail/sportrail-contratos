"""
App web — Contratos de Formação Sportrail (protótipo Caminho B).

Fluxo:
  1. Coordenador abre "/", preenche dados do curso e carrega o Excel.
  2. Sistema cria um lote, um link único de assinatura por formando.
  3. Coordenador envia os links (a app mostra-os e dá captions prontos).
  4. Formando abre o link, lê o contrato, assina no canvas, consente, submete.
  5. App gera PDF assinado + auditoria, arquiva no Drive, marca como assinado.
  6. Dashboard mostra estado por formando.

Nada de estado em disco: os lotes e os formandos vivem no Postgres do Supabase
e os PDFs no bucket `contratos`. O tier grátis do Render adormece o serviço e
tem filesystem efémero — qualquer coisa escrita localmente desaparecia, e com
ela os links de assinatura já enviados.
"""
import base64
import os
import secrets
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import (FastAPI, Request, UploadFile, Form, Depends, HTTPException,
                     status, Header)
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core import excel_parser, contract, store, drive, pdfstore

BASE = Path(__file__).resolve().parent

app = FastAPI(title="Sportrail — Contratos de Formação")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
web = Jinja2Templates(directory=str(BASE / "templates"))


# --- Proteção da zona de coordenação (Basic Auth) ---------------------------
# ADMIN_USER e ADMIN_PASS (Environment do Render) protegem "/", criar lote e o
# dashboard do lote. Estas páginas mostram nome, NIF, morada e email de todos os
# formandos e os links /assinar/<token>, que permitem assinar em nome de cada
# um — por isso a proteção FALHA FECHADA: sem as variáveis, respondem 503 em vez
# de abrirem. Ficam abertas de propósito: /assinar/<token> e /pdf/<token> (o
# token, enviado a cada formando, é que autoriza), /health (health check do
# Render; protegê-lo marcava o serviço como não saudável) e /api/gerar-contrato
# (tem o seu próprio PDF_API_TOKEN).
# auto_error=False para distinguir "sem credenciais" de "credenciais erradas".
_REALM_NOME = "Sportrail Contratos"
_security = HTTPBasic(auto_error=False, realm=_REALM_NOME)
_REALM = f'Basic realm="{_REALM_NOME}"'


def _admin_env() -> tuple[Optional[str], Optional[str]]:
    """Lidas a cada pedido — permite ao verify.py testar os vários cenários."""
    return os.environ.get("ADMIN_USER"), os.environ.get("ADMIN_PASS")


def _iguais(a: str, b: str) -> bool:
    # Em bytes: compare_digest com str rebenta (TypeError) se houver não-ASCII.
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def require_admin(creds: Optional[HTTPBasicCredentials] = Depends(_security)):
    """Exige Basic Auth nas rotas de coordenação. Sem ADMIN_USER/ADMIN_PASS → 503."""
    admin_user, admin_pass = _admin_env()
    if not (admin_user and admin_pass):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Zona de coordenação indisponível: faltam as variáveis de "
                   "ambiente ADMIN_USER e/ou ADMIN_PASS no servidor.")
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Acesso restrito: autenticação necessária.",
                            headers={"WWW-Authenticate": _REALM})
    # Avaliar os dois antes do `and`: o tempo de resposta não revela qual falhou.
    user_ok = _iguais(creds.username, admin_user)
    pass_ok = _iguais(creds.password, admin_pass)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Acesso restrito: credenciais inválidas.",
                            headers={"WWW-Authenticate": _REALM})


if not all(_admin_env()):
    print("[AVISO] ADMIN_USER/ADMIN_PASS não definidas — a zona de coordenação "
          "responde 503 até as definires (ver .env.example).")


def _base_url(request: Request) -> str:
    # Permite override por proxy (BASE_URL) para os links serem públicos.
    import os
    return os.environ.get("BASE_URL", str(request.base_url)).rstrip("/")


@app.get("/health")
def health():
    """Health check público (Render / uptime). Sem auth de propósito."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, _admin: None = Depends(require_admin)):
    return web.TemplateResponse(request, "upload.html", {"lotes": store.todos_os_lotes()})


@app.post("/criar-lote")
async def criar_lote(request: Request,
                     nome_curso: str = Form(...),
                     modalidade: str = Form("Online (formação a distância)"),
                     duracao: str = Form(...),
                     data_inicio: str = Form(...),
                     data_conclusao: str = Form(...),
                     tipo_contrato: str = Form("B2C"),
                     excel: UploadFile = Form(...),
                     _admin: None = Depends(require_admin)):
    # openpyxl quer um caminho; o ficheiro só precisa de existir durante o pedido.
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
        tmp.write(await excel.read())
        tmp.flush()
        formandos = excel_parser.ler_formandos(tmp.name)

    curso = {"nome": nome_curso, "modalidade": modalidade, "duracao": duracao,
             "data_inicio": data_inicio, "data_conclusao": data_conclusao}
    lote_id = store.criar_lote(curso, formandos, tipo_default=tipo_contrato)
    return RedirectResponse(f"/lote/{lote_id}", status_code=303)


@app.get("/lote/{lote_id}", response_class=HTMLResponse)
def dashboard(request: Request, lote_id: str, _admin: None = Depends(require_admin)):
    lote = store.obter_lote(lote_id)
    if not lote:
        return HTMLResponse("Lote não encontrado", status_code=404)
    base = _base_url(request)
    linhas = []
    for token, f in lote["formandos"].items():
        linhas.append({**f, "token": token,
                       "link": f"{base}/assinar/{token}"})
    return web.TemplateResponse(request, "dashboard.html", {"lote_id": lote_id, "curso": lote["curso"],
        "linhas": linhas})


@app.get("/assinar/{token}", response_class=HTMLResponse)
def pagina_assinar(request: Request, token: str):
    lote_id, lote, f = store.obter_formando(token)
    if not f:
        return HTMLResponse("Contrato não encontrado.", status_code=404)
    if f["estado"] == "assinado":
        return web.TemplateResponse(request, "obrigado.html", {"formando": f,
                                     "ja": True})
    html_contrato = contract.render_html(lote["curso"], f, tipo=f.get("tipo_contrato", "B2C"))
    if f.get("tipo_contrato", "B2C").upper() == "B2C":
        consentimento_txt = (
            "Declaro que li e aceito as cláusulas do contrato e consinto a "
            "assinatura eletrónica do mesmo, com o mesmo valor de uma assinatura "
            "manuscrita. Solicito expressamente o início da formação durante o "
            "prazo de livre resolução de 14 dias, ficando ciente de que, se vier a "
            "resolver o contrato, pagarei o valor proporcional ao já prestado.")
    else:
        consentimento_txt = (
            "Declaro que li e aceito as cláusulas do contrato e consinto a "
            "assinatura eletrónica do mesmo, com o mesmo valor de uma assinatura "
            "manuscrita, em representação da entidade adquirente da formação.")
    return web.TemplateResponse(request, "assinar.html", {"token": token, "formando": f,
        "curso": lote["curso"], "contrato_html": html_contrato,
        "consentimento_txt": consentimento_txt})


@app.post("/assinar/{token}")
async def submeter_assinatura(request: Request, token: str,
                              assinatura: str = Form(...),
                              consentimento: str = Form("")):
    lote_id, lote, f = store.obter_formando(token)
    if not f:
        return HTMLResponse("Contrato não encontrado.", status_code=404)
    if f["estado"] == "assinado":
        return RedirectResponse(f"/assinar/{token}", status_code=303)
    if consentimento != "on" or not assinatura.startswith("data:image"):
        return HTMLResponse("Falta consentimento ou assinatura.", status_code=400)

    ip = request.client.host if request.client else None
    doc_id = secrets.token_hex(8).upper()
    aud = contract.construir_auditoria(lote["curso"], f, assinatura, doc_id, ip)

    html = contract.render_html(lote["curso"], f, tipo=f.get("tipo_contrato", "B2C"),
                                assinatura_formando=assinatura, auditoria=aud)
    nome_seguro = "".join(c for c in f["nome"] if c.isalnum() or c in " _-").strip().replace(" ", "_")
    nome_ficheiro = f"contrato_{nome_seguro}_{doc_id}.pdf"

    pdf_bytes = contract.gerar_pdf_bytes(html)
    pdf_path = pdfstore.guardar_pdf(lote_id, nome_ficheiro, pdf_bytes)
    drive_id = drive.arquivar(pdf_bytes, lote["curso"]["nome"], nome_ficheiro,
                              pdf_path)

    store.marcar_assinado(token, assinado_em=aud["data"], ip=ip,
                          hash=aud["hash"], doc_id=doc_id,
                          pdf_path=pdf_path, drive_file_id=drive_id)

    return web.TemplateResponse(request, "obrigado.html", {"formando": f, "ja": False})


@app.get("/pdf/{token}")
def baixar_pdf(token: str):
    _, _, f = store.obter_formando(token)
    if not f or not f.get("pdf_path"):
        return HTMLResponse("Sem PDF.", status_code=404)
    nome = Path(f["pdf_path"]).name
    return Response(
        content=pdfstore.ler_pdf(f["pdf_path"]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


# --- API: motor de PDF para o Sportrail Dashboard --------------------------
# O dashboard (Next.js) trata de dados/login/UI e delega SÓ a geração do PDF a
# este serviço, que reutiliza as cláusulas jurídicas e o WeasyPrint. Chamada
# servidor-a-servidor, protegida por segredo partilhado PDF_API_TOKEN (Railway).
_pdf_api_token = os.environ.get("PDF_API_TOKEN")


class GerarContratoIn(BaseModel):
    curso: dict
    formando: dict
    tipo: str = "B2C"
    assinatura: str            # data:image/... base64 da assinatura do formando
    ip: Optional[str] = None


@app.post("/api/gerar-contrato")
def api_gerar_contrato(dados: GerarContratoIn,
                       x_api_token: Optional[str] = Header(default=None)):
    if not _pdf_api_token:
        raise HTTPException(status_code=503, detail="PDF_API_TOKEN não configurado.")
    if not x_api_token or not secrets.compare_digest(x_api_token, _pdf_api_token):
        raise HTTPException(status_code=401, detail="Token de API inválido.")

    doc_id = secrets.token_hex(8).upper()
    aud = contract.construir_auditoria(dados.curso, dados.formando,
                                       dados.assinatura, doc_id, dados.ip)
    html = contract.render_html(dados.curso, dados.formando, tipo=dados.tipo,
                                assinatura_formando=dados.assinatura, auditoria=aud)
    pdf = contract.gerar_pdf_bytes(html)
    return {
        "pdf_base64": base64.b64encode(pdf).decode(),
        "hash": aud["hash"],
        "doc_id": doc_id,
        "data": aud["data"],
        "tz": aud["tz"],
    }
