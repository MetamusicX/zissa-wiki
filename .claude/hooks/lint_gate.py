#!/usr/bin/env python3
"""Stop hook: before Claude finishes, the wiki must lint error-free and the quotes in
any source note changed this session must match their raw files.

Runs only when wiki/ or index.md has uncommitted changes, so errors that were already
there never hold up an unrelated conversation. Blocks once (exit 2, reasons on stderr);
if Claude cannot clear the errors it may then stop and explain.
"""
import json
import os
import subprocess
import sys

root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
try:
    event = json.load(sys.stdin)
except ValueError:
    event = {}
if event.get("stop_hook_active"):
    sys.exit(0)

git = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", "wiki", "index.md"],
                     cwd=root, capture_output=True, text=True)
if git.returncode != 0:
    sys.exit(0)                      # not a git checkout: nothing to scope the check to
changed = [line[3:].split(" -> ")[-1].strip().strip('"') for line in git.stdout.splitlines()]
if not changed:
    sys.exit(0)

tool = [sys.executable, os.path.join(root, "scripts", "wiki.py")]
problems = []
lint = subprocess.run(tool + ["lint", "--min-severity", "error"], cwd=root, capture_output=True, text=True)
if lint.returncode == 1:
    problems.append("`wiki.py lint` reports errors:\n" + lint.stdout.strip())
notes = [c for c in changed if c.startswith("wiki/source-notes/") and c.endswith(".md")
         and os.path.exists(os.path.join(root, c))]
if notes:
    quotes = subprocess.run(tool + ["quotes", "--min-severity", "error"] + notes,
                            cwd=root, capture_output=True, text=True)
    if quotes.returncode == 1:
        problems.append("`wiki.py quotes` finds misquotes:\n" + quotes.stdout.strip())

if problems:
    print("Before finishing, fix these wiki errors (see CLAUDE.md):\n\n" + "\n\n".join(problems),
          file=sys.stderr)
    sys.exit(2)
