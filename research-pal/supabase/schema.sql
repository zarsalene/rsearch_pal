-- Research Pal: setup of the Supabase project (multi-user mode). Run it one time:
-- Supabase dashboard > SQL Editor > New query > paste > Run.
--
-- How the data is kept: each user gets a schema of his own, "u_<user id without dashes>", with all the tables
-- (papers, pages, cards, the game, the thesis project, the settings, and the search vectors).
-- The backend makes the schema the first time the user signs in. The backend connects as the database owner and
-- selects the schema of the user of the request. A user can never reach the tables of another user, because the
-- tables are not shared: there is no table to filter wrongly.
-- The schemas are not in the list of the Supabase API ("exposed schemas"), so the browser cannot read them at all.
-- The page has only the anon key. All data goes through the backend.

create extension if not exists vector;

-- A private bucket for the PDF files. The path of a file is <user id>/<paper id>.pdf. Only the backend (service key) reads it.
insert into storage.buckets (id, name, public) values ('pdfs', 'pdfs', false) on conflict (id) do nothing;

-- Optional clean-up: an earlier version of this project kept the data of all users in shared tables of the "public" schema.
-- They are not used any more. If they exist and are empty, you can remove them:
--   drop table if exists public.chunks, public.card_vectors, public.llm_cache, public.settings, public.features, public.ai_log,
--     public.glossary, public.extra_cards, public.cards, public.pages, public.papers cascade;
--   drop function if exists public.match_chunks(uuid, vector, int, text);
