"""Shared audio + SQLite schema helpers for transcription scripts."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from config import DOWNLOADS_DIR


def standardize_entity(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


# Max variant→canonical hops (cycle guard); same as entity graph pipeline.
MAX_CANONICAL_CHAIN = 48


def load_entity_consolidation_config(
    path: Path,
) -> tuple[dict[str, str], frozenset[str]]:
    """Load variant_to_canonical and entities_to_ignore from entity_consolidations.json."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing consolidations file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("variant_to_canonical")
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain an object variant_to_canonical")
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise TypeError("Consolidation keys and values must be strings")
        out[standardize_entity(k)] = standardize_entity(v)

    ignore_raw = data.get("entities_to_ignore", [])
    if ignore_raw is None:
        ignore_raw = []
    if not isinstance(ignore_raw, list):
        raise ValueError(f"{path}: entities_to_ignore must be a list")
    ignore_set: set[str] = set()
    for x in ignore_raw:
        if not isinstance(x, str):
            raise TypeError("entities_to_ignore entries must be strings")
        sx = standardize_entity(x)
        if sx:
            ignore_set.add(sx)

    return out, frozenset(ignore_set)


def canonicalize(text: str, variant_to_canonical: dict[str, str]) -> str:
    s = standardize_entity(text)
    for _ in range(MAX_CANONICAL_CHAIN):
        if s not in variant_to_canonical:
            return s
        nxt = variant_to_canonical[s]
        if nxt == s:
            return s
        s = nxt
    raise RuntimeError(f"Canonicalization chain exceeded {MAX_CANONICAL_CHAIN} steps for {text!r}")


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
