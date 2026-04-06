# News Corpus

This document describes the `news_articles` table, the seeding pipeline, and the role of the news corpus in the evaluation framework and future news/sentiment agent.

## Purpose

The news corpus serves two functions:

1. **Evaluation**: provides a fixed set of articles for reproducible agent testing. The same corpus is used across all development stages so improvements can be attributed to system changes, not data differences.
2. **News agent**: the planned news/sentiment agent will query this table to retrieve relevant articles for a given ticker and time window, enabling temporally grounded answers.

## Schema

Table: `news_articles` in Supabase.

Migration: `backend/supabase/migrations/001_news_and_eval_tables.sql`

| Column       | Type         | Description |
|--------------|-------------|-------------|
| `id`         | uuid (PK)   | Auto-generated primary key |
| `ticker`     | text        | Stock ticker (e.g. `AAPL`) or `NONE` for off-topic noise |
| `headline`   | text        | Article headline |
| `body`       | text        | Article body or summary text |
| `source`     | text        | Publisher name (e.g. `Reuters`, `CNBC`) |
| `published_at` | timestamptz | When the article was published |
| `relevant`   | boolean     | `true` for real portfolio-relevant news, `false` for noise |
| `tags`       | text[]      | Metadata tags for filtering and categorization |
| `created_at` | timestamptz | Row insertion timestamp |

### Indexes

- `idx_news_articles_ticker` on `ticker` — fast lookup by stock
- `idx_news_articles_published` on `published_at` — time-range queries
- `idx_news_articles_relevant` on `relevant` — separate signal from noise

## Article Categories

### Relevant Articles (`relevant = true`)

Real news articles about portfolio holdings fetched from Yahoo Finance or DuckDuckGo. Tagged with the ticker symbol and source method (e.g. `["NVDA", "auto-fetched"]`).

These are the articles the agent should retrieve and cite. In the evaluation window (March 24–31, 2026), relevant articles cover the Iran war's impact on each holding: IRGC threats to tech companies, oil price surge, flight-to-quality dynamics, etc.

### Noise Articles (`relevant = false`)

Unrelated articles mixed into the corpus to test whether the agent can distinguish signal from noise. Three subcategories:

| Type | Ticker | Example | What it tests |
|------|--------|---------|---------------|
| Off-topic | `NONE` | "NASA Confirms Water Ice Deposits on Lunar South Pole" | Can the agent ignore completely irrelevant content? |
| Off-topic | `NONE` | "FIFA Announces Expanded Club World Cup Format" | Same — zero financial relevance |
| Off-topic | `NONE` | "Record Avocado Harvest Pushes Prices to Five-Year Low" | Commodity news, but wrong commodity |
| Not-in-portfolio | `TSLA` | "Tesla Unveils Refreshed Model Y" | Real financial news for a stock not in the portfolio |
| Not-in-portfolio | `PFE` | "Pfizer Reports Positive Phase 3 Results for RSV Vaccine" | Healthcare news, but for a holding we don't own (we hold LLY) |

A well-performing agent should:
- Retrieve and cite relevant articles when answering portfolio questions
- Ignore off-topic noise entirely
- Recognize that TSLA and PFE are not portfolio holdings and avoid citing them as if they were

## Current Corpus

As of the initial seed:

| Ticker | Count | Type |
|--------|-------|------|
| AAPL   | 10    | Relevant |
| AMZN   | 10    | Relevant |
| GOOGL  | 10    | Relevant |
| JPM    | 10    | Relevant |
| LLY    | 10    | Relevant |
| MSFT   | 10    | Relevant |
| NVDA   | 10    | Relevant |
| XOM    | 10    | Relevant |
| NONE   | 6     | Noise (off-topic) |
| TSLA   | 2     | Noise (not-in-portfolio) |
| PFE    | 2     | Noise (not-in-portfolio) |
| **Total** | **90** | **80 relevant + 10 noise** |

## Seeding Pipeline

Script: `script/seed_news.py`

### Fetch Real News

```bash
python script/seed_news.py                   # all 8 portfolio tickers via Yahoo Finance
python script/seed_news.py --ticker NVDA     # single ticker
python script/seed_news.py --source ddg      # use DuckDuckGo instead
python script/seed_news.py --dry-run         # preview without inserting
```

The script uses `yfinance` to fetch recent news for each ticker. Articles are inserted with `relevant = true` and tagged with the ticker and fetch method.

### Insert Noise

```bash
python script/seed_news.py --noise
```

Inserts the predefined noise articles from `NOISE_ARTICLES` in the script. These are hardcoded to ensure consistency across environments.

### Adding Custom Articles

To add articles manually (e.g. specific articles from the evaluation window):

```python
from supabase import create_client

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
sb.table("news_articles").insert({
    "ticker": "NVDA",
    "headline": "Iran IRGC Names NVIDIA as Potential Target",
    "body": "Iran's Revolutionary Guard Corps listed 18 US tech companies...",
    "source": "CNBC",
    "published_at": "2026-03-28T14:00:00+00:00",
    "relevant": True,
    "tags": ["NVDA", "iran", "geopolitical", "manual"],
}).execute()
```

## Querying the Corpus

### All articles for a ticker

```python
sb.table("news_articles").select("*").eq("ticker", "NVDA").order("published_at").execute()
```

### Only relevant articles in the evaluation window

```python
sb.table("news_articles") \
    .select("*") \
    .eq("relevant", True) \
    .gte("published_at", "2026-03-24T00:00:00+00:00") \
    .lte("published_at", "2026-03-31T23:59:59+00:00") \
    .order("published_at") \
    .execute()
```

### All noise articles

```python
sb.table("news_articles").select("*").eq("relevant", False).execute()
```

### REST API (curl)

```bash
# All articles for AAPL
curl -H "apikey: $SUPABASE_KEY" \
  "$SUPABASE_URL/rest/v1/news_articles?ticker=eq.AAPL&order=published_at"

# Noise articles only
curl -H "apikey: $SUPABASE_KEY" \
  "$SUPABASE_URL/rest/v1/news_articles?relevant=eq.false"
```

## Integration with the News Agent

The planned news/sentiment agent will use this table as its primary data source. The expected workflow:

1. User asks a portfolio question (e.g. "What is my biggest portfolio risk?")
2. The planner routes the query to the news agent
3. The news agent queries `news_articles` for the user's holdings within the relevant time window
4. It summarizes sentiment and key events from the retrieved articles
5. The summary is passed to the advisor agent as additional context for generating the response

This design ensures the agent's news awareness is grounded in stored, auditable data rather than live web searches that vary between runs.

## Files

| File | Purpose |
|------|---------|
| `docs/10-NEWS-CORPUS.md` | This document |
| `backend/supabase/migrations/001_news_and_eval_tables.sql` | Table schema |
| `script/seed_news.py` | Fetch and insert articles |
