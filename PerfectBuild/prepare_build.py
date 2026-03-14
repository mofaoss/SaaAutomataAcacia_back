from __future__ import annotations

import argparse
import ast
import fnmatch
import shutil
from dataclasses import dataclass
from pathlib import Path

try:
    from ast_i18n_transformer import process_file
except ModuleNotFoundError:
    from PerfectBuild.ast_i18n_transformer import process_file


DEFAULT_STAGE_DIR_NAME = ".nuitka_stage"

# Keep this list framework-level and build-oriented, not game-specific.
IGNORED_DIR_NAMES = {
    ".git",
    ".github",
    ".idea",
    ".mypy_cache",
    ".nuitka_stage",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "env",
    "release",
    "venv",
}

IGNORED_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
}

IGNORED_FILE_PATTERNS = [
    "*.log",
    "*.pyc",
    "*.pyd",
    "*.pyo",
    "*.tmp",
    "*.swp",
    "*.swo",
    "*.bak",
]


@dataclass
class StageResult:
    stage_dir: Path
    py_files_scanned: int
    py_files_changed: int
    remaining_dynamic_fstring_calls: int


def _project_root_from_this_file() -> Path:
    return Path(__file__).resolve().parent.parent


def _build_ignore(stage_dir_name: str):
    ignored_dir_names = set(IGNORED_DIR_NAMES)
    ignored_dir_names.add(stage_dir_name)

    def _ignore(src: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        src_path = Path(src)

        for name in names:
            full = src_path / name
            if full.is_dir() and (name in ignored_dir_names or name.startswith(".nuitka_stage")):
                ignored.add(name)
                continue

            if name in IGNORED_FILE_NAMES:
                ignored.add(name)
                continue

            if any(fnmatch.fnmatch(name, p) for p in IGNORED_FILE_PATTERNS):
                ignored.add(name)

        return ignored

    return _ignore


def copy_project_to_stage(project_root: Path, stage_dir: Path) -> None:
    if stage_dir.exists():
        shutil.rmtree(stage_dir)

    print(f"[prepare_build] copy source tree -> {stage_dir}")
    shutil.copytree(
        project_root,
        stage_dir,
        ignore=_build_ignore(stage_dir.name),
        dirs_exist_ok=False,
    )


def _count_remaining_dynamic_fstring_calls(stage_dir: Path) -> int:
    count = 0
    for py_file in stage_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8-sig"), filename=str(py_file))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "_":
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            if not isinstance(first_arg, ast.JoinedStr):
                continue
            if any(isinstance(item, ast.FormattedValue) for item in first_arg.values):
                count += 1
    return count


def transform_stage_python_files(stage_dir: Path) -> tuple[int, int, int]:
    scanned = 0
    changed = 0

    for py_file in stage_dir.rglob("*.py"):
        scanned += 1
        if process_file(py_file):
            changed += 1

    remaining_dynamic = _count_remaining_dynamic_fstring_calls(stage_dir)
    print(
        "[prepare_build] ast transform done: "
        f"changed {changed}/{scanned} python files, "
        f"remaining dynamic _(fstring) calls: {remaining_dynamic}"
    )
    return scanned, changed, remaining_dynamic


def prepare_nuitka_stage(
    project_root: str | Path | None = None,
    stage_dir_name: str = DEFAULT_STAGE_DIR_NAME,
) -> StageResult:
    root = Path(project_root).resolve() if project_root else _project_root_from_this_file()
    stage_dir = root / stage_dir_name

    copy_project_to_stage(root, stage_dir)
    scanned, changed, remaining_dynamic = transform_stage_python_files(stage_dir)

    return StageResult(
        stage_dir=stage_dir,
        py_files_scanned=scanned,
        py_files_changed=changed,
        remaining_dynamic_fstring_calls=remaining_dynamic,
    )


def merge_release_from_stage(project_root: str | Path, stage_dir: str | Path) -> int:
    """Copy all release artifacts from stage/release back to project_root/release."""
    root = Path(project_root).resolve()
    stage = Path(stage_dir).resolve()
    src_release = stage / "release"
    dst_release = root / "release"

    if not src_release.exists():
        print(f"[prepare_build] no staged release found: {src_release}")
        return 0

    copied_files = 0
    for src in src_release.rglob("*"):
        rel = src.relative_to(src_release)
        dst = dst_release / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied_files += 1

    print(f"[prepare_build] merged release artifacts: {copied_files} files")
    return copied_files


def cleanup_stage_dir(stage_dir: str | Path) -> None:
    stage = Path(stage_dir).resolve()
    if not stage.exists():
        return
    shutil.rmtree(stage)
    print(f"[prepare_build] removed stage dir: {stage}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Nuitka stage with AST i18n rewrite.")
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path. Defaults to repo root inferred from this script.",
    )
    parser.add_argument(
        "--stage-dir-name",
        default=DEFAULT_STAGE_DIR_NAME,
        help="Temporary stage directory name under project root.",
    )
    args = parser.parse_args()

    result = prepare_nuitka_stage(
        project_root=args.project_root,
        stage_dir_name=args.stage_dir_name,
    )
    print(f"[prepare_build] stage ready: {result.stage_dir}")


if __name__ == "__main__":
    main()
