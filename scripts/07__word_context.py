"""
For each transcript, find every whitespace-delimited token equal to WORD (case-insensitive)
and print the previous N and next N tokens.

Much faster than a recursive SQL tokenizer: SQLite was building one row per word for the
entire corpus before filtering.

Edit WORD / CONTEXT_WORDS below, then:
  python3 07__word_context.py > word_context.txt
"""

from __future__ import annotations

import csv
import sqlite3
import sys
import textwrap

from config import TRANSCRIPTS_DB

# --- edit these ---
WORD = "core"
CONTEXT_WORDS = 10
# Wide tab-separated rows are awkward in a terminal; set True only for machine/paste tools.
OUTPUT_AS_TSV = False
WRAP_WIDTH = 96


def _tokens(text: str) -> list[str]:
    return text.split()


def _emit_block(
    filename: str, idx: int, before: str, word: str, after: str
) -> None:
    print("-" * min(WRAP_WIDTH, 80))
    for line in textwrap.wrap(
        filename,
        width=WRAP_WIDTH,
        break_long_words=True,
        break_on_hyphens=False,
    ):
        print(line)
    print(f"Token index: {idx}   matched: {word!r}")
    print()
    body_w = max(40, WRAP_WIDTH - 2)
    print("Before:")
    print(textwrap.indent(textwrap.fill(before or "(none)", width=body_w), "  "))
    print()
    print("After:")
    print(textwrap.indent(textwrap.fill(after or "(none)", width=body_w), "  "))
    print()


def main() -> None:
    needle = WORD.strip()
    if not needle:
        print("Set WORD to a non-empty string.", file=sys.stderr)
        sys.exit(1)
    needle_lower = needle.lower()
    w = max(0, CONTEXT_WORDS)

    conn = sqlite3.connect(TRANSCRIPTS_DB)
    try:
        rows = conn.execute(
            """
            SELECT filename, transcript FROM transcripts
            WHERE transcript IS NOT NULL AND trim(transcript) != ''
            """
        ).fetchall()
    finally:
        conn.close()

    out = (
        csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
        if OUTPUT_AS_TSV
        else None
    )
    if out:
        out.writerow(
            [
                "filename",
                "match_token_index",
                "tokens_before",
                "matched_token",
                "tokens_after",
            ]
        )

    for filename, transcript in rows:
        toks = _tokens(transcript)
        for i, t in enumerate(toks):
            if t.lower() != needle_lower:
                continue
            lo = max(0, i - w)
            hi = min(len(toks), i + w + 1)
            before = " ".join(toks[lo:i])
            after = " ".join(toks[i + 1 : hi])
            idx = i + 1
            if out:
                out.writerow([filename, idx, before, t, after])
            else:
                _emit_block(filename, idx, before, t, after)


if __name__ == "__main__":
    main()
