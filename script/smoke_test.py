#!/usr/bin/env python3
"""
smoke_test.py — Phase 1b Strategist-orchestrated agent smoke test.

Kills any running uvicorn, boots a fresh one from this worktree, then runs
five milestones:
  M-CASH  build_portfolio_context() structural check (no network)
  M0      /api/agent returns 200 + len > 500 + underlying data tool in tools_called
  M1      Strategist acknowledges news corpus gap
  M2      SKIPPED (not deterministically triggerable black-box)
  M3      /api/report-agent backward compatibility (HTTP 200)

Usage:
  python3 script/smoke_test.py [--base-url URL] [--skip-boot]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import requests

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
WORKTREE_BACKEND = WORKTREE_ROOT / "backend"
UVICORN_BIN = WORKTREE_BACKEND / "venv" / "bin" / "uvicorn"
UVICORN_LOG = "/tmp/uvicorn.smoke.log"

# Underlying data tool names the Strategist wrappers are expected to append
DATA_TOOLS = {
    "retrieve_embedded_financial_report_info",
    "get_price_history_for_symbols",
    "get_stock_price_history",
}

# Keywords indicating the Strategist acknowledged the news gap
NEWS_GAP_KEYWORDS = [
    "not yet wired",
    "news corpus",
    "not available",
    "cannot retrieve news",
    "news data is",
    "phase 2",
    "unable to retrieve",
]


def _tail_log(path: str, n: int = 30) -> str:
    try:
        with open(path) as fh:
            lines = fh.readlines()
        return "".join(lines[-n:])
    except OSError:
        return "(log not readable)"


def boot_uvicorn(base_url: str) -> subprocess.Popen | None:
    print("[boot] Killing any existing uvicorn processes...")
    subprocess.run(
        "pkill -f 'uvicorn app:app' || true",
        shell=True,
        check=False,
    )
    time.sleep(2)

    print(f"[boot] Starting uvicorn from {WORKTREE_BACKEND} ...")
    log_fh = open(UVICORN_LOG, "w")
    proc = subprocess.Popen(
        [
            str(UVICORN_BIN),
            "app:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
        cwd=str(WORKTREE_BACKEND),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )

    health_url = f"{base_url}/api/health"
    deadline = time.time() + 30
    print(f"[boot] Polling {health_url} (up to 30s) ...")
    while time.time() < deadline:
        try:
            r = requests.get(health_url, timeout=3)
            if r.status_code == 200:
                print(f"[boot] Health check passed ({r.status_code})")
                print(f"uvicorn PID: {proc.pid}")
                return proc
        except requests.RequestException:
            pass
        time.sleep(1)

    print("[boot] ERROR: uvicorn never became healthy within 30s")
    print("[boot] Last uvicorn log:")
    print(_tail_log(UVICORN_LOG))
    proc.terminate()
    return None


def run_m_cash() -> tuple[bool, str]:
    """M-CASH: structural check — no network required.

    Runs build_portfolio_context() in the worktree's venv Python to avoid
    picking up an incompatible langgraph version from ~/.local/lib on the
    host, which causes an ImportError unrelated to the function under test.
    """
    venv_python = WORKTREE_BACKEND / "venv" / "bin" / "python"
    t0 = time.time()
    snippet = (
        "import sys; "
        f"sys.path.insert(0, {str(WORKTREE_BACKEND)!r}); "
        "from agent_tools.strategist_tools import build_portfolio_context; "
        "ctx = build_portfolio_context(); "
        "assert 'CASH BALANCES' in ctx, 'no CASH BALANCES section'; "
        "assert '$' in ctx, 'no dollar amount'; "
        "print('OK')"
    )
    try:
        result = subprocess.run(
            [str(venv_python), "-c", snippet],
            capture_output=True,
            text=True,
            timeout=30,
        )
        elapsed = int((time.time() - t0) * 1000)
        if result.returncode != 0 or "OK" not in result.stdout:
            detail = (result.stderr or result.stdout or "").strip()
            return False, f"M-CASH FAIL ({elapsed} ms): {detail}"
        return True, f"M-CASH PASS ({elapsed} ms)"
    except Exception as exc:
        elapsed = int((time.time() - t0) * 1000)
        return False, f"M-CASH FAIL ({elapsed} ms): {exc}"


def run_m0(base_url: str) -> tuple[bool, str]:
    """M0: /api/agent reachable + underlying data tool called + response > 500 chars."""
    t0 = time.time()
    try:
        resp = requests.post(
            f"{base_url}/api/agent",
            json={"query": "What is my biggest portfolio risk?"},
            timeout=180,
        )
        elapsed = int((time.time() - t0) * 1000)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        body = resp.json()
        result = body.get("result") or ""
        tools_called = body.get("tools_called") or []
        assert any(t in DATA_TOOLS for t in tools_called), (
            f"tools_called {tools_called} has no underlying data tool name"
        )
        assert len(result) > 500, f"response too short ({len(result)} chars)"
        return True, f"M0 PASS ({elapsed} ms, result {len(result)} chars, tools: {tools_called})"
    except Exception as exc:
        elapsed = int((time.time() - t0) * 1000)
        return False, f"M0 FAIL ({elapsed} ms): {exc}"


def run_m1(base_url: str) -> tuple[bool, str]:
    """M1: Strategist acknowledges news corpus gap when asked about news."""
    t0 = time.time()
    try:
        resp = requests.post(
            f"{base_url}/api/agent",
            json={"query": "What does the news say about IRGC threats to my tech holdings this week?"},
            timeout=180,
        )
        elapsed = int((time.time() - t0) * 1000)
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        result = (resp.json().get("result") or "").lower()
        assert any(k in result for k in NEWS_GAP_KEYWORDS), (
            f"Strategist did not acknowledge news gap. "
            f"Response snippet: {result[:300]!r}"
        )
        return True, f"M1 PASS ({elapsed} ms, gap acknowledgment present)"
    except Exception as exc:
        elapsed = int((time.time() - t0) * 1000)
        return False, f"M1 FAIL ({elapsed} ms): {exc}"


def run_m2() -> tuple[bool | None, str]:
    """M2: SKIPPED — error propagation not deterministically triggerable black-box."""
    return None, "M2 SKIPPED (manual verification only — not deterministically triggerable from a black-box smoke test)"


def run_m3(base_url: str) -> tuple[bool, str]:
    """M3: /api/report-agent backward compatibility."""
    t0 = time.time()
    try:
        resp = requests.post(
            f"{base_url}/api/report-agent",
            json={"query": "List the available financial reports in the corpus."},
            timeout=180,
        )
        elapsed = int((time.time() - t0) * 1000)
        assert resp.status_code == 200, f"/api/report-agent returned HTTP {resp.status_code}"
        return True, f"M3 PASS ({elapsed} ms, /api/report-agent HTTP 200)"
    except Exception as exc:
        elapsed = int((time.time() - t0) * 1000)
        return False, f"M3 FAIL ({elapsed} ms): {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1b Strategist smoke test")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the backend (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--skip-boot",
        action="store_true",
        help="Skip uvicorn management; assume backend is already running",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    if not args.skip_boot:
        proc = boot_uvicorn(base_url)
        if proc is None:
            return 1

    results: list[tuple[str, bool | None, str]] = []

    # M-CASH
    ok, msg = run_m_cash()
    print(msg)
    results.append(("M-CASH", ok, msg))

    # M0
    ok, msg = run_m0(base_url)
    print(msg)
    results.append(("M0", ok, msg))

    # M1
    ok, msg = run_m1(base_url)
    print(msg)
    results.append(("M1", ok, msg))

    # M2
    status, msg = run_m2()
    print(msg)
    results.append(("M2", status, msg))

    # M3
    ok, msg = run_m3(base_url)
    print(msg)
    results.append(("M3", ok, msg))

    passed = sum(1 for _, s, _ in results if s is True)
    failed = sum(1 for _, s, _ in results if s is False)
    skipped = sum(1 for _, s, _ in results if s is None)

    print()
    print(f"SUMMARY: PASS: {passed}, FAIL: {failed}, SKIP: {skipped}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
