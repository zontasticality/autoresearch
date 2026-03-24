"""Convert PDFs to HTML with metadata bars, using sources.json."""

import html
import json
import os
import re
import subprocess
import sys

from . import sources as S

# CSS for the metadata bar
METADATA_CSS = """\
<style type="text/css">
/* Override pdf2htmlEX lazy-loading: force all page content visible
   so that browser text fragment matching (#:~:text=) works. */
@media screen { .pc { display: block !important; } }
.pf .pc { display: block !important; }

/* Override pdf2htmlEX scroll container: make body the scroll root.
   pdf2htmlEX makes #page-container an absolute-positioned overlay with
   overflow:auto, creating a nested scroll context. Text fragments only
   scroll the document root, so pages beyond the first are unreachable. */
@media screen {
  #page-container {
    position: static !important;
    overflow: visible !important;
    width: auto !important;
    height: auto !important;
    padding-top: 80px;
  }
  #sidebar { display: none !important; }
  body { overflow: auto; }
}

#metadata-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10000;
  background: #1a1a2e;
  color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  padding: 10px 20px;
  border-bottom: 3px solid #e94560;
  font-size: 13px;
  line-height: 1.5;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
#metadata-bar .meta-title {
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 2px;
}
#metadata-bar .meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 20px;
}
#metadata-bar .meta-item {
  white-space: nowrap;
}
#metadata-bar .meta-label {
  color: #8888aa;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
#metadata-bar .meta-value {
  color: #e0e0e0;
}
#metadata-bar a {
  color: #e94560;
  text-decoration: none;
}
#metadata-bar a:hover {
  text-decoration: underline;
}
#metadata-bar .meta-relevance {
  color: #0f3460;
  background: #e94560;
  padding: 1px 8px;
  border-radius: 3px;
  font-weight: 600;
  font-size: 11px;
}
#metadata-bar .meta-status {
  color: #16213e;
  background: #53d8fb;
  padding: 1px 8px;
  border-radius: 3px;
  font-weight: 600;
  font-size: 11px;
}
#metadata-bar .meta-home {
  float: right;
  color: #53d8fb;
  font-size: 12px;
  margin-top: 2px;
}
</style>
"""


def build_metadata_bar(source: dict) -> str:
    """Build the metadata bar HTML from a source entry."""
    e = html.escape
    title = e(source.get("title", "Unknown"))
    authors = e(", ".join(source.get("authors", ["Unknown"])))

    journal_parts = []
    if source.get("journal"):
        journal_parts.append(source["journal"])
    ref = S.format_journal_ref(source)
    # Include year in the bar
    vol = ""
    if source.get("volume"):
        vol = source["volume"]
        if source.get("issue"):
            vol += f"({source['issue']})"
        if source.get("pages"):
            vol += f":{source['pages']}"
    journal_parts_bar = []
    if source.get("journal"):
        journal_parts_bar.append(source["journal"])
    if vol:
        journal_parts_bar.append(vol)
    if source.get("year"):
        journal_parts_bar.append(str(source["year"]))
    journal = e(", ".join(journal_parts_bar))

    doi = source.get("doi", "")
    doi_html = ""
    if doi:
        doi_html = (
            f'<span class="meta-item">'
            f'<span class="meta-label">DOI:</span> '
            f'<span class="meta-value"><a href="https://doi.org/{e(doi)}" target="_blank">{e(doi)}</a></span>'
            f"</span>"
        )

    # Original source URL
    url = source.get("url", "")
    url_html = ""
    if url:
        url_html = (
            f'<span class="meta-item">'
            f'<span class="meta-label">Source:</span> '
            f'<span class="meta-value"><a href="{e(url)}" target="_blank">{e(url)}</a></span>'
            f"</span>"
        )

    # Anna's Archive link via download hash
    dl = source.get("download") or {}
    dl_hash = dl.get("hash", "")
    anna_html = ""
    if dl_hash:
        anna_url = f"https://annas-archive.pk/md5/{dl_hash}"
        anna_html = (
            f'<span class="meta-item">'
            f'<span class="meta-label">Archive:</span> '
            f'<span class="meta-value"><a href="{e(anna_url)}" target="_blank">Anna\'s Archive</a></span>'
            f"</span>"
        )

    status = source.get("status", "unknown")
    status_detail = source.get("status_detail", "")
    if status_detail:
        status = f"{status}: {status_detail}"

    relevance_html = ""
    if source.get("relevance_level"):
        rl = e(source["relevance_level"])
        relevance_text = e(source.get("relevance", "")) if source.get("relevance") else ""
        display = f"{rl} — {relevance_text}" if relevance_text else rl
        relevance_html = f'<span class="meta-item"><span class="meta-relevance">{e(display)}</span></span>'

    bar = (
        f'<div id="metadata-bar">'
        f'<a class="meta-home" href="index.html">&larr; Back to Index</a>'
        f'<div class="meta-title">{title}</div>'
        f'<div class="meta-row">'
        f'<span class="meta-item"><span class="meta-label">Authors:</span> <span class="meta-value">{authors}</span></span>'
        f'<span class="meta-item"><span class="meta-label">Journal:</span> <span class="meta-value">{journal}</span></span>'
        f"{doi_html}"
        f"{url_html}"
        f"{anna_html}"
        f'<span class="meta-item"><span class="meta-status">{e(status)}</span></span>'
        f"{relevance_html}"
        f"</div></div>"
    )
    return bar


def postprocess_html(html_content: str, source: dict) -> str:
    """Apply all pdf2htmlEX fixes and inject metadata."""
    html_content = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL)
    html_content = html_content.replace('class="pc ', 'class="pc opened ')
    html_content = html_content.replace("</head>", METADATA_CSS + "</head>", 1)
    bar = build_metadata_bar(source)
    html_content = html_content.replace("<body>", "<body>" + bar, 1)
    return html_content


def generate_index(session: dict, sources: list[dict], docs_dir: str):
    """Generate docs/index.html from session metadata and sources."""
    e = html.escape
    title = e(session.get("title", "Research Session"))
    date = e(session.get("date", ""))
    repo = session.get("github_repo", "")
    repo_url = f"https://github.com/{repo}" if repo else ""

    cards = []
    for s in sources:
        if not s.get("html_filename"):
            continue
        encoded = s["html_filename"].replace(" ", "%20")
        s_title = e(s.get("title", "Unknown"))
        authors = e(", ".join(s.get("authors", ["Unknown"])))

        journal_parts = []
        if s.get("journal"):
            journal_parts.append(s["journal"])
        vol = ""
        if s.get("volume"):
            vol = s["volume"]
            if s.get("issue"):
                vol += f"({s['issue']})"
            if s.get("pages"):
                vol += f":{s['pages']}"
        if vol:
            journal_parts.append(vol)
        if s.get("year"):
            journal_parts.append(str(s["year"]))
        journal = e(", ".join(journal_parts))

        doi_html = ""
        if s.get("doi"):
            doi_html = (
                f'<span class="doi">DOI: <a href="https://doi.org/{e(s["doi"])}" '
                f'target="_blank">{e(s["doi"])}</a></span>'
            )

        badges = ""
        status = s.get("status", "")
        if status:
            badges += f'<span class="badge badge-status">{e(status)}</span>'
        if s.get("relevance_level"):
            badges += f'<span class="badge badge-relevance">{e(s["relevance_level"])}</span>'

        relevance_text = ""
        if s.get("relevance"):
            relevance_text = f'<p class="relevance-text">{e(s["relevance"])}</p>'

        cards.append(f"""\
    <div class="paper-card">
      <a class="paper-link" href="{encoded}">
        {s_title}
      </a>
      <div class="paper-meta">
        {authors} &middot; {journal}
        {f"&middot; {doi_html}" if doi_html else ""}
      </div>
      <div class="paper-meta">
        {badges}
      </div>
      {relevance_text}
    </div>""")

    subtitle_repo = ""
    if repo_url:
        subtitle_repo = f' &mdash; <a href="{e(repo_url)}">GitHub repo</a>'

    index_html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Source Papers</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0f0f23;
      color: #e0e0e0;
      padding: 40px 20px;
      line-height: 1.6;
    }}
    .container {{ max-width: 800px; margin: 0 auto; }}
    h1 {{
      font-size: 28px;
      color: #ffffff;
      margin-bottom: 8px;
    }}
    .subtitle {{
      color: #8888aa;
      font-size: 14px;
      margin-bottom: 30px;
    }}
    .subtitle a {{ color: #53d8fb; text-decoration: none; }}
    .subtitle a:hover {{ text-decoration: underline; }}
    .paper-card {{
      background: #1a1a2e;
      border: 1px solid #2a2a4a;
      border-radius: 8px;
      padding: 20px 24px;
      margin-bottom: 16px;
      transition: border-color 0.2s;
    }}
    .paper-card:hover {{ border-color: #e94560; }}
    .paper-card a.paper-link {{
      font-size: 18px;
      font-weight: 600;
      color: #ffffff;
      text-decoration: none;
    }}
    .paper-card a.paper-link:hover {{ color: #e94560; }}
    .paper-meta {{
      margin-top: 6px;
      font-size: 13px;
      color: #8888aa;
    }}
    .paper-meta .doi a {{ color: #e94560; text-decoration: none; }}
    .paper-meta .doi a:hover {{ text-decoration: underline; }}
    .badge {{
      display: inline-block;
      padding: 1px 8px;
      border-radius: 3px;
      font-size: 11px;
      font-weight: 600;
      margin-right: 6px;
    }}
    .badge-status {{ background: #53d8fb; color: #16213e; }}
    .badge-relevance {{ background: #e94560; color: #0f3460; }}
    .relevance-text {{
      margin-top: 8px;
      font-size: 13px;
      color: #b0b0cc;
      font-style: italic;
    }}
    .session-info {{
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #2a2a4a;
      font-size: 13px;
      color: #666680;
    }}
    .session-info a {{ color: #53d8fb; text-decoration: none; }}
    .session-info a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>{title}</h1>
    <p class="subtitle">
      Research session ({date}){subtitle_repo}
    </p>

{"".join(cards)}

    <div class="session-info">
      <p>
        These PDFs were converted to HTML via
        <a href="https://github.com/coolwanglu/pdf2htmlEX">pdf2htmlEX</a> and
        include metadata bars with source information from the research session.
        Direct quotes in the session notes link here using
        <a href="https://developer.mozilla.org/en-US/docs/Web/Text_Fragments">text fragments</a>.
      </p>
    </div>
  </div>
</body>
</html>
"""
    with open(os.path.join(docs_dir, "index.html"), "w") as f:
        f.write(index_html)


def ensure_gitignore(session_dir: str):
    """Ensure .gitignore has docs/ exceptions."""
    gitignore_path = os.path.join(session_dir, ".gitignore")
    content = ""
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            content = f.read()

    additions = []
    if "!docs/" not in content:
        additions.append("!docs/")
    if "!docs/**" not in content:
        additions.append("!docs/**")

    if additions:
        with open(gitignore_path, "a") as f:
            f.write("\n# Allow HTML docs to be committed\n")
            for line in additions:
                f.write(line + "\n")


def main(args):
    force = args.force if hasattr(args, "force") else False
    session_dir = os.path.abspath(args.dir if hasattr(args, "dir") and args.dir else ".")

    sources_path = os.path.join(session_dir, "sources.json")
    docs_dir = os.path.join(session_dir, "docs")

    if not os.path.exists(sources_path):
        print(f"Error: {sources_path} not found", file=sys.stderr)
        sys.exit(1)

    data = S.load_sources(sources_path)
    session = data.get("session", {})
    sources_list = data.get("sources", [])

    os.makedirs(docs_dir, exist_ok=True)

    converted_count = 0
    for source in sources_list:
        dl = source.get("download")
        if not dl or dl.get("format") != "pdf":
            continue

        filename = dl.get("filename", "")
        pdf_path = os.path.join(session_dir, filename)

        if not os.path.exists(pdf_path):
            print(f"  Skipping {filename} — PDF not found")
            continue

        stem = os.path.splitext(filename)[0]
        html_filename = f"{stem}.html"
        html_path = os.path.join(docs_dir, html_filename)

        if not force and os.path.exists(html_path):
            if os.path.getmtime(html_path) > os.path.getmtime(pdf_path):
                print(f"  Skipping {filename} — HTML is newer (use --force to reconvert)")
                source["html_filename"] = html_filename
                continue

        print(f"  Converting {filename}...")
        result = subprocess.run(
            [
                "podman", "run", "--rm",
                "-v", f"{session_dir}:/pdf:ro",
                "-v", f"{docs_dir}:/out",
                "bwits/pdf2htmlex",
                "pdf2htmlEX", "--zoom", "1.3", "--dest-dir", "/out",
                f"/pdf/{filename}",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  Error converting {filename}: {result.stderr}", file=sys.stderr)
            continue

        print(f"  Post-processing {html_filename}...")
        with open(html_path, "r") as f:
            content = f.read()

        content = postprocess_html(content, source)

        with open(html_path, "w") as f:
            f.write(content)

        source["html_filename"] = html_filename
        converted_count += 1
        print(f"  Done: {html_filename}")

    S.save_sources(sources_path, data)

    print("  Generating index.html...")
    generate_index(session, sources_list, docs_dir)

    ensure_gitignore(session_dir)

    print(f"Converted {converted_count} PDFs. Index updated.")
