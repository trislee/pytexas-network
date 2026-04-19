"""
Aggregate entity strings from transcripts.entities_json, count after standardization,
by number of distinct talks (files) each entity appears in at least once.

Writes two TSV reports (raw standardized strings) and two parallel reports after the same
variant→canonical mapping and entities_to_ignore filtering as 06__build_entity_graph.py.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import defaultdict

from config import (
    ENTITIES_ALPHABETICAL_CONSOLIDATED_TSV,
    ENTITIES_ALPHABETICAL_TSV,
    ENTITIES_BY_COUNT_CONSOLIDATED_TSV,
    ENTITIES_BY_COUNT_TSV,
    ENTITY_CONSOLIDATIONS_JSON,
    TRANSCRIPTS_DB,
)
from transcription_common import canonicalize, load_entity_consolidation_config, standardize_entity


def main() -> None:
    conn = sqlite3.connect(TRANSCRIPTS_DB)
    try:
        rows = conn.execute(
            """
            SELECT filename, entities_json FROM transcripts
            WHERE entities_json IS NOT NULL AND trim(entities_json) != ''
            """
        ).fetchall()
    finally:
        conn.close()

    variant_to_canonical, entities_to_ignore = load_entity_consolidation_config(
        ENTITY_CONSOLIDATIONS_JSON
    )

    # entity -> set of transcript filenames where it appears ≥ once
    entity_talks: dict[str, set[str]] = defaultdict(set)
    entity_talks_consolidated: dict[str, set[str]] = defaultdict(set)

    for filename, raw in rows:
        payload = json.loads(raw)
        seen_in_talk: set[str] = set()
        seen_in_talk_consolidated: set[str] = set()
        for ent in payload.get("entities", []):
            t = ent.get("text", "")
            key = standardize_entity(t)
            if key:
                seen_in_talk.add(key)
            c = canonicalize(t, variant_to_canonical)
            if c and c not in entities_to_ignore:
                seen_in_talk_consolidated.add(c)
        for key in seen_in_talk:
            entity_talks[key].add(filename)
        for key in seen_in_talk_consolidated:
            entity_talks_consolidated[key].add(filename)

    n_talks: dict[str, int] = {k: len(v) for k, v in entity_talks.items()}
    n_talks_consolidated: dict[str, int] = {
        k: len(v) for k, v in entity_talks_consolidated.items()
    }

    if not n_talks:
        raise ValueError("No entities found; run 04__extract_entities.py first.")
    if not n_talks_consolidated:
        raise ValueError(
            "No entities remain after consolidation / entities_to_ignore; "
            "check entity_consolidations.json."
        )

    by_talks = sorted(n_talks.items(), key=lambda x: (-x[1], x[0]))
    alphabetical = sorted(n_talks.items(), key=lambda x: x[0])
    by_talks_c = sorted(n_talks_consolidated.items(), key=lambda x: (-x[1], x[0]))
    alphabetical_c = sorted(n_talks_consolidated.items(), key=lambda x: x[0])

    with ENTITIES_BY_COUNT_TSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["entity", "n_talks"])
        w.writerows(by_talks)

    with ENTITIES_ALPHABETICAL_TSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["entity", "n_talks"])
        w.writerows(alphabetical)

    with ENTITIES_BY_COUNT_CONSOLIDATED_TSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["entity", "n_talks"])
        w.writerows(by_talks_c)

    with ENTITIES_ALPHABETICAL_CONSOLIDATED_TSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["entity", "n_talks"])
        w.writerows(alphabetical_c)

    print(
        f"Wrote {len(n_talks)} unique entities (raw standardized; "
        f"{len(n_talks_consolidated)} after consolidation), "
        f"counts = distinct talks each appears in:\n"
        f"  {ENTITIES_BY_COUNT_TSV} (by n_talks, descending)\n"
        f"  {ENTITIES_ALPHABETICAL_TSV} (alphabetical by entity)\n"
        f"  {ENTITIES_BY_COUNT_CONSOLIDATED_TSV} (consolidated, by n_talks)\n"
        f"  {ENTITIES_ALPHABETICAL_CONSOLIDATED_TSV} (consolidated, alphabetical)"
    )


if __name__ == "__main__":
    main()
