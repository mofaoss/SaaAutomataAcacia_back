from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import Flyout, FlyoutView, InfoBar, InfoBarPosition

from app.framework.core.interfaces.game_environment import IGameEnvironment
from app.framework.infra.automation.timer import Timer
from app.framework.infra.config.app_config import config
from app.framework.infra.system.windows import get_hwnd
from app.framework.ui.shared.text import ui_text

from app.features.utils.home_navigation import back_to_home


_launch_lock = threading.Lock()
_last_game_process = None
_last_launch_ts = 0.0


def is_snowbreak_running(server_interface: int | None = None):
    if server_interface is None:
        try:
            server_interface = int(config.server_interface.value)
        except Exception:
            server_interface = 0

    if server_interface != 2:
        game_name = "尘白禁区"
        game_class = "UnrealWindow"
    else:
        game_name = "Snowbreak: Containment Zone"
        game_class = "UnrealWindow"

    return get_hwnd(game_name, game_class)


def has_folder_in_path(path: str, dir_name: str):
    try:
        path_obj = Path(path)
        for item in path_obj.iterdir():
            if item.is_dir() and item.name == dir_name:
                return True
        return False
    except Exception:
        return False


def resolve_game_exe(start_path: str) -> str:
    start_path = os.path.normpath(start_path)
    if not os.path.exists(start_path):
        return ""

    parts = start_path.split(os.sep)
    anchor_path = None
    for i, part in enumerate(parts):
        if "snowbreak" in part.lower():
            anchor_path = os.sep.join(parts[: i + 1])
            break

    if not anchor_path:
        max_dir_depth = 3
        start_level = start_path.count(os.sep)
        for root, dirs, _ in os.walk(start_path):
            current_level = root.count(os.sep)
            if current_level - start_level >= max_dir_depth:
                dirs.clear()
                continue

            for subdir in dirs:
                if "snowbreak" in subdir.lower():
                    anchor_path = os.path.join(root, subdir)
                    break
            if anchor_path:
                break

    if not anchor_path:
        return ""

    max_exe_depth = 6
    anchor_level = anchor_path.count(os.sep)
    for root, _, files in os.walk(anchor_path):
        current_level = root.count(os.sep)
        if current_level - anchor_level > max_exe_depth:
            continue

        for file_name in files:
            if file_name.lower() == "game.exe":
                full_path = os.path.normpath(os.path.join(root, file_name))
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


def get_start_arguments(start_path: str, start_model: int, exe_path: str | None = None):
    start_path = os.path.normpath(start_path)

    if exe_path and os.path.exists(exe_path):
        user_dir = resolve_userdir(start_path, exe_path)
    else:
        user_dir = os.path.join(start_path, "game").replace("\\", "/")

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
    start_path: str | None = None,
    game_channel: int | None = None,
    is_game_running: Callable[[], Any] | None = None,
    logger=None,
    cooldown_seconds: int = 15,
) -> dict[str, Any]:
    global _last_game_process
    global _last_launch_ts

    if start_path is None:
        start_path = config.LineEdit_game_directory.value
    if game_channel is None:
        game_channel = int(config.server_interface.value)
    if is_game_running is None:
        is_game_running = lambda: is_snowbreak_running(game_channel)

    start_path = os.path.normpath(str(start_path or ""))
    if not start_path or start_path == "./":
        return {"ok": False, "error": "game directory is empty"}

    with _launch_lock:
        if _last_game_process is not None and _last_game_process.poll() is None:
            if logger:
                logger.info(
                    ui_text(
                        "检测到已由程序启动的游戏进程仍在运行，跳过重复启动",
                        "Detected that the game process started by the program is still running, skipping duplicate startup",
                    )
                )
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
            return {"ok": False, "error": f"launch cooldown in effect, retry after {remain}s"}

        if is_game_running():
            if logger:
                logger.info(ui_text("游戏窗口已存在", "Game window already exists"))
            return {
                "ok": True,
                "already_running": True,
                "message": "game window already exists",
                "process": None,
            }

        exe_path = resolve_game_exe(start_path)
        if not exe_path or not os.path.exists(exe_path):
            if logger:
                logger.error(
                    ui_text(
                        f"未找到游戏主程序 Game.exe，请检查路径: {start_path}",
                        f"Game.exe not found, please check the path: {start_path}",
                    )
                )
            return {
                "ok": False,
                "error": ui_text(
                    f"game exe not found under: {start_path}",
                    f"Game executable not found under: {start_path}",
                ),
            }

        launch_args = get_start_arguments(start_path, game_channel, exe_path=exe_path)
        if launch_args is None:
            if logger:
                logger.error(
                    ui_text(
                        f"游戏启动失败未找到对应参数，start_path：{start_path}，game_channel:{game_channel}",
                        f"Failed to resolve launch arguments, start_path: {start_path}, game_channel: {game_channel}",
                    )
                )
            return {"ok": False, "error": ui_text("failed to resolve launch arguments", "Failed to resolve launch arguments")}

        if logger:
            logger.debug(ui_text(f"正在启动 {exe_path} {launch_args}", f"Starting {exe_path} {launch_args}"))

        try:
            process = subprocess.Popen([exe_path] + launch_args)
        except Exception as exc:
            if logger:
                logger.error(ui_text(f"启动进程失败: {exc}", f"Failed to spawn process: {exc}"))
            return {"ok": False, "error": ui_text(f"failed to spawn process: {exc}", f"Failed to spawn process: {exc}")}

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


class EnterGameService(IGameEnvironment):
    """Unified enter-game service for game environment, launch, and UI actions."""

    def __init__(self, is_non_chinese_ui: bool):
        self._is_non_chinese_ui = bool(is_non_chinese_ui)

    def is_running(self) -> bool:
        return bool(is_snowbreak_running())

    def launch(self, logger=None) -> dict[str, Any]:
        return launch_game_with_guard(logger=logger)

    def launch_game(self, logger=None) -> dict[str, Any]:
        return self.launch(logger=logger)

    def show_path_tutorial(self, *, host, anchor_widget, tutorial_page=None):
        payload = None
        if tutorial_page is not None and hasattr(tutorial_page, "build_path_tutorial_payload"):
            payload = tutorial_page.build_path_tutorial_payload(getattr(host, "_is_non_chinese_ui", False))
        if not payload:
            from app.features.modules.enter_game.ui.enter_game_periodic_page import EnterGamePage

            payload = EnterGamePage.build_path_tutorial_payload(getattr(host, "_is_non_chinese_ui", False))

        view = FlyoutView(
            title=payload.get("title", ""),
            content=payload.get("content", ""),
            image=payload.get("image", ""),
            isClosable=True,
        )
        view.widgetLayout.insertSpacing(1, 5)
        view.widgetLayout.addSpacing(5)
        flyout = Flyout.make(view, anchor_widget, host)
        view.closed.connect(flyout.close)

    @staticmethod
    def select_game_directory(parent, current_directory: str) -> str | None:
        folder = QFileDialog.getExistingDirectory(parent, "选择游戏文件夹", "./")
        if not folder or str(folder) == str(current_directory):
            return None
        return folder

    def on_select_directory_click(self, *, host, line_edit, settings_usecase) -> None:
        folder = self.select_game_directory(parent=host, current_directory=line_edit.text())
        if not folder or settings_usecase.is_same_game_directory(folder):
            return
        line_edit.setText(folder)
        line_edit.editingFinished.emit()

    @staticmethod
    def on_auto_open_toggled(*, host, state: int) -> None:
        status = "已开启" if state == 2 else "已关闭"
        action = "将" if state == 2 else "不会"
        InfoBar.success(
            title=status,
            content=ui_text(
                f"点击“开始”按钮时{action}自动启动游戏",
                f"Clicking the 'Start' button will {action}automatically launch the game",
            ),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=host,
        )


class EnterGameModule:
    def __init__(self, auto, logger):
        self.auto = auto
        self.logger = logger
        self.enter_game_flag = False
        self.is_log = True

    def run(self):
        self.is_log = config.isLog.value
        self.handle_game()
        back_to_home(self.auto, self.logger)

    def handle_starter_new(self):
        """处理官方新启动器窗口。"""
        timeout = Timer(20).start()
        while True:
            self.auto.take_screenshot()

            if self.auto.find_element("游戏运行中", "text", crop=(0.5, 0.5, 1, 1), is_log=self.is_log):
                break
            if self.auto.click_element("开始游戏", "text", crop=(0.5, 0.5, 1, 1), action="move_click", is_log=self.is_log):
                continue
            if self.auto.find_element("正在更新", "text", crop=(0.5, 0.5, 1, 1), is_log=self.is_log):
                time.sleep(5)
                timeout.reset()
                continue
            if self.auto.click_element("继续更新", "text", crop=(0.5, 0.5, 1, 1), action="mouse_click", is_log=self.is_log):
                time.sleep(5)
                timeout.reset()
                continue
            if self.auto.click_element("更新", "text", include=False, crop=(0.5, 0.5, 1, 1), action="mouse_click", is_log=self.is_log):
                time.sleep(2)
                timeout.reset()
                self.logger.info("需要更新")
                continue
            if timeout.reached():
                self.logger.error("启动器开始游戏超时")
                break

    def handle_game(self):
        """处理游戏窗口部分。"""
        timeout = Timer(180).start()
        while True:
            self.auto.take_screenshot()

            if self.auto.click_element("获得道具", "text", crop=(824 / 1920, 0, 1089 / 1920, 129 / 1080), is_log=self.is_log):
                break
            if self.auto.find_element("基地", "text", crop=(1598 / 1920, 678 / 1080, 1661 / 1920, 736 / 1080)) and self.auto.find_element(
                "任务", "text", crop=(1452 / 1920, 327 / 1080, 1529 / 1920, 376 / 1080), is_log=self.is_log
            ):
                self.logger.info("已进入游戏")
                break

            if self.auto.click_element(["游戏", "开始"], "text", crop=(852 / 1920, 920 / 1080, 1046 / 1920, 981 / 1080), is_log=self.is_log):
                time.sleep(2)
                continue
            if self.auto.click_element(["尘白禁区", "尘白", "禁区"], "text", crop=(812 / 1920, 814 / 1080, 1196 / 1920, 923 / 1080), is_log=self.is_log):
                time.sleep(1)
                continue

            if self.auto.click_element(["X", "x"], "text", crop=(1271 / 1920, 88 / 1080, 1890 / 1920, 367 / 1080), is_log=self.is_log):
                continue
            if self.auto.click_element("app/features/assets/start_game/newbird_cancel.png", "image", crop=(0.5, 0, 1, 0.5), is_log=self.is_log):
                continue

            if timeout.reached():
                self.logger.error("进入游戏超时")
                break
