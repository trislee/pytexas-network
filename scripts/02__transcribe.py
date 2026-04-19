"""
Transcribe all MP3s under downloads/ with Parakeet; store results in SQLite.

Skips files already present in the database (idempotent re-runs).
Requires ffmpeg/ffprobe for duration, mono 16 kHz decode, and NeMo for transcription.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import nemo.collections.asr as nemo_asr
import torch

from config import DOWNLOADS_DIR, TRANSCRIPTS_DB

PARAKEET = "nvidia/parakeet-tdt-0.6b-v3"
# Long talks OOM small GPUs if processed as one tensor; split after local-attention setup.
TRANSCRIBE_CHUNK_SECONDS = 240.0


def audio_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def relative_key(path: Path) -> str:
    return path.relative_to(DOWNLOADS_DIR).as_posix()


def mono_16k_wav(src: Path) -> Path:
    """Decode audio to mono 16 kHz WAV."""
    fd, name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    out = Path(name)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-i",
                str(src),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        out.unlink(missing_ok=True)
        raise
    return out


def split_wav_segments(src: Path, segment_seconds: float) -> tuple[list[Path], Path]:
    """Write contiguous WAV segments via ffmpeg; caller must shutil.rmtree(tmpdir) when done."""
    tmpdir = Path(tempfile.mkdtemp())
    pattern = str(tmpdir / "seg_%03d.wav")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-i",
                str(src),
                "-f",
                "segment",
                "-segment_time",
                str(int(segment_seconds)),
                "-reset_timestamps",
                "1",
                pattern,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        shutil.rmtree(tmpdir)
        raise
    segs = sorted(tmpdir.glob("seg_*.wav"))
    if not segs:
        shutil.rmtree(tmpdir)
        raise RuntimeError(f"ffmpeg segment produced no files under {tmpdir}")
    return segs, tmpdir


def ensure_transcripts_schema(conn: sqlite3.Connection) -> None:
    """Create transcripts table and add new columns when upgrading old DBs."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transcripts (
            filename TEXT PRIMARY KEY,
            audio_duration_seconds REAL NOT NULL,
            transcript TEXT NOT NULL,
            transcript_canary_qwen TEXT,
            entities_json TEXT
        )
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(transcripts)").fetchall()}
    if "transcript_canary_qwen" not in cols:
        conn.execute("ALTER TABLE transcripts ADD COLUMN transcript_canary_qwen TEXT")
    if "entities_json" not in cols:
        conn.execute("ALTER TABLE transcripts ADD COLUMN entities_json TEXT")
    conn.commit()


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
