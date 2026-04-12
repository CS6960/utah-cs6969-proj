-- Migration 003: Entity-relationship graph for cross-sector causal reasoning.
-- Extracted from the news corpus by script/build_graph.py; queried by the
-- Strategist's request_graph tool at inference time.

create table if not exists entity_relationships (
    id uuid primary key default gen_random_uuid(),
    source_entity text not null,
    source_type text,
    target_entity text not null,
    target_type text,
    relationship text not null,
    evidence text,
    article_id uuid references news_articles(id),
    created_at timestamptz default now()
);

create index if not exists idx_er_source on entity_relationships(source_entity);
create index if not exists idx_er_target on entity_relationships(target_entity);
create unique index if not exists idx_er_unique on entity_relationships(source_entity, relationship, target_entity);
