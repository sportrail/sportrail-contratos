# CLAUDE.md — Sportrail · Motor de Contratos e PDF

Contexto para o Claude Code trabalhar neste repositório. Lê isto primeiro.

## O que é

Serviço **sem estado** (FastAPI) que faz duas coisas que precisam de Python:

1. **Hidrata o contrato de formação** com as cláusulas jurídicas da Sportrail
   (3 camadas, variantes B2C/B2B, livre resolução do DL 24/2014).
2. **Renderiza HTML → PDF** com o WeasyPrint.

Não escreve na base de dados, não guarda ficheiros, não tem sessões nem
utilizadores. Recebe dados, devolve documentos.

**O que NÃO está aqui:** lotes, formandos, tokens, a página de assinatura, os
PDF arquivados, o upload do Excel. Isso vive no **`sportrail-dashboard`**, que é
onde as tabelas estão. Se estás à procura de `store.py`, `db.py`, `drive.py`,
`excel_parser.py` ou `supabase_schema.sql`, foram apagados a 18 set 2026 — ver
`tasks/lessons.md`.

### Porque é que a divisão é esta

O texto jurídico tem de ter **uma fonte só**. Reescrevê-lo em TypeScript para o
dashboard o mostrar criava uma segunda versão para divergir em silêncio — e
depois um contrato assinado com um texto e uma página a mostrar outro.

O estado, ao contrário, não tem nada de especial que justifique viver em duas
aplicações. Vive onde já vivia.

## Endpoints

Todos protegidos pelo mesmo `PDF_API_TOKEN` (header `x-api-token`), exceto o
`/health`. Falham **fechados**: sem o segredo configurado respondem 503.

| Endpoint | Recebe | Devolve |
| --- | --- | --- |
| `POST /api/contrato-preview` | `{curso, formando, tipo}` | `{html, consentimento}` — o contrato por assinar, para o formando ler |
| `POST /api/gerar-contrato` | `{curso, formando, tipo, assinatura, ip}` | `{pdf_base64, hash, doc_id, data, tz}` — o contrato assinado, com auditoria |
| `POST /api/render-pdf` | `{html}` | `{pdf_base64, hash, doc_id, data, tz}` — motor genérico do dossier |
| `GET /health` | — | `{status: "ok"}` (health check do Render) |

**O `/api/render-pdf` recebe HTML de fora e NÃO é de confiar**:
`gerar_pdf_bytes_isolado` corre com `base_url=None` e um
`URLFetcher(allowed_protocols={"data"})`. Sem isso, um
`<img src="file:///etc/passwd">` transformava o endpoint numa primitiva de
leitura de ficheiros do servidor. Tudo o que o documento precise (logótipos,
assinaturas) vai embutido em `data:` URI. Há um limite de 2 MB de HTML (→ 413).

Os outros dois hidratam os nossos próprios templates, por isso não precisam do
mesmo isolamento.

## Como correr e verificar

```bash
make setup     # cria venv e instala dependências
make run       # arranca em http://127.0.0.1:8000
make verify    # smoke test — CORRE ISTO ANTES DE DAR ALGO POR FEITO
make clean
```

### Dependência de sistema (importante)
O `weasyprint` precisa de bibliotecas nativas **Pango/Cairo**.
- macOS: `brew install pango gdk-pixbuf libffi`
- Debian/Ubuntu: `apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0`
- Deploy: tratado no `Dockerfile`.
- CI: `.github/workflows/verify.yml` corre `python verify.py` em cada push/PR
  para `main`, com a mesma lista de apt do `Dockerfile`. Se mudares uma lista,
  muda a outra.

Se o `import weasyprint` falhar, é quase sempre isto.

### Variáveis de ambiente
Uma só: **`PDF_API_TOKEN`**. Igual ao `CONTRATOS_PDF_TOKEN` do dashboard.

### Deploy — Render (ativo)
`https://sportrail-contratos.onrender.com` (serviço `sportrail-contratos`,
Frankfurt, Docker). `render.yaml` + `Dockerfile`. No plano free adormece após
~15 min, e o 1.º pedido leva ~30 s a acordar — quem chama tem de tolerar isso
(o dashboard tem timeout de 60 s e uma função de aquecimento).

## Arquitetura

```
app.py                 4 rotas: 3 endpoints /api/* + /health
core/
  clausulas.py         entidade + MINUTA APROVADA pela DGERT + adenda B2C
                       + texto_consentimento()
  contract.py          hidrata template -> HTML -> PDF (weasyprint) + auditoria/hash
templates/
  contrato.html        o contrato (minuta aprovada) + adenda B2C + anexo
static/assinatura_diretora.png   SUBSTITUIR pela assinatura real
static/logo_sportrail.svg        logótipo do cabeçalho (vetorial, do EPS da marca);
                       sem ficheiro, cai para a wordmark tipográfica
static/fonts/          Bebas Neue + DM Sans (OFL); o Dockerfile instala-as como
                       fontes de sistema — ver static/fonts/README.md
verify.py              smoke test
```

Nada em `static/` é servido por HTTP: o `contract.py` lê-o do disco e embute-o
em `data:` URI. O mount `/static` saiu com as páginas web.

## Regras de domínio (não quebrar)

### Variantes de contrato
- **B2C** (formando particular = consumidor): inclui cláusula de **livre
  resolução de 14 dias** (DL 24/2014) + anexo com formulário de resolução. O
  consentimento na assinatura serve de **pedido expresso** (art. 4.º) para
  iniciar a formação antes dos 14 dias.
- **B2B** (empresa/clube adquirente): SEM livre resolução nem anexo.
- Quem escolhe a variante é o dashboard (default do lote, com override por
  linha no Excel). Aqui só se recebe `tipo` e se obedece.

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

### Excel e backfill vivem no dashboard
Esta app já não lê Excel nem guarda estado. O parser do export do WooCommerce, o
backfill do histórico e as tabelas estão no `sportrail-dashboard`
(`src/lib/contratos/excel.ts`, `/contratos/backfill`, migração `0007`). Aqui só
chega o `formando` já hidratado, por `/api/gerar-contrato`.

Os campos que a minuta aprovada precisa e que o dashboard passa a mandar:
`doc_identificacao` (o `CC` do export — a minuta identifica o formando pelo
documento, não pelo NIF), `validade_documento`, `concelho`, `distrito`, e ainda
`cedula` e `clube` para o quadro de destaque.

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
4. **Verify** — corre `make verify` antes de dar algo por concluído. Não
   declarar "feito" sem verificação.
5. **Elegance Balanced** — simples e legível; não sobre-engenheirar.
6. **Autonomous Bug Fixing** — se um teste falha, diagnostica e corrige.

## Roadmap / pendente
- [x] Dockerfile para deploy (Pango/Cairo + `$PORT`).
- [x] Deploy online (Render free).
- [x] `/api/gerar-contrato` — motor de contratos do dashboard.
- [x] `/api/render-pdf` — motor de PDF genérico do dossier.
- [x] `/api/contrato-preview` — contrato por assinar, em HTML.
- [x] Fontes da marca na imagem (antes todo o PDF saía em DejaVu, sem erro).
- [x] Sair do negócio do estado: o que tinha estado passou para o dashboard.
- [x] Corpo do contrato = minuta aprovada pela DGERT (deixou de haver rascunho).
- [ ] Jurista: confirmar as anomalias de numeração da minuta (Cl. 3.ª, Cl. 9.ª).
- [ ] Jurista: seguro em ações online (a minuta aprovada não distingue).
- [ ] Jurista: validar a adenda B2C como forma de acrescentar a livre resolução.
- [ ] Contrato de formador (além do de formando).

## Convenções
- Português europeu, "tu". Comentários e mensagens em PT.
- Segredos (`.env`) NUNCA versionados.
