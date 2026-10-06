#!/usr/bin/env bash
# Setup script for the Research framework.
# Run this after cloning the repository.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Research Framework Setup ==="
echo

# --- 1. Git submodule ---
if [ ! -f .bin/annas-mcp-src/go.mod ]; then
    echo "Initializing git submodules..."
    git submodule update --init --recursive
fi

# --- 2. Config ---
if [ ! -f config.json ]; then
    echo "Creating config.json..."
    echo
    read -rp "  GitHub org/username: " github_org
    read -rp "  Git email: " github_email
    read -rp "  Git name: " github_name
    read -rp "  Contact email (for CrossRef API): " contact_email
    cat > config.json <<CONF
{
  "github_org": "$github_org",
  "github_email": "$github_email",
  "github_name": "$github_name",
  "contact_email": "$contact_email"
}
CONF
    echo "  Written config.json"
else
    echo "config.json already exists, skipping."
fi
echo

# --- 3. annas-mcp binary ---
if [ -f .bin/annas-mcp ]; then
    echo "annas-mcp binary already exists at .bin/annas-mcp"
    echo "  (To rebuild from source, delete it and re-run setup.sh)"
else
    echo "annas-mcp binary not found."
    echo "  1) Build from submodule source (requires Go)"
    echo "  2) Skip (install manually later)"
    read -rp "  Choice [1/2]: " choice
    case "$choice" in
        1)
            if ! command -v go &>/dev/null; then
                echo "  Error: Go is not installed. Install Go and re-run, or build manually:"
                echo "    cd .bin/annas-mcp-src && go build -o ../annas-mcp ./cmd/annas-mcp/"
                exit 1
            fi
            echo "  Building annas-mcp from source..."
            (cd .bin/annas-mcp-src && go build -o ../annas-mcp ./cmd/annas-mcp/)
            echo "  Built .bin/annas-mcp"
            ;;
        *)
            echo "  Skipped. Build manually later:"
            echo "    cd .bin/annas-mcp-src && go build -o ../annas-mcp ./cmd/annas-mcp/"
            ;;
    esac
fi
echo

# --- 4. .mcp.json ---
if [ ! -f .mcp.json ]; then
    echo "Creating .mcp.json..."
    read -rp "  Anna's Archive secret key: " annas_key
    cat > .mcp.json <<MCP
{
  "mcpServers": {
    "annas-mcp": {
      "type": "stdio",
      "command": "$SCRIPT_DIR/.bin/annas-mcp",
      "args": [
        "mcp"
      ],
      "env": {
        "ANNAS_SECRET_KEY": "$annas_key",
        "ANNAS_DOWNLOAD_PATH": "$SCRIPT_DIR/inbox"
      }
    }
  }
}
MCP
    echo "  Written .mcp.json"
else
    echo ".mcp.json already exists, skipping."
fi
echo

# --- 5. Workspace dirs ---
mkdir -p "$SCRIPT_DIR/inbox" "$SCRIPT_DIR/topics"
echo
echo "=== Setup complete ==="
echo
echo "Open an agent (T3 Code / Claude Code) in $SCRIPT_DIR and ask a research question."
echo "Rules for the agent live in AGENTS.md."
