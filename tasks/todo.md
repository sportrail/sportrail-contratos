## Sessão 7 — juntar PDF (/api/juntar-pdf) para o DTP compilado

Contexto: o dossier técnico-pedagógico acaba num PDF único, ordenado pelas
secções do referencial. O dashboard tem os 15 documentos arquivados no Storage;
juntá-los é a única peça que falta e é Python — o `pypdf` já cá está, usado até
agora só pelo `verify.py`.

O DTP compilado junta os PDF **tal como foram arquivados**, não os regera. É esse
o ponto: o compilado é o dossier como ele foi assinado e datado, e o hash de cada
parte já está registado no dashboard.

- [x] `contract.juntar_pdfs(documentos)` — junta e escreve os marcadores (outline)
- [x] `POST /api/juntar-pdf` — mesmo `X-Api-Token`, sem estado, com limites próprios
- [x] Falhar fechado e falar claro: PDF corrompido ou cifrado dá 422 dizendo QUAL
- [x] verify.py: junta 3 PDF, conta páginas, lê os marcadores, rejeita lixo e
      confirma que a rota exige token
- [x] CLAUDE.md + README: a tabela de endpoints passa a ter quatro linhas
- [x] Verificado: `make verify` verde (32 verificações, 6 delas novas)

## Sessão 6 — motor de PDF genérico (/api/render-pdf) para o Dossier DGERT

Contexto: o dashboard vai gerar os documentos do dossier técnico-pedagógico. Os
templates vivem lá (junto do modelo de dados); esta app só acrescenta a peça que
falta — renderizar HTML arbitrário para PDF, isolada.

- [x] `contract.gerar_pdf_bytes_isolado(html)` — `base_url=None` + URLFetcher só com `data:`
- [x] `POST /api/render-pdf` (mesmo `X-Api-Token` do /api/gerar-contrato, stateless)
- [x] Pinar `weasyprint` (a API de URLFetcher mudou; requirements sem pin = deploy imprevisível)
- [x] Fontes da marca (Bebas Neue + DM Sans) no Dockerfile — a imagem só tinha DejaVu
- [x] verify.py: rota classificada + render mínimo + isolamento (file:// e https:// bloqueados)
- [x] CLAUDE.md: documentar o papel triplo desta app
- [x] Bónus: PNG de teste do verify.py tinha base64 inválido — a assinatura nunca renderizava
- [x] Verificado: make verify verde + fluxo HTTP (401 sem token, 200 com, 413 acima do limite)


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
- [x] Bruno confirmou: o Render pede ADMIN_USER/ADMIN_PASS na zona de coordenação (ambas definidas)

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

## Sessão 5 — CI (GitHub Actions)
- [x] `.github/workflows/verify.yml`: corre `python verify.py` em push/PR para main
- [x] apt no runner = mesma lista do Dockerfile (+ shared-mime-info); sem segredos
- [x] Validado localmente com o verify.py de main, do PR #1 e do PR #2
- [x] Confirmar job verde no separador Checks do PR (#3, run 1: success)
