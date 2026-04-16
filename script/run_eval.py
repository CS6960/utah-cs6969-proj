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
# Ground truth answers (March 24 - April 2, 2026 evaluation window)
# Prices cover Mar 24 - Apr 2 (8 trading days). News covers Mar 13 - Apr 2.
# ---------------------------------------------------------------------------

GROUND_TRUTH = {
    "What is my biggest portfolio risk?": (
        "Iran-conflict escalation and the associated energy-supply shock is the dominant risk as of "
        "April 2, 2026. Tech exposure (AAPL, MSFT, GOOGL, AMZN, NVDA) is roughly 45% of NAV — the "
        "largest single-sector concentration — and the portfolio's big-tech holdings all cite "
        "geopolitical tensions and supply-chain disruption as material risks in their 10-Ks. News "
        "from April 2 reports oil prices surging >50% on the disruption and JPMorgan CEO Jamie Dimon "
        "explicitly warning that 'a prolonged closure of the Strait of Hormuz' poses serious global "
        "economic effects. JPM itself is ~16% of NAV and exposed to trading/credit stress from a "
        "prolonged disruption. The concentration risk should be expressed in % of NAV, not count of "
        "positions."
    ),
    "Am I diversified enough?": (
        "The portfolio is under-diversified: tech (~45% of NAV) plus AAPL and JPM individually near "
        "~17% each create meaningful concentration, and cash is ~20% of NAV. The three non-tech "
        "holdings (JPM ~16%, LLY ~12%, XOM ~7%) each hedge a different macro driver — financial "
        "stability, recession-resistant healthcare demand (GLP-1), and energy-price exposure — which "
        "is the diversification that is working. The April 1-2 tape (tech rebound, XOM pulling back) "
        "illustrates why weight framing matters: the Iran narrative is partially de-escalating "
        "(Iran/Oman drafting a Hormuz traffic protocol per April 2 news) yet the sector tilt would "
        "still drive outsized portfolio swings on any re-escalation."
    ),
    "Which holdings look strongest?": (
        "On the 8-day price tape (Mar 24 - Apr 2), XOM was strongest through Mar 31 (+2.59% WoW on "
        "the Iran oil-shock narrative) but pulled back Apr 1-2 as the Hormuz traffic-protocol "
        "headline and tech rebound shifted sentiment. LLY is the defensive growth standout with an "
        "April 2 Bank of America note calling its new oral GLP-1 therapy Foundayo the 'preferred oral "
        "GLP-1' and a Medicare-coverage policy tailwind from the Trump GLP-1 plan. JPM is a "
        "flight-to-quality anchor during the crisis, cited by Dimon himself on the Hormuz risk. Tech "
        "(AAPL, MSFT, NVDA, GOOGL, AMZN) rebounded on Apr 1-2 but remains the portfolio's risk "
        "concentration and faces supply-chain / inflation pressure per 10-K language."
    ),
    "Where should new cash go?": (
        "With cash at ~20% of NAV ($12,500), the deployable capital should bias to defensive growth "
        "and non-tech diversifiers: LLY (GLP-1 secular demand, April 2 Foundayo catalyst, Medicare "
        "policy tailwind) and JPM (valuation anchor, flight-to-quality beneficiary despite Dimon's "
        "own Hormuz warning). XOM is a conditional energy hedge — attractive if the Iran conflict "
        "re-escalates, less attractive given the April 1-2 oil pullback and Hormuz de-escalation "
        "signal. Avoid adding to tech while concentration is already ~45% of NAV and supply-chain / "
        "inflation risk is live. Cash weight is not itself a problem — keeping dry powder for re-"
        "escalation or a sharper tech drawdown is defensible."
    ),
}

# ---------------------------------------------------------------------------
# Temporal facts — key date-stamped facts the agent should cite
# The judge uses these to assess temporal precision.
# Window: March 24 - April 2, 2026 (news through Apr 2, last close Apr 2).
# ---------------------------------------------------------------------------

TEMPORAL_FACTS = {
    "What is my biggest portfolio risk?": [
        "News window runs through April 2, 2026; last close is April 2, 2026",
        "Bloomberg Apr 2: 'war on Iran has disrupted oil supply from the region, causing prices to rise more than 50%'",
        "Simply Wall St Apr 2: Jamie Dimon warns 'a prolonged closure of the Strait of Hormuz' poses serious global economic effects",
        "MT Newswires Apr 2: Iran, Oman drafting Hormuz Strait traffic protocol (potential de-escalation signal)",
        "Bloomberg Apr 2: 'Bonds' Oil-Driven Selloff' — investor focus on surging energy prices as drag on growth",
        "Tech weights (AAPL, MSFT, GOOGL, AMZN, NVDA) sum to ~45% of NAV — largest sector concentration",
        "AAPL, MSFT, GOOGL, AMZN, NVDA 10-Ks all cite geopolitical tensions / supply-chain risk",
    ],
    "Am I diversified enough?": [
        "Tech exposure ~45% of NAV (AAPL ~17%, MSFT ~11%, GOOGL ~9%, AMZN ~5%, NVDA ~4%)",
        "Non-tech holdings JPM ~16%, LLY ~12%, XOM ~7% — three distinct macro hedges",
        "Cash ~20% of NAV ($12,500 USD)",
        "April 1-2 tape: tech rebounded (AAPL +0.84%, MSFT +0.89%, NVDA +1.71%), XOM pulled back (-5.3% from Mar 31)",
        "Hormuz traffic-protocol news April 2 suggests partial de-escalation",
    ],
    "Which holdings look strongest?": [
        "XOM closed Mar 31 at $169.66 (+2.59% WoW) then pulled back to $160.69 on Apr 2",
        "Tech rebounded Apr 1-2 (AAPL $255.92, MSFT $373.46, NVDA $177.39 on Apr 2)",
        "LLY Apr 2 Bank of America note: Foundayo 'preferred oral GLP-1'; Trump Medicare coverage policy tailwind",
        "JPM ~16% of NAV, Dimon Apr 2 Hormuz warning",
        "Price window: Mar 24 - Apr 2, 2026 (8 trading days)",
    ],
    "Where should new cash go?": [
        "Cash available: $12,500 (~20% of NAV $63,634.92 as of Apr 2)",
        "LLY Apr 2 catalyst: Foundayo oral GLP-1, Medicare GLP-1 coverage policy",
        "JPM ~16% of NAV already — consider incremental add vs. concentration",
        "XOM pulled back $169.66 → $160.69 on Apr 1-2 as Hormuz protocol news shifted sentiment",
        "Tech already ~45% of NAV — avoid adding",
    ],
}

# ---------------------------------------------------------------------------
# Relational connections — cross-sector causal chains the agent should identify
# The judge uses these to assess relational recall.
# ---------------------------------------------------------------------------

RELATIONAL_CONNECTIONS = {
    "What is my biggest portfolio risk?": [
        "Iran conflict → Strait of Hormuz disruption → oil price surge (>50% per Apr 2 news)",
        "Oil shock → inflation fears → bond selloff → equity pressure (Apr 2 Bloomberg thesis)",
        "Tech concentration (~45% of NAV) → amplified portfolio exposure to a single macro driver",
        "Oil move → XOM/tech inverse dynamic (XOM up through Mar 31, retraced Apr 1-2 with tech rebound)",
        "Hormuz protocol news → partial de-escalation signal → possible reversal of the risk-off trade",
    ],
    "Am I diversified enough?": [
        "Iran conflict creates opposite effects within portfolio: XOM gains vs tech losses (reversing Apr 1-2)",
        "Flight-to-quality dynamic: risk-off → flows into JPM and LLY as defensive anchors",
        "Energy hedge: XOM weight (~7%) gives partial exposure to oil upside without over-concentration",
        "Tech sector correlation: all 5 tech names co-move on macro risk (intra-sector diversification failure)",
        "3 non-tech holdings (JPM ~16%, LLY ~12%, XOM ~7%) each hedge a different macro driver: "
        "financial stability, healthcare demand, energy prices",
    ],
    "Which holdings look strongest?": [
        "XOM early-window strength linked to Iran conflict → oil surge, then Apr 1-2 pullback as Hormuz protocol news hit",
        "JPM strength linked to flight-to-quality flows during geopolitical crisis (Dimon Hormuz warning itself is a risk signal)",
        "LLY strength linked to recession-resistant GLP-1 demand + Apr 2 Foundayo catalyst + Medicare policy tailwind",
        "Tech weakness through Mar 31 linked to inflation / supply-chain risk, rebounded Apr 1-2 on partial de-escalation",
    ],
    "Where should new cash go?": [
        "JPM recommendation linked to flight-to-quality dynamic in ongoing geopolitical crisis — but JPM already ~16% of NAV",
        "LLY recommendation linked to secular GLP-1 demand + Apr 2 Foundayo + Medicare policy (non-cyclical)",
        "XOM recommendation conditional on re-escalation — weakened by Apr 1-2 pullback and Hormuz protocol signal",
        "Tech avoidance linked to ~45% NAV concentration already + live supply-chain / inflation risk",
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
