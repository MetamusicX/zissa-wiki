#!/usr/bin/env python3
"""Claude Code Stop hook: runs `wiki.py check --if-changed` before Claude finishes.

The same check runs for every other agent through the git pre-commit hook in .githooks/
and through CI; this hook only brings it forward to the end of each Claude task. It runs
only when wiki/ or index.md has uncommitted changes, and blocks once (exit 2, reasons on
stderr): if Claude cannot clear the errors it may then stop and explain.
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

run = subprocess.run([sys.executable, os.path.join(root, "scripts", "wiki.py"), "check", "--if-changed"],
                     cwd=root, capture_output=True, text=True)
if run.returncode == 1:
    print("Before finishing, fix these wiki errors (see AGENTS.md):\n\n" + run.stdout.strip(), file=sys.stderr)
    sys.exit(2)
