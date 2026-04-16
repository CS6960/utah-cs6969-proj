"""
Run evaluation: send preset questions to the agent and store responses.

Usage:
    python script/run_eval.py --stage baseline
    python script/run_eval.py --stage news_agent --score   # also run LLM-as-judge scoring
    python script/run_eval.py --report                      # print comparison across stages

Sends each preset question to the running backend, records the response,
and optionally scores it using an LLM judge against the ground truth.
Results are stored in the eval_runs Supabase table.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import time

import requests
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

DENVER_TZ = ZoneInfo("America/Denver")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("BASE_URL")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME") or os.getenv(
    "MODEL_NAME", "qwen/qwen3.5-122b-a10b"
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Portfolio and noise tickers
# ---------------------------------------------------------------------------

PORTFOLIO_TICKERS = {"AAPL", "MSFT", "JPM", "NVDA", "AMZN", "GOOGL", "LLY", "XOM"}
NOISE_TICKERS = {"TSLA", "PFE"}

# Also flag any well-known ticker that is not in the portfolio.  This list
# covers the noise articles seeded in the corpus; extend as needed.
NON_PORTFOLIO_TICKERS = NOISE_TICKERS | {
    "META",
    "NFLX",
    "BABA",
    "AMD",
    "INTC",
    "BA",
    "DIS",
    "UBER",
}

# ---------------------------------------------------------------------------
# Development stages (ordered for report output)
# ---------------------------------------------------------------------------

STAGES_ORDERED = [
    "baseline",
    "rag_reports",
    "news_agent",
    "graph",
    "critic",
]

# ---------------------------------------------------------------------------
# Preset questions
# ---------------------------------------------------------------------------

PRESET_QUESTIONS = [
    "What is my biggest portfolio risk?",
    "Am I diversified enough?",
    "Which holdings look strongest?",
    "Where should new cash go?",
]

# ---------------------------------------------------------------------------
# Ground truth answers (March 24-31, 2026 evaluation window)
# ---------------------------------------------------------------------------

GROUND_TRUTH = {
    "What is my biggest portfolio risk?": (
        "Iran war escalation is the dominant risk. 5 of 8 holdings (AAPL, NVDA, MSFT, GOOGL, AMZN) "
        "are tech companies named on the IRGC retaliatory strike target list. The oil shock from "
        "the Strait of Hormuz closure is driving inflation fears and broad market selloff. "
        "The portfolio's tech-heavy tilt amplifies exposure to geopolitical risk. "
        "The Dow entered correction on March 27 and the S&P 500 had its worst month since Dec 2022."
    ),
    "Am I diversified enough?": (
        "The portfolio is tech-concentrated (5 of 8 positions), but the 3 non-tech holdings "
        "(JPM, LLY, XOM) proved their diversification value during the week. JPM and LLY acted as "
        "flight-to-quality defensive anchors on risk-off days. XOM benefited directly from the crude "
        "oil surge (+42% YTD). The diversification that exists is working, but the tech tilt means "
        "the portfolio is net-negative during the Iran crisis."
    ),
    "Which holdings look strongest?": (
        "XOM is the strongest performer at +42% YTD driven by the crude oil surge from the Iran war. "
        "JPM is a flight-to-quality winner, leading S&P gainers on risk-off days with 17% ROTCE "
        "and trading at 14x P/E as a valuation sanctuary. LLY is the other defensive anchor with "
        "recession-resistant GLP-1 demand; JPM built a $2.93B stake and analyst targets reach $1,300. "
        "All 5 tech holdings are under pressure from the same geopolitical threat."
    ),
    "Where should new cash go?": (
        "Defensive positions: JPM (valuation sanctuary at 14x P/E, flight-to-quality beneficiary) "
        "and LLY (secular growth immune to geopolitical cycle, strong institutional accumulation). "
        "XOM if you believe the Iran conflict persists and oil stays elevated. "
        "Avoid adding to tech positions while the IRGC threat and broad risk-off sentiment persist."
    ),
}

# ---------------------------------------------------------------------------
# Temporal facts — key date-stamped facts the agent should cite
# The judge uses these to assess temporal precision.
# ---------------------------------------------------------------------------

TEMPORAL_FACTS = {
    "What is my biggest portfolio risk?": [
        "US/Israel struck Iran's energy infrastructure on Feb 28, 2026",
        "Iran closed the Strait of Hormuz on March 4, 2026",
        "Brent crude surged 57% in March 2026, past $120/bbl",
        "S&P 500 fell 6.8% in March 2026 — worst month since Dec 2022",
        "Dow entered correction on March 27, 2026",
        "IRGC named tech companies on retaliatory target list (late March 2026)",
        "March 31 de-escalation relief rally: S&P +2.91%",
    ],
    "Am I diversified enough?": [
        "XOM +42% YTD as of late March 2026 due to oil surge",
        "JPM led S&P gainers on risk-off days during March 24-31 week",
        "LLY acted as defensive anchor during March 2026 selloff",
        "S&P 500 down 6.8% in March 2026",
        "March 26-27 consecutive selloff days (-1.74%, -1.67%)",
    ],
    "Which holdings look strongest?": [
        "XOM +42% YTD driven by crude surge from Iran war (March 2026)",
        "JPM 17% ROTCE, 14x P/E — flight-to-quality during March selloff",
        "LLY analyst targets up to $1,300; JPM built $2.93B stake",
        "5 tech holdings under IRGC threat as of late March 2026",
    ],
    "Where should new cash go?": [
        "JPM at 14x P/E as of March 2026 — valuation sanctuary",
        "LLY institutional accumulation during March 2026 crisis",
        "XOM benefiting from oil staying above $120/bbl (March 2026)",
        "IRGC threat to tech companies ongoing as of March 31, 2026",
    ],
}

# ---------------------------------------------------------------------------
# Relational connections — cross-sector causal chains the agent should identify
# The judge uses these to assess relational recall.
# ---------------------------------------------------------------------------

RELATIONAL_CONNECTIONS = {
    "What is my biggest portfolio risk?": [
        "Iran conflict → Strait of Hormuz closure → oil price surge",
        "Oil shock → inflation fears → broad equity market selloff",
        "IRGC target list → simultaneous threat to 5 tech holdings (sector concentration risk)",
        "Tech concentration (5/8) → amplified portfolio exposure to single geopolitical event",
        "Oil surge → XOM benefits while tech sells off (inverse dynamic within portfolio)",
    ],
    "Am I diversified enough?": [
        "Iran conflict creates opposite effects within portfolio: XOM gains vs tech losses",
        "Flight-to-quality dynamic: risk-off days → money flows from tech into JPM and LLY",
        "Oil surge from Hormuz closure → direct XOM benefit (energy hedge working as designed)",
        "Tech sector correlation: all 5 tech names affected by same IRGC threat (diversification failure within tech)",
        "3 non-tech holdings (JPM, LLY, XOM) each hedge a different risk: "
        "financial stability, healthcare demand, energy prices",
    ],
    "Which holdings look strongest?": [
        "XOM strength is causally linked to Iran conflict → oil price surge",
        "JPM strength is causally linked to flight-to-quality flows during geopolitical crisis",
        "LLY strength is causally linked to recession-resistant healthcare demand (GLP-1)",
        "Tech weakness is collectively linked to IRGC threats and macro risk-off sentiment",
    ],
    "Where should new cash go?": [
        "JPM recommendation linked to flight-to-quality dynamic during ongoing geopolitical crisis",
        "LLY recommendation linked to secular healthcare demand being immune to geopolitical cycle",
        "XOM recommendation conditional on Iran conflict persistence → sustained oil prices",
        "Tech avoidance linked to IRGC threat + macro risk-off creating correlated downside across all 5 tech holdings",
    ],
}

# ---------------------------------------------------------------------------
# LLM Judge prompt — 5 dimensions
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """\
You are an evaluation judge for a financial advisor AI agent.

Score the agent's response against the ground truth reference answer on five dimensions.
Each score is 1-5 where 1=poor and 5=excellent.

**Groundedness** (1-5): Does the response cite real, specific data (prices, events, holdings) \
rather than generic advice? Does it avoid hallucinating facts?

**Completeness** (1-5): Does the response cover the key factors from the ground truth? \
Does it mention the relevant tickers, events, and dynamics?

**Actionability** (1-5): Does the response give specific, usable advice \
(e.g., "trim NVDA", "add to JPM") rather than vague platitudes?

**Temporal Precision** (1-5): Does the response cite facts from the correct time window \
(March 24-31, 2026)? Does it use date-specific data rather than outdated or undated claims? \
A score of 5 means the response references specific dates/weeks and the cited facts match \
the evaluation window. A score of 1 means no temporal grounding — the response could apply \
to any time period.

**Relational Recall** (1-5): Does the response identify cross-sector causal chains? \
For example, does it connect the Iran conflict to oil prices to XOM's gain, or link the \
IRGC threat list to correlated tech-sector weakness? A score of 5 means the response \
explicitly traces multi-hop cause-effect relationships across sectors. A score of 1 means \
it lists facts in isolation with no causal or relational connections.

Respond with ONLY a JSON object, no other text:
{{"groundedness": <int>, "completeness": <int>, "actionability": <int>, \
"temporal_precision": <int>, "relational_recall": <int>, "notes": "<brief explanation>"}}

--- QUESTION ---
{question}

--- GROUND TRUTH ---
{ground_truth}

--- TEMPORAL FACTS (date-stamped facts the agent should cite) ---
{temporal_facts}

--- RELATIONAL CONNECTIONS (cross-sector chains the agent should identify) ---
{relational_connections}

--- AGENT RESPONSE ---
{response}
"""


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)  # noqa: SB004


def query_agent(question: str) -> tuple[str, list[str]]:
    """Send a question to the backend agent and return (response, tools_called)."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/agent",
            json={"query": question, "role": "financial_advisor"},
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", ""), data.get("tools_called", [])
    except Exception as e:
        logger.error("Agent query failed: %s", e)
        return f"ERROR: {e}", []


def detect_noise_citations(response: str) -> list[str]:
    """Return non-portfolio tickers mentioned in the response."""
    # Normalise to uppercase for matching
    upper = response.upper()
    cited = []
    for ticker in sorted(NON_PORTFOLIO_TICKERS):
        # Match the ticker as a whole word to avoid false positives
        # (e.g. "DISABILITY" matching "DIS")
        if re.search(rf"\b{ticker}\b", upper):
            cited.append(ticker)
    return cited


_DISSENT_BLOCK_RE = re.compile(
    r"<!--\s*DISSENT_BLOCK_START_DO_NOT_SCORE\s*-->.*?(?:<!--\s*DISSENT_BLOCK_END\s*-->|\Z)",
    re.DOTALL,
)


def _strip_dissent_block(response: str) -> str:
    """Strip the dissent block from the agent response before judging.
    Phase 4 embeds the Critic's dissent inside data.result under an HTML-comment
    delimiter so the frontend can display it while the eval judge scores only the
    revised recommendation (v2). Leaving the dissent in the judge input makes the
    judge deduct points for perceived contradiction within one response.
    """
    stripped = _DISSENT_BLOCK_RE.sub("", response)
    return stripped.strip()


def score_response(question: str, response: str) -> dict:
    """Use the LLM as a judge to score the response against ground truth."""
    from openai import OpenAI

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    ground_truth = GROUND_TRUTH.get(question, "")
    temporal_facts = TEMPORAL_FACTS.get(question, [])
    relational_connections = RELATIONAL_CONNECTIONS.get(question, [])

    judge_input = JUDGE_PROMPT.format(
        question=question,
        ground_truth=ground_truth,
        temporal_facts="\n".join(f"- {f}" for f in temporal_facts),
        relational_connections="\n".join(f"- {c}" for c in relational_connections),
        response=_strip_dissent_block(response),
    )

    result = client.chat.completions.create(
        model=LLM_MODEL_NAME,
        messages=[{"role": "user", "content": judge_input}],
        temperature=0.1,
    )

    raw = result.choices[0].message.content.strip()

    # Extract JSON from response (handle markdown code blocks)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        scores = json.loads(raw)
        return {
            "groundedness": int(scores.get("groundedness", 0)),
            "completeness": int(scores.get("completeness", 0)),
            "actionability": int(scores.get("actionability", 0)),
            "temporal_precision": int(scores.get("temporal_precision", 0)),
            "relational_recall": int(scores.get("relational_recall", 0)),
            "notes": scores.get("notes", ""),
        }
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Could not parse judge response: %s\nRaw: %s", e, raw)
        return {
            "groundedness": 0,
            "completeness": 0,
            "actionability": 0,
            "temporal_precision": 0,
            "relational_recall": 0,
            "notes": f"Parse error: {raw}",
        }


def _format_dump(stage: str, backend_url: str, results: list[dict]) -> str:
    """Render eval results as a human-readable markdown transcript."""
    started = datetime.now(DENVER_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = [
        f"# Eval run — stage={stage}",
        "",
        f"- Started: {started}",
        f"- Backend: {backend_url}",
        f"- Model: {LLM_MODEL_NAME}",
        f"- Questions: {len(results)}",
        "",
        "---",
        "",
    ]
    for idx, row in enumerate(results, start=1):
        lines.append(f"## Q{idx}. {row['question']}")
        lines.append("")
        tools = row.get("tools_called") or []
        lines.append(f"**Tools called:** {', '.join(tools) if tools else '(none)'}")
        noise = row.get("noise_citations") or []
        if noise:
            lines.append(f"**Noise citations:** {', '.join(noise)}")
        if row.get("groundedness") is not None and row.get("groundedness") != 0:
            g = row["groundedness"]
            c = row["completeness"]
            a = row["actionability"]
            t = row.get("temporal_precision", "-")
            r = row.get("relational_recall", "-")
            try:
                avg = (g + c + a + (t or 0) + (r or 0)) / 5
                lines.append(
                    f"**LLM judge:** G:{g} C:{c} A:{a} T:{t} R:{r}  (avg {avg:.1f})"
                )
            except TypeError:
                lines.append(f"**LLM judge:** G:{g} C:{c} A:{a} T:{t} R:{r}")
            if row.get("notes"):
                lines.append(f"**Judge notes:** {row['notes']}")
        lines.append("")
        lines.append("### Response")
        lines.append("")
        lines.append("```")
        lines.append(row.get("response") or "")
        lines.append("```")
        lines.append("")
        lines.append("### Human score (fill in)")
        lines.append("")
        lines.append(
            "- Groundedness: \n- Completeness: \n- Actionability: "
            "\n- Temporal precision: \n- Relational recall: \n- Notes: "
        )
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _resolve_dump_path(raw: str | None, stage: str) -> Path | None:
    """Return the dump file path, generating a default when the flag has no value."""
    if raw is None:
        return None
    repo_root = Path(__file__).resolve().parent.parent
    if raw == "":
        ts = datetime.now(DENVER_TZ).strftime("%Y%m%d-%H%M%S")
        return repo_root / "internal" / f"eval_{stage}_{ts}.md"
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    return path


def run_eval(stage: str, do_score: bool = False, dump_path: Path | None = None):
    """Run all preset questions and store results."""
    sb = get_supabase()
    results = []

    for question in PRESET_QUESTIONS:
        logger.info("Asking: %s", question)
        response, tools = query_agent(question)
        logger.info("  Response length: %d chars", len(response))
        if tools:
            logger.info("  Tools called: %s", tools)

        noise = detect_noise_citations(response)
        if noise:
            logger.warning("  Noise citations detected: %s", noise)

        row = {
            "stage": stage,
            "question": question,
            "response": response,
            "tools_called": tools,
            "noise_citations": noise,
            "noise_citation_count": len(noise),
        }

        if do_score:
            logger.info("  Scoring with LLM judge...")
            scores = score_response(question, response)
            row.update(scores)
            logger.info(
                "  Scores — G:%d C:%d A:%d T:%d R:%d",
                scores["groundedness"],
                scores["completeness"],
                scores["actionability"],
                scores["temporal_precision"],
                scores["relational_recall"],
            )

        # Insert each result immediately to avoid batch insert timeouts on free-tier Supabase
        sb.table("eval_runs").insert(row).execute()  # noqa: SB003
        logger.info("  Stored result for '%s'.", question[:40])
        results.append(row)
        # sleep for 60 seconds between questions to avoid overwhelming the backend or hitting rate limits
        time.sleep(60)

    logger.info("Stored %d eval results for stage '%s'.", len(results), stage)

    if dump_path is not None:
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(_format_dump(stage, BACKEND_URL, results))
        logger.info("Wrote eval transcript to %s", dump_path)

    return results


def print_report():
    """Print a comparison table across all evaluation stages."""
    sb = get_supabase()
    rows = (
        sb.table("eval_runs")  # noqa: SB001, SB006
        .select(
            "stage,question,response,tools_called,groundedness,completeness,"
            "actionability,temporal_precision,relational_recall,noise_citations,"
            "noise_citation_count,notes,created_at"
        )
        .order("created_at")
        .execute()
        .data
        or []
    )

    if not rows:
        logger.info("No evaluation runs found.")
        return

    # Use canonical ordering; append any stages not in the predefined list
    seen_stages = list(dict.fromkeys(r["stage"] for r in rows))
    stages = [s for s in STAGES_ORDERED if s in seen_stages]
    stages += [s for s in seen_stages if s not in stages]

    header = (
        f"{'Stage':<20} {'Ground.':<8} {'Compl.':<8} {'Action.':<8} "
        f"{'Temp.P':<8} {'Rel.R':<8} {'Avg':<8} {'Noise':<6} {'Tools':<6}"
    )
    print(f"\n{header}")
    print("-" * len(header))

    for stage in stages:
        stage_rows = [r for r in rows if r["stage"] == stage]
        scored = [r for r in stage_rows if r.get("groundedness")]
        if not scored:
            print(f"{stage:<20} {'(not scored)'}")
            continue

        g = sum(r["groundedness"] for r in scored) / len(scored)
        c = sum(r["completeness"] for r in scored) / len(scored)
        a = sum(r["actionability"] for r in scored) / len(scored)
        tp = sum((r.get("temporal_precision") or 0) for r in scored) / len(scored)
        rr = sum((r.get("relational_recall") or 0) for r in scored) / len(scored)
        avg = (g + c + a + tp + rr) / 5

        noise_total = sum((r.get("noise_citation_count") or 0) for r in stage_rows)
        tools_used = sum(1 for r in stage_rows if r.get("tools_called"))

        print(
            f"{stage:<20} {g:<8.1f} {c:<8.1f} {a:<8.1f} "
            f"{tp:<8.1f} {rr:<8.1f} {avg:<8.1f} {noise_total:<6d} "
            f"{tools_used}/{len(stage_rows)}"
        )

    print()

    # Per-question detail for latest stage
    latest_stage = stages[-1]
    latest = [r for r in rows if r["stage"] == latest_stage]
    print(f"Detail for stage: {latest_stage}")
    print("-" * 80)
    for r in latest:
        print(f"\nQ: {r['question']}")
        print(f"A: {r['response'][:200]}...")
        if r.get("groundedness"):
            print(
                f"   G:{r['groundedness']} C:{r['completeness']} A:{r['actionability']} "
                f"T:{r.get('temporal_precision', '-')} R:{r.get('relational_recall', '-')}"
            )
            if r.get("notes"):
                print(f"   Notes: {r['notes']}")
        if r.get("tools_called"):
            print(f"   Tools: {r['tools_called']}")
        if r.get("noise_citations"):
            print(f"   Noise cited: {r['noise_citations']}")


def main():
    parser = argparse.ArgumentParser(description="Run agent evaluation")
    parser.add_argument(
        "--stage",
        type=str,
        choices=STAGES_ORDERED,
        help="Stage name (e.g., baseline, rag_reports, news_agent, graph, critic)",
    )
    parser.add_argument(
        "--score", action="store_true", help="Score responses with LLM judge"
    )
    parser.add_argument("--report", action="store_true", help="Print comparison report")
    parser.add_argument(
        "--dump",
        type=str,
        nargs="?",
        const="",
        default=None,
        help=(
            "Write agent transcript to a markdown file for human evaluation. "
            "Pass a path, or omit the value to auto-generate internal/eval_<stage>_<ts>.md"
        ),
    )
    args = parser.parse_args()

    if args.report:
        print_report()
        return

    if not args.stage:
        parser.error("--stage is required unless using --report")

    dump_path = _resolve_dump_path(args.dump, args.stage)
    run_eval(args.stage, do_score=args.score, dump_path=dump_path)


if __name__ == "__main__":
    main()
