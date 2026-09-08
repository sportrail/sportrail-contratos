# Lessons

- Starlette >= 1.x mudou a assinatura: usar TemplateResponse(request, "nome.html", {ctx})
  e NÃO TemplateResponse("nome.html", {"request": request, ...}) (dá TypeError: unhashable type 'dict').
- weasyprint é mais simples de alojar que Playwright para um servidor (sem binário de browser).

# Sessão 3 — deploy
- weasyprint precisa de Pango/Cairo TAMBÉM no servidor → Dockerfile com apt (libpango/cairo/gdk-pixbuf), não basta pip.
- Basic Auth com env vars: aberto se ADMIN_USER/ADMIN_PASS vazias (cómodo em local), protegido se definidas. /assinar/<token> nunca leva auth (token já protege).
- Python 3.12-slim no Docker (wheels estáveis); 3.14 fica para local.

# Sessão 4 — motor de PDF + migração para Render
- Railway trial expira depressa e SUSPENDE o serviço (home → 404). Migrado para Render free (mesmo Dockerfile).
- Render CLI: `services create` aceita --env-var (define segredos); `services update` NÃO gere env vars → para mudar env de um serviço existente, recriar via CLI ou usar o dashboard.
- Render precisa do GitHub App instalado com acesso ao repo privado (senão create dá "repository unfetchable"). "Sign in with GitHub" (OAuth) ≠ GitHub App (acesso a repos).
- write_pdf() sem argumento devolve bytes → gerar_pdf_bytes() para servir PDF em memória no endpoint.
- Endpoint /api/gerar-contrato: motor de PDF para o dashboard, protegido por PDF_API_TOKEN (não pela Basic Auth do admin).

# Sessão 5 — CI
- Um verify.py que só corre à mão não protege nada: os marcadores [JURISTA] chegaram ao PDF assinado porque ninguém o correu. Agora corre em cada push/PR (`.github/workflows/verify.yml`).
- No runner o WeasyPrint precisa dos mesmos apt do Dockerfile (Pango/Cairo/gdk-pixbuf + fonts-dejavu-core); o `pip install` sozinho não chega. Mudar a lista num sítio → mudar no outro.
- O runner não é root: `sudo apt-get`. O Dockerfile não precisa de sudo.

# Sessão 2 — variantes B2C/B2B
- DGERT não fixa lista de cláusulas; conteúdo vem de 3 camadas (DTP, DL 24/2014, contrato geral).
- B2C (consumidor) exige livre resolução 14 dias + formulário (DL 24/2014); B2B não.
- Omitir info de livre resolução estende o prazo para 12 meses — risco real.
- O checkbox de consentimento serve de "pedido expresso" (art. 4.º) para iniciar antes dos 14 dias.
- Todo o texto legal marcado [JURISTA] para validação.
