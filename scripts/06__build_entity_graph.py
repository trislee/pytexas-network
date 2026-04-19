"""
Build a co-mention graph from transcript text (not NER spans).

Transcripts are lowercased; variant phrases from entity_consolidations.json are replaced
with canonical forms using longest-first, word-boundary-safe matching. Entity talk counts
and pairwise distances use the same boundary rules on normalized text.

Node set: entities from entities_by_count_consolidated.tsv (from 05) with n_talks ≥ MIN_TALKS
(distinct talks from NER + consolidation), not re-counted from transcript text. Edges still
come from co-mentions in normalized transcripts.

Run after 04–05 and entity_consolidations.json.

Optional `entities_to_ignore` in that JSON (list of strings, same casing rules as
`standardize_entity`) drops hub/spam nodes from the graph (common words, venues, etc.).

Exports only the largest connected component to GraphML (Gephi).

Requires: pip install networkx (GraphML export for Gephi).
"""

from __future__ import annotations

import csv
import math
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import networkx as nx

from config import (
    ENTITIES_BY_COUNT_CONSOLIDATED_TSV,
    ENTITY_CONSOLIDATIONS_JSON,
    GRAPH_GRAPHML,
    TRANSCRIPTS_DB,
)
from transcription_common import load_entity_consolidation_config, standardize_entity

# --- run configuration (no argparse) ---
# Compared to n_talks in entities_by_count_consolidated.tsv (distinct talks per 05), not text search.
MIN_TALKS = 2
# "hard": add 1 to edge weight if min word distance between two mentions <= WINDOW_WORDS.
# "exp": add exp(-EXP_DECAY_LAMBDA * d) for pairs with d <= EXP_MAX_WORD_DISTANCE_WORDS.
COOCCURRENCE_MODE = "hard"
WINDOW_WORDS = 10
EXP_DECAY_LAMBDA = 0.12
EXP_MAX_WORD_DISTANCE_WORDS = 80


def _phrase_boundary_pattern(phrase: str) -> re.Pattern[str]:
    """Match exact phrase only when not adjacent to word characters (Latin-ish transcripts)."""
    phrase = standardize_entity(phrase)
    parts = phrase.split()
    if not parts:
        return re.compile(r"(?!x)x")
    inner = r"\s+".join(re.escape(p) for p in parts)
    return re.compile(r"(?<!\w)" + inner + r"(?!\w)", re.IGNORECASE)


def normalize_transcript(text: str, variant_to_canonical: dict[str, str]) -> str:
    """
    Lowercase, then replace each variant with its canonical form using boundary-safe
    matches (longest variants first to reduce partial overlaps).
    """
    t = text.lower()
    pairs = sorted(variant_to_canonical.items(), key=lambda kv: (-len(kv[0]), kv[0]))
    for variant, canonical in pairs:
        if not variant:
            continue
        if variant == canonical:
            continue
        pat = _phrase_boundary_pattern(variant)
        t = pat.sub(canonical, t)
    return t


def find_phrase_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    """Non-overlapping spans of phrase in text; phrase must already be canonical / lower."""
    phrase = standardize_entity(phrase)
    if not phrase:
        return []
    pat = _phrase_boundary_pattern(phrase)
    return [(m.start(), m.end()) for m in pat.finditer(text)]


def _word_spans(text: str) -> list[tuple[int, int, int]]:
    """List of (word_index, start_char, end_char) for whitespace-delimited tokens."""
    out: list[tuple[int, int, int]] = []
    for i, m in enumerate(re.finditer(r"\S+", text)):
        out.append((i, m.start(), m.end()))
    return out


def _word_index_range_for_span(
    spans: list[tuple[int, int, int]], start_char: int, end_char: int
) -> tuple[int, int] | None:
    idxs: list[int] = []
    for wi, s, e in spans:
        if s < end_char and e > start_char:
            idxs.append(wi)
    if not idxs:
        return None
    return min(idxs), max(idxs)


def _min_word_distance(
    a_lo: int, a_hi: int, b_lo: int, b_hi: int
) -> int:
    return min(abs(x - y) for x in range(a_lo, a_hi + 1) for y in range(b_lo, b_hi + 1))


def _write_graphml_largest_component(
    path: Path,
    allowed: set[str],
    entity_n_talks: dict[str, int],
    edge_weight: dict[tuple[str, str], float],
) -> tuple[int, int, int, int]:
    """
    Build the full undirected graph, then write only the largest connected component
    to GraphML (Label, n_talks, sqrt_n_talks, weight on edges).

    Returns (nodes_written, edges_written, nodes_full_graph, edges_full_graph).
    """
    g: nx.Graph = nx.Graph()
    for ent in allowed:
        n = int(entity_n_talks[ent])
        g.add_node(
            ent,
            Label=ent,
            n_talks=n,
            sqrt_n_talks=float(math.sqrt(n)),
        )
    for (u, v), wt in edge_weight.items():
        g.add_edge(u, v, weight=float(wt))

    n_full, e_full = g.number_of_nodes(), g.number_of_edges()
    if n_full == 0:
        raise ValueError("Graph has no nodes to export.")

    gcc = sorted(nx.connected_components(g), key=len, reverse=True)
    g0 = g.subgraph(gcc[0]).copy()
    nx.write_graphml(g0, path, encoding="utf-8")
    return g0.number_of_nodes(), g0.number_of_edges(), n_full, e_full


def _load_consolidated_n_talks(path: Path) -> dict[str, int]:
    """entity -> n_talks from 05 (distinct talks, consolidated)."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}; run 05__analyze_entities.py first.")
    out: dict[str, int] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames is None or "entity" not in reader.fieldnames:
            raise ValueError(f"{path} must be a TSV with entity and n_talks columns")
        for row in reader:
            ent = (row.get("entity") or "").strip()
            if not ent:
                continue
            raw = (row.get("n_talks") or "").strip()
            if not raw:
                continue
            out[ent] = int(raw)
    return out


def main() -> None:
    if COOCCURRENCE_MODE not in ("hard", "exp"):
        raise ValueError("COOCCURRENCE_MODE must be 'hard' or 'exp'")

    variant_to_canonical, entities_to_ignore = load_entity_consolidation_config(
        ENTITY_CONSOLIDATIONS_JSON
    )

    conn = sqlite3.connect(TRANSCRIPTS_DB)
    try:
        rows = conn.execute(
            """
            SELECT filename, transcript, entities_json FROM transcripts
            WHERE transcript IS NOT NULL AND trim(transcript) != ''
            """
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise ValueError("No transcripts in database.")

    consolidated_n_talks = _load_consolidated_n_talks(ENTITIES_BY_COUNT_CONSOLIDATED_TSV)
    allowed: set[str] = {
        e for e, n in consolidated_n_talks.items() if n >= MIN_TALKS
    }
    if not allowed:
        raise ValueError(
            f"No entities with n_talks ≥ {MIN_TALKS} in {ENTITIES_BY_COUNT_CONSOLIDATED_TSV}."
        )

    entity_n_talks: dict[str, int] = {e: consolidated_n_talks[e] for e in allowed}

    normalized_texts: list[str] = []
    for _fn, transcript, _ej in rows:
        normalized_texts.append(normalize_transcript(transcript, variant_to_canonical))

    edge_weight: dict[tuple[str, str], float] = defaultdict(float)

    for norm in normalized_texts:
        if not norm.strip():
            continue
        wspans = _word_spans(norm)

        per_ent_spans: dict[str, list[tuple[int, int]]] = {}
        for ent in allowed:
            char_spans = find_phrase_spans(norm, ent)
            wrs: list[tuple[int, int]] = []
            for cs, ce in char_spans:
                wr = _word_index_range_for_span(wspans, cs, ce)
                if wr is not None:
                    wrs.append(wr)
            if wrs:
                per_ent_spans[ent] = wrs

        ents_here = sorted(per_ent_spans.keys())
        for ii in range(len(ents_here)):
            for jj in range(ii + 1, len(ents_here)):
                a, b = ents_here[ii], ents_here[jj]
                for alo, ahi in per_ent_spans[a]:
                    for blo, bhi in per_ent_spans[b]:
                        d = _min_word_distance(alo, ahi, blo, bhi)
                        if COOCCURRENCE_MODE == "hard":
                            if d > WINDOW_WORDS:
                                continue
                            w = 1.0
                        else:
                            if d > EXP_MAX_WORD_DISTANCE_WORDS:
                                continue
                            w = math.exp(-EXP_DECAY_LAMBDA * d)
                        u, v = (a, b) if a < b else (b, a)
                        edge_weight[(u, v)] += w

    n_w, e_w, n_full, e_full = _write_graphml_largest_component(
        GRAPH_GRAPHML, allowed, entity_n_talks, edge_weight
    )

    print(
        f"Candidates (n_talks ≥ {MIN_TALKS} from {ENTITIES_BY_COUNT_CONSOLIDATED_TSV.name}): "
        f"{len(allowed)} nodes\n"
        f"Full graph before largest-CC export: {n_full} nodes, {e_full} edges\n"
        f"Largest connected component written to GraphML: {n_w} nodes, {e_w} edges\n"
        f"Co-occurrence mode: {COOCCURRENCE_MODE}"
        + (
            f" (window ≤ {WINDOW_WORDS} words)"
            if COOCCURRENCE_MODE == "hard"
            else f" (exp decay λ={EXP_DECAY_LAMBDA}, max d={EXP_MAX_WORD_DISTANCE_WORDS} words)"
        )
        + f"\nentities_to_ignore: {len(entities_to_ignore)} string(s)\n"
        + f"\nWrote:\n  {GRAPH_GRAPHML}"
    )


if __name__ == "__main__":
    main()