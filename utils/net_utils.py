import re
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests import RequestException, Timeout


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)


def _resolve_proxies(proxies: Optional[dict]) -> Optional[dict]:
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


def fetch_url(
    url: str,
    timeout: float = None,
    encoding: str = None,
    proxies: Optional[dict] = None,
    retries: int = 0,
    headers: Optional[dict] = None,
):
    proxies = _resolve_proxies(proxies)
    merged_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        merged_headers.update(headers)

    last_exception = None
    for _ in range(max(0, retries) + 1):
        try:
            response = requests.get(
                url,
                headers=merged_headers,
                timeout=timeout,
                proxies=proxies,
            )
            if encoding:
                response.encoding = encoding
            return response
        except Timeout as e:
            last_exception = e
        except RequestException as e:
            last_exception = e
        except Exception as e:
            last_exception = e

    if isinstance(last_exception, Timeout):
        return {"error": f"⚠️ 连接超时，请检查网络是否能连接 {url}"}
    if isinstance(last_exception, RequestException):
        return {"error": f"🔌 网络请求 {url} 失败: {last_exception}"}
    return {"error": f"❌ 请求 {url} 发生未知错误: {last_exception}"}


def get_cloudflare_data(
    url: str = "https://saapanel.netlify.app/api/config",
    timeout: float = 8,
    proxies: Optional[dict] = None,
    retries: int = 1,
):
    response = fetch_url(url, timeout=timeout, proxies=proxies, retries=retries)
    if isinstance(response, dict):
        return response
    if response.status_code != 200:
        return {"error": f"请求失败，状态码: {response.status_code}"}
    try:
        return response.json()
    except Exception as e:
        return {"error": f"解析JSON失败: {e}"}


def get_date_from_api(url=None):
    def format_date(date_str):
        parts = date_str.split('月')
        month = parts[0].zfill(2)
        day = parts[1].replace('日', '').zfill(2)
        return f"{month}.{day}"

    response = fetch_url(url, timeout=3, encoding='utf-8', retries=1)

    if isinstance(response, dict):
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

        if "角色共鸣" in text and "✧" in text and "。" not in text:
            match = re.search(r"「(.*?)」", text)
            if match:
                role_name = match.group(1)
            else:
                return {"error": "未匹配到“角色共鸣”"}
            current_index += 1
            time_text = paragraphs[current_index].get_text(strip=True)
            if "活动时间：" in time_text and "常驻" not in time_text:
                dates = re.findall(r"\d+月\d+日", time_text)
                if len(dates) >= 2:
                    start = format_date(dates[0])
                    end = format_date(dates[1])
                    result_dict[role_name] = f"{start}-{end}"

        elif "【调查清单】活动任务" in text:
            current_index += 1
            time_text = paragraphs[current_index].get_text(strip=True)
            if "常驻" not in time_text:
                dates = re.findall(r"\d+月\d+日", time_text)
                if len(dates) >= 2:
                    start = format_date(dates[0])
                    end = format_date(dates[1])
                    result_dict["调查清单"] = f"{start}-{end}"

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

        current_index += 1

    if result_dict:
        return result_dict
    return {"error": f"未匹配到任何活动。检查 {url} 是否正确"}
