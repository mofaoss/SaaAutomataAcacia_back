import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict

from app.utils.ui import ui_text
from app.infrastructure.config.app_config import config
from app.infrastructure.automation.timer import Timer


_launch_lock = threading.Lock()
_last_game_process = None
_last_launch_ts = 0.0

class EnterGameModule:
    def __init__(self, auto, logger):
        self.auto = auto
        self.logger = logger
        self.enter_game_flag = False
        self.is_log = True

    def run(self):
        # if not self.init_auto('game'):
        #     if not self.init_auto('starter'):
        #         return
        #     self.handle_starter_new()
        #     # 切换成auto_game
        #     time.sleep(10)
        #     self.init_auto('game', switch=True)
        # else:
        self.is_log = config.isLog.value
        self.handle_game()
        self.auto.back_to_home()

    def handle_starter_new(self):
        """
        处理官方新启动器启动器窗口部分
        :return:
        """
        timeout = Timer(20).start()
        while True:
            # 截图
            self.auto.take_screenshot()

            if self.auto.find_element('游戏运行中', 'text', crop=(0.5, 0.5, 1, 1), is_log=self.is_log):
                break
            # 对截图内容做对应处理
            if self.auto.click_element('开始游戏', 'text', crop=(0.5, 0.5, 1, 1), action='move_click',
                                       is_log=self.is_log):
                # self.logger.info("游戏无需更新或更新完毕")
                continue
            if self.auto.find_element('正在更新', 'text', crop=(0.5, 0.5, 1, 1), is_log=self.is_log):
                # 还在更新
                time.sleep(5)
                timeout.reset()
                continue
            if self.auto.click_element('继续更新', 'text', crop=(0.5, 0.5, 1, 1), action='mouse_click',
                                       is_log=self.is_log):
                time.sleep(5)
                timeout.reset()
                continue
            if self.auto.click_element('更新', 'text', include=False, crop=(0.5, 0.5, 1, 1), action='mouse_click',
                                       is_log=self.is_log):
                time.sleep(2)
                timeout.reset()
                self.logger.info("需要更新")
                continue
            if timeout.reached():
                self.logger.error("启动器开始游戏超时")
                break

    def handle_game(self):
        """处理游戏窗口部分"""
        timeout = Timer(180).start()
        while True:
            # 截图
            self.auto.take_screenshot()

            if self.auto.click_element('获得道具', 'text', crop=(824 / 1920, 0, 1089 / 1920, 129 / 1080),
                                       is_log=self.is_log):
                break
            # 对不同情况进行处理
            if self.auto.find_element('基地', 'text', crop=(
                    1598 / 1920, 678 / 1080, 1661 / 1920, 736 / 1080)) and self.auto.find_element(
                '任务', 'text', crop=(1452 / 1920, 327 / 1080, 1529 / 1920, 376 / 1080), is_log=self.is_log):
                self.logger.info("已进入游戏")
                break

            if self.auto.click_element(['游戏', '开始'], 'text', crop=(852 / 1920, 920 / 1080, 1046 / 1920, 981 / 1080),
                                       is_log=self.is_log):
                time.sleep(2)
                continue
            # 看到尘白禁区但是没看到开始游戏可以直接点尘白禁区跳过账号登录等待的那几秒
            if self.auto.click_element(['尘白禁区', '尘白', '禁区'], 'text',
                                       crop=(812 / 1920, 814 / 1080, 1196 / 1920, 923 / 1080),
                                       is_log=self.is_log):
                time.sleep(1)
                continue

            if self.auto.click_element(['X', 'x'], 'text', crop=(1271 / 1920, 88 / 1080, 1890 / 1920, 367 / 1080),
                                       is_log=self.is_log):
                continue
            if self.auto.click_element("app/presentation/resources/images/start_game/newbird_cancel.png", "image",
                                       crop=(0.5, 0, 1, 0.5), is_log=self.is_log):
                continue

            if timeout.reached():
                self.logger.error("进入游戏超时")
                break


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
            from app.infrastructure.config.app_config import config
            if start_path is None:
                start_path = config.LineEdit_game_directory.value
            if game_channel is None:
                game_channel = int(config.server_interface.value)
        except Exception:
            pass

    if is_game_running is None:
        try:
            from app.utils.windows import is_exist_snowbreak
            is_game_running = lambda: is_exist_snowbreak(game_channel)
        except Exception:
            is_game_running = lambda: False

    start_path = os.path.normpath(str(start_path or ""))
    if not start_path or start_path == "./":
        return {"ok": False, "error": "game directory is empty"}

    with _launch_lock:
        if _last_game_process is not None and _last_game_process.poll() is None:
            if logger:
                logger.info(ui_text("检测到已由程序启动的游戏进程仍在运行，跳过重复启动", "Detected that the game process started by the program is still running, skipping duplicate startup"))
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
                logger.info(ui_text("游戏窗口已存在", "Game window already exists"))
            return {"ok": True, "already_running": True, "message": "game window already exists", "process": None}

        exe_path = resolve_game_exe(start_path)
        if not exe_path or not os.path.exists(exe_path):
            if logger:
                logger.error(ui_text(f"未找到游戏主程序 Game.exe，请检查路径: {start_path}", f"Game.exe not found, please check the path: {start_path}"))
            return {"ok": False, "error": ui_text(f"game exe not found under: {start_path}", f"Game executable not found under: {start_path}")}

        launch_args = get_start_arguments(start_path, game_channel, exe_path=exe_path)
        if launch_args is None:
            if logger:
                logger.error(ui_text(f"游戏启动失败未找到对应参数，start_path：{start_path}，game_channel:{game_channel}", f"Failed to resolve launch arguments, start_path: {start_path}, game_channel: {game_channel}"))
            return {"ok": False, "error": ui_text("failed to resolve launch arguments", "Failed to resolve launch arguments")}

        if logger:
            logger.debug(ui_text(f"正在启动 {exe_path} {launch_args}", f"Starting {exe_path} {launch_args}"))

        try:
            process = subprocess.Popen([exe_path] + launch_args)
        except Exception as e:
            if logger:
                logger.error(ui_text(f"启动进程失败: {e}", f"Failed to spawn process: {e}"))
            return {"ok": False, "error": ui_text(f"failed to spawn process: {e}", f"Failed to spawn process: {e}")}

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



