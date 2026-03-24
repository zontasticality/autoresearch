"""Render sources.json to sources.md."""

import os
import sys

from . import sources as S


def format_source_entry(s: dict, pages_url: str | None) -> str:
    """Format a single source entry as markdown."""
    lines = []

    author_short = S.format_author_short(s)
    year = s.get("year", "n.d.")
    title_short = s.get("title", "Untitled")

    lines.append(f"### {s['id']}. {author_short} {year} — {title_short}")

    if s.get("html_filename") and pages_url:
        encoded = s["html_filename"].replace(" ", "%20")
        lines.append(f"- **HTML**: [View paper]({pages_url}/{encoded})")

    lines.append(f"- **Title**: {s.get('title', 'Unknown')}")
    lines.append(f"- **Authors**: {S.format_authors(s.get('authors', []))}")

    journal_ref = S.format_journal_ref(s)
    if journal_ref:
        lines.append(f"- **Journal**: {journal_ref}")

    lines.append(f"- **Year**: {year}")

    if s.get("doi"):
        lines.append(f"- **DOI**: {s['doi']}")
    if s.get("pmid"):
        lines.append(f"- **PMID**: {s['pmid']}")
    if s.get("found_via"):
        lines.append(f"- **Found via**: {s['found_via']}")

    status_parts = []
    if s.get("download"):
        status_parts.append("`[downloaded]`")
    if s.get("status"):
        detail = s.get("status_detail", "")
        status_str = s["status"]
        if detail:
            status_str += f": {detail}"
        status_parts.append(f"`[{status_str}]`")
    if status_parts:
        lines.append(f"- **Status**: {' '.join(status_parts)}")

    relevance_parts = []
    if s.get("relevance_level"):
        relevance_parts.append(f"**{s['relevance_level']}**.")
    if s.get("relevance"):
        relevance_parts.append(s["relevance"])
    if relevance_parts:
        lines.append(f"- **Relevance**: {' '.join(relevance_parts)}")

    return "\n".join(lines)


def main(args):
    sources_path = args.sources if hasattr(args, "sources") and args.sources else "./sources.json"

    data = S.load_sources(sources_path)
    session = data.get("session", {})
    sources_list = data.get("sources", [])
    pages_url = session.get("pages_url")
    title = session.get("title", "Research Session")

    downloaded = [s for s in sources_list if s.get("download")]
    web_only = [s for s in sources_list if not s.get("download")]

    lines = [f"# Sources — {title}", ""]

    if downloaded:
        lines.append("## Downloaded Papers")
        lines.append("")
        for s in downloaded:
            lines.append(format_source_entry(s, pages_url))
            lines.append("")

    if web_only:
        lines.append("## Additional Sources")
        lines.append("")
        for s in web_only:
            lines.append(format_source_entry(s, pages_url))
            lines.append("")

    lines.append("## Sources Not Yet Found / Gaps")
    lines.append("")
    lines.append("*(See questions.md for open gaps.)*")
    lines.append("")

    output = "\n".join(lines)

    out_dir = os.path.dirname(os.path.abspath(sources_path))
    out_path = os.path.join(out_dir, "sources.md")
    with open(out_path, "w") as f:
        f.write(output)

    print(f"Wrote {out_path} ({len(sources_list)} sources)")
