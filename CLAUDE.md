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
- Deploy: já tratado no `Dockerfile` (instala estas libs via apt).
- CI: `.github/workflows/verify.yml` corre `python verify.py` em cada push/PR
  para `main`, com a mesma lista de apt do `Dockerfile`. Se mudares uma lista,
  muda a outra.
Se o `import weasyprint` falhar, é quase sempre isto.

### Variáveis de ambiente (ver `.env.example`)
- `BASE_URL` — URL pública (links de assinatura). Vazio em local.
- `ADMIN_USER` / `ADMIN_PASS` — Basic Auth na zona de coordenação (`/`, criar
  lote, dashboard). FALHA FECHADA: se vazias → essas rotas respondem 503, nunca
  abrem (em local, copia `.env.example` para `.env` e usa `--env-file .env`).
  `/assinar/<token>`, `/pdf/<token>`, `/health`, `/api/gerar-contrato` e
  `/api/render-pdf` ficam fora desta proteção de propósito (token, health check
  do Render, PDF_API_TOKEN).
- `PDF_API_TOKEN` — segredo que protege `POST /api/gerar-contrato` e
  `POST /api/render-pdf` (motores de PDF do dashboard). Sem isto os endpoints dão
  503. Igual ao `CONTRATOS_PDF_TOKEN` no dashboard.
- `DRIVE_ROOT_FOLDER_ID` — arquivo no Drive; sem isto, cai para `data/arquivo/`.

### Deploy — Render (ativo)
Alojado no **Render** (free): `https://sportrail-contratos.onrender.com`
(serviço `sportrail-contratos`, região Frankfurt, Docker). `render.yaml`
(Blueprint) + `Dockerfile` (instala Pango/Cairo, lê `$PORT`). Gerido pelo CLI
`render`. No plano free adormece após ~15 min (1.º pedido ~30s a acordar).
(Antes esteve no Railway; o trial expirou → migrado para o Render.)

### Papel triplo desta app
1. **App autónoma** — fluxo completo (upload → dashboard → assinar → PDF).
2. **Motor de contratos do dashboard** — `POST /api/gerar-contrato` (protegido
   por `PDF_API_TOKEN`): recebe `{curso, formando, tipo, assinatura, ip}` e
   devolve `{pdf_base64, hash, doc_id, data, tz}`. O dashboard (Next) delega-lhe
   só o PDF, reutilizando as cláusulas jurídicas e o WeasyPrint.
3. **Motor de PDF genérico** — `POST /api/render-pdf` (mesmo token): recebe
   `{html}` já hidratado e devolve `{pdf_base64, hash, doc_id, data, tz}`, com
   `hash = SHA-256(doc_id|html)`. Serve os documentos do dossier
   técnico-pedagógico, cujos **templates vivem no dashboard**, junto do modelo de
   dados que os alimenta — aqui só acontece a parte que precisa de Python.

   O HTML vem de fora e **não é de confiar**: `gerar_pdf_bytes_isolado` corre com
   `base_url=None` e um `URLFetcher(allowed_protocols={"data"})`. Sem isso, um
   `<img src="file:///etc/passwd">` transformava o endpoint numa primitiva de
   leitura de ficheiros do servidor. Tudo o que o documento precise (logótipos,
   assinaturas) vai embutido em `data:` URI. Há também um limite de 2 MB de HTML
   (→ 413). O endpoint é **stateless**: quem persiste é o dashboard.

## Arquitetura

```
app.py                 rotas FastAPI (upload, dashboard, assinar, pdf)
core/
  clausulas.py         entidade + MINUTA APROVADA pela DGERT + adenda B2C
  excel_parser.py      lê Excel -> formandos (export WooCommerce ou folha manual)
  contract.py          hidrata template -> HTML -> PDF (weasyprint) + auditoria/hash
  store.py             estado em data/state.json (trocar por DB em produção)
  drive.py             upload Google Drive (fallback local se sem credenciais)
templates/
  contrato.html        o contrato (minuta aprovada) + adenda B2C + anexo
  upload.html          form de carregamento + seletor B2C/B2B + backfill
  backfill.html        um lote por ação encontrada no export do WooCommerce
  dashboard.html       estado por formando
  assinar.html         página de assinatura (canvas) + consentimento dinâmico
  obrigado.html        confirmação
static/assinatura_diretora.png   SUBSTITUIR pela assinatura real
static/logo_sportrail.svg        logótipo do cabeçalho (vetorial, do EPS da marca);
                       sem ficheiro, cai para a wordmark tipográfica
static/fonts/          Bebas Neue + DM Sans (OFL); o Dockerfile instala-as como
                       fontes de sistema — ver static/fonts/README.md
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

### O corpo do contrato é a minuta APROVADA (`core/clausulas.py`)
`MINUTA_APROVADA` é transcrição literal da minuta "Contrato de Formação
Sportrail V1. 2024", aprovada pela DGERT no pedido de certificação. **Não se
reescreve, não se renumera, não se "melhora" a redação.** Se o documento gerado
deixar de coincidir com ela, a certificação deixa de cobrir o que a Sportrail faz
assinar. O `verify.py` tem âncoras de texto que falham se uma cláusula cair.

Duas anomalias vêm da própria minuta e estão lá DE PROPÓSITO (com teste a
garanti-lo): a Cláusula 3.ª numera os pontos "3." e "4.", e não existe Cláusula
9.ª — salta da 8.ª para a 10.ª. Corrigi-las é decisão do jurista sobre um
documento aprovado.

As 3 camadas continuam a valer, mudou a origem do conteúdo:
1. Identificação/DTP — preâmbulo + quadro de destaque (auditável DGERT).
2. Lei do consumidor (DL 24/2014) — só B2C, e só em **ADENDA**, depois das
   assinaturas. A minuta aprovada não tem livre resolução; acrescentar cláusulas
   ao articulado alterava o documento aprovado. A adenda também não leva o
   rodapé "V1. 2024" — não foi isso que a DGERT viu.
3. Corpo do contrato — a minuta aprovada, igual em B2C e B2B.

### Excel de formandos — dois formatos
- **Export do WooCommerce** (o que a loja produz desde 2024, sem edição):
  `First Name (Billing)` + `Last Name (Billing)` (o nome vem partido),
  `Email (Billing)`, `CC`, `NIF`, `cedula`, `clube`, `Product Name`,
  `Order Total Amount`.
- **Folha manual**: `nome`, `email`, `nif`, `morada`, ... Continua a funcionar.

O `CC` é o **documento de identificação** que a minuta pede no preâmbulo — a
minuta não identifica o formando pelo NIF.

### Backfill do histórico (`/backfill/preview` → `/backfill/criar`)
Um export pode cobrir anos de formações: agrupa-se por `Product Name` e cria-se
**um lote por ação** (`origem = 'backfill'`). O WooCommerce não tem modalidade,
duração nem datas — e essas saem impressas nas cláusulas 1.ª e 2.ª, por isso são
**pedidas ao coordenador, nunca inventadas**. Um valor adivinhado ali é um
contrato errado, não um campo por preencher.

Estado `arquivado_papel`: quem já assinou em papel fica registado **sem
assinatura, sem PDF e sem hash**. Fabricar uma imagem de assinatura para fechar
uma linha do backfill era falsificar exatamente o documento que o trilho de
auditoria existe para tornar credível.

### Guarda-jurídica (CRÍTICO)
- Todo o texto legal marcado com `[JURISTA]` é RASCUNHO e tem de ser validado
  pelo advogado. **NUNCA inventar texto legal e apresentá-lo como definitivo.**
- `[EMAIL DA ENTIDADE]` e afins são placeholders a preencher.
- Quem programa NÃO decide se um profissional individual conta como consumidor
  (B2C) ou não — isso é decisão do jurista; a app só tem de suportar ambos.
  Em concreto: a coluna `clube` preenchida no export **não** torna a linha B2B.
- O seguro: a minuta aprovada dá o seguro contra acidentes como direito do
  formando (Cl. 3.ª, alínea b), **sem distinguir online de presencial**. Está
  assim porque é o texto aprovado. A regra "online → sem seguro" que esta secção
  tinha aplicava-se ao rascunho anterior; está PENDENTE de decisão do jurista
  (ver tasks/todo.md, Sessão 8).

### Marca Sportrail (fonte de verdade; se em dúvida, PERGUNTAR antes de criar)
- Cores: vermelho `#ED1C24` (hover `#c41920`), preto `#0B0A0F`, card `#13121A`,
  border `#222130`, grey `#AAAAAA`, cream `#FAF8F5`.
- Tipografia: Bebas Neue + DM Sans. Botões `border-radius: 5px`; cards `0`.
- Logótipo: `static/logo_sportrail.svg` — versão principal (fundo branco), vinda
  do `Sportrail® - Logo Principal.eps` da pasta da marca no Drive. NUNCA
  redesenhar o logótipo: se o ficheiro não estiver lá, usar a wordmark
  tipográfica e PERGUNTAR.
- NIF Sportrail: 514144785. Tratar o formando por "tu" nos textos.
- Diretora Pedagógica atual: Liliana Fernandes. Na minuta aprovada outorga como
  **Gerente**, com o nome completo "Liliana Regina Fernandes".

## Workflow (seguir nesta ordem)
1. **Plan First** — escreve/atualiza `tasks/todo.md` antes de mexer em código.
2. **Subagents** — divide trabalho independente quando fizer sentido.
3. **Self-Improvement** — regista aprendizagens em `tasks/lessons.md`.
4. **Verify** — corre `make verify` (e o fluxo HTTP se mexeste em rotas) antes
   de dar algo por concluído. Não declarar "feito" sem verificação.
5. **Elegance Balanced** — simples e legível; não sobre-engenheirar o protótipo.
6. **Autonomous Bug Fixing** — se um teste falha, diagnostica e corrige.

## Roadmap / pendente
- [x] Autenticação na zona de admin (`/` e `/lote/*`) — Basic Auth por env.
- [x] Dockerfile para deploy (Pango/Cairo + `$PORT`).
- [x] Deploy online (Render free): BASE_URL + ADMIN + PDF_API_TOKEN definidos.
- [x] Endpoint `/api/gerar-contrato` (motor de PDF para o dashboard).
- [x] Endpoint genérico `/api/render-pdf` (motor de PDF do dossier DGERT).
- [x] Fontes da marca na imagem (antes todo o PDF saía em DejaVu, sem erro).
- [x] Corpo do contrato = minuta aprovada pela DGERT (deixou de haver rascunho).
- [x] Export do WooCommerce lido tal como sai + backfill do histórico.
- [ ] Jurista: confirmar as anomalias de numeração da minuta (Cl. 3.ª, Cl. 9.ª).
- [ ] Jurista: seguro em ações online (a minuta aprovada não distingue).
- [ ] Jurista: validar a adenda B2C como forma de acrescentar a livre resolução.
- [ ] Envio automático de emails com os links (SMTP/SendGrid).
- [ ] Configurar arquivo real no Google Drive (conta de serviço — ver README).
- [ ] Trocar estado JSON por SQLite/Postgres.
- [ ] Contrato de formador (além do de formando).

## Convenções
- Português europeu, "tu". Comentários e mensagens em PT.
- Não criar ficheiros em `data/` no git (estado runtime). Ver `.gitignore`.
- Segredos (`service_account.json`, `.env`) NUNCA versionados.
