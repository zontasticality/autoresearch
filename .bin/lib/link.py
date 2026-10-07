"""Citation links that land on the passage, with archive fallbacks.

  .bin/tools link <url|docs/file.html> "<passage>"   print a verified text-fragment link
  .bin/tools link --check <file.md>                  re-verify every fragment link in a file
  .bin/tools archive <url> [--submit]                find (or request) an archived copy

Web pages are fetched with urllib (cached for a day in ~/.cache/research-link).
If the original is blocked, paywalled, or doesn't contain the passage, the
latest Wayback snapshot with HTTP 200 and then archive.today are tried; the
link goes to the first copy that actually contains the passage.
"""

import hashlib
import html.parser
import json
import os
import re
import sys
import time
import gzip
import urllib.error
import urllib.parse
import urllib.request
import zlib

from . import fragment as pdffrag

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
CACHE = os.path.expanduser("~/.cache/research-link")
CACHE_TTL = 24 * 3600


class LinkError(Exception):
    pass


# --- fetching -----------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http(url: str, data: dict | None = None, timeout: int = 60,
         follow: bool = True) -> tuple[int, str, dict]:
    """(status, body text, headers) via urllib; never raises for HTTP errors.

    Uses Python's own HTTP client rather than curl: the curl found on PATH
    under some interpreters here is broken (libcurl version mismatch).
    """
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Encoding": "gzip, deflate"})
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
    try:
        resp = opener.open(req, timeout=timeout)
        code, raw, headers = resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        code, headers = e.code, dict(e.headers or {})
        try:
            raw = e.read()
        except Exception:
            raw = b""
    except Exception:
        return 0, "", {}
    enc_hdr = {k.lower(): v for k, v in headers.items()}.get("content-encoding", "")
    try:
        if raw[:2] == b"\x1f\x8b" or "gzip" in enc_hdr:
            raw = gzip.decompress(raw)
        elif "deflate" in enc_hdr:
            raw = zlib.decompress(raw)
    except Exception:
        pass
    ctype = {k.lower(): v for k, v in headers.items()}.get("content-type", "")
    m = re.search(r"charset=([\w-]+)", ctype)
    try:
        text = raw.decode(m.group(1) if m else "utf-8", errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")
    return code, text, headers


def fetch(url: str, timeout: int = 60) -> tuple[int, str]:
    """(HTTP status, body). Successful responses are cached for a day."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest())
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < CACHE_TTL:
        with open(path, encoding="utf-8", errors="replace") as f:
            return 200, f.read()
    code, text, _ = http(url, timeout=timeout)
    if code == 200 and text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return code, text


# --- text extraction ----------------------------------------------------------

BLOCK = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "br",
         "blockquote", "section", "article", "header", "footer", "td", "th", "tr",
         "table", "figcaption", "figure", "pre", "hr", "dd", "dt", "main", "nav",
         "aside", "form", "button", "label", "option", "select", "summary", "details"}
SKIP = {"script", "style", "noscript", "template", "svg", "head", "iframe", "textarea"}


class _Extract(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def page_text(html_content: str) -> str:
    """Visible text, one line per block element (text fragments can't cross blocks)."""
    p = _Extract()
    p.feed(html_content)
    lines = []
    for line in "".join(p.parts).split("\n"):
        line = re.sub(r"[ \t\r\f\v ​]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def is_pdf2htmlex(html_content: str) -> bool:
    return "pdf2htmlEX" in html_content[:5000] or 'class="t ' in html_content


# --- matching -----------------------------------------------------------------

_TRANS = {"‘": "'", "’": "'", "‛": "'", "′": "'", "“": '"',
          "”": '"', "„": '"', "″": '"', "–": "-", "—": "-",
          "‑": "-", "−": "-", "‐": "-", " ": " ", "…": "...",
          "­": ""}


def normalize(s: str) -> tuple[str, list[int]]:
    """Lowercased, quote/dash-folded, whitespace-collapsed copy plus an index map into s."""
    out, idx = [], []
    prev_space = False
    for i, c in enumerate(s):
        c2 = _TRANS.get(c, c)
        if not c2:
            continue
        if c2.isspace():
            if prev_space:
                continue
            c2, prev_space = " ", True
        else:
            prev_space = False
        for ch in c2.lower():
            out.append(ch)
            idx.append(i)
    return "".join(out), idx


def enc(term: str) -> str:
    """Percent-encode a text-directive term (`-`, `,`, `&` are syntax)."""
    return urllib.parse.quote(term, safe="").replace("-", "%2D")


def build_fragment(text: str, passage: str) -> tuple[str, int]:
    """Return (`text=...` directive, number of occurrences) for passage in text.

    The directive is built from the page's own characters. Long passages become
    `text=start,end`; the start term is grown until its first occurrence is the
    passage, the end term until its first match after the start ends the passage.
    """
    ntext, idx = normalize(text)
    nq = normalize(passage.strip())[0]
    if not nq:
        raise LinkError("empty passage")
    pos = ntext.find(nq)
    if pos < 0:
        raise LinkError("passage not found")
    count = ntext.count(nq)
    o_start, o_end = idx[pos], idx[pos + len(nq) - 1] + 1
    sub = text[o_start:o_end].replace("­", "")
    lines = sub.split("\n")
    words = sub.split()
    if len(lines) == 1 and len(words) <= 10:
        return "text=" + enc(" ".join(words)), count

    first, last = lines[0].split(), lines[-1].split()
    start = None
    for k in range(min(4, len(first)), min(len(first), 14) + 1):
        cand = " ".join(first[:k])
        if ntext.find(normalize(cand)[0]) == pos:
            start = cand
            break
    if start is None:
        raise LinkError("the start of the passage also occurs earlier on the page; "
                        "begin the passage with more distinctive words")
    after = pos + len(normalize(start)[0])
    end_target = pos + len(nq)
    for k in range(min(3, len(last)), min(len(last), 12) + 1):
        cand = " ".join(last[-k:])
        nc = normalize(cand)[0]
        p = ntext.find(nc, after)
        if p >= 0 and p + len(nc) == end_target:
            if cand == start:
                return "text=" + enc(start), count
            return f"text={enc(start)},{enc(cand)}", count
    raise LinkError("could not find a clean end term; shorten the passage")


def _local_fragment(path: str, passage: str) -> tuple[str, int]:
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    if is_pdf2htmlex(content):
        divs = pdffrag.extract_div_texts(content)
        hit = pdffrag.find_quote_in_divs(divs, passage)
        if hit is None:
            raise LinkError("passage not found (try a shorter passage without hyphenated line breaks)")
        return pdffrag.make_text_fragment(hit[2]), 1
    return build_fragment(page_text(content), passage)


# --- archives -----------------------------------------------------------------

def wayback_latest(url: str) -> str | None:
    """Timestamp of the latest Wayback capture with HTTP 200, None if none, 'ERR' on failure."""
    q = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(
        {"url": url, "output": "json", "fl": "timestamp,statuscode",
         "filter": "statuscode:200", "limit": "-1"})
    for _ in range(3):
        code, text, _ = http(q, timeout=90)
        try:
            d = json.loads(text)
            return d[-1][0] if len(d) > 1 else None
        except (json.JSONDecodeError, IndexError):
            continue
    return "ERR"


def archive_today(url: str) -> str | None:
    """URL of the newest archive.today snapshot, if any."""
    code, _, headers = http("https://archive.is/newest/" + url, timeout=40, follow=False)
    loc = {k.lower(): v for k, v in headers.items()}.get("location", "")
    return loc if 300 <= code < 400 and "archive." in loc else None


def _archive_candidates(url: str):
    ts = wayback_latest(url)
    if ts and ts != "ERR":
        yield ("Wayback " + ts, f"https://web.archive.org/web/{ts}/{url}",
               f"https://web.archive.org/web/{ts}id_/{url}")
    snap = archive_today(url)
    if snap:
        yield ("archive.today", snap, snap)


def spn_submit(url: str) -> str | None:
    """Ask Wayback Save Page Now to capture url (the POST form; GET /save/<url> fails)."""
    _, text, _ = http("https://web.archive.org/save/", data={"url": url, "capture_all": "on"},
                      timeout=120)
    m = re.search(r"spn2-[0-9a-f]+", text)
    return m.group(0) if m else None


def spn_status(job: str) -> dict:
    _, text, _ = http(f"https://web.archive.org/save/status/{job}", timeout=60)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"status": "unknown"}


# --- commands -----------------------------------------------------------------

def make_link(target: str, passage: str, use_archives: bool = True) -> tuple[str, list[str]]:
    """Return (link, notes)."""
    notes: list[str] = []
    if not re.match(r"https?://", target):
        if not os.path.exists(target):
            raise LinkError(f"no such file: {target}")
        frag, count = _local_fragment(target, passage)
        if count > 1:
            notes.append(f"passage occurs {count} times; linked the first")
        return f"{urllib.parse.quote(target, safe='/')}#:~:{frag}", notes

    code, body = fetch(target)
    reason = f"HTTP {code}"
    if code == 200 and body:
        try:
            frag, count = build_fragment(page_text(body), passage)
            if count > 1:
                notes.append(f"passage occurs {count} times; linked the first")
            return f"{target}#:~:{frag}", notes
        except LinkError as e:
            reason = f"HTTP 200 but {e}"
    if not use_archives:
        raise LinkError(reason)
    for label, link_base, raw_url in _archive_candidates(target):
        c2, b2 = fetch(raw_url)
        if c2 != 200 or not b2:
            continue
        try:
            frag, count = build_fragment(page_text(b2), passage)
        except LinkError:
            continue
        notes.append(f"original: {reason}; linked {label} copy (link the original too)")
        if count > 1:
            notes.append(f"passage occurs {count} times; linked the first")
        return f"{link_base}#:~:{frag}", notes
    raise LinkError(f"{reason}; no archived copy contains the passage "
                    f"(try `.bin/tools archive {target} --submit`)")


def _parse_directive(frag: str) -> list[str]:
    """Terms of a text directive, ignoring prefix-/-suffix context terms."""
    parts = frag.split(",")
    terms = []
    for p in parts:
        t = urllib.parse.unquote(p)
        if p.endswith("-") or p.startswith("-"):
            continue
        terms.append(t)
    return terms


def check_file(md_path: str) -> int:
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    base_dir = os.path.dirname(os.path.abspath(md_path))
    links = re.findall(r"\]\(([^)\s]+#:~:text=[^)\s]+)\)", md)
    texts: dict[str, str | None] = {}
    bad = 0
    for link in links:
        base, frag = link.split("#:~:text=", 1)
        if base not in texts:
            if re.match(r"https?://", base):
                raw = re.sub(r"^(https://web\.archive\.org/web/\d+)/", r"\1id_/", base)
                code, body = fetch(raw)
                texts[base] = page_text(body) if code == 200 and body else None
            else:
                path = os.path.join(base_dir, urllib.parse.unquote(base))
                if not os.path.exists(path):
                    texts[base] = None
                else:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    if is_pdf2htmlex(content):
                        texts[base] = " ".join(pdffrag.extract_div_texts(content))
                    else:
                        texts[base] = page_text(content)
        text = texts[base]
        if text is None:
            print(f"UNREACHABLE  {base}")
            bad += 1
            continue
        ntext = normalize(text)[0]
        terms = _parse_directive(frag)
        p = ntext.find(normalize(terms[0])[0])
        ok = p >= 0
        if ok and len(terms) > 1:
            ok = ntext.find(normalize(terms[-1])[0], p) >= 0
        if not ok:
            print(f"NOT FOUND    {base}  {[t[:60] for t in terms]}")
            bad += 1
    print(f"{len(links)} fragment links checked, {bad} problems")
    return 1 if bad else 0


def main(args):
    if args.check:
        sys.exit(check_file(args.check))
    if not args.target or args.passage is None:
        print('usage: .bin/tools link <url|docs/file.html> "<passage>"  |  link --check <file.md>',
              file=sys.stderr)
        sys.exit(2)
    try:
        link, notes = make_link(args.target, args.passage, use_archives=not args.no_archive)
    except LinkError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(link)
    for n in notes:
        print(f"note: {n}", file=sys.stderr)


def archive_main(args):
    url = args.url
    ts = wayback_latest(url)
    snap = archive_today(url)
    print(f"Wayback (HTTP 200): {'https://web.archive.org/web/' + ts + '/' + url if ts and ts != 'ERR' else ('lookup failed' if ts == 'ERR' else 'none')}")
    print(f"archive.today:      {snap or 'none'}")
    if not args.submit:
        return
    if ts and ts != "ERR" and not args.force:
        print("Already in Wayback; not submitting (use --force to re-capture).")
        return
    job = spn_submit(url)
    if not job:
        print("Save Page Now gave no job id (rate-limited or refused).", file=sys.stderr)
        sys.exit(1)
    print(f"Submitted: {job}")
    deadline = time.time() + args.wait
    st = {"status": "pending"}
    while time.time() < deadline:
        time.sleep(10)
        st = spn_status(job)
        if st.get("status") in ("success", "error"):
            break
    status = st.get("status")
    if status == "success":
        hs = st.get("http_status")
        print(f"Captured: https://web.archive.org/web/{st.get('timestamp')}/{url} (HTTP {hs})")
        if hs and int(hs) != 200:
            print("Warning: the capture is an error page (the site blocks crawlers); "
                  "check archive.today instead.", file=sys.stderr)
    elif status == "error":
        print(f"Capture failed: {st.get('message', st)}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Still {status} after {args.wait}s; check later: "
              f"https://web.archive.org/save/status/{job}")
