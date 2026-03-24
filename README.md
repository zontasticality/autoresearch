# Research Framework

An AI-assisted research framework using [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Anna's Archive](https://annas-archive.org/) for structured literature research sessions.

Each session produces structured notes, source tracking (`sources.json`), and optionally HTML paper views hosted on GitHub Pages — all driven by a Claude Code agent with epistemic guardrails.

## Features

- **Session management** — create, list, resume research sessions with `research <question>`
- **Source tracking** — `sources.json` tracks every source with metadata, relevance assessments, and download hashes for reproducibility
- **PDF-to-HTML conversion** — convert papers to scrollable HTML with metadata bars, hosted via GitHub Pages
- **Text fragment URLs** — generate `#:~:text=` links to specific passages in converted papers
- **CrossRef enrichment** — auto-populate metadata from DOIs
- **Git sync** — push session notes/sources to GitHub (binary files excluded, restorable via hashes)
- **Anna's Archive integration** — search and download papers/books via MCP tools

## Prerequisites

- Python 3.12+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- [GitHub CLI](https://cli.github.com/) (`gh`)
- [Podman](https://podman.io/) (for PDF-to-HTML conversion)
- [Go](https://go.dev/) (optional — only needed to build annas-mcp from source)
- [Git LFS](https://git-lfs.com/) (for the pre-built annas-mcp binary)

## Setup

```bash
git clone --recurse-submodules <repo-url> ~/Research
cd ~/Research
./setup.sh
```

The setup script will:
1. Prompt for your GitHub username, email, and Anna's Archive API key
2. Create `config.json` and `.mcp.json`
3. Offer to use the pre-built `annas-mcp` binary (via Git LFS) or build from source
4. Symlink the `research` CLI to `~/.local/bin/research`

## Usage

```bash
# Start a new research session (launches Claude Code)
research "What is the effect of pathogens on host lifespan?"

# List all sessions
research list

# Resume a previous session
research resume

# Other tools (run inside a session directory)
research enrich --add 10.1038/s41586-020-2649-2   # add source by DOI
research enrich --all                              # enrich all sources
research pdf2html                                  # convert PDFs to HTML
research fragment doc.html "quote text"            # generate text fragment URL
research sources                                   # regenerate sources.md
research sync                                      # commit and push to GitHub
```

## How It Works

1. `research <question>` creates a dated session directory with a `CLAUDE.md` (epistemic guidelines), empty `sources.json`, and launches Claude Code
2. Claude searches for relevant sources using anna-mcp tools, downloads papers, and populates `sources.json`
3. Research notes go into `notes.md`, synthesis into `summary.md`, open questions into `questions.md`
4. `research pdf2html` converts downloaded PDFs to HTML for GitHub Pages viewing
5. `research sync` pushes the session to GitHub (PDFs excluded — anyone can restore them via `sources.json` hashes)

## Configuration

- `config.json` — GitHub org, git identity, contact email (see `config.example.json`)
- `.mcp.json` — Anna's Archive MCP server config with API key (see `.mcp.json.example`)

Both files are gitignored. The `setup.sh` script creates them interactively.

## License

MIT
