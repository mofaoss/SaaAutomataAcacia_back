#!/usr/bin/env python
# coding:utf-8
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "release"
REPORT_FILE = REPORT_DIR / "preflight_report.md"

TARGET_DIRS = [
    ROOT / "runtime" / "temp",
    ROOT / "build",
    ROOT / "dist",
    ROOT / ".pytest_cache",
]


def run(cmd: list[str], timeout: int = 180) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def remove_path(path: Path) -> str:
    if not path.exists():
        return f"skip: `{path.relative_to(ROOT)}` not found"

    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        return f"removed dir: `{path.relative_to(ROOT)}`"

    path.unlink(missing_ok=True)
    return f"removed file: `{path.relative_to(ROOT)}`"


def clean_workspace(clean_logs: bool) -> list[str]:
    actions: list[str] = []

    for p in TARGET_DIRS:
        actions.append(remove_path(p))

    for pycache in ROOT.rglob("__pycache__"):
        actions.append(remove_path(pycache))

    for pyc in ROOT.rglob("*.pyc"):
        actions.append(remove_path(pyc))

    if clean_logs:
        log_dir = ROOT / "runtime" / "log"
        actions.append(remove_path(log_dir))
        actions.append(remove_path(ROOT / "runtime" / "appdata" / "crash.log"))

    return actions


def compile_checks() -> tuple[bool, list[str]]:
    outputs: list[str] = []

    code, out, err = run([sys.executable, "-m", "compileall", "app"], timeout=240)
    outputs.append("`python -m compileall app`")
    outputs.append(out.strip())
    if err.strip():
        outputs.append(err.strip())
    if code != 0:
        return False, outputs

    code, out, err = run([sys.executable, "-m", "py_compile", "SAA.py"], timeout=60)
    outputs.append("`python -m py_compile SAA.py`")
    if out.strip():
        outputs.append(out.strip())
    if err.strip():
        outputs.append(err.strip())
    if code != 0:
        return False, outputs

    return True, outputs


def runtime_check(startup_seconds: int) -> tuple[bool, list[str]]:
    outputs: list[str] = []
    proc = subprocess.Popen(
        [sys.executable, "SAA.py"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        time.sleep(startup_seconds)
        code = proc.poll()
        out, err = proc.communicate(timeout=5) if code is not None else ("", "")

        if "Traceback" in out or "Traceback" in err:
            outputs.append("runtime traceback detected")
            outputs.append(out.strip())
            outputs.append(err.strip())
            return False, outputs

        if code is not None and code != 0:
            outputs.append(f"`python SAA.py` exited with non-zero code: {code}")
            outputs.append(out.strip())
            outputs.append(err.strip())
            return False, outputs

        outputs.append(f"`python SAA.py` startup smoke passed ({startup_seconds}s)")
        if out.strip():
            outputs.append(out.strip())
        if err.strip():
            outputs.append(err.strip())
        return True, outputs
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def write_report(clean_actions: list[str], compile_logs: list[str], runtime_logs: list[str], ok: bool) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    lines = [
        "# Release Preflight Report",
        "",
        f"- Generated at: `{now}`",
        f"- Overall: `{'PASS' if ok else 'FAIL'}`",
        "",
        "## Cleanup",
    ]
    lines.extend([f"- {x}" for x in clean_actions] or ["- no cleanup actions"])
    lines.append("")
    lines.append("## Compile Checks")
    lines.extend([f"- {x}" for x in compile_logs if x] or ["- no compile logs"])
    lines.append("")
    lines.append("## Runtime Smoke")
    lines.extend([f"- {x}" for x in runtime_logs if x] or ["- no runtime logs"])
    lines.append("")

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-release cleanup pack for SaaAssistantAca")
    parser.add_argument("--clean-logs", action="store_true", help="remove `log/` and `crash.log`")
    parser.add_argument("--startup-seconds", type=int, default=10, help="seconds to wait for SAA.py startup smoke")
    args = parser.parse_args()

    clean_actions = clean_workspace(clean_logs=args.clean_logs)
    compile_ok, compile_logs = compile_checks()
    runtime_ok, runtime_logs = runtime_check(startup_seconds=max(3, args.startup_seconds))
    ok = compile_ok and runtime_ok

    write_report(clean_actions, compile_logs, runtime_logs, ok)

    print(f"Report: {REPORT_FILE}")
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
