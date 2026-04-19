"""
Fill transcript_canary_qwen using NVIDIA Canary-Qwen-2.5B (NeMo SALM).

Only processes rows already in the database with a Parakeet transcript (no new MP3s on
disk until 02__transcribe.py has run for them). Idempotent: skips rows where
transcript_canary_qwen is already set.

Model card: training used ~40s audio segments; chunks are kept shorter than that.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Any

import torch
from nemo.collections.speechlm2.models import SALM

from config import DOWNLOADS_DIR, TRANSCRIPTS_DB
from transcription_common import (
    audio_duration_seconds,
    ensure_transcripts_schema,
    mono_16k_wav,
    split_wav_segments,
)

CANARY_QWEN = "nvidia/canary-qwen-2.5b"
# Model card: max training audio ~40s; stay slightly under for quality.
CANARY_CHUNK_SECONDS = 35.0
MAX_NEW_TOKENS = 512


def _generate_chunk(model: Any, wav_path: Path) -> str:
    answer_ids = model.generate(
        prompts=[
            [
                {
                    "role": "user",
                    "content": f"Transcribe the following: {model.audio_locator_tag}",
                    "audio": [str(wav_path)],
                }
            ]
        ],
        max_new_tokens=MAX_NEW_TOKENS,
    )
    return model.tokenizer.ids_to_text(answer_ids[0].cpu())


def _transcribe_wav_salm(model: Any, wav: Path) -> str:
    duration = audio_duration_seconds(wav)
    if duration <= CANARY_CHUNK_SECONDS:
        return _generate_chunk(model, wav)

    segs, tmpdir = split_wav_segments(wav, CANARY_CHUNK_SECONDS)
    try:
        parts: list[str] = []
        for j, seg in enumerate(segs, start=1):
            print(f"    chunk {j}/{len(segs)} ({seg.name})")
            parts.append(_generate_chunk(model, seg))
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        return " ".join(parts)
    finally:
        shutil.rmtree(tmpdir)


def main() -> None:
    if not DOWNLOADS_DIR.is_dir():
        raise FileNotFoundError(f"Downloads directory does not exist: {DOWNLOADS_DIR}")

    conn = sqlite3.connect(TRANSCRIPTS_DB)
    try:
        ensure_transcripts_schema(conn)

        rows = conn.execute(
            """
            SELECT filename FROM transcripts
            WHERE transcript_canary_qwen IS NULL
               OR trim(transcript_canary_qwen) = ''
            """
        ).fetchall()
        pending_keys = [row[0] for row in rows]

        n_done = conn.execute(
            """
            SELECT count(*) FROM transcripts
            WHERE transcript_canary_qwen IS NOT NULL
              AND trim(transcript_canary_qwen) != ''
            """
        ).fetchone()[0]

        print(
            f"Database: {n_done} row(s) already have Canary-Qwen; "
            f"{len(pending_keys)} row(s) to transcribe."
        )

        if not pending_keys:
            return

        model = SALM.from_pretrained(CANARY_QWEN)

        for i, key in enumerate(pending_keys, start=1):
            path = DOWNLOADS_DIR / key
            if not path.is_file():
                raise FileNotFoundError(
                    f"MP3 missing on disk for DB row {key!r}: expected {path}"
                )
            print(f"[{i}/{len(pending_keys)}] {key}")
            wav = mono_16k_wav(path)
            try:
                text = _transcribe_wav_salm(model, wav)
            finally:
                wav.unlink(missing_ok=True)

            conn.execute(
                """
                UPDATE transcripts
                SET transcript_canary_qwen = ?
                WHERE filename = ?
                """,
                (text, key),
            )
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
