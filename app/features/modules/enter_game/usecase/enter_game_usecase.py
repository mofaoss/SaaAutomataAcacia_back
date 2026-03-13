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

from app.framework.infra.automation.timer import Timer
from app.framework.infra.system.windows import get_hwnd
from app.framework.infra.config.app_config import config
from app.framework.core.module_system import Field, on_demand_module, periodic_module

from app.features.utils.home_navigation import back_to_home
from app.framework.i18n import _


_launch_lock = threading.Lock()
_last_game_process = None
_last_launch_ts = 0.0

_ENTER_GAME_FIELDS = {
    "CheckBox_open_game_directly": Field("自动拉起游戏", group="启动设置"),
    "LineEdit_game_directory": Field("游戏目录", group="启动设置"),
}


@periodic_module(
    "自动登录",
    periodic_role="bootstrap",
    fields=_ENTER_GAME_FIELDS,
    description=(
        "### 提示\n"
        "* 请先在设置中选择服务器。\n"
        "* 启用自动打开游戏后，定时任务可自动拉起游戏。\n"
        "* 请填写启动器中显示的游戏安装路径。"
    ),
    actions={
        "教程": "show_path_tutorial",
        "浏览": "select_game_directory",
    },
)
class EnterGameModule:
    def __init__(
        self,
        auto,
        logger,
        isLog: bool = False,
        CheckBox_open_game_directly: bool = False,
        LineEdit_game_directory: str = "./",
    ):
        self.auto = auto
        self.logger = logger
        self.is_log = bool(isLog)
        self.enter_game_flag = False
        self.auto_open_game = bool(CheckBox_open_game_directly)
        self.game_directory = str(LineEdit_game_directory or "./")

    def run(self):
        self.handle_game()
        back_to_home(self.auto, self.logger)

    @staticmethod
    def build_path_tutorial_payload(is_non_chinese_ui: bool) -> dict[str, str]:
        title = "How to find the game path" if is_non_chinese_ui else "如何查找对应游戏路径"
        content = (
            _("不管你是哪个渠道服玩家，第一步都应该先去设置里选服。\n"
            "国际服可选择类似 \"E:\\SteamLibrary\\steamapps\\common\\SNOWBREAK\" 的目录。\n"
            "官服和 B 服请先打开尘白启动器，在启动器设置中查看游戏安装目录。\n"
            "然后在下方路径中选择该目录即可。")
        )
        module_root = Path(__file__).resolve().parents[1]
        image_candidates = [
            module_root / "assets" / "images" / "path_tutorial.png",
            module_root.parents[1] / "assets" / "enter_game" / "path_tutorial.png",
        ]
        image_path = next((str(p) for p in image_candidates if p.exists()), str(image_candidates[0]))
        return {
            "title": str(title),
            "content": str(content),
            "image": image_path,
        }
    def show_path_tutorial(self, *, host=None, page=None, button=None, **_kwargs):
        service = EnterGameService(is_non_chinese_ui=getattr(host, "_is_non_chinese_ui", False), app_config=config)
        anchor = button or page or host
        if anchor is None or host is None:
            return
        service.show_path_tutorial(host=host, anchor_widget=anchor, tutorial_page=self)

    def select_game_directory(self, *, host=None, page=None, **_kwargs):
        if page is None or host is None:
            return
        line_edit = getattr(page, "LineEdit_game_directory", None)
        if line_edit is None:
            return
        folder = EnterGameService.select_game_directory(parent=host, current_directory=line_edit.text())
        if not folder or str(folder) == str(line_edit.text()):
            return
        line_edit.setText(folder)
        line_edit.editingFinished.emit()

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
                self.logger.info(_("需要更新"))
                continue
            if timeout.reached():
                self.logger.error(_("启动器开始游戏超时"))
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
                self.logger.info(_("已进入游戏"))
                break

            if self.auto.click_element(["游戏", "开始"], "text", crop=(852 / 1920, 920 / 1080, 1046 / 1920, 981 / 1080), is_log=self.is_log):
                time.sleep(2)
                continue
            if self.auto.click_element(["尘白禁区", "尘白", "禁区"], "text", crop=(812 / 1920, 814 / 1080, 1196 / 1920, 923 / 1080), is_log=self.is_log):
                time.sleep(1)
                continue

            if self.auto.click_element(["X", "x"], "text", crop=(1271 / 1920, 88 / 1080, 1890 / 1920, 367 / 1080), is_log=self.is_log):
                continue
            if self.auto.click_element("app/features/modules/enter_game/assets/images/newbird_cancel.png", "image", crop=(0.5, 0, 1, 0.5), is_log=self.is_log):
                continue

            if timeout.reached():
                self.logger.error(_("进入游戏超时"))
                break


def is_snowbreak_running(server_interface: int | None = None, app_config=None):
    if server_interface is None:
        try:
            server_interface = int(app_config.server_interface.value) if app_config is not None else 0
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
    app_config=None,
    logger=None,
    cooldown_seconds: int = 1,
) -> dict[str, Any]:
    global _last_game_process
    global _last_launch_ts

    if start_path is None:
        if app_config is None:
            return {"ok": False, "error": "missing app_config for game directory"}
        start_path = app_config.LineEdit_game_directory.value
    if game_channel is None:
        game_channel = int(app_config.server_interface.value) if app_config is not None else 0
    if is_game_running is None:
        is_game_running = lambda: is_snowbreak_running(game_channel, app_config=app_config)

    start_path = os.path.normpath(str(start_path or ""))
    if not start_path or start_path == "./":
        return {"ok": False, "error": "game directory is empty"}

    with _launch_lock:
        if _last_game_process is not None and _last_game_process.poll() is None:
            if logger:
                logger.info(
                    _('检测到程序启动的游戏进程仍在运行，跳过重复启动', msgid='detected_that_the_game_process_started_by_the_pr')
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
            return {"ok": False, "error": _(f"启动冷却中，{remain}s后重试", msgid='launch_cooldown_in_effect_retry_after_remain_s')}

        if is_game_running():
            if logger:
                logger.info(_('游戏窗口已存在', msgid='game_window_already_exists'))
            return {
                "ok": True,
                "already_running": True,
                "message": _('游戏窗口已存在', msgid='game_window_already_exists'),
                "process": None,
            }

        exe_path = resolve_game_exe(start_path)
        if not exe_path or not os.path.exists(exe_path):
            if logger:
                logger.error(
                    # _(f'Game.exe not found, please check the path: {start_path}', msgid='game_exe_not_found_please_check_the_path_start_p')
                    _(f'Game.exe 游戏可执行文件未找到，请检查路径: {start_path}', msgid='game_exe_not_found_please_check_the_path_start_p')
                )
            return {
                "ok": False,
                "error": _(f'Game.exe 游戏可执行文件未找到，请检查路径: {start_path}', msgid='game_exe_not_found_please_check_the_path_start_p'),
            }

        launch_args = get_start_arguments(start_path, game_channel, exe_path=exe_path)
        if launch_args is None:
            if logger:
                logger.error(
                    # _(f'Failed to resolve launch arguments, start_path: {start_path}, game_channel: {game_channel}', msgid='failed_to_resolve_launch_arguments_start_path_st')
                    _(f'无法解析启动参数，start_path: {start_path}, game_channel: {game_channel}', msgid='failed_to_resolve_launch_arguments_start_path_st')

                )
            return {"ok": False, "error": _('无法解析启动参数', msgid='failed_to_resolve_launch_arguments')}

        if logger:
            logger.debug(_(f'正在启动 {exe_path} {launch_args}', msgid='starting_exe_path_launch_args'))
        try:
            process = subprocess.Popen([exe_path] + launch_args)
        except Exception as exc:
            if logger:
                logger.error(_(f'无法启动进程: {exc}', msgid='failed_to_spawn_process_exc'))
            return {"ok": False, "error": _(f'无法启动进程: {exc}', msgid='failed_to_spawn_process_exc')}

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


class EnterGameService:
    """Unified enter-game service for game environment, launch, and UI actions."""

    def __init__(self, is_non_chinese_ui: bool, app_config=None):
        self._is_non_chinese_ui = bool(is_non_chinese_ui)
        self._app_config = app_config

    def is_running(self) -> bool:
        return bool(is_snowbreak_running(app_config=self._app_config))

    def launch(self, logger=None) -> dict[str, Any]:
        return launch_game_with_guard(logger=logger, app_config=self._app_config)

    def launch_game(self, logger=None) -> dict[str, Any]:
        return self.launch(logger=logger)

    def show_path_tutorial(self, *, host, anchor_widget, tutorial_page=None):
        payload = None
        if tutorial_page is not None and hasattr(tutorial_page, "build_path_tutorial_payload"):
            payload = tutorial_page.build_path_tutorial_payload(getattr(host, "_is_non_chinese_ui", False))
        if not payload:
            payload = EnterGameModule.build_path_tutorial_payload(getattr(host, "_is_non_chinese_ui", False))

        view = FlyoutView(
            title=str(payload.get("title", "") or ""),
            content=str(payload.get("content", "") or ""),
            image=str(payload.get("image", "") or ""),
            isClosable=True,
        )
        view.widgetLayout.insertSpacing(1, 5)
        view.widgetLayout.addSpacing(5)
        flyout = Flyout.make(view, anchor_widget, host)
        view.closed.connect(flyout.close)

    @staticmethod
    def select_game_directory(parent, current_directory: str) -> str | None:
        folder = QFileDialog.getExistingDirectory(parent, str("选择游戏文件夹"), "./")
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
        status = _(f"已开启", msgid='auto_open_toggled_on') if state == 2 else _(f"已关闭", msgid='auto_open_toggled_off')
        InfoBar.success(
            title=status,
            content=str(
                _(f"自启游戏", msgid='clicking_the_start_button_will_action_automatica')
            ),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=host,
        )
