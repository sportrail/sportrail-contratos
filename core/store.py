"""
Estado persistido em Postgres (Supabase).

Antes vivia em data/state.json. No tier grátis do Render o filesystem é
efémero e o serviço adormece ao fim de ~15 min — cada restart apagava os
tokens de assinatura já enviados aos formandos, e com eles o registo de quem
já tinha assinado. Agora nada disto depende do disco do contentor.

A API pública e os formatos de retorno são iguais aos da versão JSON, para
app.py e os templates não terem de mudar: um "lote" continua a ser
{curso, criado_em, formandos: {token: {...}}}.
"""
import secrets
import datetime

from .db import client

# Colunas que descrevem o formando (o resto da linha é metadados internos).
_CAMPOS_FORMANDO = (
    "nome", "nif", "email", "valor_pago", "morada", "tipo_contrato",
    "estado", "assinado_em", "ip", "hash", "doc_id", "pdf_path",
    "drive_file_id",
)


def _linha_para_formando(linha):
    return {campo: linha.get(campo) for campo in _CAMPOS_FORMANDO}


def _montar_lote(batch, linhas):
    """Reconstrói a forma {curso, criado_em, formandos: {token: {...}}}."""
    return {
        "curso": batch["curso"],
        "criado_em": batch["criado_em"],
        "formandos": {l["token"]: _linha_para_formando(l) for l in linhas},
    }


def criar_lote(curso, formandos, tipo_default="B2C"):
    sb = client()
    lote_id = secrets.token_urlsafe(6)

    sb.table("contract_batches").insert({
        "id": lote_id,
        "curso": curso,
        "tipo_default": tipo_default.upper(),
        "criado_em": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }).execute()

    linhas = []
    for ordem, f in enumerate(formandos):
        # tipo do formando: usa o do Excel se existir, senão o default do lote.
        tipo = (f.get("tipo_contrato") or "").upper() or tipo_default.upper()
        linhas.append({
            "token": secrets.token_urlsafe(16),
            "batch_id": lote_id,
            "nome": f["nome"],
            "nif": f.get("nif") or None,
            "email": f["email"],
            "valor_pago": f.get("valor_pago") or None,
            "morada": f.get("morada") or None,
            "tipo_contrato": tipo,
            "estado": "pendente",
            "ordem": ordem,
        })
    sb.table("contract_signers").insert(linhas).execute()
    return lote_id


def obter_lote(lote_id):
    sb = client()
    batch = (sb.table("contract_batches")
               .select("id, curso, criado_em")
               .eq("id", lote_id)
               .maybe_single()
               .execute())
    if not batch or not batch.data:
        return None
    linhas = (sb.table("contract_signers")
                .select("*")
                .eq("batch_id", lote_id)
                .order("ordem")
                .execute())
    return _montar_lote(batch.data, linhas.data or [])


def obter_formando(token):
    sb = client()
    linha = (sb.table("contract_signers")
               .select("batch_id")
               .eq("token", token)
               .maybe_single()
               .execute())
    if not linha or not linha.data:
        return None, None, None
    lote_id = linha.data["batch_id"]
    lote = obter_lote(lote_id)
    if lote is None:
        return None, None, None
    return lote_id, lote, lote["formandos"][token]


def marcar_assinado(token, **campos):
    sb = client()
    resposta = (sb.table("contract_signers")
                  .update({"estado": "assinado", **campos})
                  .eq("token", token)
                  .execute())
    return bool(resposta.data)


def todos_os_lotes():
    """Dois queries e agrupamento em memória — a alternativa era N+1."""
    sb = client()
    batches = (sb.table("contract_batches")
                 .select("id, curso, criado_em")
                 .order("criado_em", desc=True)
                 .execute())
    if not batches.data:
        return {}

    linhas = (sb.table("contract_signers")
                .select("*")
                .in_("batch_id", [b["id"] for b in batches.data])
                .order("ordem")
                .execute())

    por_lote = {}
    for l in linhas.data or []:
        por_lote.setdefault(l["batch_id"], []).append(l)

    return {
        b["id"]: _montar_lote(b, por_lote.get(b["id"], []))
        for b in batches.data
    }
