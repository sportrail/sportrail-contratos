# Sportrail — Contratos de Formação (protótipo Caminho B)

App web onde carregas um Excel de formandos + dados do curso e o sistema:
gera o contrato hidratado (com a assinatura da Diretora já incluída) → cria um
link de assinatura único por formando → recolhe a assinatura no browser →
carimba trilho de auditoria (data, IP, consentimento, hash SHA-256) → arquiva
o PDF assinado na pasta DTP do curso no Google Drive.

> ⚠️ **Aviso legal.** O texto das 8 cláusulas em `core/clausulas.py` é um
> **rascunho de andaime**. Substitui-o pelas cláusulas validadas do teu
> `generate_contracts_v2.js` antes de qualquer uso real. Não é aconselhamento
> jurídico — valida a conformidade com quem trata da parte jurídica/DGERT.

---

## 1. O que precisas de fornecer

**Por curso (no formulário da app):** nome da ação, modalidade, duração,
data de início, data de conclusão.

**Por formando (no Excel):** primeira linha = cabeçalhos. Colunas:
- `nome` *(obrigatório)*
- `email` *(obrigatório)*
- `nif` *(opcional)*
- `valor_pago` *(opcional — cobre early bird vs. normal, ex.: 47 / 49)*
- `morada` *(opcional)*
- `tipo_contrato` *(opcional — B2C ou B2B; vazio herda o default do lote)*

Vê `formandos_exemplo.xlsx`. O sistema tira tudo o resto do Excel
automaticamente — não precisas de tocar em JSON nem em código por curso.

## Variantes de contrato: B2C vs. B2B

O contrato é gerado em duas variantes, escolhidas no lote (com override por
linha no Excel via coluna `tipo_contrato`):

- **B2C** (formando particular = consumidor): inclui a cláusula de **direito de
  livre resolução de 14 dias** (Decreto-Lei 24/2014) e um **anexo com o
  formulário de livre resolução**. O consentimento na assinatura serve também
  de **pedido expresso** para iniciar a formação dentro do prazo de 14 dias.
- **B2B** (empresa/clube adquirente, que não é consumidor): sem cláusula de
  livre resolução nem anexo.

As cláusulas estão organizadas em 3 camadas em `core/clausulas.py`: Camada 1
(identificação/DTP, no quadro de destaque), Camada 2 (lei do consumidor, só
B2C) e Camada 3 (contrato geral). **Todo o texto legal marcado com `[JURISTA]`
tem de ser confirmado pelo advogado** antes de uso real — em especial a livre
resolução e a eventual renúncia ao abrigo do art. 17.º.

**Assinatura da Diretora:** substitui `static/assinatura_diretora.png` por um
PNG com fundo transparente da assinatura real. (Convém ela autorizar por
escrito o uso da assinatura nestes contratos padronizados.)

---

## 2. Correr localmente (testar em 2 minutos)

```bash
pip install -r requirements.txt
cp .env.example .env          # traz ADMIN_USER/ADMIN_PASS de exemplo
uvicorn app:app --reload --port 8000 --env-file .env
```

A zona de coordenação (`/`, criar lote, dashboard) exige `ADMIN_USER` e
`ADMIN_PASS` — sem elas responde 503, nunca abre. Em produção define-as no
Environment do Render.

Abre `http://127.0.0.1:8000`, preenche o curso, carrega o Excel de exemplo.
A app leva-te ao dashboard com um link de assinatura por formando.

> Em local, os links `127.0.0.1` só funcionam na tua máquina. Para os formandos
> assinarem de qualquer lado, precisas de alojar (secção 4).

---

## 3. Onde fica alojado

A app é um servidor FastAPI. Os formandos abrem um link no telemóvel/PC, por
isso precisa de **um URL público**. Três opções, da mais simples à mais barata:

| Opção | Custo | Esforço | Notas |
|---|---|---|---|
| **Render / Railway / Fly.io** | grátis–€5/mês | baixo | deploy direto do repositório; URL HTTPS automático |
| **VPS (Hetzner, DigitalOcean)** | €4–6/mês | médio | controlas tudo; precisas de configurar HTTPS (Caddy/Nginx) |
| **A tua própria máquina + Cloudflare Tunnel** | grátis | médio | bom para testar com formandos reais sem alugar servidor |

Recomendo **Render** para começar: ligas o repositório, defines o comando
`uvicorn app:app --host 0.0.0.0 --port $PORT`, e tens URL HTTPS em minutos.

Define a variável de ambiente `BASE_URL` com o teu domínio público (ex.:
`https://contratos.sportrail.pt`) para os links de assinatura saírem corretos.

### Onde vive o estado (e porquê não em disco)

Os lotes e os formandos ficam no **Postgres do Supabase** e os PDFs assinados no
bucket privado **`contratos`**. Nada é escrito no disco do servidor.

Isto não é preferência de arquitetura, é obrigatório no plano free do Render: o
filesystem é efémero e o serviço adormece ao fim de ~15 min sem tráfego. Com o
estado em `data/state.json`, cada vez que o serviço acordava os tokens de
assinatura já enviados aos formandos deixavam de existir — o link no email
passava a dar 404 — e os PDFs assinados desapareciam com eles.

Antes do primeiro deploy, uma vez:

1. corre o **`supabase_schema.sql`** no SQL Editor do Supabase;
2. cria o bucket **`contratos`** em Storage → New bucket, **Private**;
3. define `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` no Render.

Sem as duas variáveis a app arranca e rebenta no primeiro pedido, de propósito:
mais vale isso do que aceitar assinaturas e perdê-las no restart seguinte.

A service role key ignora o RLS e **só pode viver no servidor**. As tabelas têm
o RLS ligado sem políticas nenhumas: o service role passa à frente, e as roles
`anon`/`authenticated` (as que o dashboard usa no browser) não conseguem ler
nada. São dados pessoais de terceiros — nome, NIF, morada, email, IP — por isso
o default tem de ser fechado.

---

## 4. Arquivo no Google Drive

Sem configurar nada, os PDFs assinados ficam no Supabase Storage — que já é
arquivo durável. Para arquivar **também** no Drive, na pasta DTP do curso:

1. Em Google Cloud Console → cria uma **conta de serviço** → gera uma chave
   JSON. Guarda-a como `data/service_account.json`.
2. Ativa a **Google Drive API** nesse projeto.
3. No Drive, **partilha a pasta-raiz DTP** (onde queres as subpastas por curso)
   com o email da conta de serviço (algo como `...@...iam.gserviceaccount.com`),
   com permissão de Editor.
4. Define a variável de ambiente `DRIVE_ROOT_FOLDER_ID` com o ID dessa pasta
   (está no URL da pasta no Drive).

A app cria automaticamente uma subpasta com o nome do curso e lá coloca cada
`contrato_<Nome>_<ID>.pdf`. Se as credenciais faltarem, cai para o modo local
sem rebentar.

---

## 5. Fluxo operacional (como usar no dia a dia)

1. Fecham as inscrições do curso.
2. Exportas os inscritos para um Excel com as colunas acima.
3. Abres a app → preenches o curso → carregas o Excel.
4. No dashboard, copias o link de cada formando e envias (email/WhatsApp).
   *Justificação natural:* "preciso da tua assinatura no contrato para emitir
   o teu certificado" — dá deadline e alinha com a conclusão da formação.
5. Cada formando lê o contrato, assina no telemóvel, dá consentimento, submete.
6. O dashboard passa a "assinado" e o PDF fica arquivado no Drive.

---

## 6. Estrutura do código

```
app.py                  # rotas FastAPI (upload, dashboard, assinar, pdf)
core/
  clausulas.py          # entidade + 8 cláusulas (RASCUNHO a substituir)
  excel_parser.py       # lê o Excel -> formandos
  contract.py           # hidrata template -> HTML -> PDF + auditoria
  store.py              # estado em JSON (trocar por base de dados depois)
  drive.py              # upload Drive (com fallback local)
templates/
  contrato.html         # o contrato (merge fields, brand Sportrail)
  upload.html           # página de carregamento
  dashboard.html        # estado por formando
  assinar.html          # página de assinatura (canvas) + consentimento
  obrigado.html         # confirmação
static/
  assinatura_diretora.png   # SUBSTITUIR pela assinatura real
formandos_exemplo.xlsx
```

---

## 7. Limitações deste protótipo (consciente)

- Estado em JSON (`data/state.json`), não base de dados — bom para validar,
  trocar por SQLite/Postgres para produção.
- Sem envio automático de emails — o dashboard dá-te os links para enviares.
  Fácil de adicionar depois (SMTP/SendGrid).
- Zona de coordenação (`/` e `/lote/*`) protegida só por Basic Auth
  (`ADMIN_USER`/`ADMIN_PASS`, que falha fechada: sem elas responde 503) — um
  único utilizador, sem login por pessoa. As páginas `/assinar/<token>` são
  protegidas pelo token aleatório.
- Trilho de auditoria é caseiro (timestamp+IP+hash+consentimento). Suficiente
  e admissível como assinatura eletrónica simples; se quiseres robustez
  probatória de fornecedor, é o Caminho A.
```
