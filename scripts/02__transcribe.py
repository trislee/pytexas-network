"""
Transcribe all MP3s under downloads/ with Parakeet; store results in SQLite.

Skips files already present in the database (idempotent re-runs).
Requires ffmpeg/ffprobe for duration, mono 16 kHz decode, and NeMo for transcription.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Any

import nemo.collections.asr as nemo_asr
import torch

from config import DOWNLOADS_DIR, TRANSCRIPTS_DB
from transcription_common import (
    audio_duration_seconds,
    ensure_transcripts_schema,
    mono_16k_wav,
    relative_key,
    split_wav_segments,
)

PARAKEET = "nvidia/parakeet-tdt-0.6b-v3"
# Long talks OOM small GPUs if processed as one tensor; split after local-attention setup.
TRANSCRIBE_CHUNK_SECONDS = 240.0


def _transcribe_wav(asr_model: Any, wav: Path) -> str:
    """Transcribe one mono 16 kHz WAV; chunk long files to avoid GPU OOM."""
    duration = audio_duration_seconds(wav)
    if duration <= TRANSCRIBE_CHUNK_SECONDS:
        out = asr_model.transcribe([str(wav)], batch_size=1, num_workers=0)
        return out[0].text

    segs, tmpdir = split_wav_segments(wav, TRANSCRIBE_CHUNK_SECONDS)
    try:
        parts: list[str] = []
        for j, seg in enumerate(segs, start=1):
            print(f"    chunk {j}/{len(segs)} ({seg.name})")
            out = asr_model.transcribe([str(seg)], batch_size=1, num_workers=0)
            parts.append(out[0].text)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        return " ".join(parts)
    finally:
        shutil.rmtree(tmpdir)


def _configure_model_for_long_audio(asr_model: Any) -> None:
    """Local attention + subsampling chunking (Parakeet / NeMo long-form guidance)."""
    asr_model.change_attention_model(
        self_attention_model="rel_pos_local_attn",
        att_context_size=[256, 256],
    )
    asr_model.change_subsampling_conv_chunking_factor(2)


def main() -> None:
    if not DOWNLOADS_DIR.is_dir():
        raise FileNotFoundError(f"Downloads directory does not exist: {DOWNLOADS_DIR}")

    mp3s = sorted(
        p
        for p in DOWNLOADS_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() == ".mp3"
    )

    conn = sqlite3.connect(TRANSCRIPTS_DB)
    try:
        ensure_transcripts_schema(conn)
        done = {
            row[0]
            for row in conn.execute("SELECT filename FROM transcripts").fetchall()
        }

        pending = [p for p in mp3s if relative_key(p) not in done]
        skipped = len(mp3s) - len(pending)

        print(
            f"Found {len(mp3s)} MP3 file(s); {skipped} already in DB; {len(pending)} to transcribe."
        )

        if not pending:
            return

        asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=PARAKEET)
        _configure_model_for_long_audio(asr_model)

        for i, path in enumerate(pending, start=1):
            key = relative_key(path)
            print(f"[{i}/{len(pending)}] {key}")
            duration = audio_duration_seconds(path)
            wav = mono_16k_wav(path)
            try:
                text = _transcribe_wav(asr_model, wav)
            finally:
                wav.unlink(missing_ok=True)
            conn.execute(
                """
                INSERT INTO transcripts (filename, audio_duration_seconds, transcript)
                VALUES (?, ?, ?)
                """,
                (key, duration, text),
            )
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
