from __future__ import annotations

import argparse
import locale
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PerfectBuild.prepare_build import cleanup_stage_dir, prepare_nuitka_stage


SMOKE_ROOT_BASE = ROOT / "runtime" / "temp" / "nuitka_prepare_smoke"
RUN_ID = os.environ.get("NPS_RUN_ID", f"run_{os.getpid()}_{int(time.time() * 1000)}")
SMOKE_ROOT = SMOKE_ROOT_BASE / RUN_ID
PROJECT_ROOT = SMOKE_ROOT / "project"
PROJECT_ENTRY = PROJECT_ROOT / "main.py"
STAGE_DIR_NAME = ".nuitka_stage"
EXPECTED_LINES = [
    "Preparing role_shard, returning to home...",
    "Hello World and K and World",
    "Client area size: 1920x1080 (1.778:1), ratio_ok 16:9 standard ratio",
]

SAMPLE_SOURCE = """from __future__ import annotations

def _(text: str, **kwargs) -> str:
    return text


def main() -> None:
    task_name = "role_shard"
    name = "World"
    data = {"key": "K"}
    client_width = 1920
    client_height = 1080
    actual_ratio = client_width / client_height
    status = "ratio_ok"

    print(_(f"Preparing {task_name}, returning to home..."))
    print(_(f"Hello {name} and {data['key']} and {name}"))
    print(_(f"Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status} 16:9 standard ratio"))


if __name__ == "__main__":
    main()
"""


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def _run_command(cmd: list[str], *, cwd: Path | None = None) -> CommandResult:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=False,
        env=env,
    )
    return CommandResult(
        returncode=proc.returncode,
        stdout=_decode_stream(proc.stdout),
        stderr=_decode_stream(proc.stderr),
    )


def _decode_stream(raw: bytes) -> str:
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _run_program(path: Path, *, cwd: Path | None = None) -> list[str]:
    result = _run_command([sys.executable, str(path)], cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(
            f"Program failed: {path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    lines = [line.rstrip("\r") for line in result.stdout.splitlines() if line.strip()]
    return lines


def _assert_expected(lines: list[str], label: str) -> None:
    if lines != EXPECTED_LINES:
        raise AssertionError(
            f"{label} output mismatch.\nexpected: {EXPECTED_LINES}\nactual:   {lines}"
        )


def _prepare_mock_project() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT)
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    PROJECT_ENTRY.write_text(SAMPLE_SOURCE, encoding="utf-8")


def _ensure_transformed(stage_entry: Path) -> None:
    transformed = stage_entry.read_text(encoding="utf-8")
    if "_(f" in transformed:
        raise AssertionError("Stage still contains dynamic _(f\"...\") after prepare_build.")
    if ".format(" not in transformed:
        raise AssertionError("Stage source does not contain .format(...) rewrite.")


def _maybe_run_nuitka(script_path: Path, output_dir: Path, *, standalone: bool) -> Path:
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--assume-yes-for-downloads",
        "--remove-output",
        "--no-pyi-file",
        "--zig",
        f"--output-dir={output_dir}",
    ]
    if standalone:
        cmd.append("--standalone")
    cmd.append(str(script_path))

    result = _run_command(cmd, cwd=script_path.parent)
    if result.returncode != 0:
        raise RuntimeError(
            "Nuitka build failed.\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    exe_name = f"{script_path.stem}.exe"
    if standalone:
        exe_path = output_dir / f"{script_path.stem}.dist" / exe_name
    else:
        exe_path = output_dir / exe_name
    if not exe_path.exists():
        raise FileNotFoundError(f"Nuitka output not found: {exe_path}")
    return exe_path


def _run_executable(exe_path: Path) -> list[str]:
    result = _run_command([str(exe_path)], cwd=exe_path.parent)
    if result.returncode != 0:
        raise RuntimeError(
            f"Executable failed: {exe_path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return [line.rstrip("\r") for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test prepare_build f-string rewrite with optional Nuitka compilation."
    )
    parser.add_argument(
        "--skip-nuitka",
        action="store_true",
        help="Only verify source + prepare stage behavior, skip Nuitka compile and run.",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Use --standalone mode for Nuitka (default is accelerated mode).",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help=f"Keep temp files for debugging (under {SMOKE_ROOT_BASE}).",
    )
    args = parser.parse_args()

    _prepare_mock_project()
    print(f"[1/5] mock project ready: {PROJECT_ROOT}")

    raw_lines = _run_program(PROJECT_ENTRY)
    _assert_expected(raw_lines, "raw python")
    print("[2/5] raw source run ok")

    stage_result = prepare_nuitka_stage(project_root=PROJECT_ROOT, stage_dir_name=STAGE_DIR_NAME)
    stage_entry = stage_result.stage_dir / "main.py"
    _ensure_transformed(stage_entry)
    stage_lines = _run_program(stage_entry, cwd=stage_result.stage_dir)
    _assert_expected(stage_lines, "prepared stage python")
    print(
        "[3/5] prepare stage run ok "
        f"(changed {stage_result.py_files_changed}/{stage_result.py_files_scanned}, "
        f"remaining dynamic={stage_result.remaining_dynamic_fstring_calls})"
    )

    if not args.skip_nuitka:
        build_root = SMOKE_ROOT / "build"
        src_out = build_root / "src"
        stage_out = build_root / "stage"
        src_exe = _maybe_run_nuitka(PROJECT_ENTRY, src_out, standalone=args.standalone)
        stage_exe = _maybe_run_nuitka(stage_entry, stage_out, standalone=args.standalone)

        src_exe_lines = _run_executable(src_exe)
        stage_exe_lines = _run_executable(stage_exe)
        _assert_expected(src_exe_lines, "nuitka raw exe")
        _assert_expected(stage_exe_lines, "nuitka prepared exe")
        if src_exe_lines != stage_exe_lines:
            raise AssertionError(
                "Nuitka outputs diverged between raw and prepare-stage sources.\n"
                f"raw exe: {src_exe_lines}\n"
                f"stage exe: {stage_exe_lines}"
            )
        print(f"[4/5] nuitka run ok (standalone={args.standalone})")
    else:
        print("[4/5] skipped nuitka by --skip-nuitka")

    print("[5/5] smoke test passed")
    return 0


if __name__ == "__main__":
    stage_dir = PROJECT_ROOT / STAGE_DIR_NAME
    try:
        raise SystemExit(main())
    finally:
        # Keep temp files only when explicit debugging is requested.
        keep = "--keep-temp" in sys.argv
        if not keep:
            try:
                cleanup_stage_dir(stage_dir)
            except Exception:
                pass
            if SMOKE_ROOT.exists():
                shutil.rmtree(SMOKE_ROOT, ignore_errors=True)
