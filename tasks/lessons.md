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

# Sessão 8 — a minuta aprovada e o export real
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
- **O parser rejeitava o ficheiro real desde sempre.** O export do WooCommerce não tem
  coluna `nome` — tem `First Name (Billing)` e `Last Name (Billing)`. O parser exigia
  `nome` e `email` e dava "o Excel tem de ter as colunas nome e email" ao ficheiro que
  é o input verdadeiro do sistema. Escreveu-se um export sintético com a forma exata do
  real no verify.py; o exemplo à mão que lá estava validava um formato que ninguém usa.
- **Um número lido de Excel não é uma string.** `str(233385169.0)` dá "233385169.0" num
  NIF, e `str(150)` dá "€ 150" num valor de contrato. Ambos saíam impressos assim.
- **Os testes de guarda pagaram-se todos nesta sessão.** As rotas novas acusaram "por
  classificar" no teste de auth, as colunas novas acusaram "a mais" no teste de schema
  (o leitor só via `create table`, não os `alter table` das migrações) e o `origem` novo
  acusou na forma de retorno do `obter_lote`. Quatro falhas, quatro coisas reais.
- **O backfill não pode fechar linhas com assinaturas inventadas.** Quem já assinou em
  papel fica em `arquivado_papel`: sem assinatura, sem PDF, sem hash. Há um teste a
  garantir que continua assim — é a única parte disto onde um atalho seria falsificação.
