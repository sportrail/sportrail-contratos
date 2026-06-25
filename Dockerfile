# Imagem de produção — Sportrail Contratos de Formação.
# Python 3.12 (wheels estáveis para weasyprint/fastapi/pydantic).
FROM python:3.12-slim

# Dependências NATIVAS do WeasyPrint (Pango/Cairo/GDK-Pixbuf) + fontes.
# Sem isto, o import weasyprint rebenta no servidor (igual ao brew em macOS).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libcairo2 \
        libffi8 \
        fonts-dejavu-core \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar deps primeiro (camada cacheável) e só depois copiar o código.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway/Render injetam a porta em $PORT; localmente cai para 8000.
# --proxy-headers + --forwarded-allow-ips: atrás do proxy da plataforma, faz
# com que os links de assinatura saiam com o esquema certo (https), mesmo sem
# BASE_URL definido.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
