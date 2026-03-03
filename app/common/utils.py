import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional

import cpufeature
import cv2
import numpy as np
import requests
import win32api
import win32con
import win32gui
from bs4 import BeautifulSoup
from requests import Timeout, RequestException

from app.common.config import config


_launch_lock = threading.Lock()
_last_game_process = None
_last_launch_ts = 0.0


def random_normal_distribution_int(a, b, n=15):
    """
    在区间 [a, b) 内产生符合正态分布的随机数，原理是取n个随机数的平均值来模拟正态分布
    :param a: 最小值
    :param b: 最大值
    :param n: 随机数的数量，值越大分布越集中
    :return:int
    """
    if a < b:
        output = np.mean(np.random.randint(a, b, size=n))
        return int(output.round())
    else:
        return b


def random_rectangle_point(area, n=3):
    """
    在区域内产生符合二维正态分布的随机点，通常在点击操作中使用
    :param area: ((upper_left_x, upper_left_y), (bottom_right_x, bottom_right_y)).
    :param n: 随机数的数量，值越大分布越集中
    :return: tuple(int): (x, y)
    """
    # print(f"{area=}")
    # area=((1285, 873), (1417, 921))
    x = random_normal_distribution_int(area[0][0], area[1][0], n=n)
    y = random_normal_distribution_int(area[0][1], area[1][1], n=n)
    return x, y


def is_fullscreen(hwnd):
    """
    判断窗口是否全屏运行
    :param hwnd: 窗口句柄
    :return: True if the window is fullscreen, False otherwise
    """
    # 获取窗口的矩形区域（left, top, right, bottom）
    window_rect = win32gui.GetWindowRect(hwnd)
    window_width = window_rect[2] - window_rect[0]  # 窗口宽度
    window_height = window_rect[3] - window_rect[1]  # 窗口高度

    # 获取屏幕的宽度和高度
    screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

    # 判断窗口大小是否与屏幕大小一致
    if window_width == screen_width and window_height == screen_height:
        return True
    else:
        return False


def get_all_children(widget):
    """
    递归地获取指定QWidget及其所有后代控件的列表。

    :param widget: QWidget对象，从该对象开始递归查找子控件。
    :return: 包含所有子控件（包括后代）的列表。
    """
    children = []
    for child in widget.children():
        children.append(child)
        children.extend(get_all_children(child))  # 递归调用以获取后代控件
    return children


# 添加随机噪声的函数
def add_noise(image, noise_factor=0.01):
    noise = np.random.normal(0, 1, image.shape) * noise_factor
    noisy_image = np.clip(image + noise, 0, 255).astype(np.uint8)
    return noisy_image


def enumerate_child_windows(parent_hwnd):
    def callback(handle, windows):
        windows.append(handle)
        return True

    child_windows = []
    win32gui.EnumChildWindows(parent_hwnd, callback, child_windows)
    return child_windows


def get_hwnd(window_title, window_class):
    """根据传入的窗口名和类型确定可操作的句柄"""
    hwnd = win32gui.FindWindow(None, window_title)
    handle_list = []
    if hwnd:
        handle_list.append(hwnd)
        handle_list.extend(enumerate_child_windows(hwnd))
        for handle in handle_list:
            class_name = win32gui.GetClassName(handle)
            if class_name == window_class:
                # 找到需要的窗口句柄
                return handle
    return None


def fetch_url(url: str, timeout: float = None, encoding: str = None):
    """
    通用网络请求函数

    参数:
        url: 请求的URL
        timeout: 超时时间（秒）
        encoding: 手动指定的编码格式

    返回:
        成功: requests.Response 对象
        失败: 包含错误信息的字典
    """
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/134.0.0.0 Safari/537.36"
    }
    port = config.update_proxies.value
    proxies = {
        "http": f"http://127.0.0.1:{port}",
        "https": f"http://127.0.0.1:{port}"
    } if port else None

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            proxies=proxies
        )
        if encoding:
            response.encoding = encoding
        return response
    except Timeout:
        return {"error": f"⚠️ 连接超时，请检查网络是否能连接 {url}"}
    except RequestException as e:
        return {"error": f"🔌 网络请求 {url} 失败: {e}"}
    except Exception as e:
        return {"error": f"❌ 请求 {url} 发生未知错误: {e}"}


def get_date_from_api(url=None):
    """
    获取具体的活动日期
    :param url: 尘白官网的内容api接口链接
    :return: {'爆爆菜园': '07.17-08.21', '噬神斗场': '07.10-08.07', '禁区协议': '07.28-08.11', '激战智域': '08.04-08.18', '勇者游戏': '08.07-08.21', '青之迷狂': '07.10-08.21', '奇迹诺言': '07.24-08.21', '铭心指任': '07.10-08.21', '风行影随': '07.31-08.21'}
    """

    def format_date(date_str):
        """格式化日期字符串为 MM.DD 格式"""
        parts = date_str.split('月')
        month = parts[0].zfill(2)
        day = parts[1].replace('日', '').zfill(2)
        return f"{month}.{day}"

    # url = 'https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid=7131&id=282'
    API_URL = url
    response = fetch_url(API_URL, timeout=3, encoding='utf-8')

    if isinstance(response, dict):  # 错误处理
        return response
    if response.status_code != 200:
        return {"error": f"请求失败，状态码: {response.status_code}"}

    try:
        data = response.json()
        content_html = data["data"][0]["content"]
    except (KeyError, IndexError, ValueError) as e:
        return {"error": f"❌ 解析JSON数据失败: {e}"}

    soup = BeautifulSoup(content_html, 'html.parser')
    paragraphs = soup.find_all('p')
    result_dict = {}
    current_index = 0
    while current_index < len(paragraphs):
        p = paragraphs[current_index]
        text = p.get_text(strip=True)
        # print(text)
        # 提取角色共鸣,同时还需要判断句号不在句子中，排除干扰
        if "角色共鸣" in text and "✧" in text and "。" not in text:
            match = re.search(r"「(.*?)」", text)
            if match:
                role_name = match.group(1)
            else:
                return {"error": f"未匹配到“角色共鸣”"}
            current_index += 1
            time_text = paragraphs[current_index].get_text(strip=True)
            if "活动时间：" in time_text and "常驻" not in time_text:
                dates = re.findall(r"\d+月\d+日", time_text)
                # 检查是否匹配到两个日期
                if len(dates) >= 2:
                    start = format_date(dates[0])
                    end = format_date(dates[1])
                    result_dict[role_name] = f"{start}-{end}"
                else:
                    print(f"警告：角色共鸣时间格式异常: {time_text}")
                    # 跳过或记录错误

        # 提取活动任务时间
        elif "【调查清单】活动任务" in text:
            current_index += 1
            time_text = paragraphs[current_index].get_text(strip=True)
            if "常驻" not in time_text:
                dates = re.findall(r"\d+月\d+日", time_text)
                if len(dates) >= 2:
                    start = format_date(dates[0])
                    end = format_date(dates[1])
                    result_dict["调查清单"] = f"{start}-{end}"
                else:
                    print(f"警告：调查清单时间格式异常: {time_text}")

        # 提取挑战玩法
        elif "挑战玩法" in text and "✧" in text:
            challenge_name = re.search(r"【(.*?)】", text).group(1)
            time_text = ''
            while "活动时间" not in time_text:
                current_index += 1
                time_text = paragraphs[current_index].get_text(strip=True)
            if "常驻" not in time_text:
                dates = re.findall(r"\d+月\d+日", time_text)
                if len(dates) >= 2:
                    start = format_date(dates[0])
                    end = format_date(dates[1])
                    result_dict[challenge_name] = f"{start}-{end}"
                else:
                    print(f"警告：挑战玩法时间格式异常: {time_text}")

        elif "趣味玩法" in text and "✧" in text:
            play_name = re.search(r"【(.*?)】", text).group(1)
            current_index += 1
            time_text = paragraphs[current_index].get_text(strip=True)
            if "常驻" not in time_text:
                dates = re.findall(r"\d+月\d+日", time_text)
                if len(dates) >= 2:
                    start = format_date(dates[0])
                    end = format_date(dates[1])
                    result_dict[play_name] = f"{start}-{end}"
                else:
                    # print(f"警告：趣味玩法时间格式异常: {time_text}")
                    pass

        current_index += 1

    if len(result_dict) != 0:
        return result_dict
    else:
        return {"error": f"未匹配到任何活动。检查 {url} 是否正确"}


def cpu_support_avx2():
    """
    判断 CPU 是否支持 AVX2 指令集。
    """
    config.set(config.cpu_support_avx2, cpufeature.CPUFeature["AVX2"])
    return cpufeature.CPUFeature["AVX2"]


def count_color_blocks(image, lower_color, upper_color, preview=False):
    """计算颜色块数量，并可选择预览掩膜"""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_color, upper_color)

    if preview:  # 添加预览模式
        # 将掩膜与原图叠加显示
        masked_img = cv2.bitwise_and(image, image, mask=mask)
        cv2.imshow("Mask Preview", masked_img)
        # cv2.waitKey(1)  # 保持1ms后自动关闭（非阻塞模式）
        cv2.waitKey(0)  # 按任意键继续（阻塞模式）

    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return len(contours)


def rgb_to_opencv_hsv(r, g, b):
    # 输入：RGB 值（范围 0-255）
    # 输出：OpenCV 格式的 HSV 值（H:0-179, S:0-255, V:0-255）
    rgb_color = np.uint8([[[b, g, r]]])  # OpenCV 使用 BGR 顺序
    hsv_color = cv2.cvtColor(rgb_color, cv2.COLOR_BGR2HSV)
    return hsv_color[0][0]


def get_hsv(target_rgb):
    # 转换为 OpenCV 的 HSV 值
    h, s, v = rgb_to_opencv_hsv(*target_rgb)

    # 设置容差范围
    h_tolerance = 2
    s_tolerance = 35
    v_tolerance = 10

    lower_color = np.array([max(0, h - h_tolerance), max(0, s - s_tolerance), max(0, v - v_tolerance)])
    upper_color = np.array([min(179, h + h_tolerance), min(255, s + s_tolerance), min(255, v + v_tolerance)])

    print(f"Lower HSV: {lower_color}")
    print(f"Upper HSV: {upper_color}")


def get_gitee_text(text_path: str):
    """
        从Gitee获取文本文件并按行返回内容

        参数:
            text_path: 文件在仓库中的路径 (如: "requirements.txt")

        返回:
            成功: 包含每行文本的列表
            失败: None
    """
    url = f"https://gitee.com/laozhu520/auto_chenbai/raw/main/{text_path}"
    response = fetch_url(url, timeout=3)

    if isinstance(response, dict):  # 错误处理
        return response
    if response.status_code != 200:
        print(f"请求失败，状态码: {response.status_code}")
        return None

    # 自动检测编码并处理文本
    response.encoding = response.apparent_encoding
    return response.text.splitlines()


def get_cloudflare_data():
    """从cloudflare上获取数据"""
    url = "https://saapanel.netlify.app/api/config"
    response = fetch_url(url)
    if isinstance(response, dict):
        return response
    if response.status_code != 200:
        return {"error": f"请求失败，状态码: {response.status_code}"}
    try:
        return response.json()
    except Exception as e:
        return {"error": f"解析JSON失败: {e}"}


def get_start_arguments(start_path, start_model, exe_path: str = None):
    """
    自动判断是什么服，什么启动器，返回对应的启动参数
    :param start_path: 启动路径，由用户提供，可以在启动器查看
    :param start_model: 由用户设置，在SAA设置中选服
    :return:
    """
    start_path = os.path.normpath(start_path)

    # 如果传了 exe_path，就用它推 userdir；否则退回老逻辑
    if exe_path and os.path.exists(exe_path):
        user_dir = resolve_userdir(start_path, exe_path)
    else:
        user_dir = os.path.join(start_path, 'game').replace('\\', '/')

    arg = None

    # 国服
    if start_model == 0:
        if has_folder_in_path(start_path, "Temp"):
            arg = [
                "-FeatureLevelES31",
                "-ChannelID=jinshan",
                f"-userdir={user_dir}",
                '--launcher-language="en"',
                '--launcher-channel="CBJQos"',
                '--launcher-gamecode="cbjq"',
            ]
        else:
            arg = [
                "-FeatureLevelES31",
                "-ChannelID=jinshan",
                f"-userdir={user_dir}",
            ]

    # b服
    elif start_model == 1:
        arg = [
            "-FeatureLevelES31",
            "-ChannelID=bilibili",
            f"-userdir={user_dir}",
        ]

    # 国际服（Steam/Epic）
    elif start_model == 2:
        arg = [
            "-FeatureLevelES31",
            "-channelid=seasun",
            "steamapps",
        ]

    return arg


def launch_game_with_guard(start_path: Optional[str] = None,
                           game_channel: Optional[int] = None,
                           logger=None,
                           cooldown_seconds: int = 15) -> Dict[str, Any]:
    """统一游戏启动入口：包含重复启动保护与冷却防抖。"""
    global _last_game_process
    global _last_launch_ts

    if start_path is None:
        start_path = config.LineEdit_game_directory.value
    if game_channel is None:
        game_channel = config.server_interface.value

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

        if is_exist_snowbreak():
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

        process = subprocess.Popen([exe_path] + launch_args)
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


def resolve_game_exe(start_path: str) -> str:
    start_path = os.path.normpath(start_path)

    candidates = [
        os.path.join(start_path, r"game\Game\Binaries\Win64\Game.exe"),
        os.path.join(start_path, r"Game\Binaries\Win64\Game.exe"),
        # 容错：用户选到子目录
        os.path.join(start_path, r"..\game\Game\Binaries\Win64\Game.exe"),
        os.path.join(start_path, r"..\Game\Binaries\Win64\Game.exe"),
    ]

    for p in candidates:
        p = os.path.normpath(p)
        if os.path.exists(p):
            return p

    # 兜底：递归找 Game.exe 且包含 Binaries\Win64
    for root, _, files in os.walk(start_path):
        if "Game.exe" in files:
            p = os.path.normpath(os.path.join(root, "Game.exe"))
            if re.search(r"binaries\\win64", p.lower()):
                return p

    return ""


def resolve_userdir(start_path: str, exe_path: str) -> str:
    """
    目标：userdir（通常是 <root>/game）
    """
    start_path = os.path.normpath(start_path)
    exe_path = os.path.normpath(exe_path)

    # 从 exe 推 root：.../Game/Binaries/Win64/Game.exe -> 往上 3 层到 .../Game
    game_folder = os.path.normpath(os.path.join(os.path.dirname(exe_path), r"..\..\.."))
    # 再往上一层通常是安装根目录（例如 SNOWBREAK）
    root = os.path.normpath(os.path.join(game_folder, r".."))

    # 兼容原来的设计：优先 <root>/game
    cand1 = os.path.join(root, "game")
    if os.path.isdir(cand1):
        return cand1.replace("\\", "/")

    # 有些结构可能直接就是 root 本身作为 userdir（或 game_folder）
    if os.path.isdir(start_path) and os.path.isdir(os.path.join(start_path, "Game")):
        # 用户很可能选的是 root
        return start_path.replace("\\", "/")

    return root.replace("\\", "/")


def has_folder_in_path(path, dir_name):
    """
    判断指定路径是否包含名为 dir_name 的文件夹（区分大小写）
    :param path: 要检查的路径
    :param dir_name: 要检查的文件夹名字
    :return: bool: 如果包含 dir_name 文件夹返回 True，否则返回 False
    """
    try:
        path = Path(path)
        for item in path.iterdir():
            if item.is_dir() and item.name == dir_name:
                return True
        return False
    except Exception as e:
        print(f"检查子文件夹出错:{e}")
        return False


def is_exist_snowbreak():
    if config.server_interface.value != 2:
        game_name = '尘白禁区'
        game_class = 'UnrealWindow'
    else:
        game_name = 'Snowbreak: Containment Zone'  # 国际服
        game_class = 'UnrealWindow'
    return get_hwnd(game_name, game_class)


def get_local_version(file_path="update_data.txt"):
    """
        从txt文件中读取第二行的版本信息

        参数:
            file_path (str): txt文件路径

        返回:
            str: 版本信息字符串
        """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # 读取所有行
            lines = file.readlines()
            # 检查是否有至少两行
            if len(lines) >= 2:
                # 返回第二行并去除前后空白字符
                return lines[1].strip()
            else:
                print("文件行数不足，没有版本信息")
                return None
    except FileNotFoundError:
        print(f"{file_path}文件未找到")
        return None
    except Exception as e:
        print(f"读取文件时出错: {str(e)}")
        return None


def get_github_latest_release_version(repo_url: str):
    """
    根据仓库地址获取 GitHub 最新 release 的版本号。

    参数:
        repo_url: 仓库地址，如 https://github.com/owner/repo

    返回:
        成功: 版本号字符串（如 2.0.9）
        失败: None
    """
    if not repo_url:
        return None

    match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if not match:
        return None

    owner, repo = match.group(1), match.group(2)
    repo = repo.replace('.git', '').strip('/')

    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    response = fetch_url(api_url, timeout=5)

    if isinstance(response, dict):
        return None
    if response.status_code != 200:
        return None

    try:
        data = response.json()
        tag_name = (data.get("tag_name") or "").strip()
        if not tag_name:
            return None
        return tag_name.lstrip('vV')
    except Exception:
        return None


def _parse_github_repo(repo_url: str):
    if not repo_url:
        return None, None

    match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if not match:
        return None, None

    owner, repo = match.group(1), match.group(2)
    return owner, repo.replace('.git', '').strip('/')


def is_prerelease_version(version: str) -> bool:
    if not version:
        return False
    raw = str(version).strip().lower()
    return bool(re.search(r'(?:-|_|\.)?(alpha|a|beta|b|rc|pre|preview)(?:-|_|\.)?\d*', raw))


def _pick_release_download_url(release: dict):
    if not isinstance(release, dict):
        return None

    assets = release.get("assets")
    if not isinstance(assets, list) or not assets:
        return None

    exe_url = None
    msi_url = None
    portable_zip_url = None
    portable_tokens = ("portable", "便携", "移动版", "green")

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        url = (asset.get("browser_download_url") or "").strip()
        if not url:
            continue

        name = (asset.get("name") or "").strip().lower()
        if name.endswith(".exe") and exe_url is None:
            exe_url = url
            continue

        if name.endswith(".msi") and msi_url is None:
            msi_url = url
            continue

        if name.endswith(".zip") and any(token in name for token in portable_tokens) and portable_zip_url is None:
            portable_zip_url = url

    return exe_url or msi_url or portable_zip_url


def get_github_release_channels(repo_url: str):
    """
    获取 GitHub 的稳定版与预发布版版本信息。

    返回示例：
    {
        "latest": {"version": "2.1.0", "url": "..."} | None,
        "prerelease": {"version": "2.3.0-beta", "url": "..."} | None
    }
    """
    result = {
        "latest": None,
        "prerelease": None
    }

    owner, repo = _parse_github_repo(repo_url)
    if not owner or not repo:
        return result

    # 优先使用 releases 列表，一次请求拿到 stable + prerelease
    list_api = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=30"
    response = fetch_url(list_api, timeout=6)

    if not isinstance(response, dict) and response.status_code == 200:
        try:
            releases = response.json()
            if isinstance(releases, list):
                for release in releases:
                    if not isinstance(release, dict):
                        continue
                    if release.get("draft"):
                        continue

                    tag_name = (release.get("tag_name") or "").strip().lstrip('vV')
                    if not tag_name:
                        continue

                    release_item = {
                        "version": tag_name,
                        "url": (release.get("html_url") or "").strip() or f"{repo_url.rstrip('/')}/releases",
                        "download_url": _pick_release_download_url(release)
                    }

                    if release.get("prerelease"):
                        current = result["prerelease"]
                        if current is None or is_remote_version_newer(current["version"], tag_name):
                            result["prerelease"] = release_item
                    else:
                        current = result["latest"]
                        if current is None or is_remote_version_newer(current["version"], tag_name):
                            result["latest"] = release_item
        except Exception:
            pass

    # 兜底：若列表解析失败，至少保证 latest 可用
    if result["latest"] is None:
        latest_api = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        latest_response = fetch_url(latest_api, timeout=5)
        if not isinstance(latest_response, dict) and latest_response.status_code == 200:
            try:
                data = latest_response.json()
                tag_name = (data.get("tag_name") or "").strip().lstrip('vV')
                if tag_name:
                    result["latest"] = {
                        "version": tag_name,
                        "url": (data.get("html_url") or "").strip() or f"{repo_url.rstrip('/')}/releases",
                        "download_url": _pick_release_download_url(data)
                    }
            except Exception:
                pass

    return result


def is_remote_version_newer(local_version: str, remote_version: str) -> bool:
    """
    判断线上版本是否高于本地版本。

    规则：
    - 支持 alpha/beta/rc 等预发布标识（例如 2.1.0 > 2.1.0-beta）
    - 若无法识别预发布标识，则回退为纯数字段比较，避免误报
    """

    stage_rank = {
        'alpha': 0,
        'a': 0,
        'beta': 1,
        'b': 1,
        'rc': 2,
        'pre': 2,
        'preview': 2,
    }

    def _parse(version: str):
        if not version:
            return None

        raw = str(version).strip().lstrip('vV').lower()
        if not raw:
            return None

        numbers = tuple(int(num) for num in re.findall(r'\d+', raw))
        if not numbers:
            return None

        core = numbers[:3]
        if len(core) < 3:
            core = core + (0,) * (3 - len(core))

        # 识别常见预发布标识：2.1.0-beta / 2.1.0rc1 / 2.1.0-alpha.2
        # 未识别到则按正式版处理（兼容 2.1.0-n 这类渠道后缀）
        match = re.search(r'(?:-|_|\.)?(alpha|a|beta|b|rc|pre|preview)(?:-|_|\.)?(\d*)', raw)
        if not match:
            return core, 3, 0

        stage = match.group(1)
        stage_num_text = match.group(2)
        stage_num = int(stage_num_text) if stage_num_text else 0
        return core, stage_rank.get(stage, 3), stage_num

    local_parsed = _parse(local_version)
    remote_parsed = _parse(remote_version)

    if not remote_parsed:
        return False
    if not local_parsed:
        return True

    return remote_parsed > local_parsed


if __name__ == "__main__":
    # get_hsv((124, 174, 235))
    # get_hsv((112, 165, 238))
    # get_hsv((205, 202, 95))
    # get_hsv((209,207, 96))
    get_cloudflare_data()
