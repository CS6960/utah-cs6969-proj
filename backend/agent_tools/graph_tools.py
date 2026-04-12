"""
Entity-relationship graph traversal for Phase 3 cross-sector causal reasoning.

Queries the entity_relationships Supabase table using a 2-query hop pattern
that is SB003-compliant (no queries inside loops).
"""

from __future__ import annotations

import logging
import os

import _env_bootstrap  # noqa: F401
from supabase import Client, create_client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

_supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def traverse_entity_graph(entities: list[str], hops: int = 1) -> list[dict]:
    """
    Traverse the entity-relationship graph starting from the given entities.

    Uses a 2-query pattern (hop-1 + hop-2) that is SB003-compliant:
    no Supabase queries inside loops.

    Args:
        entities: Starting entity names to search for.
        hops: 1 for direct edges only, 2 for one additional hop.

    Returns:
        List of edge dicts with keys: source_entity, source_type,
        target_entity, target_type, relationship, evidence.
    """
    if not entities:
        return []

    cols = "source_entity,source_type,target_entity,target_type,relationship,evidence"

    # Query 1a: edges where source_entity IN entities
    hop1a = _supabase.table("entity_relationships").select(cols).in_("source_entity", entities).limit(50).execute()
    # Query 1b: edges where target_entity IN entities
    hop1b = _supabase.table("entity_relationships").select(cols).in_("target_entity", entities).limit(50).execute()
    hop1_all = (hop1a.data or []) + (hop1b.data or [])

    if hops < 2 or not hop1_all:
        return hop1_all

    # Collect neighbor entities for hop-2
    hop1_targets = list({r["target_entity"] for r in hop1_all} | {r["source_entity"] for r in hop1_all})
    hop1_targets = [t for t in hop1_targets if t not in entities]
    if not hop1_targets:
        return hop1_all

    # Query 2: hop-2 edges (SB003: no loop, single .in_() call)
    hop2 = _supabase.table("entity_relationships").select(cols).in_("source_entity", hop1_targets).limit(50).execute()

    return hop1_all + (hop2.data or [])
