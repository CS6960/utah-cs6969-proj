-- Migration 002: Extend eval_runs with temporal, relational, and noise metrics
-- Adds columns proposed in the evaluation methodology review to align the
-- scoring rubric with the paper's stated hypotheses (temporal precision,
-- relational recall) and to track noise-filtering quality.

-- New scoring dimensions (1-5, same scale as existing dimensions)
alter table eval_runs add column if not exists temporal_precision integer;
alter table eval_runs add column if not exists relational_recall  integer;

-- Noise citation tracking
alter table eval_runs add column if not exists noise_citations     text[] default '{}';
alter table eval_runs add column if not exists noise_citation_count integer default 0;
