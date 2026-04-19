"""
Download MP3 audio from each playlist URL listed in youtube_links.txt.

Only downloads entries shorter than one hour. Requires yt-dlp and ffmpeg:
  pip install yt-dlp
"""

from pathlib import Path

import yt_dlp
from config import DOWNLOADS_DIR, YOUTUBE_LINKS_FILE


def _under_one_hour(info_dict: dict, *, incomplete: bool) -> str | None:
    """Return a skip reason string, or None to allow download."""
    if incomplete:
        return None
    duration = info_dict.get("duration")
    if duration is not None and duration >= 3600:
        return "duration >= 1 hour"
    return None


def _load_playlist_urls(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def main() -> None:
    urls = _load_playlist_urls(YOUTUBE_LINKS_FILE)
    if not urls:
        raise ValueError(f"No playlist URLs in {YOUTUBE_LINKS_FILE}")

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    for i, url in enumerate(urls, start=1):
        out = DOWNLOADS_DIR / f"playlist_{i:02d}"
        out.mkdir(parents=True, exist_ok=True)

        opts: dict = {
            "format": "bestaudio/best",
            "outtmpl": str(out / "%(title)s.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "match_filter": _under_one_hour,
            # watch?v=…&list=… URLs: download the full playlist, not only that video
            "noplaylist": False,
            "noprogress": False,
        }

        print(f"\n--- [{i}/{len(urls)}] {url}\n -> {out}/")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])


if __name__ == "__main__":
    main()
