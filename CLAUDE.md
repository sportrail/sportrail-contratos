# CLAUDE.md — Sportrail · Contratos de Formação

Contexto para o Claude Code trabalhar neste repositório. Lê isto primeiro.

## O que é

App web (FastAPI) que automatiza a assinatura digital de contratos de formação
da Sportrail. Fluxo: o coordenador carrega um Excel de formandos + dados do
curso → o sistema gera um contrato hidratado por pessoa (com a assinatura da
Diretora Pedagógica já incluída) → cada formando recebe um link único → assina
no browser (canvas) e consente → o sistema carimba trilho de auditoria
(timestamp, IP, hash SHA-256), gera o PDF final e arquiva-o na pasta DTP do
curso no Google Drive.

É o "Caminho B" (construir em vez de comprar SaaS de assinatura). Implementa
assinatura eletrónica **simples** (eIDAS), suficiente e admissível para
contratos de formação.

## Como correr e verificar

```bash
make setup     # cria venv e instala dependências
make run       # arranca em http://127.0.0.1:8000
make verify    # smoke test do pipeline (sem servidor) — CORRE ISTO ANTES DE DAR ALGO POR FEITO
make clean      # limpa estado e PDFs gerados
```

Sem `make`:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
python verify.py
```

### Dependência de sistema (importante)
O `weasyprint` (motor HTML→PDF) precisa de bibliotecas nativas **Pango/Cairo**.
- macOS: `brew install pango gdk-pixbuf libffi`
- Debian/Ubuntu: `apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0`
Se o `import weasyprint` falhar, é quase sempre isto.

## Arquitetura

```
app.py                 rotas FastAPI (upload, dashboard, assinar, pdf)
core/
  clausulas.py         entidade + cláusulas em 3 CAMADAS + variantes B2C/B2B
  excel_parser.py      lê Excel -> formandos (colunas com aliases)
  contract.py          hidrata template -> HTML -> PDF (weasyprint) + auditoria/hash
  store.py             estado em data/state.json (trocar por DB em produção)
  drive.py             upload Google Drive (fallback local se sem credenciais)
templates/
  contrato.html        o contrato (merge fields, brand) + anexo livre resolução
  upload.html          form de carregamento + seletor B2C/B2B
  dashboard.html       estado por formando
  assinar.html         página de assinatura (canvas) + consentimento dinâmico
  obrigado.html        confirmação
static/assinatura_diretora.png   SUBSTITUIR pela assinatura real
verify.py              smoke test do pipeline
formandos_exemplo.xlsx exemplo de input
```

## Regras de domínio (não quebrar)

### Variantes de contrato
- **B2C** (formando particular = consumidor): inclui cláusula de **livre
  resolução de 14 dias** (DL 24/2014) + anexo com formulário de resolução. O
  consentimento na assinatura serve de **pedido expresso** (art. 4.º) para
  iniciar a formação antes dos 14 dias.
- **B2B** (empresa/clube adquirente): SEM livre resolução nem anexo.
- Variante escolhida por default no lote, com override por linha no Excel
  (coluna `tipo_contrato` = B2C/B2B). Default vazio → herda o do lote.

### Cláusulas em 3 camadas (`core/clausulas.py`)
1. Identificação/DTP — no quadro de destaque do template (auditável DGERT).
2. Lei do consumidor (DL 24/2014) — só B2C.
3. Contrato geral — objeto, pagamento, certificação SIGO, RGPD, etc.

### Guarda-jurídica (CRÍTICO)
- Todo o texto legal marcado com `[JURISTA]` é RASCUNHO e tem de ser validado
  pelo advogado. **NUNCA inventar texto legal e apresentá-lo como definitivo.**
- `[EMAIL DA ENTIDADE]` e afins são placeholders a preencher.
- Quem programa NÃO decide se um profissional individual conta como consumidor
  (B2C) ou não — isso é decisão do jurista; a app só tem de suportar ambos.
- Formação online → sem cláusula de seguro. Presencial → com seguro.

### Marca Sportrail (fonte de verdade; se em dúvida, PERGUNTAR antes de criar)
- Cores: vermelho `#ED1C24` (hover `#c41920`), preto `#0B0A0F`, card `#13121A`,
  border `#222130`, grey `#AAAAAA`, cream `#FAF8F5`.
- Tipografia: Bebas Neue + DM Sans. Botões `border-radius: 5px`; cards `0`.
- NIF Sportrail: 514144785. Tratar o formando por "tu" nos textos.
- Diretora Pedagógica atual: Liliana Fernandes.

## Workflow (seguir nesta ordem)
1. **Plan First** — escreve/atualiza `tasks/todo.md` antes de mexer em código.
2. **Subagents** — divide trabalho independente quando fizer sentido.
3. **Self-Improvement** — regista aprendizagens em `tasks/lessons.md`.
4. **Verify** — corre `make verify` (e o fluxo HTTP se mexeste em rotas) antes
   de dar algo por concluído. Não declarar "feito" sem verificação.
5. **Elegance Balanced** — simples e legível; não sobre-engenheirar o protótipo.
6. **Autonomous Bug Fixing** — se um teste falha, diagnostica e corrige.

## Roadmap / pendente
- [ ] Colar o texto jurídico validado por cima dos blocos `[JURISTA]`.
- [ ] Envio automático de emails com os links (SMTP/SendGrid).
- [ ] Deploy: Dockerfile + Railway (BASE_URL, DRIVE_ROOT_FOLDER_ID).
- [ ] Configurar arquivo real no Google Drive (conta de serviço — ver README).
- [ ] Trocar estado JSON por SQLite/Postgres.
- [ ] Autenticação na zona de admin (`/` e `/lote/*`).
- [ ] Contrato de formador (além do de formando).

## Convenções
- Português europeu, "tu". Comentários e mensagens em PT.
- Não criar ficheiros em `data/` no git (estado runtime). Ver `.gitignore`.
- Segredos (`service_account.json`, `.env`) NUNCA versionados.
