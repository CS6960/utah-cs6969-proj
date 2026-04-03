# Supabase Free-Tier Rules

This project runs on **Supabase Free (Nano) tier**. All backend and script code
must respect the constraints below. A pre-commit linter
(`scripts/check_supabase_rules.py`) enforces the machine-checkable subset.

## Hard Limits (free tier, April 2026)

| Resource | Limit |
|---|---|
| Database size | 500 MB (read-only if exceeded) |
| Statement timeout (anon) | **3 seconds** |
| Statement timeout (authenticated) | 8 seconds |
| Direct connections | 60 |
| Pooled connections (Supavisor) | 200 |
| API response rows | 1 000 default max |
| Egress bandwidth | 10 GB / month |
| Edge function invocations | 500 000 / month |
| Compute | Shared CPU, 0.5 GB RAM |
| Auto-pause | After 7 days inactivity |

## Coding Rules

### SB001 — Always use `.limit()` on read queries

Every `.table().select().execute()` chain **must** include `.limit(N)` unless the
table is known-small (see `SMALL_TABLES` in the linter). Unbounded result sets
risk the 3-second statement timeout and transfer excessive data.

```python
# BAD — unbounded
supabase.table("eval_runs").select("*").execute()

# GOOD
supabase.table("eval_runs").select("stage, question, groundedness").limit(100).execute()
```

**Exceptions:** `portfolio_positions`, `stocks`, `portfolio_cash` are whitelisted
because they have < 50 rows by design.

### SB002 — Never select the `embedding` column over the API

Embeddings are 3 072-float vectors (~24 KB JSON each). Fetching N rows with
embeddings transfers `N × 24 KB`. For a 600-node document that is **14 MB** —
enough to trigger statement timeouts and blow through egress.

```python
# BAD — pulls embeddings client-side
supabase.table("document_tree_nodes") \
    .select("id, text, embedding") \
    .eq("file_title", title).execute()

# GOOD — server-side similarity via RPC
supabase.rpc("match_document_tree_nodes", {
    "query_embedding": vec,
    "match_threshold": 0.1,
    "match_count": 5,
    "match_depth": 2,
}).execute()
```

### SB003 — No Supabase queries inside loops

Querying inside a `for` / `while` loop creates N+1 patterns that multiply
request count and latency. Fetch all needed data before the loop, or use a
single query with `.in_()` / `.or_()`.

```python
# BAD — 8 queries for 8 tickers
for ticker in tickers:
    supabase.table("stock_prices").select("close").eq("stock_symbol", ticker).limit(1).execute()

# GOOD — 1 query
supabase.table("stock_prices").select("stock_symbol, close") \
    .in_("stock_symbol", tickers).eq("trading_date", date).execute()
```

### SB004 — Use module-level Supabase clients

`create_client()` opens an HTTP session. Calling it per-request wastes
connection slots (60 direct max). Create the client once at module level.

```python
# BAD — inside every function
def get_data():
    sb = create_client(url, key)  # new session each time
    return sb.table("t").select("*").limit(10).execute()

# GOOD — module singleton
_sb = create_client(url, key)

def get_data():
    return _sb.table("t").select("*").limit(10).execute()
```

### SB005 — Batch inserts ≤ 50 rows

Large batch inserts can exceed the 3-second statement timeout or the request
body size limit. Keep batches at 50 rows max, especially for tables with
embeddings or large text columns.

```python
# BAD
supabase.table("nodes").insert(all_600_rows).execute()

# GOOD
BATCH = 50
for i in range(0, len(rows), BATCH):
    supabase.table("nodes").insert(rows[i:i+BATCH]).execute()
```

### SB006 — Never `.select("*")`

Selecting all columns pulls embeddings, metadata blobs, and other large fields.
Always list the specific columns you need.

```python
# BAD
supabase.table("eval_runs").select("*").execute()

# GOOD
supabase.table("eval_runs").select("stage, question, groundedness, completeness").limit(50).execute()
```

## Database-Side Rules

### Use RPC functions for heavy computation

Similarity search, tree traversal, and aggregations should run server-side
via Postgres functions (RPC). This avoids transferring intermediate data.

| Operation | RPC function |
|---|---|
| Semantic search | `match_document_tree_nodes` |
| Tree traversal | `traverse_document_tree_nodes` |

### Keep queries under 3 seconds

The anon role has a 3-second statement timeout. If a query risks exceeding this:
- Add indexes (especially on `file_title`, `node_type`, `stock_symbol`)
- Reduce result set size with `.limit()` and filters
- Move computation to an RPC function

### Monitor database size

At 500 MB the database goes read-only. Embeddings are the largest consumer.
Before adding a new 10-K filing (~600 nodes × 24 KB = 14 MB), check current
usage in the Supabase dashboard.

## Pre-Commit Enforcement

The linter runs automatically on `git commit` via `.git/hooks/pre-commit`.

**Manual run:**
```bash
python scripts/check_supabase_rules.py                          # scan all backend/script files
python scripts/check_supabase_rules.py backend/pipeline.py      # scan specific file
```

**Rules checked automatically:** SB001–SB006 (see script docstring for details).

**To suppress a false positive**, add `# noqa: SB0XX` on the line (not yet
implemented — document exceptions here until needed).

## Incident Log

| Date | Issue | Root Cause | Fix |
|---|---|---|---|
| 2026-04-03 | Pipeline times out, Supabase 522 | `retrieve_embedded_financial_report_info` fetched 600 rows with embeddings (~14 MB) | Switched to `match_document_tree_nodes` RPC |
| 2026-04-03 | Eval batch insert fails | Single insert of 4 rows with 10 KB+ response text | Changed to per-row insert |
| 2026-04-03 | Retriever agent causes statement timeouts | Agent makes 6 parallel `retrieve_embedded_financial_report_info` calls | Added `RETRIEVER_USE_AGENT` toggle, default off |
