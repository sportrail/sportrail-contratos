
## Sessão 2 — concluído
- [x] Reestruturar cláusulas em 3 camadas
- [x] Variante B2C (com livre resolução + anexo) e B2B (sem)
- [x] Override por linha no Excel (coluna tipo_contrato) + default no lote
- [x] Consentimento dinâmico = pedido expresso art. 4.º (B2C)
- [x] Anexo formulário de livre resolução no PDF B2C
- [x] Verificado: B2C 3 págs, B2B 2 págs, fluxo HTTP OK

## Sessão 3 — deploy (GitHub + URL público)
- [x] Basic Auth na zona de admin (ADMIN_USER/ADMIN_PASS por env; aberto em local)
- [x] Dockerfile com Pango/Cairo (weasyprint corre no servidor)
- [x] .dockerignore (não copiar venv/data/segredos para a imagem)
- [x] uvicorn lê $PORT (Railway/Render injetam a porta)
- [x] .env.example: documentar ADMIN_USER/ADMIN_PASS
- [x] make verify OK + auth testada (401/200/404) por HTTP
- [ ] Push para repo GitHub privado
- [ ] Deploy (Railway): BASE_URL + ADMIN_USER/ADMIN_PASS no painel
