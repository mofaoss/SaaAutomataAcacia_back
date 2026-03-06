import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional


_launch_lock = threading.Lock()
_last_game_process = None
_last_launch_ts = 0.0


def has_folder_in_path(path, dir_name):
    try:
        path = Path(path)
        for item in path.iterdir():
            if item.is_dir() and item.name == dir_name:
                return True
        return False
    except Exception:
        return False


def resolve_game_exe(start_path: str) -> str:
    start_path = os.path.normpath(start_path)
    if not os.path.exists(start_path):
        return ""

    # 1. 寻找“锚点”：确定真实的 snowbreak 根文件夹
    parts = start_path.split(os.sep)
    anchor_path = None

    # 1.1 先尝试“向上回溯”：如果传入的路径本身包含 snowbreak（如 D:/Games/Snowbreak/Launcher）
    for i, part in enumerate(parts):
        if "snowbreak" in part.lower():
            anchor_path = os.sep.join(parts[:i+1])
            break

    # 1.2 如果向上没找到（兜底逻辑），则“向下寻找”：从起点往下找名为/包含 snowbreak 的文件夹
    if not anchor_path:
        # 限制向下找文件夹的深度，防止用户误选 C:\ 或 D:\ 导致全盘疯狂扫描
        max_dir_depth = 3
        start_level = start_path.count(os.sep)

        for root, dirs, _ in os.walk(start_path):
            current_level = root.count(os.sep)
            if current_level - start_level >= max_dir_depth:
                # 关键：清空 dirs 列表，阻止 os.walk 继续深入当前分支
                dirs.clear()
                continue

            # 寻找包含 snowbreak 的目录 (忽略大小写)
            for d in dirs:
                if "snowbreak" in d.lower():
                    anchor_path = os.path.join(root, d)
                    break

            if anchor_path:
                break

    # 关键防跨游戏误判：如果连兜底都没找到 snowbreak 目录，说明选错地方了，直接阻断
    if not anchor_path:
        return ""

    # 2. 只有在确定了 snowbreak 锚点后，才在锚点内部深度遍历寻找 Game.exe
    max_exe_depth = 6
    anchor_level = anchor_path.count(os.sep)

    for root, _, files in os.walk(anchor_path):
        current_level = root.count(os.sep)
        if current_level - anchor_level > max_exe_depth:
            continue

        # 遍历文件，忽略大小写比对 (防止出现 game.exe)
        for file in files:
            if file.lower() == "game.exe":
                full_path = os.path.normpath(os.path.join(root, file))

                # 3. 终极验证：路径特征必须包含 binaries\win64
                # 使用 [\\/] 正则来兼容可能出现的正反斜杠混用情况
                if re.search(r"binaries[\\/]win64", full_path.lower()):
                    return full_path

    return ""


def resolve_userdir(start_path: str, exe_path: str) -> str:
    start_path = os.path.normpath(start_path)
    exe_path = os.path.normpath(exe_path)

    game_folder = os.path.normpath(os.path.join(os.path.dirname(exe_path), r"..\..\.."))
    root = os.path.normpath(os.path.join(game_folder, r".."))

    cand1 = os.path.join(root, "game")
    if os.path.isdir(cand1):
        return cand1.replace("\\", "/")

    if os.path.isdir(start_path) and os.path.isdir(os.path.join(start_path, "Game")):
        return start_path.replace("\\", "/")

    return root.replace("\\", "/")


def get_start_arguments(start_path, start_model, exe_path: str = None):
    start_path = os.path.normpath(start_path)

    if exe_path and os.path.exists(exe_path):
        user_dir = resolve_userdir(start_path, exe_path)
    else:
        user_dir = os.path.join(start_path, 'game').replace('\\', '/')

    if start_model == 0:
        if has_folder_in_path(start_path, "Temp"):
            return [
                "-FeatureLevelES31",
                "-ChannelID=jinshan",
                f"-userdir={user_dir}",
                '--launcher-language="en"',
                '--launcher-channel="CBJQos"',
                '--launcher-gamecode="cbjq"',
            ]
        return [
            "-FeatureLevelES31",
            "-ChannelID=jinshan",
            f"-userdir={user_dir}",
        ]

    if start_model == 1:
        return [
            "-FeatureLevelES31",
            "-ChannelID=bilibili",
            f"-userdir={user_dir}",
        ]

    if start_model == 2:
        return [
            "-FeatureLevelES31",
            "-channelid=seasun",
            "steamapps",
        ]

    return None


def launch_game_with_guard(
    start_path: str = None,
    game_channel: int = None,
    is_game_running: callable = None,
    logger=None,
    cooldown_seconds: int = 15,
) -> Dict[str, Any]:
    global _last_game_process
    global _last_launch_ts

    if start_path is None or game_channel is None:
        try:
            from app.common.config import config
            if start_path is None:
                start_path = config.LineEdit_game_directory.value
            if game_channel is None:
                game_channel = int(config.server_interface.value)
        except Exception:
            pass

    if is_game_running is None:
        try:
            from utils.win_utils import is_exist_snowbreak
            is_game_running = lambda: is_exist_snowbreak(game_channel)
        except Exception:
            is_game_running = lambda: False

    start_path = os.path.normpath(str(start_path or ""))
    if not start_path or start_path == "./":
        return {"ok": False, "error": "game directory is empty"}

    with _launch_lock:
        if _last_game_process is not None and _last_game_process.poll() is None:
            if logger:
                logger.info("检测到已由程序启动的游戏进程仍在运行，跳过重复启动")
            return {
                "ok": True,
                "already_running": True,
                "message": "game process already running",
                "pid": _last_game_process.pid,
                "process": _last_game_process,
            }

        now = time.time()
        if cooldown_seconds > 0 and now - _last_launch_ts < cooldown_seconds:
            remain = round(cooldown_seconds - (now - _last_launch_ts), 1)
            return {
                "ok": False,
                "error": f"launch cooldown in effect, retry after {remain}s",
            }

        if is_game_running():
            if logger:
                logger.info("游戏窗口已存在")
            return {"ok": True, "already_running": True, "message": "game window already exists", "process": None}

        exe_path = resolve_game_exe(start_path)
        if not exe_path or not os.path.exists(exe_path):
            if logger:
                logger.error(f"未找到游戏主程序 Game.exe，请检查路径: {start_path}")
            return {"ok": False, "error": f"game exe not found under: {start_path}"}

        launch_args = get_start_arguments(start_path, game_channel, exe_path=exe_path)
        if launch_args is None:
            if logger:
                logger.error(f"游戏启动失败未找到对应参数，start_path：{start_path}，game_channel:{game_channel}")
            return {"ok": False, "error": "failed to resolve launch arguments"}

        if logger:
            logger.debug(f"正在启动 {exe_path} {launch_args}")

        try:
            process = subprocess.Popen([exe_path] + launch_args)
        except Exception as e:
            if logger:
                logger.error(f"启动进程失败: {e}")
            return {"ok": False, "error": f"failed to spawn process: {e}"}

        _last_game_process = process
        _last_launch_ts = time.time()
        return {
            "ok": True,
            "already_running": False,
            "pid": process.pid,
            "exe_path": exe_path,
            "args": launch_args,
            "process": process,
        }
