"""
PDFs assinados no Supabase Storage (bucket privado `contratos`).

Os PDFs ficavam em data/pdfs/. No Render free o disco é efémero, por isso um
restart deixava a coluna pdf_path a apontar para nada. O bucket nunca é
exposto ao exterior: /pdf/<token> serve os bytes a partir da app.
"""
from .db import BUCKET_CONTRATOS, client


def caminho(batch_id: str, nome_ficheiro: str) -> str:
    return f"{batch_id}/{nome_ficheiro}"


def guardar_pdf(batch_id: str, nome_ficheiro: str, conteudo: bytes) -> str:
    """Carrega o PDF e devolve o caminho a gravar em contract_signers.pdf_path."""
    destino = caminho(batch_id, nome_ficheiro)
    client().storage.from_(BUCKET_CONTRATOS).upload(
        destino,
        conteudo,
        {"content-type": "application/pdf"},
    )
    return destino


def ler_pdf(destino: str) -> bytes:
    return client().storage.from_(BUCKET_CONTRATOS).download(destino)
