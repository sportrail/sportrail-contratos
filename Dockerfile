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

# Fontes da marca. Nem Bebas Neue nem DM Sans existem no apt, por isso vão
# versionadas em static/fonts/ e entram como fontes de SISTEMA. Sem este passo
# os PDFs saem em DejaVu — sem erro nenhum, que é o pior tipo de falha.
# Instaladas assim (e não por @font-face com URL) para que a resolução passe
# pelo fontconfig e não pelo url_fetcher, que o render isolado tranca em `data:`.
COPY static/fonts/*.ttf /usr/share/fonts/truetype/sportrail/
RUN fc-cache -f

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
