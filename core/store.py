"""Estado persistido em JSON (suficiente para protótipo; trocar por DB depois)."""
import json
import secrets
import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
STATE = DATA / "state.json"


def _carregar():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"lotes": {}}


def _gravar(d):
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def criar_lote(curso, formandos, tipo_default="B2C"):
    d = _carregar()
    lote_id = secrets.token_urlsafe(6)
    registos = {}
    for f in formandos:
        token = secrets.token_urlsafe(16)
        # tipo do formando: usa o do Excel se existir, senão o default do lote.
        tipo = (f.get("tipo_contrato") or "").upper() or tipo_default.upper()
        registos[token] = {
            **f,
            "tipo_contrato": tipo,
            "estado": "pendente",
            "assinado_em": None,
            "ip": None,
            "hash": None,
            "doc_id": None,
            "pdf_path": None,
            "drive_file_id": None,
        }
    d["lotes"][lote_id] = {
        "curso": curso,
        "criado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "formandos": registos,
    }
    _gravar(d)
    return lote_id


def obter_lote(lote_id):
    return _carregar()["lotes"].get(lote_id)


def obter_formando(token):
    d = _carregar()
    for lote_id, lote in d["lotes"].items():
        if token in lote["formandos"]:
            return lote_id, lote, lote["formandos"][token]
    return None, None, None


def marcar_assinado(token, **campos):
    d = _carregar()
    for lote in d["lotes"].values():
        if token in lote["formandos"]:
            lote["formandos"][token].update(estado="assinado", **campos)
            _gravar(d)
            return True
    return False


def todos_os_lotes():
    return _carregar()["lotes"]
