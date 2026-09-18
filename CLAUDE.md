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
| `POST /api/juntar-pdf` | `{documentos:[{pdf_base64, titulo}]}` | `{pdf_base64, hash, doc_id, data, tz, paginas}` — o DTP compilado |
| `GET /health` | — | `{status: "ok"}` (health check do Render) |

**O `/api/render-pdf` recebe HTML de fora e NÃO é de confiar**:
`gerar_pdf_bytes_isolado` corre com `base_url=None` e um
`URLFetcher(allowed_protocols={"data"})`. Sem isso, um
`<img src="file:///etc/passwd">` transformava o endpoint numa primitiva de
leitura de ficheiros do servidor. Tudo o que o documento precise (logótipos,
assinaturas) vai embutido em `data:` URI. Há um limite de 2 MB de HTML (→ 413).

Os outros dois hidratam os nossos próprios templates, por isso não precisam do
mesmo isolamento.

**O `/api/juntar-pdf` junta PDF como eles foram arquivados — não os regera.**
É esse o ponto do DTP compilado: é o dossier tal como foi datado e arquivado, e
o hash de cada parte já está registado no dashboard. A ordem é a que vem no
pedido; quem conhece a ordem do referencial é o dashboard, que tem o catálogo.
Falha **fechado e a dizer qual**: base64 inválido, PDF ilegível, cifrado ou sem
páginas dão 422 com o título do documento na mensagem. Uma parte ignorada em
silêncio dava um dossier com um documento a menos, e ninguém reparava até à
auditoria. Limites: 40 documentos e 40 MB no conjunto.

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
app.py                 5 rotas: 4 endpoints /api/* + /health
core/
  clausulas.py         entidade + cláusulas em 3 CAMADAS + variantes B2C/B2B
                       + texto_consentimento()
  contract.py          hidrata template -> HTML -> PDF (weasyprint) + auditoria/hash
                       + juntar_pdfs() (pypdf) para o DTP compilado
templates/
  contrato.html        o contrato (merge fields, brand) + anexo livre resolução
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

### Cláusulas em 3 camadas (`core/clausulas.py`)
1. Identificação/DTP — no quadro de destaque do template (auditável DGERT).
2. Lei do consumidor (DL 24/2014) — só B2C.
3. Contrato geral — objeto, pagamento, certificação SIGO, RGPD, etc.

`texto_consentimento()` vive aqui, e não na página que o mostra, pela mesma
razão: é texto jurídico.

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
- Logótipo: `static/logo_sportrail.svg` — versão principal (fundo branco), vinda
  do `Sportrail® - Logo Principal.eps` da pasta da marca no Drive. NUNCA
  redesenhar o logótipo: se o ficheiro não estiver lá, usar a wordmark
  tipográfica e PERGUNTAR.
- NIF Sportrail: 514144785. Tratar o formando por "tu" nos textos.
- Diretora Pedagógica atual: Liliana Fernandes.

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
- [x] `/api/juntar-pdf` — junta os documentos arquivados no DTP compilado.
- [x] Fontes da marca na imagem (antes todo o PDF saía em DejaVu, sem erro).
- [x] Sair do negócio do estado: o que tinha estado passou para o dashboard.
- [ ] **Colar o texto jurídico validado por cima dos blocos `[JURISTA]`.**
- [ ] Contrato de formador (além do de formando).

## Convenções
- Português europeu, "tu". Comentários e mensagens em PT.
- Segredos (`.env`) NUNCA versionados.
