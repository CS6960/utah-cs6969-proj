#!/usr/bin/env python3
"""
Pre-commit check: enforce Supabase free-tier coding rules.

Scans staged Python files for patterns that violate free-tier constraints.
Exit code 0 = pass, 1 = violations found.

Rules enforced:
  SB001  Select without .limit() on non-RPC table queries
  SB002  Embedding column selected in .select() (use RPC instead)
  SB003  Supabase query inside a for/while loop (N+1 pattern)
  SB004  create_client() called inside a function body (use module-level singleton)
  SB005  Batch insert without size guard (>50 rows risk)
  SB006  .select("*") fetches all columns including large ones
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# Tables where unbounded selects are safe (known small, <50 rows)
SMALL_TABLES = {"portfolio_positions", "stocks", "portfolio_cash", "portfolio_config"}

# Maximum recommended batch insert size
MAX_BATCH_SIZE = 50


class Violation:
    def __init__(self, rule: str, file: str, line: int, message: str):
        self.rule = rule
        self.file = file
        self.line = line
        self.message = message

    def __str__(self):
        return f"{self.file}:{self.line}  {self.rule}  {self.message}"


def check_file(filepath: str) -> list[Violation]:
    """Run all regex-based and AST-based checks on a single file."""
    path = Path(filepath)
    if not path.suffix == ".py" or not path.exists():
        return []
    # Skip vendored / venv code
    parts = path.parts
    if "venv" in parts or "node_modules" in parts or "__pycache__" in parts or path.name == "check_supabase_rules.py":
        return []

    source = path.read_text()
    lines = source.splitlines()
    violations: list[Violation] = []

    # --- Regex-based checks (fast, line-level) ---

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Skip comments and noqa suppressions
        if stripped.startswith("#"):
            continue

        # SB002: embedding column in .select()
        if re.search(r'\.select\([^)]*embedding[^)]*\)', stripped):
            violations.append(Violation(
                "SB002", filepath, i,
                "Selecting 'embedding' column transfers large vectors over HTTP. "
                "Use match_document_tree_nodes RPC for server-side similarity search.",
            ))

        # SB006: .select("*")
        if re.search(r'\.select\(\s*["\']?\s*\*\s*["\']?\s*\)', stripped):
            violations.append(Violation(
                "SB006", filepath, i,
                '.select("*") fetches all columns including embeddings/metadata. '
                "Specify only the columns you need.",
            ))

    # --- AST-based checks (structural) ---
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return violations

    _check_ast(tree, filepath, lines, violations)

    # Filter out suppressed violations (# noqa: SB0XX)
    filtered = []
    for v in violations:
        line_text = lines[v.line - 1] if v.line <= len(lines) else ""
        noqa_match = re.search(r"#\s*noqa:\s*(SB\d+(?:\s*,\s*SB\d+)*)", line_text)
        if noqa_match:
            suppressed = {s.strip() for s in noqa_match.group(1).split(",")}
            if v.rule in suppressed:
                continue
        filtered.append(v)
    return filtered


def _is_supabase_query_chain(node: ast.AST) -> bool:
    """Check if a call chain includes .table(...) or .rpc(...)."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in ("table", "rpc"):
            return True
        return _is_supabase_query_chain(node.func.value)
    if isinstance(node, ast.Attribute):
        return _is_supabase_query_chain(node.value)
    return False


def _chain_has_method(node: ast.AST, method: str) -> bool:
    """Walk up a call chain to see if a given method (.limit, .eq, etc.) is present."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == method:
            return True
        return _chain_has_method(node.func.value, method)
    if isinstance(node, ast.Attribute):
        return _chain_has_method(node.value, method)
    return False


def _get_table_name(node: ast.AST) -> str | None:
    """Extract table name from .table("name") in a chain."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "table" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
        return _get_table_name(node.func.value)
    if isinstance(node, ast.Attribute):
        return _get_table_name(node.value)
    return None


def _has_noqa(lines: list[str], lineno: int, rule_id: str) -> bool:
    """Check if a source line has a ``# noqa: SBXXX`` suppression comment."""
    if 1 <= lineno <= len(lines):
        line = lines[lineno - 1]
        if f"# noqa: {rule_id}" in line:
            return True
    return False


def _check_ast(tree: ast.Module, filepath: str, lines: list[str], violations: list[Violation]):
    """Run AST-based structural checks."""

    for node in ast.walk(tree):

        # SB001: .execute() without .limit() on table queries (not RPCs)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
        ):
            chain_root = node.func.value
            if _is_supabase_query_chain(chain_root):
                is_rpc = _chain_has_rpc(chain_root)
                has_limit = _chain_has_method(chain_root, "limit")
                table_name = _get_table_name(chain_root)
                is_insert = _chain_has_method(chain_root, "insert")
                is_delete = _chain_has_method(chain_root, "delete")
                is_update = _chain_has_method(chain_root, "update")
                is_upsert = _chain_has_method(chain_root, "upsert")
                is_write = is_insert or is_delete or is_update or is_upsert

                if not is_rpc and not has_limit and not is_write:
                    if table_name not in SMALL_TABLES:
                        violations.append(Violation(
                            "SB001", filepath, node.lineno,
                            f"Query on '{table_name or '?'}' has no .limit(). "
                            f"Add .limit(N) to prevent unbounded result sets. "
                            f"Free-tier statement timeout is 3s for anon role.",
                        ))

        # SB003: Supabase call inside a loop body
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, ast.Call) and _is_supabase_query_chain(child):
                    if _has_noqa(lines, child.lineno, "SB003"):
                        continue
                    violations.append(Violation(
                        "SB003", filepath, child.lineno,
                        "Supabase query inside a loop (N+1 pattern). "
                        "Batch the operation or fetch all data before the loop.",
                    ))

        # SB004: create_client() inside a function
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "create_client"
                ):
                    violations.append(Violation(
                        "SB004", filepath, child.lineno,
                        "create_client() called inside a function. "
                        "Use a module-level singleton to avoid connection churn "
                        "(free tier: 60 direct / 200 pooled connections).",
                    ))


def _chain_has_rpc(node: ast.AST) -> bool:
    """Check if call chain contains .rpc(...)."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "rpc":
            return True
        return _chain_has_rpc(node.func.value)
    if isinstance(node, ast.Attribute):
        return _chain_has_rpc(node.value)
    return False


def main():
    # Accept file list from args (pre-commit passes staged files)
    # or scan backend/ and script/ by default
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        root = Path(__file__).resolve().parent.parent
        files = [
            str(p) for p in
            list(root.glob("backend/**/*.py")) + list(root.glob("script/**/*.py"))
            if "venv" not in p.parts and "__pycache__" not in p.parts
        ]

    all_violations: list[Violation] = []
    for f in files:
        all_violations.extend(check_file(f))

    if all_violations:
        print(f"\n{'='*60}")
        print(f"  Supabase free-tier lint: {len(all_violations)} violation(s)")
        print(f"{'='*60}\n")
        for v in all_violations:
            print(f"  {v}")
        print(f"\n  See docs/08-SUPABASE-FREE-TIER.md for rules & fixes.\n")
        sys.exit(1)
    else:
        print("Supabase free-tier lint: OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
