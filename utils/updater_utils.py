from __future__ import annotations

import os
import sys
import re
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple
import subprocess
import requests
from PySide6.QtCore import QThread, Signal
from urllib.parse import urlparse

from packaging.version import parse as parse_version


# Lock to prevent concurrent API calls during startup
_fetch_lock = threading.Lock()
logger = logging.getLogger(__name__)


def get_app_root():
    """获取程序运行时的根目录，兼容开发环境和 Nuitka 打包环境"""
    # Nuitka 和 PyInstaller 在打包后通常会设置 sys.frozen 或类似标识
    # 但最稳妥的方法是判断 sys.argv[0] 或 sys.executable
    if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):
        # 打包后的 exe 所在目录
        return os.path.dirname(sys.executable)
    # 开发环境下，假设当前文件在 utils 目录，根目录是上一级
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def get_binary_path(bin_name):
    """专门用于获取 binary 目录下工具的路径"""
    root = get_app_root()
    # 无论打包还是开发，确保路径指向 app/resource/binary/xxx.exe
    path = os.path.join(root, "app", "resource", "binary", bin_name)
    return path


def _resolve_proxies(proxies: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    if proxies is not None:
        return proxies
    try:
        from app.common.config import config
        port = config.update_proxies.value
        if port:
            return {
                "http": f"http://127.0.0.1:{port}",
                "https": f"http://127.0.0.1:{port}",
            }
    except Exception:
        pass
    return None


def _normalize_tag(tag: str) -> str:
    return (tag or "").strip().lstrip("vV")


def _parse_github_repo(repo_url: str) -> Tuple[Optional[str], Optional[str]]:
    if not repo_url:
        return None, None
    match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if not match:
        return None, None
    owner = (match.group(1) or "").strip()
    repo = (match.group(2) or "").strip().replace(".git", "").strip("/")
    if not owner or not repo:
        return None, None
    return owner, repo


def _score_exe(name_lower: str) -> int:
    score = 0
    if "64" in name_lower or "x64" in name_lower or "win64" in name_lower:
        score += 100
    if "x86" in name_lower or "32" in name_lower or "win32" in name_lower:
        score -= 100
    return score


def extract_best_download_url(assets: list) -> Optional[str]:
    if not isinstance(assets, list):
        return None

    exe_candidates = []
    portable_zip_candidates = []
    portable_tokens = ("portable", "green", "便携")

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        url = (asset.get("browser_download_url") or "").strip()
        if not url:
            continue

        name = (asset.get("name") or "").strip().lower()
        if name.endswith(".exe"):
            exe_candidates.append((url, _score_exe(name), len(name)))
            continue

        if name.endswith(".zip") and any(token in name for token in portable_tokens):
            portable_zip_candidates.append((url, len(name)))

    if exe_candidates:
        exe_candidates.sort(key=lambda item: (item[1], item[2]), reverse=True)
        return exe_candidates[0][0]

    if portable_zip_candidates:
        portable_zip_candidates.sort(key=lambda item: item[1], reverse=True)
        return portable_zip_candidates[0][0]

    return None


def _build_release_item(release: Dict[str, Any]) -> Optional[Dict[str, Optional[str]]]:
    tag_name = _normalize_tag(str(release.get("tag_name") or ""))
    if not tag_name:
        return None
    return {
        "version": tag_name,
        "url": (release.get("html_url") or "").strip() or None,
        "download_url": extract_best_download_url(release.get("assets") or []),
    }


def _choose_newer(current: Optional[Dict[str, Any]], candidate: Dict[str, Any]) -> Dict[str, Any]:
    if not current:
        return candidate
    if parse_version(str(candidate["version"])) > parse_version(str(current["version"])):
        return candidate
    return current


def get_github_release_channels(
    repo_url: str,
    timeout: float = 8,
    per_page: int = 15,
    proxies: Optional[Dict[str, str]] = None,
) -> Dict[str, Optional[Dict[str, Optional[str]]]]:
    from app.common.config import config

    CACHE_TTL_SECONDS = 3600 * 8  # 8 hours

    result: Dict[str, Optional[Dict[str, Optional[str]]]] = {
        "latest": None,
        "prerelease": None,
    }

    owner, repo = _parse_github_repo(repo_url)
    if not owner or not repo:
        return result

    # 1. Check Config Cache First
    cached_obj = config.github_api_cache.value or {}
    if "timestamp" in cached_obj and "data" in cached_obj:
        if time.time() - cached_obj["timestamp"] < CACHE_TTL_SECONDS:
            return cached_obj["data"]  # Return ultra-fast, minimal parsed cache

    # 2. Cache Miss or Expired: Fetch from API (with lock to prevent concurrent startup calls)
    with _fetch_lock:
        # Double-check cache in case another thread populated it while waiting for lock
        cached_obj = config.github_api_cache.value or {}
        if "timestamp" in cached_obj and "data" in cached_obj:
            if time.time() - cached_obj["timestamp"] < CACHE_TTL_SECONDS:
                return cached_obj["data"]

        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page={max(1, int(per_page))}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "SaaAutomataAcacia-Updater",
        }
        proxies = _resolve_proxies(proxies)

        try:
            response = requests.get(api_url, headers=headers, timeout=timeout, proxies=proxies)
            if response.status_code == 200:
                releases = response.json()
                if isinstance(releases, list):
                    # Process the bloated raw data into our minimal `result`
                    for release in releases:
                        if not isinstance(release, dict) or bool(release.get("draft")):
                            continue
                        item = _build_release_item(release)
                        if not item:
                            continue
                        if bool(release.get("prerelease")):
                            result["prerelease"] = _choose_newer(result["prerelease"], item)
                        else:
                            result["latest"] = _choose_newer(result["latest"], item)

                    # Save ONLY the minimal result and timestamp to config.json
                    config.set(config.github_api_cache, {
                        "timestamp": time.time(),
                        "data": result
                    })
                    return result

            elif response.status_code in (403, 429):
                logger.error(f"GitHub API {response.status_code} Rate Limit hit! Using fallback.")
            else:
                logger.error(f"GitHub API Error {response.status_code}: {response.text}")

        except Exception as e:
            logger.error(f"GitHub API Connection Error: {e}")

    # 3. Fallback: If API failed, try to use expired config cache
    if "data" in cached_obj and cached_obj["data"].get("latest"):
        logger.warning("Falling back to expired config cache due to API failure.")
        return cached_obj["data"]

    return result


def is_remote_version_newer(local_version: str, remote_version: str) -> bool:
    local_norm = _normalize_tag(local_version)
    remote_norm = _normalize_tag(remote_version)
    if not remote_norm:
        return False
    if not local_norm:
        return True
    return parse_version(remote_norm) > parse_version(local_norm)


def is_prerelease_version(version: str) -> bool:
    normalized = _normalize_tag(version)
    if not normalized:
        return False
    return bool(parse_version(normalized).is_prerelease)


def get_github_latest_release_version(repo_url: str) -> Optional[str]:
    channels = get_github_release_channels(repo_url)
    latest = channels.get("latest") if isinstance(channels, dict) else None
    if not isinstance(latest, dict):
        return None
    version = (latest.get("version") or "").strip()
    return version or None


def get_local_version(file_path="update_data.txt"):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            if len(lines) >= 2:
                return lines[1].strip()
            return None
    except Exception:
        return None


def get_best_update_candidate(repo_url: str, local_version: str, check_prerelease: bool = False) -> Optional[Dict[str, Any]]:
    """
    Makes a SINGLE call to get release channels and determines the absolute best candidate
    based on the user's prerelease preferences.
    """
    channels = get_github_release_channels(repo_url)
    stable = channels.get("latest")
    prerelease = channels.get("prerelease")

    if not stable and not prerelease:
        return None

    should_check_prerelease = is_prerelease_version(local_version) or check_prerelease
    candidates = []

    if stable and isinstance(stable, dict):
        candidates.append({
            "version": stable.get("version"),
            "download_url": stable.get("download_url"),
            "is_prerelease": False
        })

    if prerelease and isinstance(prerelease, dict) and should_check_prerelease:
        candidates.append({
            "version": prerelease.get("version"),
            "download_url": prerelease.get("download_url"),
            "is_prerelease": True
        })

    if not candidates:
        return None

    best = candidates[0]
    for candidate in candidates[1:]:
        if is_remote_version_newer(best["version"], candidate["version"]):
            best = candidate

    return best


def resolve_batch_dir(downloaded_path: str) -> str:
    """
    判断 downloaded_path 是否位于受保护目录（如 Program Files、系统盘根目录等），
    若是则将批处理脚本写入用户可写的 AppData 目录，否则沿用文件所在目录。
    """
    # 受保护的前缀目录（统一转小写比较）
    protected_prefixes = (
        os.environ.get("ProgramFiles", r"C:\Program Files").lower(),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)").lower(),
        os.environ.get("ProgramW6432", r"C:\Program Files").lower(),
        os.environ.get("SystemRoot", r"C:\Windows").lower(),
        os.environ.get("SystemDrive", "c:").lower() + os.sep,  # 仅 C:\ 根目录本身
    )

    download_dir = os.path.dirname(os.path.abspath(downloaded_path)).lower()

    is_protected = any(download_dir.startswith(p) for p in protected_prefixes)

    if is_protected:
        app_name = "SaaAutomataAcacia"
        return os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            app_name
        )

    # 非受保护目录：直接使用下载文件所在目录
    return os.path.dirname(downloaded_path)


class UpdateDownloadThread(QThread):
    progress_signal = Signal(int)
    finished_signal = Signal(str)
    fallback_signal = Signal(str, str)

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

        # 使用适配函数获取路径
        self.aria2c_path = get_binary_path("aria2c.exe")
        self.temp_dir = os.path.join(get_app_root(), "temp", "update")

        # 解析文件名 (修复之前提到的 parsed_url 报错)
        from urllib.parse import urlparse
        parsed_url = urlparse(download_url)
        self.filename = os.path.basename(parsed_url.path) or "update_package.zip"
        self.filepath = os.path.join(self.temp_dir, self.filename)

        # 调试用：打包后如果报错，可以在日志里打印这个路径看看它到底指向哪
        print(f"DEBUG: aria2c path is {self.aria2c_path}")

    def run(self):
        process = None  # 显式初始化，避免 NameError
        try:
            # 确保临时目录存在
            os.makedirs(self.temp_dir, exist_ok=True)

            # 如果旧文件存在，先尝试删除
            if os.path.exists(self.filepath):
                try:
                    os.remove(self.filepath)
                except Exception:
                    pass

            # 构建 aria2c 命令
            aria2c_cmd = [
                self.aria2c_path,
                "-d", self.temp_dir,
                "-o", self.filename,
                "-x", "8",
                "-s", "8",
                "--lowest-speed-limit=100K",
                "--allow-overwrite=true",
                self.download_url
            ]

            # 启动进程
            process = subprocess.Popen(
                aria2c_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # 读取输出（用于以后扩展进度条）
            if process.stdout:
                for line in process.stdout:
                    # TODO: 在这里解析 line 提取百分比并 emit(progress_signal)
                    pass

            process.wait()

            # 检查下载状态
            if process.returncode != 0:
                self.fallback_signal.emit("下载中断", "下载器异常退出，可尝试浏览器下载")
                return

            # 校验文件大小（防止下载到错误的 HTML 页面）
            if not os.path.exists(self.filepath) or os.path.getsize(self.filepath) < 5000:
                self.fallback_signal.emit("无效文件", "下载的文件过小，可能是链接失效或网络拦截。")
                return

            # 下载成功
            self.finished_signal.emit(self.filepath)

        except Exception as e:
            self.fallback_signal.emit("下载引擎错误", str(e))
        finally:
            if process:
                try:
                    process.kill() # 确保释放资源
                except:
                    pass