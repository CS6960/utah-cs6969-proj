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
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen/qwen3.5-122b-a10b")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

PRESET_QUESTIONS = [
    "What is my biggest portfolio risk?",
    "Am I diversified enough?",
    "Which holdings look strongest?",
    "Where should new cash go?",
]

# Ground truth answers for the March 24-31, 2026 evaluation window.
# Used by the LLM judge to score agent responses.
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

JUDGE_PROMPT = """\
You are an evaluation judge for a financial advisor AI agent.

Score the agent's response against the ground truth reference answer on three dimensions.
Each score is 1-5 where 1=poor and 5=excellent.

**Groundedness** (1-5): Does the response cite real, specific data (prices, events, holdings) \
rather than generic advice? Does it avoid hallucinating facts?

**Completeness** (1-5): Does the response cover the key factors from the ground truth? \
Does it mention the relevant tickers, events, and dynamics?

**Actionability** (1-5): Does the response give specific, usable advice \
(e.g., "trim NVDA", "add to JPM") rather than vague platitudes?

Respond with ONLY a JSON object, no other text:
{{"groundedness": <int>, "completeness": <int>, "actionability": <int>, "notes": "<brief explanation>"}}

--- QUESTION ---
{question}

--- GROUND TRUTH ---
{ground_truth}

--- AGENT RESPONSE ---
{response}
"""


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def query_agent(question: str) -> tuple[str, list[str]]:
    """Send a question to the backend agent and return (response, tools_called)."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/agent",
            json={"query": question, "role": "financial_advisor"},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", ""), []
    except Exception as e:
        logger.error("Agent query failed: %s", e)
        return f"ERROR: {e}", []


def score_response(question: str, response: str) -> dict:
    """Use the LLM as a judge to score the response against ground truth."""
    from openai import OpenAI

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    ground_truth = GROUND_TRUTH.get(question, "")

    judge_input = JUDGE_PROMPT.format(
        question=question,
        ground_truth=ground_truth,
        response=response,
    )

    result = client.chat.completions.create(
        model=MODEL_NAME,
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
            "notes": scores.get("notes", ""),
        }
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Could not parse judge response: %s\nRaw: %s", e, raw)
        return {"groundedness": 0, "completeness": 0, "actionability": 0, "notes": f"Parse error: {raw}"}


def run_eval(stage: str, do_score: bool = False):
    """Run all preset questions and store results."""
    sb = get_supabase()
    results = []

    for question in PRESET_QUESTIONS:
        logger.info("Asking: %s", question)
        response, tools = query_agent(question)
        logger.info("  Response length: %d chars", len(response))

        row = {
            "stage": stage,
            "question": question,
            "response": response,
            "tools_called": tools,
        }

        if do_score:
            logger.info("  Scoring with LLM judge...")
            scores = score_response(question, response)
            row.update(scores)
            logger.info(
                "  Scores — G:%d C:%d A:%d",
                scores["groundedness"],
                scores["completeness"],
                scores["actionability"],
            )

        results.append(row)

    sb.table("eval_runs").insert(results).execute()
    logger.info("Stored %d eval results for stage '%s'.", len(results), stage)
    return results


def print_report():
    """Print a comparison table across all evaluation stages."""
    sb = get_supabase()
    rows = sb.table("eval_runs").select("*").order("created_at").execute().data or []

    if not rows:
        logger.info("No evaluation runs found.")
        return

    stages = sorted(set(r["stage"] for r in rows))

    print(f"\n{'Stage':<20} {'Ground.':<8} {'Compl.':<8} {'Action.':<8} {'Avg':<8}")
    print("-" * 52)

    for stage in stages:
        stage_rows = [r for r in rows if r["stage"] == stage]
        scored = [r for r in stage_rows if r.get("groundedness")]
        if not scored:
            print(f"{stage:<20} {'(not scored)'}")
            continue

        g = sum(r["groundedness"] for r in scored) / len(scored)
        c = sum(r["completeness"] for r in scored) / len(scored)
        a = sum(r["actionability"] for r in scored) / len(scored)
        avg = (g + c + a) / 3
        print(f"{stage:<20} {g:<8.1f} {c:<8.1f} {a:<8.1f} {avg:<8.1f}")

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
            print(f"   G:{r['groundedness']} C:{r['completeness']} A:{r['actionability']}")
            if r.get("notes"):
                print(f"   Notes: {r['notes']}")


def main():
    parser = argparse.ArgumentParser(description="Run agent evaluation")
    parser.add_argument("--stage", type=str, help="Stage name (e.g., baseline, news_agent)")
    parser.add_argument("--score", action="store_true", help="Score responses with LLM judge")
    parser.add_argument("--report", action="store_true", help="Print comparison report")
    args = parser.parse_args()

    if args.report:
        print_report()
        return

    if not args.stage:
        parser.error("--stage is required unless using --report")

    run_eval(args.stage, do_score=args.score)


if __name__ == "__main__":
    main()
