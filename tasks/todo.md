
## Sessão 2 — concluído
- [x] Reestruturar cláusulas em 3 camadas
- [x] Variante B2C (com livre resolução + anexo) e B2B (sem)
- [x] Override por linha no Excel (coluna tipo_contrato) + default no lote
- [x] Consentimento dinâmico = pedido expresso art. 4.º (B2C)
- [x] Anexo formulário de livre resolução no PDF B2C
- [x] Verificado: B2C 3 págs, B2B 2 págs, fluxo HTTP OK

## Sessão 5 — zona de coordenação falha fechada
- [x] `require_admin`: sem ADMIN_USER/ADMIN_PASS → 503 (antes abria a quem tivesse o URL)
- [x] Sem credenciais → 401 + `WWW-Authenticate: Basic realm=...`; erradas → 401
- [x] Comparação em bytes (compare_digest com str rebenta em passwords não-ASCII)
- [x] Manter abertas: /assinar/<token>, /pdf/<token>, /health, /api/gerar-contrato
- [x] .env.example: valores de exemplo para local (deixou de haver "sem password")
- [x] verify.py: 503/401/401/401/passa + wiring das rotas (mutação manual acusa FALHA)
- [ ] Bruno: confirmar ADMIN_PASS no Environment do Render ANTES do merge

## Sessão 3 — deploy (GitHub + URL público)
- [x] Basic Auth na zona de admin (ADMIN_USER/ADMIN_PASS por env; aberto em local)
- [x] Dockerfile com Pango/Cairo (weasyprint corre no servidor)
- [x] .dockerignore (não copiar venv/data/segredos para a imagem)
- [x] uvicorn lê $PORT (Railway/Render injetam a porta)
- [x] .env.example: documentar ADMIN_USER/ADMIN_PASS
- [x] make verify OK + auth testada (401/200/404) por HTTP
- [x] Push para repo GitHub privado (github.com/sportrail/sportrail-contratos)
- [x] Deploy Railway (projeto pleasing-dream, serviço sportrail-contratos)
- [x] Env: BASE_URL + ADMIN_USER + ADMIN_PASS + PORT=8000 (via railway CLI)
- [x] Domínio público + fluxo e2e validado online (401/200/303, links https)
- URL: https://sportrail-contratos-production.up.railway.app
