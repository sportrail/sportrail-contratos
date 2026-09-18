# Imagem de produção — Sportrail, motor de contratos e de PDF.
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

# O Render injeta a porta em $PORT; localmente cai para 8000.
# --proxy-headers + --forwarded-allow-ips: atrás do proxy da plataforma, para
# o esquema e o IP de origem chegarem corretos ao uvicorn. (Serviam também os
# links de assinatura, que saíram deste repo com o BASE_URL.)
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
