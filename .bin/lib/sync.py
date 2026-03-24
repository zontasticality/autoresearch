"""Git sync: initialize repo, commit, and push to GitHub."""

import os
import subprocess
import sys

from . import render
from . import sources as S

def _get_config():
    cfg = S.load_config()
    return {
        "github_org": cfg.get("github_org", ""),
        "github_email": cfg.get("github_email", ""),
        "github_name": cfg.get("github_name", ""),
    }

GITIGNORE_CONTENT = """\
# Binary source files (restored via sources.json)
*.pdf
*.epub
*.mobi
*.azw3
*.djvu

# Converted text files from epub/pdf extraction
*.txt

# Allow HTML docs to be committed
!docs/
!docs/**

# Editor/OS junk
.DS_Store
*~
*.swp
"""


def run(cmd, **kwargs):
    """Run a shell command, printing it first."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, **kwargs)


def ensure_git_init(session_dir: str):
    git_dir = os.path.join(session_dir, ".git")
    if not os.path.isdir(git_dir):
        print("Initializing git repo...")
        run(["git", "init"], cwd=session_dir, check=True)
        run(["git", "branch", "-M", "main"], cwd=session_dir, check=True)

    cfg = _get_config()
    if cfg["github_email"]:
        run(["git", "config", "user.email", cfg["github_email"]], cwd=session_dir, check=True)
    if cfg["github_name"]:
        run(["git", "config", "user.name", cfg["github_name"]], cwd=session_dir, check=True)


def ensure_gitignore(session_dir: str):
    gitignore_path = os.path.join(session_dir, ".gitignore")
    with open(gitignore_path, "w") as f:
        f.write(GITIGNORE_CONTENT)


def ensure_remote(session_dir: str, name: str):
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=session_dir, capture_output=True, text=True,
    )
    if result.returncode == 0:
        return  # remote already set

    cfg = _get_config()
    org = cfg["github_org"]
    if not org:
        print("Error: github_org not set in config.json", file=sys.stderr)
        sys.exit(1)

    print("Setting up GitHub remote...")
    check = subprocess.run(
        ["gh", "repo", "view", f"{org}/{name}"],
        cwd=session_dir, capture_output=True, text=True,
    )
    if check.returncode == 0:
        print("  Repo exists, adding remote...")
        run(
            ["git", "remote", "add", "origin", f"git@github.com:{org}/{name}.git"],
            cwd=session_dir, check=True,
        )
    else:
        print(f"  Creating repo {org}/{name}...")
        run(
            ["gh", "repo", "create", f"{org}/{name}", "--private", "--source=.", "--remote=origin"],
            cwd=session_dir, check=True,
        )


def main(args):
    session_dir = os.path.abspath(args.dir if hasattr(args, "dir") and args.dir else ".")
    name = os.path.basename(session_dir)

    # Guard: must be a direct subdirectory of ~/Research
    parent = os.path.dirname(session_dir)
    if parent != str(S.RESEARCH_DIR):
        print("Error: must be run from a direct subdirectory of ~/Research/", file=sys.stderr)
        print(f"  Current dir: {session_dir}", file=sys.stderr)
        sys.exit(1)

    ensure_git_init(session_dir)
    ensure_gitignore(session_dir)

    # Auto-generate sources.md from sources.json
    sources_path = os.path.join(session_dir, "sources.json")
    if os.path.exists(sources_path):
        print("Generating sources.md from sources.json...")

        class RenderArgs:
            sources = sources_path

        render.main(RenderArgs())

    # Commit and push
    run(["git", "add", "-A"], cwd=session_dir, check=True)

    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=session_dir,
    )
    if result.returncode == 0:
        print("No changes to commit.")
    else:
        import datetime
        msg = f"sync {datetime.datetime.now().isoformat(timespec='seconds')}"
        print(f"Committing: {msg}")
        run(["git", "commit", "-m", msg], cwd=session_dir, check=True)

    ensure_remote(session_dir, name)

    print("Pushing to origin/main...")
    run(["git", "push", "-u", "origin", "main"], cwd=session_dir, check=True)

    cfg = _get_config()
    print(f"Done. https://github.com/{cfg['github_org']}/{name}")
