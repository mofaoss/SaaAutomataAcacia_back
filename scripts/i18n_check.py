#!/usr/bin/env python
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_step(name: str, cmd: list[str]) -> int:
    print(f"== {name} ==")
    proc = subprocess.run(cmd, cwd=ROOT, text=True)
    print(f"exit_code={proc.returncode}")
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified i18n workflow: extract -> normalize -> seed -> audit -> guard")
    parser.add_argument("--all", action="store_true", help="Run guard on all files (default: changed files only)")
    args = parser.parse_args()

    py = sys.executable
    steps = [
        ("extract", [py, "scripts/extract_module_i18n.py"]),
        ("normalize", [py, "scripts/normalize_i18n_data.py"]),
        ("seed-missing", [py, "scripts/seed_i18n_missing.py"]),
        ("audit", [py, "scripts/audit_i18n.py", "--fail-on-issues"]),
    ]
    guard_cmd = [py, "scripts/i18n_guard.py"]
    if args.all:
        guard_cmd.append("--all")
    steps.append(("guard", guard_cmd))

    failed = False
    for name, cmd in steps:
        code = _run_step(name, cmd)
        if code != 0:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
