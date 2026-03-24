"""Shared utilities for sources.json: load/save, formatting, entry templates."""

import json
import os
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent.parent.parent


def load_config() -> dict:
    """Load user config from config.json in the research root."""
    config_path = RESEARCH_DIR / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def load_sources(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def save_sources(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def next_id(sources: list[dict]) -> int:
    if not sources:
        return 1
    return max(s.get("id", 0) for s in sources) + 1


def new_entry_template(entry_id: int, doi: str | None = None, **overrides) -> dict:
    entry = {
        "id": entry_id,
        "title": None,
        "authors": [],
        "year": None,
        "doi": doi,
        "pmid": None,
        "journal": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "type": None,
        "found_via": None,
        "download": None,
        "status": "not-yet-read",
        "status_detail": None,
        "relevance_level": None,
        "relevance": None,
        "html_filename": None,
        "crossref_enriched": False,
    }
    entry.update(overrides)
    return entry


def format_journal_ref(s: dict) -> str:
    """Build a journal reference string like 'JACI 147(6):2263-2270'."""
    parts = []
    if s.get("journal"):
        parts.append(s["journal"])
    vol_issue = ""
    if s.get("volume"):
        vol_issue = s["volume"]
        if s.get("issue"):
            vol_issue += f"({s['issue']})"
        if s.get("pages"):
            vol_issue += f":{s['pages']}"
    if vol_issue:
        parts.append(vol_issue)
    return ", ".join(parts)


def format_authors(authors: list) -> str:
    if not authors:
        return "Unknown"
    return ", ".join(authors)


def format_author_short(s: dict) -> str:
    first_author = s["authors"][0] if s.get("authors") else "Unknown"
    if first_author.endswith(" et al."):
        return first_author
    short = first_author.split()[-1]
    if len(s.get("authors", [])) > 1:
        short += " et al."
    return short


def find_sources_json(start_dir: str | None = None) -> str | None:
    """Walk up from start_dir to find sources.json."""
    d = os.path.abspath(start_dir or os.getcwd())
    for _ in range(10):
        candidate = os.path.join(d, "sources.json")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None
