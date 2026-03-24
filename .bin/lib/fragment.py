"""Generate text fragment URLs for quotes in pdf2htmlEX output."""

import html.parser
import json
import os
import re
import sys
import urllib.parse

# Common ligature replacements found in PDF text
LIGATURES = {
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb00": "ff",
    "\u0132": "IJ",
    "\u0133": "ij",
    "\ufb06": "st",
    "\ufb05": "st",  # long s + t
}

# PUA character class used by pdf2htmlEX for font-specific ligatures
_PUA = "[\uE000-\uF8FF]"

# ASCII ligature sequences and their regex alternatives (longest first)
_LIGATURE_ALTS = [
    ("ffi", f"(?:ffi|f{_PUA}|{_PUA})"),
    ("ffl", f"(?:ffl|f{_PUA}|{_PUA})"),
    ("fi", f"(?:fi|{_PUA})"),
    ("fl", f"(?:fl|{_PUA})"),
    ("ff", f"(?:ff|{_PUA})"),
]


def replace_ligatures(text: str) -> str:
    for lig, repl in LIGATURES.items():
        text = text.replace(lig, repl)
    return text


def normalize(text: str) -> str:
    """Normalize text for URL generation: replace Unicode ligatures, collapse whitespace.
    Preserves PUA characters (needed for browser text fragment matching)."""
    text = replace_ligatures(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _quote_to_regex(quote: str) -> re.Pattern:
    """Build a regex from a quote that matches PUA ligatures in pdf2htmlEX output.

    Converts ASCII ligature sequences (fi, fl, ff, ffi, ffl) into patterns
    that also match PUA characters at those positions.
    """
    text = replace_ligatures(quote)
    parts: list[str] = []
    i = 0
    while i < len(text):
        matched = False
        for lig_str, lig_pat in _LIGATURE_ALTS:
            if text[i : i + len(lig_str)] == lig_str:
                parts.append(lig_pat)
                i += len(lig_str)
                matched = True
                break
        if not matched:
            ch = text[i]
            if ch.isspace():
                parts.append(r"\s+")
            else:
                parts.append(re.escape(ch))
            i += 1
    return re.compile("".join(parts), re.IGNORECASE)


class DivTextExtractor(html.parser.HTMLParser):
    """Extract text content from <div class="t ..."> elements in pdf2htmlEX output."""

    def __init__(self):
        super().__init__()
        self.divs: list[str] = []
        self._in_t_div = False
        self._depth = 0
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            attr_dict = dict(attrs)
            classes = attr_dict.get("class", "").split()
            if "t" in classes and not self._in_t_div:
                self._in_t_div = True
                self._depth = 1
                self._current_text = []
            elif self._in_t_div:
                self._depth += 1

    def handle_endtag(self, tag):
        if tag == "div" and self._in_t_div:
            self._depth -= 1
            if self._depth == 0:
                self._in_t_div = False
                text = "".join(self._current_text)
                self.divs.append(text)

    def handle_data(self, data):
        if self._in_t_div:
            self._current_text.append(data)


def extract_div_texts(html_content: str) -> list[str]:
    parser = DivTextExtractor()
    parser.feed(html_content)
    return parser.divs


def find_quote_in_divs(
    divs: list[str], quote: str
) -> tuple[int, int, str] | None:
    """Find which div range contains the quote.
    Returns (start_div_index, end_div_index, raw_matched_text) or None.
    The raw matched text preserves PUA characters for URL generation.
    """
    pattern = _quote_to_regex(quote)

    # Try single-div match
    for i, div_text in enumerate(divs):
        m = pattern.search(div_text)
        if m:
            return (i, i, div_text[m.start() : m.end()])

    # Try multi-div match
    for start in range(len(divs)):
        combined = ""
        for end in range(start, min(start + 50, len(divs))):
            if combined:
                combined += " "
            combined += divs[end]
            m = pattern.search(combined)
            if m:
                return (start, end, combined[m.start() : m.end()])

    return None


def url_encode_text(text: str) -> str:
    return urllib.parse.quote(text, safe="")


def make_text_fragment(raw_match: str) -> str:
    """Build the text= fragment value from raw matched text.
    Uses raw text (with PUA chars) so the browser can match against the DOM."""
    # Collapse whitespace but preserve PUA characters
    text = re.sub(r"\s+", " ", raw_match).strip()

    words = text.split()
    if len(words) <= 8:
        return f"text={url_encode_text(text)}"

    prefix = " ".join(words[:4])
    suffix = " ".join(words[-4:])
    return f"text={url_encode_text(prefix)},{url_encode_text(suffix)}"


def get_pages_url(sources_path: str | None) -> str | None:
    if not sources_path:
        return None
    try:
        with open(sources_path, "r") as f:
            data = json.load(f)
        return data.get("session", {}).get("pages_url")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main(args):
    html_file = args.file
    quote = args.quote
    sources_path = args.sources if hasattr(args, "sources") and args.sources else None

    # Auto-detect sources.json
    if not sources_path:
        html_dir = os.path.dirname(os.path.abspath(html_file))
        for candidate in [
            os.path.join(html_dir, "sources.json"),
            os.path.join(os.path.dirname(html_dir), "sources.json"),
        ]:
            if os.path.exists(candidate):
                sources_path = candidate
                break

    with open(html_file, "r") as f:
        content = f.read()

    divs = extract_div_texts(content)
    if not divs:
        print("Error: no text divs found in HTML file", file=sys.stderr)
        sys.exit(1)

    result = find_quote_in_divs(divs, quote)
    if result is None:
        print(f"Error: quote not found in {html_file}", file=sys.stderr)
        print(f'  Quote: "{quote[:80]}..."', file=sys.stderr)
        sys.exit(1)

    start, end, raw_match = result
    fragment = make_text_fragment(raw_match)

    pages_url = get_pages_url(sources_path)
    filename = os.path.basename(html_file)
    encoded_filename = urllib.parse.quote(filename, safe="")

    if pages_url:
        url = f"{pages_url}/{encoded_filename}#:~:{fragment}"
    else:
        url = f"{encoded_filename}#:~:{fragment}"

    print(url)
