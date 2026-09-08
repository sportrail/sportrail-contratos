"""
Arquivo do PDF assinado no Google Drive (pasta DTP do curso).

Setup (ver README): conta de serviço Google + partilha da pasta DTP com o
email da conta de serviço. Coloca o JSON em data/service_account.json e o
ID da pasta-raiz em DRIVE_ROOT_FOLDER_ID (variável de ambiente).

Se não houver credenciais, a função devolve o caminho do PDF no Supabase
Storage — que já é arquivo durável. Antes copiava para data/arquivo/, mas no
Render esse disco desaparece no restart seguinte: era uma cópia que dava a
ilusão de arquivo sem o ser.
"""
import io
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CRED = BASE / "data" / "service_account.json"


def _tem_credenciais():
    return CRED.exists() and os.environ.get("DRIVE_ROOT_FOLDER_ID")


def _garantir_subpasta(service, nome_pasta, parent_id):
    q = (f"name = '{nome_pasta}' and mimeType = "
         f"'application/vnd.google-apps.folder' and '{parent_id}' in parents "
         f"and trashed = false")
    res = service.files().list(q=q, fields="files(id)").execute()
    itens = res.get("files", [])
    if itens:
        return itens[0]["id"]
    meta = {"name": nome_pasta,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id]}
    pasta = service.files().create(body=meta, fields="id").execute()
    return pasta["id"]


def arquivar(pdf_bytes, nome_curso, nome_ficheiro, caminho_supabase):
    """
    Carrega o PDF para a subpasta DTP do curso. Devolve um id do Drive ou, sem
    credenciais, o caminho no Storage — onde o PDF já está guardado.
    """
    if not _tem_credenciais():
        return f"supabase::{caminho_supabase}"

    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload

    scopes = ["https://www.googleapis.com/auth/drive"]
    creds = service_account.Credentials.from_service_account_file(
        str(CRED), scopes=scopes)
    service = build("drive", "v3", credentials=creds)

    root = os.environ["DRIVE_ROOT_FOLDER_ID"]
    pasta_curso = _garantir_subpasta(service, nome_curso, root)

    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
    meta = {"name": nome_ficheiro, "parents": [pasta_curso]}
    f = service.files().create(body=meta, media_body=media,
                               fields="id").execute()
    return f["id"]
