import re
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

import requests
from bs4 import BeautifulSoup
from requests import RequestException, Timeout
from PySide6.QtCore import QThread, Signal, Qt
from qfluentwidgets import InfoBar, InfoBarPosition

from app.framework.infra.config.app_config import config
from app.framework.infra.config.data_models import ApiResponse, parse_config_update_data
from app.framework.i18n import _


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)


def _resolve_proxies(proxies: Optional[dict]) -> Optional[dict]:
    if proxies is not None:
        return proxies
    try:
        from app.framework.infra.config.app_config import config
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


def calculate_time_difference(date_due: str):
    current_year = datetime.now().year
    start_date_str, end_date_str = date_due.split('-')
    start_time = datetime.strptime(f"{current_year}.{start_date_str}", "%Y.%m.%d")
    end_time = datetime.strptime(f"{current_year}.{end_date_str}", "%Y.%m.%d")

    if end_time < start_time:
        end_time = datetime.strptime(f"{current_year + 1}.{end_date_str}", "%Y.%m.%d")

    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_day = (end_time - start_time).days + 1

    if now < start_time:
        days_to_start = (start_time - now).days
        return days_to_start, total_day, 1
    elif now > end_time:
        return 0, total_day, -1
    else:
        days_remaining = (end_time - now).days + 1
        return days_remaining, total_day, 0


class CloudflareUpdateThread(QThread):
    update_finished = Signal(dict)
    update_failed = Signal(str)

    def run(self):
        try:
            data = get_cloudflare_data()
            if 'error' in data:
                self.update_failed.emit(data["error"])
            else:
                self.update_finished.emit(data)
        except Exception as e:
            self.update_failed.emit(f"网络请求异常: {str(e)}")


def start_cloudflare_update(parent):
    """
    启动 Cloudflare 更新线程，并绑定回调到当前模块中的处理函数
    :param parent: 页面实例，用于访问 logger、refresh_tips 回调和作为 InfoBar 的父组件
    """
    parent.cloudflare_thread = CloudflareUpdateThread()
    parent.cloudflare_thread.update_finished.connect(
        lambda data: handle_cloudflare_success(data, parent))
    parent.cloudflare_thread.update_failed.connect(
        lambda msg: handle_cloudflare_error(msg, parent))
    parent.cloudflare_thread.start()


def _refresh_tips(parent, *, url=None):
    refresh_fn = getattr(parent, "refresh_tips", None)
    if callable(refresh_fn):
        if url is None:
            refresh_fn()
        else:
            refresh_fn(url=url)
        return

    # Backward compatibility for legacy hosts.
    legacy_fn = getattr(parent, "get_tips", None)
    if callable(legacy_fn):
        if url is None:
            legacy_fn()
        else:
            legacy_fn(url=url)


def handle_cloudflare_success(data, parent):
    try:
        if 'data' not in data:
            parent.logger.error(_('Error occurred while updating through Cloudflare: Incorrect data format returned', msgid='8e0f80b3ac5a'))
            return

        online_data = data["data"]
        required_fields = ['updateData', 'redeemCodes', 'version']
        update_data_fields = ['linkCatId', 'linkId', 'questName']

        for field in required_fields:
            if field not in online_data:
                parent.logger.error(
                    _(f'Error occurred while updating through Cloudflare: Missing required field {field} in updateData', msgid='94c67e5d88ed')
                )
                _refresh_tips(parent)
                return

        if 'updateData' in online_data:
            for field in update_data_fields:
                if field not in online_data['updateData']:
                    parent.logger.error(
                        _(f'Error occurred while updating through Cloudflare: Missing required field {field} in updateData', msgid='7c8d1cc74bea')
                    )
                    _refresh_tips(parent)
                    return

        try:
            response = ApiResponse.from_dict(data)
            handle_update_logic(data, online_data, response, parent)
        except Exception as e:
            parent.logger.error(
                _(f'Error occurred while parsing API response data: {str(e)}', msgid='a20f1c9de24f')
            )
            traceback.print_exc()
            handle_update_logic_fallback(data, online_data, parent)
    except Exception as e:
        parent.logger.error(
            _(f'Error occurred while processing Cloudflare data: {str(e)}', msgid='7f7b01f6e149')
        )
        _refresh_tips(parent)


def handle_update_logic(raw_data: Dict[str, Any], online_data: Dict[str, Any], response: ApiResponse, parent):
    local_config_data = parse_config_update_data(config.update_data.value)

    if not local_config_data:
        config.set(config.update_data, raw_data)
        if config.isLog.value:
            parent.logger.info(_(f'Obtained update information: {online_data}', msgid='fa29abd83616'))
        url = (
            f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail"
            f"&catid={response.data.updateData.linkCatId}&id={response.data.updateData.linkId}"
        )
        _refresh_tips(parent, url=url)
        InfoBar.success(
            title=_('Update Successful', msgid='8567828f9a6f'),
            content=_('New redeem code event information detected', msgid='f47b94019072'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=10000,
            parent=parent,
        )
    else:
        if online_data != local_config_data.data.model_dump():
            content = ''
            local_redeem_codes = [
                code.model_dump()
                for code in local_config_data.data.redeemCodes
            ]

            if online_data['redeemCodes'] != [] and online_data['redeemCodes'] != local_redeem_codes:
                new_used_codes = []
                old_used_codes = config.used_codes.value
                for code in response.data.redeemCodes:
                    if code.code in old_used_codes:
                        new_used_codes.append(code.code)
                config.set(config.used_codes, new_used_codes)
                content += ' 兑换码 '

            if online_data['updateData'] != local_config_data.data.updateData.model_dump():
                content += ' 活动信息 '

            if content:
                if config.isLog.value:
                    parent.logger.info(_(f'Obtained update information: {online_data}', msgid='b67b771d218f'))
                config.set(config.update_data, raw_data)
                config.set(config.task_name,
                           response.data.updateData.questName)
                url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={response.data.updateData.linkCatId}&id={response.data.updateData.linkId}"
                _refresh_tips(parent, url=url)
                InfoBar.success(
                    title=_('Update Successful', msgid='8567828f9a6f'),
                    content=_(f'New {content} detected', msgid='1662a4d93a4b'),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=10000,
                    parent=parent,
                )
            else:
                _refresh_tips(parent)
        else:
            _refresh_tips(parent)


def handle_update_logic_fallback(data, online_data, parent):
    if not config.update_data.value:
        config.set(config.update_data, data)
        if config.isLog.value:
            parent.logger.info(f'获取到更新信息：{online_data}')
        catId = online_data["updateData"]["linkCatId"]
        linkId = online_data["updateData"]["linkId"]
        url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={catId}&id={linkId}"
        _refresh_tips(parent, url=url)
        InfoBar.success(
            title=_('Update Successful', msgid='8567828f9a6f'),
            content=_('New redeem code event information detected', msgid='f47b94019072'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=10000,
            parent=parent,
        )
    else:
        if not isinstance(config.update_data.value, dict) or 'data' not in config.update_data.value:
            parent.logger.error(
                _('Local configuration data format is incorrect, using online data', msgid='f04deae1d035')
            )
            config.set(config.update_data, data)
            config.set(config.task_name, online_data["updateData"]["questName"])
            catId = online_data["updateData"]["linkCatId"]
            linkId = online_data["updateData"]["linkId"]
            url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={catId}&id={linkId}"
            _refresh_tips(parent, url=url)
            return

        local_data = config.update_data.value["data"]
        if online_data != local_data:
            # 简化版 fallback 逻辑，不再详细比对，直接提示更新
            # 实际场景中 fallback 很少触发，这里为了代码简洁略去部分重复逻辑
            _refresh_tips(parent)
        else:
            _refresh_tips(parent)


def handle_cloudflare_error(error_msg, parent):
    parent.logger.error(f'通过cloudflare在线更新出错: {error_msg}')
    _refresh_tips(parent)


