# Research Harness

`~/Research` is a workspace for AI-assisted research. Each question gets a
folder under `topics/`. The agent researches there, writes `report.md`, and
answers in the console (the user reads in T3 Code) with a condensed version
that links to it.

## Layout

```
~/Research/
├── AGENTS.md                ← this file (CLAUDE.md imports it)
├── topics/YYYY-MM-DD-slug/
│   ├── report.md            ← the write-up the console answer links to
│   ├── notes.md             ← working notes, deep-read extracts, SQL/API queries
│   ├── sources.json         ← record of every source used
│   ├── docs/                ← local HTML copies of PDFs, for fragment links
│   └── *.pdf *.epub *.txt   ← full texts and extractions (gitignored)
├── inbox/                   ← Anna's Archive downloads land here; move them out
├── .annas-ledger.tsv        ← Anna's download log
├── .bin/tools               ← helper scripts (agent-only, see below)
└── config.json, .mcp.json   ← config and secrets (gitignored)
```

Folders from before 2026-10 have their own `CLAUDE.md`, `summary.md`, and so
on. Keep those files when working in one, but follow this file for output.

## Workflow

1. **Make the folder first:** `topics/$(date +%F)-<3-5-word-slug>/`, even
   for short questions. If the question continues a topic (`ls topics/`),
   extend that topic's `report.md` instead.
2. **Clarify** only if the question is truly ambiguous. Otherwise state your
   interpretation in the report and proceed.
3. **Find sources** (see *Source ladder*). Add each one you rely on to
   `sources.json` as you go.
4. **Read.** Read abstracts and TOCs yourself.
   - Hand long full texts to a sub-agent with the question and the file path.
   - It reads the whole thing and returns exact quotes (curly quotes and
     dashes kept) with page numbers and the source URL, plus the authors'
     stated limitations and the source's relevance.
5. **Compute** where a public dataset or API answers directly (OpenAlex,
   Europe PMC, data.cdc.gov, …). Pull the numbers yourself, tag them
   `[MEASURED, my pull]`, and record the query in `notes.md`.
6. **Write `report.md`**, run `.bin/tools link --check report.md`, then answer
   in the console with a condensed version ending
   `Full report: [report.md](<absolute path>)`.

### `report.md`

```markdown
# <Question>
_YYYY-MM-DD · status: quick pass | in progress | thorough_

## Bottom line
## Findings
## Confounders & caveats
## Gaps
```

- **Bottom line:** short bullets, hedged to the evidence. This is often the
  only part anyone reads, so every claim links to its evidence. No tags here;
  the links carry it.
- **Findings:** sections by sub-question. Every factual claim is tagged and
  linked.
- **Confounders & caveats:** what else could explain the result; measurement
  problems; selection effects.
- **Gaps:** what you looked for and couldn't find; what would change the
  conclusion.
- No source list at the end. `sources.json` is the record.

## Citations

Cite inline, at the claim, in both the report and the console answer.

- **Link the words that name the thing** ("Pinker's RAND citation", "the
  2019 tweet"). The prose should read the same with the links removed.
  - Quote directly only when the exact wording is itself the point:
    `"exact words" ([Author Year, p. N](link))`.
- **Links land on the passage, not just the page.** Make them with
  `.bin/tools link <url> "<passage>"`.
  - It fetches the page, checks the passage is there, and prints a
    text-fragment URL.
  - If the original is blocked or paywalled, it falls back to a Wayback or
    archive.today copy that contains the passage. Link the original as well.
  - If no copy has the text, run `.bin/tools archive <url> --submit`, link
    the original, and say where you read the text.
- **By source type:**
  - **PDFs:** the original URL with `#page=N`. Where the wording matters,
    also make a local copy with `.bin/tools pdf2html --file <pdf>` and link
    it with `.bin/tools link docs/<file>.html "<passage>"`.
  - **Tweets:** the status URL. X doesn't support text fragments.
  - **Google Books snippets:**
    `https://books.google.com/books?id=<id>&q=%22<phrase>%22`, plus the page
    number.
  - **Local files:** paths relative to `report.md` in the report; absolute
    paths in the console.
- **Tags** (in Findings):
  - **Claim:**
    - `[MEASURED]`: the source reports a direct measurement.
    - `[INFERRED]`: inferred from data plus a model or theory.
    - `[CLAIMED]`: asserted without evidence in that source.
    - `[MY SYNTHESIS]`: your own dot-connecting or arithmetic.
  - **Provenance:**
    - `[V]`: verbatim from text you actually read (full text, abstract, raw
      data).
    - `[2nd]`: from a search snippet, a WebFetch summary (a summarizer, so
      not verbatim) or a secondary report.
- No page numbers (HTML, abstracts)? Say so once; don't invent them.

## Epistemic standards

Every claim has a chain: reality → measurement → authors' interpretation →
selection effects (why *this* source reached you) → your reading → your
summary. Be paranoid about each link.

- Write "the authors found X", not "X is true".
- "Three papers report X" only counts as convergence if they don't share
  data, methods or citation chains.
- Hunt for **confounders** and **base rates**: compare any count to its
  denominator and to the background rate before calling it an effect.
- Report conflicts between sources with both sides cited; don't silently pick.
- Say what you couldn't find. Absence of evidence isn't evidence of absence.
- Tell the user when you skip a source or are unsure about a finding.

## Source ladder (cheapest first)

1. **Already on disk:** `find ~/Research/topics -iname '*<keyword>*'`. Reuse
   a file with a hard link (`ln`); symlinks break the podman tools.
2. **Discovery (free):**
   - Web search.
   - scry (below).
   - OpenAlex: `https://api.openalex.org/works?search=…`, or
     `/works/doi:<DOI>` for the abstract, citations, references and
     `best_oa_location`.
3. **Open-access full text (free):**
   - arXiv (`/pdf/<id>`).
   - Europe PMC:
     `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:"<doi>"&resultType=core&format=json`
     gives the `pmcid`, then `/rest/<PMCID>/fullTextXML`. This works when
     publishers return 403.
   - Unpaywall: `https://api.unpaywall.org/v2/<doi>?email=<contact_email>`,
     with `contact_email` from `config.json`.
   - NBER, SSRN, author pages.
   - Download with `curl -L -A "Mozilla/5.0" -o <topic>/<Name - Author Year>.pdf`
     and check the result with `file`.
4. **Anna's Archive:** 25 downloads a day, for paywalled papers and books you
   will deep-read.
   - Count today's use first:
     `grep -c "^$(date +%F)" ~/Research/.annas-ledger.tsv`. At 25, stop and
     tell the user.
   - After every attempt, append
     `date<TAB>book|article<TAB>md5-or-doi<TAB>filename<TAB>ok|failed`.
   - Prefer EPUB for books. Retail EPUBs often carry print page numbers
     (`grep -c 'epub:type="pagebreak"'`), so you rarely need a PDF just for
     page numbers. Move downloads out of `inbox/` immediately and record
     `download.hash`.
   - `book_search` scrapes Anna's HTML search, which sits behind DDoS-Guard
     and returns nothing. Find MD5s in scry instead:
     `books.catalog WHERE family = 'files' AND hasAllTokens(search_text_lc, tokens('<title author>'))`.
     Then call `book_download(hash, …)`. Downloads use the JSON API on the
     mirror set in `ANNAS_FIXED_BASE_URL` in `.mcp.json`; open-slum.org lists
     live mirrors.
   - `article_download` sometimes saves a SciDB landing page (`.htm`, about
     170 KB) instead of the paper. Check with `file`; if so, delete it and
     log `failed`.
   - If the tools error, say so and fall back to steps 2–3. Don't retry in a
     loop.

**scry** (`mcp.scry.io`; follow its own guide) is SQL over Twitter/X, Reddit,
HN, LessWrong, arXiv, Wikipedia, prediction markets and more.
- Use it for tweets, discourse, mention trends and market odds.
- It doesn't replace journals or official statistics.
- Forum posts are `[CLAIMED]`.
- Record the SQL in `notes.md`.

## Reading files

- **PDF:** `pdftotext -layout F.pdf F.txt` puts a form feed between pages.
  - Page N is `awk -v RS='\f' 'NR==N' F.txt`.
  - Find a phrase's page with `awk -v RS='\f' '/pattern/{print "p." NR}' F.txt`.
  - These are PDF page indices; check them against the printed page numbers
    before citing a journal page.
- **EPUB:** `pandoc F.epub -t plain -o F.txt`. There are no pages, so cite
  chapter or section.
- **Scanned PDF with no text layer:** say so, and look for another copy
  before spending an Anna's download on it.

## sources.json

One per topic. It's the record of what was used, and it makes Anna's
downloads restorable. Create entries with
`.bin/tools enrich --add <DOI> <topic>/sources.json` when there's a DOI.

```json
{
  "session": {"title": "…", "date": "YYYY-MM-DD", "question": "…"},
  "sources": [{
    "id": 1, "title": "…", "authors": ["…"], "year": 2024, "doi": "…",
    "url": "original URL", "archive_url": "snapshot used if the original is blocked",
    "journal": "…", "type": "journal-article", "found_via": "…",
    "download": {"hash": "<md5>", "format": "pdf", "filename": "…"},
    "local_file": "media/X.pdf", "html_filename": "X.html",
    "status": "read-full", "relevance_level": "HIGH", "relevance": "one line"
  }]
}
```

- `download` is only for Anna's downloads (null otherwise).
- Restore a download with
  `mcp__annas-mcp__book_download(hash, filename without extension, format)`.
  This counts against the daily budget.
- `html_filename` is set by `pdf2html`.

## Helper scripts (`.bin/tools`)

Agent-only. Run them from `~/Research` or a topic folder.

- `link <url|docs/file.html> "<passage>"`: prints a verified text-fragment
  link, with archive fallback.
- `link --check <file.md>`: re-verifies every fragment link in the file.
- `archive <url> [--submit]`: finds Wayback and archive.today copies, or
  requests a Wayback capture.
- `pdf2html --file <pdf>`: converts any PDF inside a topic to
  `docs/<stem>.html`. Plain `pdf2html [topic-dir]` converts the Anna's PDFs
  listed in `sources.json`.
- `fragment <docs/file.html> "<quote>"`: the low-level matcher for pdf2html
  output. `link` uses it.
- `enrich [--add] <DOI> [sources.json] | --all`: fetches CrossRef metadata.
- `sources [sources.json]`: renders `sources.md`.
- `sync [topic-dir]`: commits and pushes the topic to a **private** GitHub
  repo, because the full texts are copyrighted. Only when asked.
  - Publishing `docs/` through GitHub Pages is legacy; it needs a paid plan
    for private repos.
