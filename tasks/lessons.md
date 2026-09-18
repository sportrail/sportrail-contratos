# Lessons

- Starlette >= 1.x mudou a assinatura: usar TemplateResponse(request, "nome.html", {ctx})
  e NÃO TemplateResponse("nome.html", {"request": request, ...}) (dá TypeError: unhashable type 'dict').
- weasyprint é mais simples de alojar que Playwright para um servidor (sem binário de browser).

# Sessão 3 — deploy
- weasyprint precisa de Pango/Cairo TAMBÉM no servidor → Dockerfile com apt (libpango/cairo/gdk-pixbuf), não basta pip.
- Basic Auth com env vars: ADMIN_USER/ADMIN_PASS por env. /assinar/<token> nunca leva auth (token já protege). (Sessão 5: deixou de abrir quando vazias — ver abaixo.)

# Sessão 5 — zona de coordenação falha fechada
- Auth que "abre se a env var faltar" é uma bomba-relógio: ADMIN_PASS é sync:false no render.yaml (define-se à mão), logo um deploy novo sem ela expunha nome/NIF/morada/email e os links de assinatura a quem tivesse o URL. Regra: sem config → 503, nunca aberto. Um aviso no arranque não chega.
- secrets.compare_digest(str, str) rebenta com TypeError se houver caracteres não-ASCII → comparar sempre em bytes (.encode("utf-8")). E avaliar user e password ambos antes do `and`.
- /health fica SEMPRE fora da auth: o Render faz o health check sem credenciais; protegê-lo marcava o serviço como não saudável para sempre.
- Ler as env vars no momento do pedido (não no import) deixa o verify.py testar os cenários chamando require_admin diretamente, sem servidor nem httpx.
- Um teste de wiring (que rotas levam a dependência) só vale se acusar quando se tira a dependência à mão — provar isso antes de dar por feito.
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

# Sessão 6 — motor de PDF genérico para o dossier
- **Renderizar HTML de fora é uma primitiva de leitura de ficheiros até se provar o contrário.**
  O `/api/gerar-contrato` podia usar `base_url=BASE` porque o HTML era nosso; o `/api/render-pdf`
  recebe HTML do dashboard e precisa de `base_url=None` + `URLFetcher(allowed_protocols={"data"})`.
  Sem isso, um `<img src="file:///etc/passwd">` bastava. Está testado no verify.py com um
  documento hostil — e o teste lê o TEXTO do PDF, não o log, porque o WeasyPrint engole
  falhas de recurso em silêncio e o render "passa" na mesma.
- **Dep sem pin + API de segurança = a proteção pode partir-se num redeploy.** O isolamento
  depende de `URLFetcher(allowed_protocols=...)`; com `weasyprint` sem versão no
  requirements.txt, um major novo trocava a API sem passar por nenhum commit. Pinado.
- **O PNG de teste do verify.py tinha base64 inválido (95 chars, padding errado).** O
  WeasyPrint descartava a imagem sem erro, portanto todos os testes de contrato assinado
  corriam com a assinatura ausente enquanto diziam estar a testá-la. Lição: um recurso
  embutido só está testado se algo o for procurar ao output — assumir que "renderizou logo
  entrou" é falso para imagens.
- **Os PDFs saíam todos em DejaVu desde sempre.** O `contrato.html` pede "DM Sans", mas a
  imagem só instalava `fonts-dejavu-core`. Nenhum erro, nenhum aviso — só um PDF fora da
  marca. Fontes que a marca exige têm de estar na imagem; e como fontes de SISTEMA
  (fontconfig), não por `@font-face` com URL, senão o url_fetcher isolado bloqueia-as.
- **O verify.py só cobria o que o contrato usa.** O contrato é de página única e sem
  numeração, por isso `@page`, `counter(page)` e `position: running()` nunca tinham sido
  exercitados — e são exatamente o que os documentos do dossier precisam. Testes novos
  cobrem-nos antes de o dashboard depender deles.

# Sessão 7 — logótipo nos documentos
- O logótipo entra por ficheiro em `static/` (SVG), lido em `_logo()` e embutido
  no HTML. Nunca redesenhado: um logótipo traçado à mão é uma marca inventada, e a
  regra do CLAUDE.md sobre parâmetros de marca é PERGUNTAR.
- O original é o EPS da pasta da marca no Drive, convertido com
  `gs -dEPSCrop` + `pdftocairo -svg`: 19 paths, sem fontes embutidas, e o vermelho
  sai exatamente #ED1C24 — o que confirma que é o ativo verdadeiro e não uma
  aproximação.
- O fallback é a wordmark tipográfica que já lá estava. Assim o contrato sai na
  mesma sem o ficheiro, em vez de rebentar ou sair com um buraco.

---

## 2026-09-18 — Um teste que valida código contra a sua própria suposição não prova nada

**O que aconteceu.** Durante meses, nenhum formando conseguiu assinar um
contrato. Ninguém reparou. O `verify.py` estava verde a cada commit.

**Porquê.** Este repo tinha um `supabase_schema.sql` que declarava
`contract_batches` com `id text` e uma coluna `curso jsonb`. O `core/store.py`
foi escrito contra esse schema. O `verify.py` testava o store contra um duplo
em memória e — a parte que parecia cuidadosa — comparava as colunas escritas
com as declaradas **nesse mesmo ficheiro**.

Só que o schema nunca chegou a ser aplicado. A base de dados já tinha as
tabelas criadas pela migration `0003` do dashboard, com `id uuid`, `user_id` e
o curso em colunas separadas. O `create table if not exists` encontrou-as e não
fez nada — sem erro, sem aviso.

Resultado: o teste comparava o store com o schema que o store assumia. Os dois
concordavam perfeitamente. E ambos estavam errados sobre a realidade.

**O que o escondeu.** O que o dashboard consome desta app todos os dias
(`/api/gerar-contrato`, `/api/render-pdf`) é sem estado e nunca toca na base de
dados. Os PDF saíam, o dossier funcionava, tudo parecia bem. O único caminho
partido era o que ninguém percorre a testar outra coisa: um formando a abrir o
link que recebeu.

**A lição, que não é "escrever mais testes".** Um teste que lê a definição do
sistema a partir do próprio código do sistema mede consistência interna, não
correção. Vale quase nada contra um desvio entre o código e o mundo.

Onde há um schema, a fonte de verdade é a base de dados, não um ficheiro `.sql`
no repo que *talvez* tenha sido aplicado. Se não se consegue testar contra a
base de dados a sério, mais vale saber que não se está a testar isso do que ter
um teste verde a dizer que sim.

**E há um sinal que se ignorou:** duas aplicações declaravam as mesmas tabelas
com formas diferentes, ambas a dizer que apontavam para o mesmo projeto
Supabase. Isso é impossível por construção — uma das duas tinha de estar
errada. Estava escrito nos dois repos, em texto simples, e passou.

**Correção:** o estado saiu deste repo (ficou só o motor de contratos e de
PDF). A página de assinatura passou para o dashboard, onde as tabelas estão
mesmo. Detalhe em `tasks/bug-assinatura.md`, no dashboard.

---

## 2026-09-18 — A minuta aprovada pela DGERT

- **O texto legal que estava no repo era rascunho inventado.** Havia um comentário a
  dizer "dado como validado pela Sportrail" por cima de cláusulas que ninguém tinha
  aprovado. Quando o documento real apareceu, não coincidia em nada: outra estrutura,
  outra identificação das partes (documento de identificação, não NIF), outro fecho.
  Lição: "validado" num comentário não é validação; a fonte tem de ser um ficheiro que
  se possa apontar.
- **Um documento aprovado reproduz-se com os defeitos.** A minuta numera a Cláusula 3.ª
  com os pontos "3." e "4." e salta da Cláusula 8.ª para a 10.ª. A tentação é arrumar
  isso. Arrumar era alterar o que a DGERT aprovou — e ninguém dava por ela. Ficaram
  como estão, com um teste que FALHA se alguém os "corrigir" sem passar pelo jurista.
- **Acrescentar ao aprovado faz-se por fora.** A livre resolução (DL 24/2014) não está
  na minuta e é obrigatória para consumidores. Meter cláusulas no articulado resolvia o
  problema jurídico e criava outro: o contrato deixava de ser o aprovado. Foi para
  adenda, depois das assinaturas, e o rodapé "V1. 2024" não a acompanha.
- **Âncoras de texto são o teste que este ficheiro precisa.** Contar cláusulas não
  chega: o corpo pode sair truncado com a contagem certa. O verify.py procura no TEXTO
  DO PDF uma frase inconfundível por cláusula — se uma cai, o teste sabe qual.

---

## 2026-09-18 — Trabalhei contra um `main` que já não existia

**O que aconteceu.** Comecei esta sessão de um clone tirado antes do merge do
PR #6, que tirou o estado a esta app. Reescrevi `core/excel_parser.py`,
`core/store.py`, o `supabase_schema.sql` e três templates — ficheiros que o
`main` tinha apagado quinze minutos antes. Fiz `make verify` verde, abri o PR, e
só ao ler o CI é que dei pelo desencontro: metade do meu diff ressuscitava a
metade que tinha acabado de ser deliberadamente removida.

**A lição.** Verde localmente não diz nada sobre a base. Antes de abrir um PR,
`git fetch origin main` e olhar para `HEAD..origin/main` — sobretudo num repo com
PRs a andar no mesmo dia. O clone da sessão é uma fotografia, não o repositório.

**O que se salvou.** A parte do trabalho que era mesmo deste repo — a minuta
aprovada — sobreviveu inteira. O parser e o backfill mudaram de casa para o
dashboard, que é onde o estado passou a viver, e é lá que estão. Isto foi barato
porque as duas metades já estavam separadas por módulo; se estivessem entrelaçadas
no mesmo ficheiro, o desencontro custava a sessão toda.
