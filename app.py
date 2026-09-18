"""
Motor de contratos e de PDF da Sportrail (FastAPI).

Esta app **não tem estado**. Não escreve na base de dados, não guarda ficheiros,
não tem sessões. Recebe dados, devolve documentos.

O que cá vive, e a razão de cá viver, é o **texto jurídico**: as cláusulas em 3
camadas, as variantes B2C/B2B, a livre resolução do DL 24/2014 e a declaração
de consentimento. Uma segunda cópia disso em TypeScript seria uma segunda
versão para divergir em silêncio. Cá vive também o WeasyPrint, que é Python.

Tudo o que tem estado — lotes, formandos, tokens, PDF arquivados, a página de
assinatura — vive no `sportrail-dashboard`, que é onde as tabelas estão mesmo.
Já era assim na prática: o `supabase_schema.sql` desta app nunca chegou a ser
aplicado (o `create table if not exists` encontrou as tabelas do dashboard e
não fez nada), e por isso a metade com estado desta app estava morta há meses,
sem dar erro, porque ninguém a percorria. Ver `tasks/bug-assinatura.md` no
dashboard.

Endpoints, todos protegidos pelo mesmo `PDF_API_TOKEN`, exceto o health check:

  POST /api/contrato-preview  {curso, formando, tipo} -> {html, consentimento}
      O contrato por assinar, para o formando ler. Sem assinatura, sem auditoria.

  POST /api/gerar-contrato    {curso, formando, tipo, assinatura, ip}
                              -> {pdf_base64, hash, doc_id, data, tz}
      O contrato assinado, com trilho de auditoria.

  POST /api/render-pdf        {html} -> {pdf_base64, hash, doc_id, data, tz}
      Motor genérico para os documentos do dossier, cujos templates vivem no
      dashboard. O HTML vem de fora e NÃO é de confiar — ver
      contract.gerar_pdf_bytes_isolado.

  POST /api/juntar-pdf        {documentos:[{pdf_base64, titulo}]}
                              -> {pdf_base64, hash, doc_id, data, tz, paginas}
      Junta PDF já gerados num só, com marcadores — o DTP compilado. Junta os
      documentos TAL COMO foram arquivados; não os regera.

  GET  /health                health check do Render.
"""
import base64
import io
import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from pypdf import PdfReader

from core import contract, clausulas

BASE = Path(__file__).resolve().parent

app = FastAPI(title="Sportrail — Motor de Contratos e PDF")


@app.get("/health")
def health():
    """Health check público (Render / uptime). Sem auth de propósito."""
    return {"status": "ok"}


# --- Autenticação dos endpoints --------------------------------------------
# Segredo partilhado com o dashboard (lá chama-se CONTRATOS_PDF_TOKEN). Estes
# endpoints geram documentos com dados pessoais a partir do que lhes mandam:
# sem segredo configurado, não abrem a ninguém.
_pdf_api_token = os.environ.get("PDF_API_TOKEN")

if not _pdf_api_token:
    print("[AVISO] PDF_API_TOKEN não definido — os endpoints respondem 503 "
          "até o definires (ver .env.example).")


def _exigir_token_api(x_api_token: Optional[str]):
    """Falha fechada: sem PDF_API_TOKEN configurado, o motor não abre a ninguém."""
    if not _pdf_api_token:
        raise HTTPException(status_code=503, detail="PDF_API_TOKEN não configurado.")
    if not x_api_token or not secrets.compare_digest(x_api_token, _pdf_api_token):
        raise HTTPException(status_code=401, detail="Token de API inválido.")


class ContratoPreviewIn(BaseModel):
    curso: dict
    formando: dict
    tipo: str = "B2C"


class GerarContratoIn(BaseModel):
    curso: dict
    formando: dict
    tipo: str = "B2C"
    assinatura: str            # data:image/... base64 da assinatura do formando
    ip: Optional[str] = None


class RenderPdfIn(BaseModel):
    html: str
    nome: Optional[str] = None     # só para diagnóstico; não afeta o render


class DocumentoParaJuntar(BaseModel):
    pdf_base64: str
    titulo: Optional[str] = None   # vira marcador (outline) no PDF final


class JuntarPdfIn(BaseModel):
    documentos: list[DocumentoParaJuntar]


# --- API: contrato por assinar, em HTML ------------------------------------
# A página de assinatura vive no dashboard, mas o texto do contrato e a
# declaração de consentimento são texto jurídico e têm de ter uma fonte só.
# Devolve os dois já hidratados, sem assinatura e sem auditoria: é o que o
# formando lê antes de assinar.
@app.post("/api/contrato-preview")
def api_contrato_preview(dados: ContratoPreviewIn,
                         x_api_token: Optional[str] = Header(default=None)):
    _exigir_token_api(x_api_token)
    return {
        "html": contract.render_html(dados.curso, dados.formando,
                                     tipo=dados.tipo),
        "consentimento": clausulas.texto_consentimento(dados.tipo),
    }


# --- API: contrato assinado, em PDF ----------------------------------------
@app.post("/api/gerar-contrato")
def api_gerar_contrato(dados: GerarContratoIn,
                       x_api_token: Optional[str] = Header(default=None)):
    _exigir_token_api(x_api_token)

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


# --- API: render genérico de HTML -> PDF (documentos do dossier) ------------
# O dashboard é dono dos templates do dossier técnico-pedagógico (vivem junto do
# modelo de dados que os alimenta) e manda-nos o HTML já hidratado. Aqui só
# acontece a parte que precisa de Python: o WeasyPrint.
#
# Ao contrário dos outros dois, o HTML vem de fora e não é de confiar — ver
# contract.gerar_pdf_bytes_isolado para o porquê do isolamento.
@app.post("/api/render-pdf")
def api_render_pdf(dados: RenderPdfIn,
                   x_api_token: Optional[str] = Header(default=None)):
    _exigir_token_api(x_api_token)

    doc_id = secrets.token_hex(8).upper()
    try:
        pdf = contract.gerar_pdf_bytes_isolado(dados.html)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    aud = contract.construir_auditoria_documento(doc_id, dados.html)
    return {
        "pdf_base64": base64.b64encode(pdf).decode(),
        "hash": aud["hash"],
        "doc_id": doc_id,
        "data": aud["data"],
        "tz": aud["tz"],
    }


# --- API: juntar PDF já gerados (DTP compilado) -----------------------------
# O dossier técnico-pedagógico acaba num PDF único, ordenado pelas secções do
# referencial. Quem sabe essa ordem é o dashboard, que tem os documentos
# arquivados e o catálogo; aqui só acontece a parte que precisa de Python.
#
# Junta os PDF COMO ELES FORAM ARQUIVADOS. Regerá-los aqui dava um compilado que
# não corresponde a nenhum dos documentos cujo hash está registado — e é o hash
# que torna o arquivo credível.
@app.post("/api/juntar-pdf")
def api_juntar_pdf(dados: JuntarPdfIn,
                   x_api_token: Optional[str] = Header(default=None)):
    _exigir_token_api(x_api_token)

    partes = []
    for indice, d in enumerate(dados.documentos, start=1):
        titulo = (d.titulo or f"Documento {indice}").strip()
        try:
            # validate=True: sem isto o base64 ignora lixo em silêncio e o
            # pypdf rebentava depois, com uma mensagem sobre outra coisa.
            partes.append({"pdf": base64.b64decode(d.pdf_base64, validate=True),
                           "titulo": titulo})
        except Exception:
            raise HTTPException(status_code=422,
                                detail=f"{titulo}: base64 inválido.")

    try:
        pdf = contract.juntar_pdfs(partes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    doc_id = secrets.token_hex(8).upper()
    aud = contract.construir_auditoria_compilado(doc_id, pdf)
    return {
        "pdf_base64": base64.b64encode(pdf).decode(),
        "hash": aud["hash"],
        "doc_id": doc_id,
        "data": aud["data"],
        "tz": aud["tz"],
        "paginas": len(PdfReader(io.BytesIO(pdf)).pages),
    }
