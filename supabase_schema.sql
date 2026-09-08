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
