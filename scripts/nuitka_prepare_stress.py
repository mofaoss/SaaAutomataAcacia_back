from __future__ import annotations

import argparse
import ast
import json
import locale
import os
import re
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


SMOKE_ROOT_BASE = ROOT / "runtime" / "temp" / "nuitka_prepare_stress"
RUN_ID = os.environ.get("NPS_RUN_ID", f"run_{os.getpid()}_{int(time.time() * 1000)}")
SMOKE_ROOT = SMOKE_ROOT_BASE / RUN_ID
PROJECT_ROOT = SMOKE_ROOT / "project"
PROJECT_ENTRY = PROJECT_ROOT / "main.py"
STAGE_DIR_NAME = ".nuitka_stage"

CASE_IDS = [
    "T01",
    "T02",
    "T03",
    "T04",
    "T05",
    "T06",
    "T07",
    "T08",
    "T09",
    "T10",
    "T11",
    "T12",
    "T13",
    "T14",
    "T15",
    "T16",
    "T17",
    "T18",
    "T19",
    "T20",
    "T21",
]

SAMPLE_SOURCE = """from __future__ import annotations

import logging
import sys

import app.framework.i18n.runtime as i18n_runtime

i18n_runtime._resolve_lang = lambda: "zh_CN"
i18n_runtime.load_i18n_catalogs()

from app.framework.i18n import _


class LogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rendered = i18n_runtime.render_message(record.msg, context="log", levelno=record.levelno)
        cid = getattr(record, "cid", "NOCASE")
        return f"{cid}|{rendered}"


def build_logger() -> logging.Logger:
    logger = logging.getLogger("nuitka.prepare.stress")
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(LogFormatter())
    logger.addHandler(handler)
    return logger


class TaskObj:
    def __init__(self, task_id: str) -> None:
        self.id = task_id

def run_cases() -> None:
    logger = build_logger()

    task_name = "role_shard"
    reason = "OOM{42}"
    template_name = "btn.start"
    conf = 0.8765
    threshold = 0.9
    event = "tick"
    event_code = "E42"
    task_id = "T-7"
    detail = "retry=3,mode=safe"
    current_time_str = "00:58"
    scheduled_task_ids = ["task_get_reward"]
    w = 640
    h = 360
    new_w = 960
    new_h = 540
    scale = 1.5
    client_width = 1920
    client_height = 1080
    actual_ratio = client_width / client_height
    status = _("Meets", msgid="meets")
    task = TaskObj(task_id)

    logger.warning(
        _(f"Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status} 16:9 standard ratio", msgid="client_area_size_client_width_x_client_height_ac"),
        extra={"cid": "T01"},
    )
    logger.warning(
        _("Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status} 16:9 standard ratio", msgid="client_area_size_client_width_x_client_height_ac").format(
            client_width=client_width,
            client_height=client_height,
            actual_ratio=actual_ratio,
            status=status,
        ),
        extra={"cid": "T02"},
    )
    logger.warning(
        _("Client area size: %sx%s (%.3f:1), %s 16:9 standard ratio" % (client_width, client_height, actual_ratio, status), msgid="client_area_size_client_width_x_client_height_ac"),
        extra={"cid": "T03"},
    )
    logger.warning(
        _(f"Target image: {template_name} Similarity: {conf:.2f}", msgid="target_image_template_name_similarity_conf"),
        extra={"cid": "T04"},
    )
    logger.warning(
        _("Target image: %(template_name)s Similarity: %(conf).2f" % {"template_name": template_name, "conf": conf}, msgid="target_image_template_name_similarity_conf"),
        extra={"cid": "T05"},
    )
    logger.warning(
        _("Target image: {template_name} Similarity: {conf:.2f}, below {threshold}".format(
            template_name=template_name,
            conf=conf,
            threshold=threshold,
        ), msgid="target_image_template_name_similarity_conf_below"),
        extra={"cid": "T06"},
    )
    logger.warning(
        _("Preparing " + task_name + ", returning to home...", msgid="preparing_task_name_returning_to_home"),
        extra={"cid": "T07"},
    )
    logger.warning(
        _("Current task: {}".format(task_name), msgid="current_task_task_name"),
        extra={"cid": "T08"},
    )
    logger.warning(
        _("Current task: %s" % task_name, msgid="current_task_task_name"),
        extra={"cid": "T09"},
    )
    logger.warning(
        _("Task failed: %s, reason=%s" % (task_name, reason), msgid="task_failed_reason"),
        extra={"cid": "T10"},
    )
    logger.warning(
        _("Periodic diagnostic: event={event} ({event_code}) task_id={task_id} task_name={task_name} detail={detail}".format(
            event=event,
            event_code=event_code,
            task_id=task_id,
            task_name=task_name,
            detail=detail,
        ), msgid="periodic_diagnostic_event_event_code_task_id_task_name_detail"),
        extra={"cid": "T11"},
    )
    logger.warning(
        _("OCR low-res enhance: %dx%d -> %dx%d (x%.2f)" % (w, h, new_w, new_h, scale), msgid="ocr_low_res_enhance_w_x_h_new_w_x_new_h_x_scale"),
        extra={"cid": "T12"},
    )

    # Auto-wrap cases: source intentionally does not call _().
    logger.warning("Game window ratio is not 16:9", extra={"cid": "T13"})
    logger.warning(f"Current task: {task_name}", extra={"cid": "T14"})
    logger.warning("Current task: %s" % task_name, extra={"cid": "T15"})
    logger.warning("Current task: {}".format(task_name), extra={"cid": "T16"})
    logger.warning(f"Target image: {template_name} Similarity: {conf:.2f}", extra={"cid": "T17"})
    logger.warning("Preparing " + task_name + ", returning to home...", extra={"cid": "T18"})
    logger.warning("Task failed: %s, reason=%s" % (task_name, reason), extra={"cid": "T19"})

    logger.warning(
        _(f"Periodic diagnostic: event={event} ({event_code}) task_id={task.id} task_name={task_name} detail={detail}", msgid="periodic_diagnostic_event_event_code_task_id_task_name_detail"),
        extra={"cid": "T20"},
    )
    logger.warning(
        _("\\u23f0 Scheduled task triggered at {current_time_str}, executing tasks: {task_ids}").format(
            current_time_str=current_time_str,
            task_ids=scheduled_task_ids,
        ),
        extra={"cid": "T21"},
    )


if __name__ == "__main__":
    run_cases()
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

    current_pythonpath = env.get("PYTHONPATH", "")
    pythonpath_entries = [str(ROOT)]
    if current_pythonpath:
        pythonpath_entries.append(current_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

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


def _normalize_output_lines(output: str) -> list[str]:
    lines: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.rstrip("\r").strip()
        if not line:
            continue
        line = re.sub(r"\x1b\[[0-9;]*m", "", line)
        if "QFluentWidgets Pro is now released." in line:
            continue
        if "qfluentwidgets.com/pages/pro" in line:
            continue
        lines.append(line)
    return lines


def _run_program(path: Path, *, cwd: Path | None = None) -> list[str]:
    result = _run_command([sys.executable, str(path)], cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(
            f"Program failed: {path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return _normalize_output_lines(result.stdout)


def _run_executable(exe_path: Path) -> list[str]:
    result = _run_command([str(exe_path)], cwd=exe_path.parent)
    if result.returncode != 0:
        raise RuntimeError(
            f"Executable failed: {exe_path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return _normalize_output_lines(result.stdout)


def _prepare_mock_project() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT)
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    PROJECT_ENTRY.write_text(SAMPLE_SOURCE, encoding="utf-8")


def _log_catalog(lang: str) -> dict[str, str]:
    path = ROOT / "app" / "framework" / "i18n" / f"{lang}.json"
    catalog = json.loads(path.read_text(encoding="utf-8-sig"))
    return {str(k): str(v) for k, v in catalog.items()}


def _fmt(catalog: dict[str, str], key: str, **kwargs) -> str:
    template = catalog[key]
    return template.format(**kwargs) if kwargs else template


def _expected_outputs() -> tuple[list[str], list[str]]:
    en = _log_catalog("en")
    zh = _log_catalog("zh_CN")

    task_name = "role_shard"
    reason = "OOM{42}"
    template_name = "btn.start"
    conf = 0.8765
    threshold = 0.9
    event = "tick"
    event_code = "E42"
    task_id = "T-7"
    detail = "retry=3,mode=safe"
    current_time_str = "00:58"
    scheduled_task_ids = ["task_get_reward"]
    w = 640
    h = 360
    new_w = 960
    new_h = 540
    scale = 1.5
    client_width = 1920
    client_height = 1080
    actual_ratio = client_width / client_height
    status_zh = zh["framework.ui.meets"]

    stage: dict[str, str] = {
        "T01": _fmt(
            zh,
            "framework.log.client_area_size_client_width_x_client_height_ac",
            client_width=client_width,
            client_height=client_height,
            actual_ratio=actual_ratio,
            status=status_zh,
        ),
        "T02": _fmt(
            zh,
            "framework.log.client_area_size_client_width_x_client_height_ac",
            client_width=client_width,
            client_height=client_height,
            actual_ratio=actual_ratio,
            status=status_zh,
        ),
        "T03": _fmt(
            zh,
            "framework.log.client_area_size_client_width_x_client_height_ac",
            client_width=client_width,
            client_height=client_height,
            actual_ratio=actual_ratio,
            status=status_zh,
        ),
        "T04": _fmt(
            zh,
            "framework.log.target_image_template_name_similarity_conf",
            template_name=template_name,
            conf=conf,
        ),
        "T05": _fmt(
            zh,
            "framework.log.target_image_template_name_similarity_conf",
            template_name=template_name,
            conf=conf,
        ),
        "T06": _fmt(
            zh,
            "framework.log.target_image_template_name_similarity_conf_below",
            template_name=template_name,
            conf=conf,
            threshold=threshold,
        ),
        "T07": _fmt(zh, "framework.log.preparing_task_name_returning_to_home", task_name=task_name),
        "T08": _fmt(zh, "framework.log.current_task_task_name", task_name=task_name),
        "T09": _fmt(zh, "framework.log.current_task_task_name", task_name=task_name),
        "T10": _fmt(zh, "framework.log.task_failed_reason", task_name=task_name, reason=reason),
        "T11": _fmt(
            zh,
            "framework.log.periodic_diagnostic_event_event_code_task_id_task_name_detail",
            event=event,
            event_code=event_code,
            task_id=task_id,
            task_name=task_name,
            detail=detail,
        ),
        "T12": _fmt(
            zh,
            "framework.log.ocr_low_res_enhance_w_x_h_new_w_x_new_h_x_scale",
            w=w,
            h=h,
            new_w=new_w,
            new_h=new_h,
            scale=scale,
        ),
        "T13": _fmt(zh, "framework.log.game_window_ratio_is_not_16_9"),
        "T14": _fmt(zh, "framework.log.current_task_task_name", task_name=task_name),
        "T15": _fmt(zh, "framework.log.current_task_task_name", task_name=task_name),
        "T16": _fmt(zh, "framework.log.current_task_task_name", task_name=task_name),
        "T17": _fmt(
            zh,
            "framework.log.target_image_template_name_similarity_conf",
            template_name=template_name,
            conf=conf,
        ),
        "T18": _fmt(zh, "framework.log.preparing_task_name_returning_to_home", task_name=task_name),
        "T19": _fmt(zh, "framework.log.task_failed_reason", task_name=task_name, reason=reason),
        "T20": _fmt(
            zh,
            "framework.log.periodic_diagnostic_event_event_code_task_id_task_name_detail",
            event=event,
            event_code=event_code,
            task_id=task_id,
            task_name=task_name,
            detail=detail,
        ),
        "T21": _fmt(
            zh,
            "framework.ui.scheduled_task_triggered_at_current_time_str_executing_tasks_task_ids",
            current_time_str=current_time_str,
            task_ids=scheduled_task_ids,
        ),
    }

    raw = dict(stage)
    raw.update(
        {
            "T13": _fmt(en, "framework.log.game_window_ratio_is_not_16_9"),
            "T14": _fmt(en, "framework.log.current_task_task_name", task_name=task_name),
            "T15": _fmt(en, "framework.log.current_task_task_name", task_name=task_name),
            "T16": _fmt(en, "framework.log.current_task_task_name", task_name=task_name),
            "T17": _fmt(
                en,
                "framework.log.target_image_template_name_similarity_conf",
                template_name=template_name,
                conf=conf,
            ),
            "T18": _fmt(en, "framework.log.preparing_task_name_returning_to_home", task_name=task_name),
            "T19": _fmt(en, "framework.log.task_failed_reason", task_name=task_name, reason=reason),
        }
    )

    expected_raw = [f"{cid}|{raw[cid]}" for cid in CASE_IDS]
    expected_stage = [f"{cid}|{stage[cid]}" for cid in CASE_IDS]
    return expected_raw, expected_stage


def _assert_lines(actual: list[str], expected: list[str], label: str) -> None:
    if actual == expected:
        return
    raise AssertionError(
        f"{label} output mismatch.\nexpected({len(expected)}): {expected}\nactual({len(actual)}):   {actual}"
    )


def _is_logger_warning_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "warning"


def _call_msgid(node: ast.Call) -> str | None:
    for kw in node.keywords:
        if kw.arg == "msgid" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _is_str_format_call(expr: ast.AST) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    if not isinstance(expr.func, ast.Attribute) or expr.func.attr != "format":
        return False
    return isinstance(expr.func.value, ast.Constant) and isinstance(expr.func.value.value, str)


def _assert_stage_transform(stage_entry: Path) -> None:
    transformed = stage_entry.read_text(encoding="utf-8")
    tree = ast.parse(transformed)

    if "_(f" in transformed:
        raise AssertionError("Stage still contains _(f\"...\") calls.")

    flags = {
        "explicit_percent": False,
        "explicit_dotformat": False,
        "scheduled_dotformat_no_msgid": False,
        "auto_percent": False,
        "auto_dotformat": False,
    }
    rewritten_count = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name) and node.func.id == "_":
            if node.args and isinstance(node.args[0], ast.JoinedStr):
                raise AssertionError("Stage still contains _() with JoinedStr argument.")
            msgid = _call_msgid(node)
            if msgid == "current_task_task_name" and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.BinOp) and isinstance(arg0.op, ast.Mod):
                    flags["explicit_percent"] = True
            if msgid == "periodic_diagnostic_event_event_code_task_id_task_name_detail" and node.args:
                if _is_str_format_call(node.args[0]):
                    flags["explicit_dotformat"] = True

        if not _is_logger_warning_call(node) or not node.args:
            continue

        first_arg = node.args[0]
        if isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Name) and first_arg.func.id == "_":
            inner = first_arg.args[0] if first_arg.args else None
            if isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.Mod):
                flags["auto_percent"] = True
            if inner is not None and _is_str_format_call(inner):
                flags["auto_dotformat"] = True

        if isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Attribute) and first_arg.func.attr == "format":
            base = first_arg.func.value
            if isinstance(base, ast.Call) and isinstance(base.func, ast.Name) and base.func.id == "_":
                rewritten_count += 1
                if base.args and isinstance(base.args[0], ast.Constant) and isinstance(base.args[0].value, str):
                    base_text = base.args[0].value
                    if (
                        "Scheduled task triggered at {current_time_str}, executing tasks: {task_ids}" in base_text
                        and _call_msgid(base) is None
                    ):
                        flags["scheduled_dotformat_no_msgid"] = True

    missing = [name for name, ok in flags.items() if not ok]
    if missing:
        raise AssertionError(f"Stage transform missing expected patterns: {missing}")
    if rewritten_count < 5:
        raise AssertionError(f"Expected >=5 rewritten _(...).format(...) logger payloads, got {rewritten_count}")


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
        f"--include-data-dir={ROOT / 'app' / 'framework' / 'i18n'}=app/framework/i18n",
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stress-test prepare_build against f-string / percent / .format i18n paths with Nuitka."
    )
    parser.add_argument(
        "--skip-nuitka",
        action="store_true",
        help="Skip Nuitka compile+run and only validate raw/stage Python behavior.",
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

    expected_raw, expected_stage = _expected_outputs()

    _prepare_mock_project()
    print(f"[1/7] stress project ready: {PROJECT_ROOT}")

    raw_lines = _run_program(PROJECT_ENTRY)
    _assert_lines(raw_lines, expected_raw, "raw python")
    print("[2/7] raw python output verified")

    stage_result = prepare_nuitka_stage(project_root=PROJECT_ROOT, stage_dir_name=STAGE_DIR_NAME)
    stage_entry = stage_result.stage_dir / "main.py"
    _assert_stage_transform(stage_entry)
    if stage_result.remaining_dynamic_fstring_calls != 0:
        raise AssertionError(
            "prepare_build still reports remaining dynamic _(fstring) calls: "
            f"{stage_result.remaining_dynamic_fstring_calls}"
        )
    print(
        "[3/7] stage transform verified "
        f"(changed {stage_result.py_files_changed}/{stage_result.py_files_scanned})"
    )

    stage_lines = _run_program(stage_entry, cwd=stage_result.stage_dir)
    _assert_lines(stage_lines, expected_stage, "staged python")
    print("[4/7] staged python output verified")

    if args.skip_nuitka:
        print("[5/7] skipped Nuitka by --skip-nuitka")
        print("[6/7] skipped executable checks")
        print("[7/7] stress test passed (python-only)")
        return 0

    build_root = SMOKE_ROOT / "build"
    raw_out = build_root / "raw"
    stage_out = build_root / "stage"
    raw_exe = _maybe_run_nuitka(PROJECT_ENTRY, raw_out, standalone=args.standalone)
    print(f"[5/7] raw Nuitka build ok (standalone={args.standalone})")
    stage_exe = _maybe_run_nuitka(stage_entry, stage_out, standalone=args.standalone)
    print(f"[6/7] staged Nuitka build ok (standalone={args.standalone})")

    raw_exe_lines = _run_executable(raw_exe)
    _assert_lines(raw_exe_lines, expected_raw, "raw exe")
    stage_exe_lines = _run_executable(stage_exe)
    _assert_lines(stage_exe_lines, expected_stage, "staged exe")

    print("[7/7] stress test passed")
    return 0


if __name__ == "__main__":
    stage_dir = PROJECT_ROOT / STAGE_DIR_NAME
    try:
        raise SystemExit(main())
    finally:
        keep = "--keep-temp" in sys.argv
        if not keep:
            try:
                cleanup_stage_dir(stage_dir)
            except Exception:
                pass
            if SMOKE_ROOT.exists():
                shutil.rmtree(SMOKE_ROOT, ignore_errors=True)
