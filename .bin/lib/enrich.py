"""CrossRef enrichment: fetch metadata by DOI and enrich sources.json entries."""

import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import json

from . import sources as S

CROSSREF_API = "https://api.crossref.org/works/"
def _user_agent():
    cfg = S.load_config()
    email = cfg.get("contact_email", "user@example.com")
    return f"ResearchToolchain/1.0 (mailto:{email})"
RATE_LIMIT_SEC = 1.0

_last_request_time = 0.0


def fetch_crossref(doi: str) -> dict | None:
    """Fetch metadata for a DOI from the CrossRef API."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_SEC:
        time.sleep(RATE_LIMIT_SEC - elapsed)

    url = CROSSREF_API + urllib.parse.quote(doi, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            _last_request_time = time.time()
            return data.get("message", {})
    except urllib.error.HTTPError as e:
        print(f"  CrossRef HTTP {e.code} for {doi}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  CrossRef error for {doi}: {e}", file=sys.stderr)
        return None


def extract_fields(msg: dict) -> dict:
    """Extract relevant fields from a CrossRef API response message."""
    fields = {}

    titles = msg.get("title", [])
    if titles:
        fields["title"] = titles[0]

    authors = []
    for a in msg.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        name = f"{given} {family}".strip()
        if name:
            authors.append(name)
    if authors:
        fields["authors"] = authors

    for date_field in ("published-print", "published-online", "issued"):
        parts = msg.get(date_field, {}).get("date-parts", [[]])
        if parts and parts[0] and parts[0][0]:
            fields["year"] = parts[0][0]
            break

    containers = msg.get("container-title", [])
    if containers:
        fields["journal"] = containers[0]

    if msg.get("volume"):
        fields["volume"] = msg["volume"]
    if msg.get("issue"):
        fields["issue"] = msg["issue"]
    if msg.get("page"):
        fields["pages"] = msg["page"]
    if msg.get("type"):
        fields["type"] = msg["type"]

    return fields


def enrich_entry(entry: dict, cr_fields: dict) -> bool:
    """Fill null/missing fields in entry from CrossRef data. Returns True if changed."""
    changed = False
    for key, value in cr_fields.items():
        current = entry.get(key)
        if current is None or current == "" or current == []:
            entry[key] = value
            changed = True
    entry["crossref_enriched"] = True
    return changed


def main(args):
    sources_path = args.sources or "./sources.json"
    data = S.load_sources(sources_path)
    sources_list = data.get("sources", [])

    if args.all:
        count = 0
        for entry in sources_list:
            if entry.get("doi") and not entry.get("crossref_enriched"):
                print(f"  Enriching #{entry['id']}: {entry.get('doi')}")
                msg = fetch_crossref(entry["doi"])
                if msg:
                    cr_fields = extract_fields(msg)
                    enrich_entry(entry, cr_fields)
                    count += 1
        S.save_sources(sources_path, data)
        print(f"Enriched {count} entries.")
    elif args.add:
        doi = args.doi
        print(f"  Fetching CrossRef for {doi}...")
        msg = fetch_crossref(doi)
        if not msg:
            print("Error: could not fetch CrossRef data", file=sys.stderr)
            sys.exit(1)
        cr_fields = extract_fields(msg)
        nid = S.next_id(sources_list)
        entry = S.new_entry_template(nid, doi=doi, crossref_enriched=True)
        enrich_entry(entry, cr_fields)
        sources_list.append(entry)
        data["sources"] = sources_list
        S.save_sources(sources_path, data)
        print(f"Added source #{nid}: {entry.get('title', doi)}")
    else:
        doi = args.doi
        found = False
        for entry in sources_list:
            if entry.get("doi") == doi:
                found = True
                print(f"  Enriching #{entry['id']}: {doi}")
                msg = fetch_crossref(doi)
                if msg:
                    cr_fields = extract_fields(msg)
                    enrich_entry(entry, cr_fields)
                    S.save_sources(sources_path, data)
                    print("  Done.")
                break
        if not found:
            print(f"Error: no entry with DOI {doi} found. Use --add to create.", file=sys.stderr)
            sys.exit(1)
