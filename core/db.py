"""Cliente Supabase partilhado (service role, só servidor)."""
import os
from functools import lru_cache

from supabase import Client, create_client

BUCKET_CONTRATOS = "contratos"


@lru_cache(maxsize=1)
def client() -> Client:
    """
    Usa a SERVICE ROLE KEY: esta app é o próprio limite de confiança — o
    coordenador entra por Basic Auth e os formandos por token, por isso não há
    sessão de utilizador para o RLS avaliar. A chave nunca sai do servidor.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Faltam SUPABASE_URL e/ou SUPABASE_SERVICE_ROLE_KEY. "
            "Vê o .env.example — sem isto o estado não persiste e os links "
            "de assinatura morrem no primeiro restart."
        )
    return create_client(url, key)
