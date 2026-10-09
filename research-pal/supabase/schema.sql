-- Research Pal: Supabase schema (Postgres + pgvector).
-- Run it one time: Supabase dashboard > SQL Editor > New query > paste > Run.
-- Every row belongs to one user (user_id = the Google login). The backend uses the service key and
-- always filters by user_id. Row Level Security (RLS) is on, so the public API key sees nothing.

create extension if not exists vector;

-- ---------- tables (same fields as the SQLite version) ----------
create table if not exists papers (
  id          text primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  filename    text, title text, status text, error text, purpose text,
  focus       text default '',
  n_pages     integer default 0,
  created_at  double precision, updated_at double precision
);

create table if not exists pages (
  user_id  uuid not null references auth.users(id) on delete cascade,
  paper_id text not null references papers(id) on delete cascade,
  page     integer not null,
  text     text,
  primary key (paper_id, page)
);

create table if not exists cards (
  paper_id   text primary key references papers(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  data       jsonb,
  updated_at double precision
);

create table if not exists extra_cards (
  id         text primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  paper_id   text references papers(id) on delete cascade,
  focus text, purpose text, status text, error text,
  data       jsonb,
  created_at double precision, updated_at double precision
);

create table if not exists glossary (
  id         text primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  term text, explanation text, source text,
  paper_id   text,                       -- no foreign key: a term can have no paper (empty text)
  page       integer default 0,
  created_at double precision
);

create table if not exists ai_log (
  id       bigint generated always as identity primary key,
  user_id  uuid not null references auth.users(id) on delete cascade,
  time     double precision, feature text,
  paper_id text, provider text, model text
);

create table if not exists features (
  user_id uuid not null references auth.users(id) on delete cascade,
  name    text not null,
  enabled boolean not null,
  primary key (user_id, name)
);

create table if not exists settings (
  user_id uuid not null references auth.users(id) on delete cascade,
  key     text not null,
  value   text,
  primary key (user_id, key)
);

create table if not exists llm_cache (
  user_id    uuid not null references auth.users(id) on delete cascade,
  key        text not null,
  tag text, provider text, model text,
  response   jsonb,
  created_at double precision,
  primary key (user_id, key)
);

-- ---------- vectors (768 values = Gemini embedding, GEMINI_EMBED_DIM) ----------
create table if not exists chunks (
  id        text primary key,                      -- "<paper_id>:<chunk id>"
  user_id   uuid not null references auth.users(id) on delete cascade,
  paper_id  text not null references papers(id) on delete cascade,
  page integer, idx integer, document text,
  embedding vector(768)
);
create index if not exists chunks_embedding_idx on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_paper_idx on chunks(user_id, paper_id);

create table if not exists card_vectors (
  paper_id  text primary key references papers(id) on delete cascade,
  user_id   uuid not null references auth.users(id) on delete cascade,
  document  text,
  embedding vector(768)
);

-- ---------- search function (cosine distance, one user, optional paper) ----------
create or replace function match_chunks(
  p_user uuid, p_embedding vector(768), p_count int, p_paper text default null
) returns table (paper_id text, page int, idx int, document text, distance double precision)
language sql stable as $$
  select paper_id, page, idx, document, (embedding <=> p_embedding)::double precision
  from chunks
  where user_id = p_user and (p_paper is null or paper_id = p_paper)
  order by embedding <=> p_embedding
  limit p_count;
$$;

-- ---------- indexes ----------
create index if not exists papers_user_idx on papers(user_id, created_at desc);
create index if not exists extra_cards_paper_idx on extra_cards(user_id, paper_id);
create index if not exists glossary_user_idx on glossary(user_id);
create index if not exists ai_log_user_idx on ai_log(user_id, time desc);

-- ---------- security: RLS on, and a user can only see his own rows ----------
do $$
declare t text;
begin
  foreach t in array array['papers','pages','cards','extra_cards','glossary','ai_log','features','settings','llm_cache','chunks','card_vectors']
  loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists own_rows on %I', t);
    execute format('create policy own_rows on %I for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid())', t);
  end loop;
end $$;

-- ---------- private bucket for the PDF files (path: <user_id>/<paper_id>.pdf) ----------
insert into storage.buckets (id, name, public) values ('pdfs', 'pdfs', false) on conflict (id) do nothing;
