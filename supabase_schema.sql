-- ============================================================================
-- Sportrail — Contratos de Formação: estado em Postgres
-- ============================================================================
-- Corre isto UMA VEZ no SQL Editor do Supabase (mesmo projeto do dashboard).
--
-- PORQUÊ: o estado vivia em data/state.json e os PDFs em data/pdfs/. O tier
-- grátis do Render adormece o serviço e tem filesystem efémero — cada restart
-- apagava os tokens de assinatura já enviados aos formandos. Aqui não.
--
-- ACESSO: a app liga-se com a SERVICE ROLE KEY (só servidor). Por isso o RLS
-- fica ligado SEM políticas: o service role passa à frente do RLS, e as roles
-- `anon`/`authenticated` — as que o dashboard usa no browser — não conseguem
-- ler nada. Estas tabelas têm dados pessoais de terceiros (nome, NIF, morada,
-- email, IP), por isso o default tem de ser fechado.
-- ============================================================================

create table if not exists contract_batches (
  id            text primary key,          -- lote_id (token_urlsafe(6))
  curso         jsonb not null,            -- nome, modalidade, duracao, datas
  tipo_default  text not null default 'B2C',
  criado_em     timestamptz not null default now()
);

create table if not exists contract_signers (
  token          text primary key,         -- token_urlsafe(16), vai no link
  batch_id       text not null references contract_batches(id) on delete cascade,

  nome           text not null,
  nif            text,
  email          text not null,
  valor_pago     text,
  morada         text,
  tipo_contrato  text not null,            -- B2C | B2B

  estado         text not null default 'pendente',   -- pendente | assinado
  assinado_em    text,                     -- string legível construída na auditoria
  ip             text,
  hash           text,                     -- SHA-256 do conteúdo lógico
  doc_id         text,
  pdf_path       text,                     -- caminho no bucket `contratos`
  drive_file_id  text,

  ordem          int not null default 0,   -- preserva a ordem do Excel
  criado_em      timestamptz not null default now()
);

create index if not exists contract_signers_batch_idx
  on contract_signers (batch_id, ordem);

alter table contract_batches enable row level security;
alter table contract_signers enable row level security;

-- Sem políticas de propósito: só a service role (servidor) toca nestas tabelas.

-- ============================================================================
-- STORAGE
-- ============================================================================
-- Cria o bucket `contratos` como **Private** na UI (Storage → New bucket).
-- Não são precisas políticas: a app acede pela service role, e os PDFs são
-- servidos pela própria app em /pdf/<token>, nunca por URL direto do bucket.
-- ============================================================================

-- ============================================================================
-- MIGRAÇÃO — Sessão 8: export real do WooCommerce + backfill do histórico
-- ============================================================================
-- Corre isto UMA VEZ, depois do bloco acima (é idempotente, dá para repetir).
--
-- PORQUÊ:
--  * A minuta aprovada pela DGERT identifica o formando pelo DOCUMENTO DE
--    IDENTIFICAÇÃO (n.º + validade) e pela residência (morada, concelho,
--    distrito) — não pelo NIF. Nenhuma dessas colunas existia.
--  * O export do WooCommerce traz ainda `cedula` (treinador) e `clube`, que
--    são os dados que tornam a ficha do formando útil à coordenação.
--  * `origem` distingue um lote normal de um lote importado do histórico.
-- ============================================================================

alter table contract_signers
  add column if not exists doc_identificacao  text,   -- CC no export
  add column if not exists validade_documento text,
  add column if not exists cedula             text,   -- cédula de treinador
  add column if not exists clube              text,
  add column if not exists concelho           text,
  add column if not exists distrito           text;

alter table contract_batches
  add column if not exists origem text not null default 'normal';
                                          -- 'normal' | 'backfill'

-- `estado` passa a aceitar 'arquivado_papel': formação antiga cujo contrato foi
-- assinado em papel. Fica registada SEM assinatura e SEM PDF — inventar uma
-- assinatura para fechar a linha era falsificar o documento.
-- (A coluna é `text` livre, não há enum a alterar; fica aqui por ser onde se
--  procura o significado dos estados.)
