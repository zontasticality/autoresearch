# Research Harness

`~/Research` is a workspace for AI-assisted research. Each question gets a
folder; the agent researches inside it, writes the full result to a markdown
file there, and answers in the console with inline citations plus a link to
that file. (The user reads results in the console via T3 Code, not on GitHub
Pages.)

## Layout

```
~/Research/
├── AGENTS.md              ← this file (CLAUDE.md just imports it)
├── topics/                ← one folder per research question
│   └── YYYY-MM-DD-short-slug/
│       ├── report.md      ← the full write-up (what the console answer links to)
│       ├── notes.md       ← optional: working notes, deep-read extracts, scry SQL
│       ├── sources.json   ← every source used (schema below)
│       ├── *.pdf / *.epub ← full texts for this topic
│       └── *.txt          ← text extractions (regenerable, gitignored)
├── inbox/                 ← Anna's Archive download target; never leave files here
├── .annas-ledger.tsv      ← Anna's download log (daily budget, see below)
├── .bin/tools             ← helper scripts the agent runs (no user CLI)
├── config.json, .mcp.json ← user config + secrets (gitignored)
```

## Workflow

1. **Make the folder first.** `topics/$(date +%F)-<3-5-word-slug>/`. If the
   question continues an existing topic (`ls topics/`), work in that folder
   instead and add to its `report.md`. Short questions get a folder too.
2. **Clarify** only if the question is truly ambiguous; otherwise state your
   interpretation in the report and proceed.
3. **Discover** sources (see *Source ladder*). Log each source you rely on
   in `sources.json` as you go.
4. **Read.** Read abstracts/TOCs yourself. For full texts you need to quote,
   extract the text (see *Reading files*) and, for anything long, hand it to
   a sub-agent with: the question, the file path, and instructions to read
   the whole thing and return direct quotes **with page numbers**, the
   authors' stated limitations, and its relevance.
5. **Compute** where possible. If a public dataset or API answers the
   question directly (e.g. CDC data.cdc.gov Socrata, Europe PMC, OpenAlex),
   pull the numbers yourself and say so (`[MEASURED, my pull]`), recording
   the query in `notes.md`.
6. **Write `report.md`** (structure below), then **answer in the console**:
   a condensed version with the same inline citations, ending with
   `Full report: [report.md](<absolute path to topics/<slug>/report.md>)`
   (expand `~` to the real absolute path so it's clickable in T3 Code).

### `report.md` structure

```markdown
# <Question>
_YYYY-MM-DD · status: quick pass | in progress | thorough_

## Bottom line
2-5 sentences, hedged to the evidence.

## Findings
Sections by sub-question. Every factual claim cited inline.

## Confounders & caveats
What else could explain the result; measurement problems; selection effects.

## Gaps
What I looked for and couldn't find; what would change the conclusion.

## Sources
Numbered list matching sources.json ids (title, authors, year, DOI/URL, local file).
```

## Citations (console and report)

Cite **inline, at the claim**, never only in an end list.

- Format: `claim [TAG][V] ([Author Year, p. N](link))` or a direct quote:
  `"exact words" ([Author Year, p. N](link))`.
- **Link targets:** a URL for web sources; for local files, a path
  (`topics/<slug>/File.pdf#page=N` in the report, absolute path in the
  console). For quotes in a web page, a text-fragment URL
  (`url#:~:text=exact%20words`) is a cheap way to make the claim checkable.
- **Claim type tags:**
  - `[MEASURED]`: the source reports a direct measurement
  - `[INFERRED]`: the source infers it from data plus a model or theory
  - `[CLAIMED]`: asserted without evidence in that source
  - `[MY SYNTHESIS]`: you are connecting dots; also use it for your own arithmetic
- **Provenance tags:**
  - `[V]`: verbatim from text you actually read (full text, abstract, raw data)
  - `[2nd]`: from a search snippet, a WebFetch summary, or a secondary report.
    WebFetch runs pages through a small summarizer model, so its "quotes"
    are not verbatim. For a real quote, `curl` the page/API or read the file.
- No page numbers available (HTML, abstracts)? Say so once, don't invent them.

## Epistemic standards

Every claim has a chain: reality → measurement → authors' interpretation →
selection effects (why *this* paper reached you) → your reading → your
summary. Be paranoid about each link.

- "The authors found X", not "X is true". "Three papers report X" only
  counts as convergence if they don't share data, methods or citation chains.
- Hunt for **confounders** and **base rates**: compare any count to its
  denominator and to the background rate before calling it an effect.
- Report conflicts between sources with both sides cited; don't silently pick.
- Say what you couldn't find. Absence of evidence ≠ evidence of absence.
- Tell the user when you skip a source or are unsure about a finding.

## Source ladder (cheapest first)

The Anna's Archive key allows **25 downloads per day**. Spend them only on
full texts you will deep-read and can't get any other way.

1. **Already on disk:** `find ~/Research/topics -iname '*<keyword>*'`. Reuse
   across topics with a hard link (`ln`, not `cp`; symlinks break podman
   tools), and add the entry to this topic's `sources.json`.
2. **Discovery (free):** web search; **scry** (below) for forums, arXiv,
   LessWrong and prediction markets; OpenAlex
   (`https://api.openalex.org/works?search=...`, or
   `/works/doi:<DOI>` for abstract, citation count, references and
   `best_oa_location`) to follow citation chains.
3. **Open-access full text (free):** for papers, try:
   - arXiv (`/pdf/<id>`)
   - Europe PMC: `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:"<doi>"&resultType=core&format=json`
     gives the abstract, `pmcid` and `isOpenAccess`; then `/rest/<PMCID>/fullTextXML`
     for the full text. This works when publisher sites return 403.
   - Unpaywall: `https://api.unpaywall.org/v2/<doi>?email=<contact_email from config.json>`
   - NBER, SSRN, author pages
   Download with `curl -L -A "Mozilla/5.0" -o topics/<slug>/<Name - Author Year>.pdf`
   and check it with `file`.
4. **Anna's Archive (budgeted):** only for paywalled papers and books.
   - Before downloading, count today's use:
     `grep -c "^$(date +%F)" ~/Research/.annas-ledger.tsv`. Stop at 25 and tell the user.
   - After *every* attempt, successful or not, append
     `date<TAB>book|article<TAB>md5-or-doi<TAB>filename<TAB>ok|failed`.
   - Prefer EPUB over PDF for books (cleaner text extraction).
   - Downloads land in `inbox/`. Move them into the topic folder immediately
     and add a `sources.json` entry with `download.hash`.
   - `article_download` can fall back to SciDB and save an HTML landing page
     (`.htm`, about 170 KB) instead of a paper. Check with `file`; if it's
     HTML, delete it and log the attempt as `failed`.
   - If the anna-mcp tools error, say so and fall back to steps 2–3; don't retry in a loop.

### scry (`mcp.scry.io`)

SQL/Datalog over about 10^11 rows of Reddit, Hacker News, LessWrong, arXiv,
Stack Exchange, Wikipedia and prediction markets. Costs fractions of a cent
to a few cents per query. Use it for:
- discourse questions: who argues X, what are the positions on LessWrong or
  HN, first-person reports on Reddit
- counting or trending mentions over time
- sweeping arXiv for a concept across many papers
- market-implied probabilities

It does **not** replace journals or official statistics. Treat forum
content as `[CLAIMED]` anecdote. Call `schema` before writing SQL, always
use a literal `LIMIT`, record the SQL in `notes.md`, and cite rows by their
URI. It needs a one-time OAuth: if its tools are missing, tell the user to
run `/mcp` in an interactive Claude Code session.

## Reading files

- PDF: `pdftotext -layout F.pdf F.txt` puts a form feed between pages, so page N is
  `awk -v RS='\f' 'NR==N' F.txt`, and pages matching a pattern are
  `awk -v RS='\f' '/pattern/{print "p." NR}' F.txt`.
  These are PDF page indices. Check them against the printed page numbers
  before citing a journal page.
- EPUB: `pandoc F.epub -t plain -o F.txt` (no pages, so cite chapter/section).
- Scanned PDF with no text layer: say so. Look for another copy before
  spending an Anna's download on it.

## sources.json

One per topic. It's the record of what was used, and it makes downloads
restorable.

```json
{
  "session": {"title": "...", "date": "YYYY-MM-DD", "question": "..."},
  "sources": [{
    "id": 1, "title": "...", "authors": ["..."], "year": 2024,
    "doi": "10.x/...", "url": "https://...", "journal": "...",
    "type": "journal-article", "found_via": "how it was discovered",
    "download": {"hash": "<md5>", "format": "pdf", "filename": "Name - Author Year.pdf"},
    "status": "scouted-only | not-yet-read | read-partial | read-full | downloaded",
    "relevance_level": "LOW | MODERATE | MODERATE-HIGH | HIGH | VERY HIGH",
    "relevance": "one line"
  }]
}
```

- `download` is non-null only for Anna's downloads; that is what allows a
  restore. For open-access files, put the URL in `url` and set `download: null`.
- `~/Research/.bin/tools enrich --add <DOI> <topic>/sources.json` creates or fills an entry from CrossRef.
- **To restore downloads**, call `mcp__annas-mcp__book_download(hash, filename
  without extension, format)` for each non-null `download`. This counts
  against the daily budget.

## Helper scripts (`~/Research/.bin/tools`)

There is no user-facing command. The user only makes requests in
`~/Research`; you create folders and run these as needed. They take a
`sources.json` path or topic directory argument and default to the current
directory. Only `enrich` is routine; use the rest only when asked.

- `.bin/tools enrich [--add] <DOI> [sources.json] | --all`: CrossRef metadata.
- `.bin/tools sources [sources.json]`: render `sources.md` from `sources.json`.
- `.bin/tools sync [topic-dir]`: git commit and push the topic to a **private**
  GitHub repo. Repos stay private because the full texts are copyrighted.
- `.bin/tools pdf2html` / `.bin/tools fragment`: HTML plus text-fragment links for
  GitHub Pages. This is legacy; Pages needs a paid plan for private repos.

## Legacy topics

Folders created before 2026-10 contain their own `CLAUDE.md` (the old
session template) and `notes.md` / `summary.md` / `questions.md`. When
working in one, keep its existing files, but this AGENTS.md wins on output
format: inline citations in the console plus a link to the main markdown
file.
