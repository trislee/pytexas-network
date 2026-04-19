"""Repo-root paths shared by pipeline scripts."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
YOUTUBE_LINKS_FILE = REPO_ROOT / "youtube_links.txt"
DOWNLOADS_DIR = REPO_ROOT / "downloads"
TRANSCRIPTS_DB = REPO_ROOT / "transcripts.sqlite"
ENTITIES_BY_COUNT_CONSOLIDATED_TSV = REPO_ROOT / "entities_by_count_consolidated.tsv"
ENTITY_CONSOLIDATIONS_JSON = REPO_ROOT / "entity_consolidations.json"
GRAPH_GRAPHML = REPO_ROOT / "entity_graph.graphml"
