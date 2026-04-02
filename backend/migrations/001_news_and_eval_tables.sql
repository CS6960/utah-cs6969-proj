-- Migration 001: News articles corpus and evaluation runs
-- Used for reproducible evaluation of agent quality across development stages.

-- News articles table: stores news for the evaluation window (March 24-31, 2026).
-- The `relevant` flag enables mixing related and unrelated articles to test
-- whether the agent can distinguish signal from noise.
create table if not exists news_articles (
    id uuid primary key default gen_random_uuid(),
    ticker text not null,
    headline text not null,
    body text not null,
    source text,
    published_at timestamptz not null,
    relevant boolean not null default true,
    tags text[] default '{}',
    created_at timestamptz default now()
);

create index if not exists idx_news_articles_ticker on news_articles (ticker);
create index if not exists idx_news_articles_published on news_articles (published_at);
create index if not exists idx_news_articles_relevant on news_articles (relevant);

-- Evaluation runs table: stores agent responses to preset questions at each
-- development stage so we can compare quality over time.
create table if not exists eval_runs (
    id uuid primary key default gen_random_uuid(),
    stage text not null,             -- e.g. 'baseline', 'rag_reports', 'news_agent', 'critic'
    question text not null,          -- the preset question
    response text not null,          -- agent's full response
    tools_called text[] default '{}',
    groundedness integer,            -- 1-5 score
    completeness integer,            -- 1-5 score
    actionability integer,           -- 1-5 score
    notes text,
    created_at timestamptz default now()
);

create index if not exists idx_eval_runs_stage on eval_runs (stage);
