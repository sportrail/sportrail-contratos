# Sportrail — Motor de Contratos e PDF

Serviço **sem estado** que hidrata o contrato de formação com as cláusulas
jurídicas da Sportrail e renderiza HTML → PDF com o WeasyPrint.

Recebe dados, devolve documentos. Não escreve na base de dados, não guarda
ficheiros, não tem sessões nem utilizadores.

> ⚠️ **Aviso legal.** O texto das cláusulas em `core/clausulas.py` é um
> **rascunho de andaime** (blocos marcados `[JURISTA]`). Substitui-o pelas
> cláusulas validadas antes de qualquer uso real. Não é aconselhamento
> jurídico — valida a conformidade com quem trata da parte jurídica/DGERT.

---

## Onde está o resto

Lotes, formandos, tokens, a página de assinatura, o upload do Excel e os PDF
arquivados vivem no **`sportrail-dashboard`**. Este repo é só a parte que
precisa de Python.

A divisão tem uma razão: o texto jurídico tem de ter **uma fonte só**.
Reescrevê-lo em TypeScript para o dashboard o mostrar criava uma segunda
versão para divergir em silêncio, e depois um contrato assinado com um texto e
uma página a mostrar outro. O estado não tem esse problema, por isso vive onde
as tabelas estão.

Até 18 set 2026 esta app também tinha estado — mas contra um schema que nunca
chegou a ser aplicado, e por isso estava morta há meses sem dar erro. Ver
`tasks/lessons.md`.

---

## Endpoints

Todos protegidos por `PDF_API_TOKEN` (header `x-api-token`), exceto o
`/health`. **Falham fechados**: sem o segredo configurado respondem 503.

### `POST /api/contrato-preview`
O contrato por assinar, para o formando ler.
```json
{ "curso": {...}, "formando": {...}, "tipo": "B2C" }
→ { "html": "...", "consentimento": "Declaro que li e aceito..." }
```

### `POST /api/gerar-contrato`
O contrato assinado, com trilho de auditoria.
```json
{ "curso": {...}, "formando": {...}, "tipo": "B2C",
  "assinatura": "data:image/png;base64,...", "ip": "1.2.3.4" }
→ { "pdf_base64": "...", "hash": "...", "doc_id": "...", "data": "...", "tz": "..." }
```

### `POST /api/render-pdf`
Motor genérico, para os documentos do dossier (templates no dashboard).
```json
{ "html": "<html>...</html>" }
→ { "pdf_base64": "...", "hash": "...", "doc_id": "...", "data": "...", "tz": "..." }
```
O HTML vem de fora e **não é de confiar**: corre isolado, sem acesso ao disco
nem à rede, e recusa acima de 2 MB (→ 413).

### `GET /health`
Health check do Render. Aberto de propósito.

---

## Correr

```bash
make setup     # cria venv e instala dependências
make run       # http://127.0.0.1:8000
make verify    # smoke test — antes de dares algo por feito
```

O `weasyprint` precisa de Pango/Cairo:
`apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0`
(no macOS, `brew install pango gdk-pixbuf libffi`). Se o `import weasyprint`
falhar, é quase sempre isto.

**Configuração:** uma variável, `PDF_API_TOKEN`. Copia `.env.example` para
`.env`. Tem de ser igual ao `CONTRATOS_PDF_TOKEN` do dashboard.

---

## Variantes de contrato

- **B2C** (formando particular = consumidor): cláusula de **livre resolução de
  14 dias** (DL 24/2014) + anexo com formulário de resolução. O consentimento
  na assinatura é o **pedido expresso** do art. 4.º para iniciar a formação
  antes dos 14 dias.
- **B2B** (empresa/clube adquirente): sem livre resolução nem anexo.

Quem escolhe é o dashboard; aqui recebe-se `tipo` e obedece-se.

---

## Deploy

Render (free), Frankfurt, Docker: `https://sportrail-contratos.onrender.com`.
`render.yaml` + `Dockerfile`. Adormece após ~15 min e o 1.º pedido leva ~30 s
a acordar — quem chama tem de tolerar isso.
