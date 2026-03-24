"""Session management: new, list, resume, open."""

import json
import os
import re
import shutil
import subprocess
import sys
import tty
import termios
from datetime import date

from . import sources as S


def slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:60]


def session_dirs() -> list[str]:
    """List session directories sorted by name (date-prefixed = chronological)."""
    research = str(S.RESEARCH_DIR)
    if not os.path.isdir(research):
        return []
    dirs = []
    for entry in sorted(os.listdir(research)):
        full = os.path.join(research, entry)
        if os.path.isdir(full) and re.match(r'^\d{4}-\d{2}-\d{2}-', entry):
            dirs.append(full)
    return dirs


def resolve_session(target: str) -> str:
    """Resolve a session target (number or name fragment) to a directory path."""
    dirs = session_dirs()

    # By index number
    if target.isdigit():
        idx = int(target)
        if 1 <= idx <= len(dirs):
            return dirs[idx - 1]
        print(f"No session at index {target}", file=sys.stderr)
        sys.exit(1)

    # By name fragment (first match)
    for d in dirs:
        if target in os.path.basename(d):
            return d

    print(f"No session matching '{target}'", file=sys.stderr)
    sys.exit(1)


def cmd_new(question: str):
    slug = slugify(question)
    today = date.today().isoformat()
    dir_name = f"{today}-{slug}"
    session_dir = os.path.join(str(S.RESEARCH_DIR), dir_name)

    if os.path.isdir(session_dir):
        from datetime import datetime
        session_dir += f"-{datetime.now().strftime('%H%M%S')}"

    os.makedirs(session_dir)

    # Write .question
    with open(os.path.join(session_dir, ".question"), "w") as f:
        f.write(question + "\n")

    # Write CLAUDE.md from template
    template_path = os.path.join(str(S.RESEARCH_DIR), ".session-template.md")
    if os.path.exists(template_path):
        shutil.copy(template_path, os.path.join(session_dir, "CLAUDE.md"))
    else:
        print(f"Warning: template not found at {template_path}", file=sys.stderr)

    # Write initial sources.json
    cfg = S.load_config()
    org = cfg.get("github_org", "")
    github_repo = f"{org}/{dir_name}" if org else ""
    pages_url = f"https://{org}.github.io/{dir_name}" if org else ""
    initial = {
        "session": {
            "title": question,
            "date": today,
            "question": question,
            "github_repo": github_repo,
            "pages_url": pages_url,
        },
        "sources": [],
    }
    S.save_sources(os.path.join(session_dir, "sources.json"), initial)

    print(f"Created research session: {session_dir}")
    os.chdir(session_dir)
    os.execvp("claude", [
        "claude", "--dangerously-skip-permissions",
        f"Research question: {question}\n\nBegin by searching for relevant sources using the anna-mcp tools. Scout what you find before diving deep.",
    ])


def cmd_list():
    dirs = session_dirs()
    if not dirs:
        print("No research sessions yet.")
        return

    print("Research sessions:")
    print()

    for i, d in enumerate(dirs, 1):
        name = os.path.basename(d)

        question = ""
        q_path = os.path.join(d, ".question")
        if os.path.exists(q_path):
            with open(q_path) as f:
                question = f.read().strip()

        status = "[empty]"
        if os.path.exists(os.path.join(d, "summary.md")):
            status = "[summary]"
        elif os.path.exists(os.path.join(d, "notes.md")):
            status = "[notes]"
        elif os.path.exists(os.path.join(d, "sources.md")):
            status = "[sources]"

        print(f"  {i:2d}. {name:<62s} {status}")
        if question:
            print(f"      {question}")


def _session_status(d: str) -> str:
    if os.path.exists(os.path.join(d, "summary.md")):
        return "[summary]"
    elif os.path.exists(os.path.join(d, "notes.md")):
        return "[notes]"
    elif os.path.exists(os.path.join(d, "sources.md")):
        return "[sources]"
    return "[empty]"


def _read_key() -> str:
    """Read a single keypress, returning arrow keys as 'up'/'down' and enter as 'enter'."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\r" or ch == "\n":
            return "enter"
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            if seq == "[A":
                return "up"
            if seq == "[B":
                return "down"
            return "esc"
        if ch == "\x03":  # Ctrl-C
            return "ctrl-c"
        if ch == "q":
            return "quit"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _interactive_pick(dirs: list[str]) -> str | None:
    """Show an interactive picker for session directories. Returns chosen path or None."""
    items = []
    for d in dirs:
        name = os.path.basename(d)
        question = ""
        q_path = os.path.join(d, ".question")
        if os.path.exists(q_path):
            with open(q_path) as f:
                question = f.read().strip()
        status = _session_status(d)
        items.append((d, name, question, status))

    selected = len(items) - 1  # start at most recent
    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80

    def render():
        # Move cursor up to overwrite previous render (except first time)
        sys.stderr.write(f"\x1b[?25l")  # hide cursor
        for i, (_, name, question, status) in enumerate(items):
            if i == selected:
                prefix = "\x1b[1;36m> "  # bold cyan
                suffix = "\x1b[0m"
            else:
                prefix = "  "
                suffix = ""
            # Truncate name to fit
            display_name = name[:term_width - 20]
            line = f"{prefix}{i + 1:2d}. {display_name:<{term_width - 18}s} {status}{suffix}"
            sys.stderr.write(line + "\n")
            if question and i == selected:
                q_trunc = question[:term_width - 8]
                sys.stderr.write(f"      \x1b[2m{q_trunc}\x1b[0m\n")

    def clear():
        # Count lines to clear
        lines = len(items)
        if items[selected][2]:  # question line for selected
            lines += 1
        sys.stderr.write(f"\x1b[{lines}A")  # move up
        for _ in range(lines):
            sys.stderr.write(f"\x1b[2K\n")  # clear each line
        sys.stderr.write(f"\x1b[{lines}A")  # move back up

    sys.stderr.write("Select a session (up/down, enter to confirm, q to cancel):\n\n")
    render()

    try:
        while True:
            key = _read_key()
            if key == "up" and selected > 0:
                clear()
                selected -= 1
                render()
            elif key == "down" and selected < len(items) - 1:
                clear()
                selected += 1
                render()
            elif key == "enter":
                sys.stderr.write("\x1b[?25h")  # show cursor
                sys.stderr.write("\n")
                return items[selected][0]
            elif key in ("quit", "esc", "ctrl-c"):
                sys.stderr.write("\x1b[?25h")  # show cursor
                sys.stderr.write("\n")
                return None
    except (KeyboardInterrupt, EOFError):
        sys.stderr.write("\x1b[?25h")
        sys.stderr.write("\n")
        return None


def cmd_resume(target: str):
    if not target:
        dirs = session_dirs()
        if not dirs:
            print("No research sessions yet.")
            sys.exit(1)
        d = _interactive_pick(dirs)
        if d is None:
            sys.exit(0)
    else:
        d = resolve_session(target)

    print(f"Resuming session: {os.path.basename(d)}")
    os.chdir(d)
    os.execvp("claude", ["claude", "--dangerously-skip-permissions", "--continue"])


def cmd_open(target: str):
    if not target:
        print("Usage: research open <number|name>")
        sys.exit(1)

    d = resolve_session(target)
    print(d)


def main(args):
    # Dispatch based on which subcommand was invoked
    if hasattr(args, "session_func"):
        args.session_func(args)
