# Evaluation

This document describes the evaluation framework used to measure Meridian's agent quality across development stages.

## Overview

Meridian uses a staged evaluation approach: the same set of preset questions is run against the system at each development milestone, responses are scored on a fixed rubric, and results are compared across stages to quantify improvement.

The framework is designed for reproducibility. News articles are stored in the database so the same corpus is used across all evaluations, and noise articles are mixed in to test the agent's ability to filter irrelevant context.

## Evaluation Window

**March 24–31, 2026** was selected as the evaluation window because it provides high news density across all 8 portfolio tickers and clear cross-sector dynamics.

### Macro Context

The US-Iran war dominated financial markets during this period:

- US/Israel struck Iran's energy infrastructure on Feb 28, 2026
- Iran closed the Strait of Hormuz on March 4, disrupting 20% of global oil supply
- Brent crude surged 57% in March, past $120/bbl
- S&P 500 fell 6.8% in March, worst monthly decline since Dec 2022
- Dow entered correction on March 27
- Late-month rally on de-escalation hopes (March 31: S&P +2.91%)

### Daily Index Performance

| Date     | S&P 500         | Nasdaq             | Driver                       |
|----------|-----------------|--------------------|-----------------------------|
| Mon 3/24 | 6,556           | 21,762 (-0.84%)    | Iran tensions resurfaced     |
| Tue 3/25 | 6,592 (+0.54%)  | 21,930 (+0.77%)    | Ceasefire hopes              |
| Wed 3/26 | 6,477 (-1.74%)  | 21,408 (-2.38%)    | Oil spikes, yields rise      |
| Thu 3/27 | 6,369 (-1.67%)  | 20,948 (-2.15%)    | Dow enters correction        |
| Mon 3/31 | 6,529 (+2.91%)  | —                  | De-escalation hopes          |

### Per-Ticker Impact

| Ticker | Role             | Iran War Impact |
|--------|------------------|-----------------|
| XOM    | Energy hedge     | +42% YTD on crude surge. Dropped 5% on de-escalation talks. |
| JPM    | Financial ballast| Flight-to-quality winner. Led S&P gainers on risk-off days. 17% ROTCE. |
| LLY    | Healthcare growth| Defensive anchor. GLP-1 demand recession-proof. Analyst targets up to $1,300. |
| AAPL   | Large-cap core   | On IRGC retaliatory strike target list. Supply chain concern. |
| NVDA   | AI/momentum      | On IRGC target list. TSMC manufacturing dependency. |
| MSFT   | AI platform      | On IRGC list but cloud/software more insulated. |
| GOOGL  | Cash-rich, ads   | On IRGC list. Ad cyclicality risk as macro deteriorates. |
| AMZN   | Consumer + cloud | Consumer spending slowdown fears. AWS partially hedges. |

## Preset Questions

The chat UI exposes 4 portfolio-level preset questions. These are used as the fixed evaluation inputs:

1. "What is my biggest portfolio risk?"
2. "Am I diversified enough?"
3. "Which holdings look strongest?"
4. "Where should new cash go?"

### Ground Truth Answers

For the March 24–31 window, the expected answers are:

**"What is my biggest portfolio risk?"**
Iran war escalation. 5 of 8 holdings (AAPL, NVDA, MSFT, GOOGL, AMZN) are tech companies named on the IRGC retaliatory strike target list. The oil shock from the Strait of Hormuz closure is driving inflation fears and broad market selloff. The portfolio's tech-heavy tilt amplifies exposure to geopolitical risk.

**"Am I diversified enough?"**
The portfolio is tech-concentrated (5 of 8 positions), but the 3 non-tech holdings (JPM, LLY, XOM) proved their diversification value. JPM and LLY acted as flight-to-quality defensive anchors on risk-off days. XOM benefited directly from the crude oil surge (+42% YTD). The diversification that exists is working, but the tech tilt means the portfolio is net-negative during the crisis.

**"Which holdings look strongest?"**
XOM (+42% YTD on crude surge), JPM (flight-to-quality winner, 17% ROTCE, 14x P/E), and LLY (recession-resistant GLP-1 demand, institutional accumulation). All 5 tech holdings are under pressure from the same geopolitical threat.

**"Where should new cash go?"**
Defensives: JPM (valuation sanctuary at 14x P/E) and LLY (secular growth immune to geopolitical cycle). XOM if the Iran conflict persists and oil stays elevated. Avoid adding to tech positions while the IRGC threat and broad risk-off sentiment persist.

## Development Stages

Each stage represents a development milestone. The system is evaluated after each stage is implemented.

| Stage          | What Changes                                                 |
|----------------|--------------------------------------------------------------|
| `baseline`     | Advisor agent with DuckDuckGo, Yahoo News, stock price tools |
| `rag_reports`  | + SEC filing retrieval via tree-RAG                          |
| `news_agent`   | + Dedicated news/sentiment agent with stored news corpus     |
| `critic`       | + Adversarial critic agent that challenges recommendations   |

## Scoring Rubric

Each response is scored 1–5 on three dimensions by an LLM judge.

### Groundedness (1–5)

Does the response cite real, specific data rather than generic advice?

| Score | Criteria |
|-------|----------|
| 1     | Pure generic advice, no data cited |
| 2     | Mentions tickers but no specific data points |
| 3     | Cites some real data (prices, percentages) but misses key facts |
| 4     | Cites multiple real data points, mostly accurate |
| 5     | Fully grounded in real data with accurate citations |

### Completeness (1–5)

Does it cover the key factors from the ground truth?

| Score | Criteria |
|-------|----------|
| 1     | Misses all major factors |
| 2     | Covers 1 factor, misses the rest |
| 3     | Covers 2–3 factors but misses important context |
| 4     | Covers most factors, minor gaps |
| 5     | Covers all key factors from ground truth |

### Actionability (1–5)

Does it give specific, usable advice?

| Score | Criteria |
|-------|----------|
| 1     | "Diversify more" with no specifics |
| 2     | Names tickers but no direction (buy/sell/hold) |
| 3     | Gives direction for some holdings |
| 4     | Specific recommendations with reasoning for most holdings |
| 5     | Concrete recommendations with reasoning and risk context |

## Scoring Method

### Primary: LLM-as-Judge

Automated scoring using the same LLM (Qwen 3.5-122B via NVIDIA API). The judge receives:

- The preset question
- The ground truth reference answer
- The agent's response

It returns integer scores for each dimension plus a brief explanation. The prompt is defined in `script/run_eval.py:JUDGE_PROMPT`.

### Secondary: Human Review

Manual spot-check of scores and responses, especially for edge cases where the LLM judge may disagree with human intuition. Disagreements are recorded in the `eval_runs.notes` field.

## News Corpus

The news corpus is stored in the `news_articles` Supabase table and contains two categories of articles.

### Relevant Articles

Real news articles from the evaluation window, fetched via Yahoo Finance for each of the 8 portfolio tickers. These are tagged `relevant = true`. The agent should surface and cite these when answering questions.

### Noise Articles

Unrelated articles mixed in to test whether the agent can distinguish signal from noise. Tagged `relevant = false`. Two types:

- **Off-topic**: articles about unrelated domains (space, sports, agriculture) with `ticker = "NONE"`
- **Not-in-portfolio**: articles about real companies not held in the portfolio (TSLA, PFE) that could plausibly distract the agent

A good agent ignores noise. A weak agent cites irrelevant articles or lets them dilute the quality of relevant context.

The noise ratio starts at ~5 articles and can be increased in later stages to stress-test filtering.

## Database Schema

### `news_articles`

| Column       | Type         | Description |
|--------------|-------------|-------------|
| id           | uuid (PK)   | Auto-generated |
| ticker       | text        | Stock ticker or "NONE" for off-topic noise |
| headline     | text        | Article headline |
| body         | text        | Article body/summary |
| source       | text        | Publisher name |
| published_at | timestamptz | Publication timestamp |
| relevant     | boolean     | True for signal, false for noise |
| tags         | text[]      | Metadata tags for filtering |
| created_at   | timestamptz | Insert timestamp |

### `eval_runs`

| Column        | Type         | Description |
|---------------|-------------|-------------|
| id            | uuid (PK)   | Auto-generated |
| stage         | text        | Development stage identifier |
| question      | text        | The preset question asked |
| response      | text        | Agent's full response |
| tools_called  | text[]      | Tools the agent invoked |
| groundedness  | integer     | 1–5 score |
| completeness  | integer     | 1–5 score |
| actionability | integer     | 1–5 score |
| notes         | text        | Judge explanation or human notes |
| created_at    | timestamptz | Evaluation timestamp |

## Running Evaluations

### Prerequisites

1. Apply the migration: run `backend/migrations/001_news_and_eval_tables.sql` in the Supabase SQL editor
2. Seed news articles: `python script/seed_news.py`
3. Seed noise articles: `python script/seed_news.py --noise`
4. Start the backend: `cd backend && python app.py`

### Record a Stage

```bash
python script/run_eval.py --stage baseline --score
```

The `--score` flag enables LLM-as-judge scoring. Without it, responses are stored but not scored.

### Compare Stages

```bash
python script/run_eval.py --report
```

Prints a comparison table across all recorded stages:

```
Stage                Ground.  Compl.   Action.  Avg
----------------------------------------------------
baseline             1.0      1.0      1.0      1.0
rag_reports          ...      ...      ...      ...
news_agent           ...      ...      ...      ...
critic               ...      ...      ...      ...
```

### Seed News Options

```bash
python script/seed_news.py                   # fetch for all 8 tickers
python script/seed_news.py --ticker NVDA     # single ticker
python script/seed_news.py --noise           # insert noise articles only
python script/seed_news.py --dry-run         # preview without inserting
python script/seed_news.py --source ddg      # use DuckDuckGo instead of Yahoo Finance
```

## Baseline Results

The baseline evaluation (advisor agent with no news corpus integration) scored **1.0 across all dimensions**. The agent failed to use its available tools and instead asked the user for portfolio data it already had access to, producing generic non-answers.

This establishes the floor for measuring improvement.

## Files

| File | Purpose |
|------|---------|
| `docs/09-EVALUATION.md` | This document |
| `backend/migrations/001_news_and_eval_tables.sql` | Supabase schema for news + eval tables |
| `script/seed_news.py` | Fetch and insert news articles into the corpus |
| `script/run_eval.py` | Run evaluations, score with LLM judge, print reports |
| `backend/portfolio.py` | Static portfolio definition (8 holdings) |

## Sources

- [CNBC: Dow tumbles, enters correction (March 27, 2026)](https://www.cnbc.com/2026/03/26/stock-market-today-live-updates.html)
- [CNN: Dow closes in correction, oil at war highs](https://www.cnn.com/2026/03/27/investing/us-stocks-iran)
- [CNBC: Iran IRGC threatens NVDA, AAPL](https://www.cnbc.com/2026/04/01/iran-irgc-nvidia-appple-attack-threat.html)
- [Flight to Quality: JPM and LLY as defensive anchors](https://markets.financialcontent.com/stocks/article/marketminute-2026-3-13-flight-to-quality-jpmorgan-and-eli-lilly-emerge-as-defensive-anchors-amid-geopolitical-storm)
- [XOM Iran war price impact](https://intellectia.ai/blog/xom-stock-price-prediction-2026-us-iran-war-oil-price)
- [CNBC: Oil prices and Hormuz crisis](https://www.cnbc.com/2026/03/28/oil-gas-prices-iran-war-hormuz.html)
