"""
Aggregate entity strings from transcripts.entities_json, count after standardization and
variant→canonical mapping (same rules as 06__build_entity_graph.py).

Writes entities_by_count_consolidated.tsv: distinct talks per entity, sorted by n_talks descending.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import defaultdict

from config import ENTITIES_BY_COUNT_CONSOLIDATED_TSV, ENTITY_CONSOLIDATIONS_JSON, TRANSCRIPTS_DB
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

    entity_talks: dict[str, set[str]] = defaultdict(set)

    for filename, raw in rows:
        payload = json.loads(raw)
        seen_in_talk: set[str] = set()
        for ent in payload.get("entities", []):
            t = ent.get("text", "")
            c = canonicalize(t, variant_to_canonical)
            if c and c not in entities_to_ignore:
                seen_in_talk.add(c)
        for key in seen_in_talk:
            entity_talks[key].add(filename)

    n_talks: dict[str, int] = {k: len(v) for k, v in entity_talks.items()}

    if not n_talks:
        raise ValueError(
            "No entities remain after consolidation / entities_to_ignore; "
            "check entity_consolidations.json and run 04__extract_entities.py first."
        )

    by_talks = sorted(n_talks.items(), key=lambda x: (-x[1], x[0]))

    with ENTITIES_BY_COUNT_CONSOLIDATED_TSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["entity", "n_talks"])
        w.writerows(by_talks)

    print(
        f"Wrote {len(n_talks)} consolidated entities (distinct talks per entity) to:\n"
        f"  {ENTITIES_BY_COUNT_CONSOLIDATED_TSV}"
    )


if __name__ == "__main__":
    main()
