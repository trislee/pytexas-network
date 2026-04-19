"""
Run spaCy NER on each Parakeet transcript; store filtered entities as JSON per row.

Idempotent: only fills rows where entities_json is NULL or empty.
Requires: pip install spacy && python -m spacy download en_core_web_lg
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import spacy
from spacy.language import Language

from config import TRANSCRIPTS_DB
from transcription_common import ensure_transcripts_schema

SPACY_MODEL = "en_core_web_lg"
BAD_NER_LABELS = frozenset({"TIME", "ORDINAL", "DATE", "CARDINAL", "MONEY"})
PIPE_BATCH_SIZE = 16


def _load_nlp() -> Language:
    try:
        return spacy.load(SPACY_MODEL)
    except OSError as e:
        raise RuntimeError(
            f"spaCy model {SPACY_MODEL!r} not found. Install with:\n"
            f"  python -m pip install spacy\n"
            f"  python -m spacy download {SPACY_MODEL}"
        ) from e


def _doc_to_entities_payload(doc: Any) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    for ent in doc.ents:
        if ent.label_ in BAD_NER_LABELS:
            continue
        entities.append(
            {
                "text": ent.text,
                "label": ent.label_,
                "start_char": ent.start_char,
                "end_char": ent.end_char,
            }
        )
    return {"entities": entities}


def main() -> None:
    conn = sqlite3.connect(TRANSCRIPTS_DB)
    try:
        ensure_transcripts_schema(conn)
        rows = conn.execute(
            """
            SELECT filename, transcript FROM transcripts
            WHERE entities_json IS NULL OR trim(entities_json) = ''
            """
        ).fetchall()

        n_done = conn.execute(
            """
            SELECT count(*) FROM transcripts
            WHERE entities_json IS NOT NULL AND trim(entities_json) != ''
            """
        ).fetchone()[0]

        print(
            f"Database: {n_done} row(s) already have entities_json; "
            f"{len(rows)} row(s) to process."
        )
        if not rows:
            return

        nlp = _load_nlp()
        texts = [r[1] for r in rows]
        filenames = [r[0] for r in rows]
        max_len = max(len(t) for t in texts)
        if max_len > nlp.max_length:
            nlp.max_length = max_len + 10_000

        for i, doc in enumerate(
            nlp.pipe(texts, batch_size=PIPE_BATCH_SIZE),
            start=1,
        ):
            key = filenames[i - 1]
            print(f"[{i}/{len(rows)}] {key}")
            payload = _doc_to_entities_payload(doc)
            conn.execute(
                "UPDATE transcripts SET entities_json = ? WHERE filename = ?",
                (json.dumps(payload, ensure_ascii=False), key),
            )
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
