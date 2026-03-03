from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

import requests
from packaging.version import parse as parse_version


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
    proxies = _resolve_proxies(proxies)
    result: Dict[str, Optional[Dict[str, Optional[str]]]] = {
        "latest": None,
        "prerelease": None,
    }

    owner, repo = _parse_github_repo(repo_url)
    if not owner or not repo:
        return result

    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page={max(1, int(per_page))}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SaaAutomataAcacia-Updater",
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=timeout, proxies=proxies)
        if response.status_code != 200:
            return result
        releases = response.json()
    except Exception:
        return result

    if not isinstance(releases, list):
        return result

    for release in releases:
        if not isinstance(release, dict):
            continue
        if bool(release.get("draft")):
            continue

        item = _build_release_item(release)
        if not item:
            continue

        if bool(release.get("prerelease")):
            result["prerelease"] = _choose_newer(result["prerelease"], item)
        else:
            result["latest"] = _choose_newer(result["latest"], item)

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


def get_gitee_text(text_path: str, timeout: float = 5, proxies: Optional[Dict[str, str]] = None) -> Optional[list]:
    proxies = _resolve_proxies(proxies)
    if not text_path:
        return None
    url = f"https://gitee.com/laozhu520/auto_chenbai/raw/main/{text_path}"
    headers = {"User-Agent": "SaaAutomataAcacia-Updater"}

    try:
        response = requests.get(url, headers=headers, timeout=timeout, proxies=proxies)
        if response.status_code != 200:
            return None
        response.encoding = response.apparent_encoding
        return response.text.splitlines()
    except Exception:
        return None


def get_local_version(file_path="update_data.txt"):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            if len(lines) >= 2:
                return lines[1].strip()
            return None
    except Exception:
        return None
