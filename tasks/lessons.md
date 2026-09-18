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

## 2026-09-18 — Juntar não é gerar

- **O compilado junta o que foi arquivado; não o regera.** A tentação era hidratar
  tudo outra vez e imprimir de seguida — sai mais simples e dá um PDF mais bonito.
  Mas o hash de cada documento já está registado no dashboard, e um compilado
  regerado não corresponde a nenhum deles. O valor do arquivo é ser verificável; um
  PDF bonito que não bate com nenhum hash não vale nada numa auditoria.
- **Falhar em silêncio é pior do que falhar.** Quinze PDF a entrar e um corrompido:
  ignorá-lo dava um dossier com um documento a menos, e ninguém reparava. Por isso o
  `juntar_pdfs` recusa a operação inteira e põe **o título do documento** na
  mensagem — o que falta saber é qual, não que houve um problema.
- **`base64.b64decode` sem `validate=True` engole lixo.** Sem a flag, aceita
  qualquer coisa e devolve bytes que não são um PDF; o erro só aparecia mais à
  frente, no `pypdf`, com uma mensagem sobre outra coisa. O erro tem de aparecer
  onde a suposição se quebra.
- **Um teste que vale a pena: a ordem.** Verificar que juntar a lista invertida dá
  os marcadores invertidos parece tolice. Não é: fixa que a ordem do referencial é
  decisão do dashboard, e não deste motor. Se alguém aqui resolver ordenar por
  título "para ficar arrumado", o teste acusa.
