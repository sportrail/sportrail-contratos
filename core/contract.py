"""Hidrata o template do contrato e gera o PDF. Calcula trilho de auditoria."""
import hashlib
import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

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
        assinatura_formando=assinatura_formando,
        auditoria=auditoria,
        formulario_resolucao=precisa_formulario_resolucao(tipo),
        prazo_resolucao=PRAZO_LIVRE_RESOLUCAO_DIAS,
    )


def gerar_pdf(html, destino):
    """Renderiza HTML -> PDF no caminho destino."""
    HTML(string=html, base_url=str(BASE)).write_pdf(destino)
    return destino


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
