import functools
import inspect
import math
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import win32gui
import win32clipboard
import win32con

from app.framework.infra.config.app_config import config
from app.framework.infra.vision.image import ImageUtils
from app.framework.infra.vision.matcher import matcher
from app.framework.infra.events.signal_bus import signalBus
from app.framework.infra.automation.text_normalizer import normalize_chinese_text
from app.framework.infra.automation.randoms import random_rectangle_point
from app.framework.infra.system.windows import get_hwnd
from app.framework.infra.automation.input import Input
from app.framework.infra.automation.screenshot import Screenshot
from app.framework.infra.vision.ocr_service import run_ocr
from app.framework.i18n import _
from app.framework.infra.ui_manifest import ModuleContext, UIDefinition, UIReference, UIResolver, UIResolveError, U


def atoms(func):
    """
    用于各种原子操作中实现立即停止的装饰器
    :param func:
    :return:
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 检查self.running是否为false
        if not args[0].running:
            raise Exception("stopped_by_user")
        else:
            # 判断是否暂停
            if args[0].is_paused:
                # 每次执行完原子函数后，等待外部条件重新开始
                args[0].pause_event.wait()  # 等待外部触发继续执行
        return func(*args, **kwargs)

    return wrapper


class Automation:
    """
    自动化管理类，用于管理与游戏窗口相关的自动化操作。
    """

    _click_verify_first_delay = 0.06
    _click_verify_second_delay = 0.2
    _click_verify_change_threshold = 1.0
    _click_verify_roi_padding = 12
    _ui_id_pattern = re.compile(r"^[A-Za-z0-9_.-]+$")
    _project_root = Path(__file__).resolve().parents[4]
    _modules_root = _project_root / "app" / "features" / "modules"

    def __init__(self, window_title, window_class, logger):
        """
        :param window_title: 游戏窗口的标题。
        :param window_class: 是启动器还是游戏窗口
        :param logger: 用于记录日志的Logger对象，可选参数。
        """
        # 启动器截图和操作的窗口句柄不同
        self.screenshot_hwnd = win32gui.FindWindow(None, window_title)
        self.window_title = window_title
        self.window_class = window_class
        # self.is_starter = window_class != config.LineEdit_game_class.value
        self.is_starter = False
        self.logger = logger
        self.hwnd = self.get_hwnd()
        self.screenshot = Screenshot(self.logger)
        # 当前截图
        self.current_screenshot = None
        # 保存状态机的第一张截图，为了让current_screenshot可以肆无忌惮的裁切
        self.first_screenshot = None
        self.scale_x = 1
        self.scale_y = 1
        self.relative_pos = None
        self.ocr_result = None

        self.running = True
        self.is_paused = False
        self.pause_event = threading.Event()  # 用来控制暂停
        self._last_error_log = {}
        self._ui_resolver = UIResolver()

        self._init_input()

    def _resolve_ui_click(self, ref_or_id, **kwargs):
        if isinstance(ref_or_id, UIReference):
            ref = UIReference(
                id=ref_or_id.id,
                source_file=ref_or_id.source_file,
                source_line=ref_or_id.source_line,
                module_name=ref_or_id.module_name,
                text=ref_or_id.text,
                image=ref_or_id.image,
                roi=ref_or_id.roi if "roi" not in kwargs else kwargs.get("roi"),
                threshold=ref_or_id.threshold if "threshold" not in kwargs else kwargs.get("threshold"),
                include=ref_or_id.include if "include" not in kwargs else kwargs.get("include"),
                need_ocr=ref_or_id.need_ocr if "need_ocr" not in kwargs else kwargs.get("need_ocr"),
                find_type=ref_or_id.find_type if "find_type" not in kwargs else kwargs.get("find_type"),
                extra={**ref_or_id.extra, **kwargs},
            )
        elif isinstance(ref_or_id, UIDefinition):
            ref = UIReference(
                id=ref_or_id.id,
                source_file=ref_or_id.source_file,
                source_line=ref_or_id.source_line,
                module_name=ref_or_id.module_name,
                text=ref_or_id.content if isinstance(ref_or_id.content, str) and ref_or_id.kind == "text" else None,
                image=ref_or_id.image,
                roi=ref_or_id.roi if "roi" not in kwargs else kwargs.get("roi"),
                threshold=ref_or_id.threshold if "threshold" not in kwargs else kwargs.get("threshold"),
                include=ref_or_id.include if "include" not in kwargs else kwargs.get("include"),
                need_ocr=ref_or_id.need_ocr if "need_ocr" not in kwargs else kwargs.get("need_ocr"),
                find_type=ref_or_id.find_type if "find_type" not in kwargs else kwargs.get("find_type"),
                extra={**ref_or_id.extra, **kwargs},
            )
        elif isinstance(ref_or_id, str):
            ref = U(
                ref_or_id,
                id=kwargs.pop("id", None),
                roi=kwargs.pop("roi", None),
                image=kwargs.pop("image", None),
                threshold=kwargs.pop("threshold", None),
                include=kwargs.pop("include", None),
                need_ocr=kwargs.pop("need_ocr", None),
                find_type=kwargs.pop("find_type", None),
                **kwargs,
            )
        else:
            raise UIResolveError("resolve/invalid_reference_type", f"Unsupported UI ref type: {type(ref_or_id).__name__}")

        module_ctx = ModuleContext.from_callsite(skip=3)
        current_resolution = None
        if self.first_screenshot is not None and hasattr(self.first_screenshot, "shape") and len(self.first_screenshot.shape) >= 2:
            h, w = self.first_screenshot.shape[:2]
            current_resolution = (int(w), int(h))
        return self._ui_resolver.resolve(
            ref,
            module_ctx,
            environment={"window_title": self.window_title, "window_class": self.window_class},
            current_resolution=current_resolution,
        )

    def _maybe_resolve_legacy_target(
        self,
        target,
        find_type: str | None,
        threshold: float,
        crop: tuple,
        include: bool,
        need_ocr: bool,
    ):
        if isinstance(target, (UIReference, UIDefinition)):
            return self._resolve_ui_click(
                target,
                find_type=find_type,
                threshold=threshold,
                roi=crop,
                include=include,
                need_ocr=need_ocr,
            )
        if not isinstance(target, str):
            return None
        probe = target.strip()
        if not probe or not self._ui_id_pattern.fullmatch(probe):
            return None
        if probe.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
            return None
        try:
            return self._resolve_ui_click(
                U(probe),
                find_type=find_type,
                threshold=threshold,
                roi=crop,
                include=include,
                need_ocr=need_ocr,
            )
        except UIResolveError:
            return None

    def click(self, ref_or_id, **kwargs):
        """
        High-level UI resource click API.
        Supports:
        - self.auto.click(U("开始", id="start", roi=(...)))
        - self.auto.click("start")
        """
        action = kwargs.pop("action", "move_click")
        offset = kwargs.pop("offset", (0, 0))
        n = kwargs.pop("n", 3)
        take_screenshot = kwargs.pop("take_screenshot", False)
        extract = kwargs.pop("extract", None)
        is_log = kwargs.pop("is_log", False)

        try:
            resolved = self._resolve_ui_click(ref_or_id, **kwargs)
            if is_log:
                self.logger.debug(
                    _(f"ui_click_resolved id={resolved.id} type={resolved.find_type} target={resolved.target} trace={';'.join(resolved.trace)}",
                      msgid="ui_click_resolved_id_type_target_trace")
                )
            return self.click_element(
                target=resolved.target,
                find_type=resolved.find_type,
                threshold=resolved.threshold,
                crop=resolved.roi,
                take_screenshot=take_screenshot,
                include=resolved.include,
                need_ocr=resolved.need_ocr,
                extract=extract,
                action=action,
                offset=offset,
                n=n,
                is_log=is_log,
            )
        except UIResolveError as exc:
            self._log_error_throttled(
                "ui_click_resolve_error",
                _(f"[UI_RESOLVE_FAILED] code={exc.code} detail={exc} trace={exc.trace}", msgid="ui_resolve_failed_code_detail_trace"),
            )
            return False

    def explain(self, ref_or_id, **kwargs):
        def _layer_from_code(code: str) -> str:
            if code.startswith("resolve/"):
                return "resolve"
            if code.startswith("match/"):
                return "match"
            if code.startswith("execute/"):
                return "execute"
            return "unknown"

        try:
            resolved = self._resolve_ui_click(ref_or_id, **kwargs)
            return {
                "ok": True,
                "layer": "resolve",
                "code": "resolve/success",
                "id": resolved.id,
                "module_name": resolved.module_name,
                "locale": resolved.locale,
                "target": resolved.target,
                "text": resolved.text,
                "image_path": resolved.image_path,
                "roi": resolved.roi,
                "threshold": resolved.threshold,
                "find_type": resolved.find_type,
                "trace": resolved.trace,
                "resolution_trace": resolved.resolution_trace,
                "explain_trace": resolved.explain_trace,
            }
        except UIResolveError as exc:
            return {
                "ok": False,
                "layer": _layer_from_code(exc.code),
                "code": exc.code,
                "detail": str(exc),
                "trace": exc.trace,
            }
        except Exception as exc:
            self._log_error_throttled(
                "ui_click_execute_error",
                _(f"[UI_EXECUTE_FAILED] {exc}", msgid="ui_execute_failed_exc"),
            )
            return False

    def _log_error_throttled(self, key, message, interval=2.0, level="error"):
        now = time.time()
        last = self._last_error_log.get(key, 0)
        if now - last >= interval:
            log_fn = getattr(self.logger, level, self.logger.error)
            log_fn(message)
            self._last_error_log[key] = now


    @staticmethod
    def _callsite_module_context(skip_min: int = 3, skip_max: int = 14) -> ModuleContext:
        for frame_info in inspect.stack()[skip_min: skip_max + 1]:
            frame_path = Path(frame_info.filename).resolve()
            lower_parts = [part.lower() for part in frame_path.parts]
            if "modules" not in lower_parts:
                continue
            try:
                idx = lower_parts.index("modules")
                module_name = frame_path.parts[idx + 1]
            except Exception:
                continue
            module_dir = (Automation._modules_root / module_name).resolve()
            if not module_dir.exists() or not module_dir.is_dir():
                continue
            assets_dir = module_dir / "assets"
            return ModuleContext(
                module_id=module_name,
                module_name=module_name,
                module_dir=module_dir,
                assets_dir=assets_dir,
                images_root=assets_dir / "images",
                ocr_root=assets_dir / "ocr",
                ui_manifest_path=assets_dir / "ui.json",
                generated_manifest_path=assets_dir / "ui.generated.json",
                callsite_file=str(frame_path),
                callsite_line=int(frame_info.lineno),
            )
        return ModuleContext.from_callsite(skip=skip_min)

    @staticmethod
    def _module_context_from_template_prefix(template: str) -> ModuleContext | None:
        if not isinstance(template, str):
            return None
        normalized = template.replace("\\", "/").strip()
        if not normalized or normalized.startswith("/"):
            return None
        parts = [p for p in normalized.split("/") if p]
        if len(parts) >= 4 and parts[0] == "app" and parts[1] == "features" and parts[2] == "modules":
            first = parts[3]
        else:
            first = parts[0] if parts else ""
        if not first or first in {"assets", "images", "ocr", "resources", "app", "features", "modules"}:
            return None
        module_dir = (Automation._modules_root / first).resolve()
        if not module_dir.exists() or not module_dir.is_dir():
            return None
        return ModuleContext(
            module_id=first,
            module_name=first,
            module_dir=module_dir,
            assets_dir=module_dir / "assets",
            images_root=module_dir / "assets" / "images",
            ocr_root=module_dir / "assets" / "ocr",
            ui_manifest_path=module_dir / "assets" / "ui.json",
            generated_manifest_path=module_dir / "assets" / "ui.generated.json",
        )

    @staticmethod
    def _resolve_template_path(template: str, module_ctx: ModuleContext | None = None) -> Path | None:
        if not isinstance(template, str):
            return None
        normalized = template.replace("\\", "/").strip()
        if not normalized:
            return None
        candidate = Path(normalized)
        if candidate.is_absolute():
            return candidate if candidate.exists() else None

        # Strict module sandbox: only resolve within current module directory.
        if module_ctx is not None and module_ctx.module_dir is not None:
            module_dir = module_ctx.module_dir
            rel_candidates: list[str] = [normalized]
            if module_ctx.module_name:
                module_prefix = f"{module_ctx.module_name}/"
                if normalized.startswith(module_prefix):
                    stripped = normalized[len(module_prefix):]
                    rel_candidates.append(stripped)
                full_module_prefix = f"app/features/modules/{module_ctx.module_name}/"
                if normalized.startswith(full_module_prefix):
                    rel_candidates.append(normalized[len(full_module_prefix):])

            candidates: list[Path] = []
            seen_paths: set[str] = set()
            for rel in rel_candidates:
                rel = rel.strip("/")
                if not rel:
                    continue
                probes = [
                    (module_dir / rel).resolve(),
                    (module_dir / "assets" / rel).resolve(),
                ]
                for probe in probes:
                    probe_key = probe.as_posix().lower()
                    if probe_key in seen_paths:
                        continue
                    seen_paths.add(probe_key)
                    candidates.append(probe)
            for probe in candidates:
                try:
                    probe.relative_to(module_dir)
                except Exception:
                    continue
                if probe.exists():
                    return probe
        return None

    @staticmethod
    def _template_log_name(template: str, module_ctx: ModuleContext | None = None) -> str:
        if not isinstance(template, str):
            return str(template)
        normalized = template.replace("\\", "/").strip()
        resolved = Automation._resolve_template_path(normalized, module_ctx=module_ctx)
        if resolved is not None:
            try:
                return resolved.relative_to(Automation._project_root).as_posix()
            except Exception:
                return resolved.as_posix()
        module_tag = module_ctx.module_name if module_ctx and module_ctx.module_name else "unknown"
        return f"{normalized} (missing; module={module_tag})"

    def _init_input(self):
        self.input_handler = Input(self.hwnd, self.logger)
        # 鼠标部分
        self.move_click = self.input_handler.move_click
        self.mouse_click = self.input_handler.mouse_click
        self.mouse_down = self.input_handler.mouse_down
        self.mouse_up = self.input_handler.mouse_up
        self.mouse_scroll = self.input_handler.mouse_scroll
        self.move_to = self.input_handler.move_to
        # 按键部分
        self.press_key = self.input_handler.press_key
        self.key_down = self.input_handler.key_down
        self.key_up = self.input_handler.key_up

    def _ensure_input_hwnd(self):
        if self.hwnd and win32gui.IsWindow(self.hwnd):
            if self.input_handler.hwnd != self.hwnd:
                self.input_handler.hwnd = self.hwnd
            return True
        hwnd = get_hwnd(self.window_title, self.window_class)
        if not hwnd:
            self._log_error_throttled(
                "refresh_hwnd_failed",
                _(f'Handle for window {self.window_title} not found', msgid='handle_for_window_value_not_found'),
            )
            return False
        self.hwnd = hwnd
        self.input_handler.hwnd = hwnd
        return True

    def type_string(self, text):
        """
        向句柄窗口粘贴文本内容
        :param text: 需要粘贴的字符串
        :return:
        """
        win32clipboard.OpenClipboard()

        try:
            # 设置剪贴板内容
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)

            time.sleep(0.3)

            # 激活目标窗口
            # win32gui.SetForegroundWindow(self.hwnd)

            # 发送粘贴命令 (Shift+Insert)
            win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, win32con.VK_SHIFT, 0)
            win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, win32con.VK_INSERT, 0)
            win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, win32con.VK_INSERT, 0)
            win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, win32con.VK_SHIFT, 0)
        finally:
            # 关闭剪贴板
            win32clipboard.CloseClipboard()

    def get_hwnd(self):
        """根据传入的窗口名和类型确定可操作的句柄"""
        hwnd = get_hwnd(self.window_title, self.window_class)
        if hwnd:
            self.logger.info(_(f'Found handle for window {self.window_title}: {hwnd}', msgid='found_handle_for_window_value_hwnd'))
            return hwnd
        else:
            raise ValueError(_(f'Handle for {self.window_title} not found', msgid='handle_for_value_not_found'))
    def take_screenshot(self, crop=(0, 0, 1, 1), is_interval=True):
        """
        捕获游戏窗口的截图。
        :param is_interval:
        :param crop: 截图的裁剪区域，格式为(x1, y1, width, height)，默认为全屏。
        :return: 成功时返回截图及其位置和缩放因子，失败时抛出异常。
        """
        try:
            result = self.screenshot.screenshot(self.screenshot_hwnd, (0, 0, 1, 1), self.is_starter,
                                                is_interval=is_interval)
            if result:
                self.first_screenshot, self.scale_x, self.scale_y, self.relative_pos = result
                if crop != (0, 0, 1, 1):
                    self.current_screenshot, self.relative_pos = ImageUtils.crop_image(self.first_screenshot, crop,
                                                                                       self.hwnd)
                else:
                    self.current_screenshot = self.first_screenshot
                return result
            else:
                self.current_screenshot = None
        except Exception as e:
            self._log_error_throttled("take_screenshot_failed", _(f'Screenshot failed: {e}', msgid='screenshot_failed_e'))

    def calculate_positions(self, max_loc):
        """
        找到图片后计算相对位置，input_handler接收的均为相对窗口的相对坐标，所以这里要返回的也是相对坐标
        :param template:
        :param max_loc:匹配点左上角坐标(x,y,w,h)
        :return:
        """
        top_left = (
            int(max_loc[0] + self.relative_pos[0]),
            int(max_loc[1] + self.relative_pos[1]),
        )
        bottom_right = (
            top_left[0] + int(max_loc[2]),
            top_left[1] + int(max_loc[3]),
        )
        return top_left, bottom_right


    def find_image_element(self, template, threshold, match_method=cv2.TM_SQDIFF_NORMED, extract=None, is_log=False,
                           is_show=False):
        temp = self.current_screenshot
        if temp is None:
            self._log_error_throttled(
                "find_image_without_screenshot",
                _('No available screenshot currently, skipping image matching', msgid='no_available_screenshot_currently_skipping_image'),
            )
            return None, None, None

        if extract:
            letter = extract[0]
            thr = extract[1]
            temp = ImageUtils.extract_letters(temp, letter, thr)
        try:
            module_ctx = self._callsite_module_context(skip_min=3, skip_max=40)
            if (module_ctx is None or module_ctx.module_dir is None) and isinstance(template, str):
                inferred = self._module_context_from_template_prefix(template)
                if inferred is not None:
                    module_ctx = inferred
            resolved_template = self._resolve_template_path(template, module_ctx=module_ctx) if isinstance(template, str) else None
            template_input = str(resolved_template) if resolved_template is not None else template
            matches = matcher.match(template_input, temp)
            if len(matches) >= 1:
                x, y, w, h, conf = matches[0]
                if conf >= threshold or threshold is None:
                    top_left, bottom_right = self.calculate_positions((x, y, w, h))
                    if is_log:
                        template_name = self._template_log_name(str(template_input), module_ctx=module_ctx)
                        self.logger.debug(_(f'Target image: {template_name} Similarity: {conf:.2f}', msgid='target_image_template_name_similarity_conf'))
                    return top_left, bottom_right, conf
                else:
                    if is_log:
                        template_name = self._template_log_name(str(template_input), module_ctx=module_ctx)
                        self.logger.debug(_(f'Target image: {template_name} Similarity: {conf:.2f}, below {threshold}', msgid='target_image_template_name_similarity_conf_below'))
            else:
                if is_log:
                    template_name = self._template_log_name(str(template_input), module_ctx=module_ctx)
                    self.logger.debug(_(f'Target image: {template_name} No match found', msgid='target_image_template_name_no_match_found'))
            if is_show:
                for idx, (x, y, w, h, conf) in enumerate(matches):
                    cv2.rectangle(temp,
                                  (x, y),
                                  (x + w, y + h),
                                  (0, 255, 0), 2)
                    text = f"{conf:.2f}"
                    cv2.putText(temp, text,
                                (x, y - 5),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0, 255, 0), 2)
                ImageUtils.show_ndarray(temp)
        except Exception as e:
            self._log_error_throttled("find_image_error", _(f'Error finding image: {e}', msgid='error_finding_image_e'))
            return None, None, None
        return None, None, None

    @atoms
    def perform_ocr(self, extract: list = None, image=None, is_log=False):
        """执行OCR识别，并更新OCR结果列表。如果未识别到文字，保留ocr_result为一个空列表。"""
        try:
            if image is None:
                if self.current_screenshot is None:
                    self.ocr_result = []
                    return
                self.ocr_result = run_ocr(self.current_screenshot, extract, is_log=is_log)
            else:
                self.ocr_result = run_ocr(image, extract, is_log=is_log)
            if not self.ocr_result:
                self.ocr_result = []
        except Exception as e:
            self._log_error_throttled("perform_ocr_error", _(f'OCR recognition failed: {e}', msgid='ocr_recognition_failed_e'))
            self.ocr_result = []  # 确保在异常情况下，ocr_result为列表类型

    def calculate_text_position(self, result):
        """
        计算文本所在的相对位置
        :param result: 格式=['适龄提示', 1.0, [[10.0, 92.0], [71.0, 106.0]]],单条结果
        :return: 左上，右下相对坐标
        """
        result_pos = result[2]
        result_width = result_pos[1][0] - result_pos[0][0]
        result_height = result_pos[1][1] - result_pos[0][1]

        # self.relative_pos格式：(800, 480, 1600, 960),转回用户尺度后再加相对窗口坐标
        top_left = (
            self.relative_pos[0] + result_pos[0][0],
            self.relative_pos[1] + result_pos[0][1]
        )
        bottom_right = (
            top_left[0] + result_width,
            top_left[1] + result_height,
        )
        # print(f"{top_left=}")
        # print(f"{bottom_right=}")
        return top_left, bottom_right

    def is_text_match(self, text, targets, include):
        """
        判断文本是否符合搜索条件，并返回匹配的文本。
        :param text: OCR识别出的文本。
        :param targets: 目标文本列表。
        :param include: 是否包含目标字符串。
        :return: (是否匹配, 匹配的目标文本)
        """
        if config.game_language.value == 1:
            text = normalize_chinese_text(text)
            normalized_targets = [normalize_chinese_text(target) for target in targets]
        else:
            normalized_targets = targets
        if include:
            for target in normalized_targets:
                if target in text:
                    return True, target  # 直接返回匹配成功及匹配的目标文本
            return False, None  # 如果没有匹配，返回False和None
        else:
            return text in normalized_targets, text if text in normalized_targets else None

    def search_text_in_ocr_results(self, targets, include):
        """从ocr识别结果中找目标文字"""
        for result in self.ocr_result:
            match, matched_text = self.is_text_match(result[0], targets, include)
            if match:
                # self.matched_text = matched_text  # 更新匹配的文本变量
                # self.logger.info(f"目标文字：{matched_text} 相似度：{result[1]:.2f}")
                return self.calculate_text_position(result)
        # self.logger.info(f"目标文字：{', '.join(targets)} 未找到匹配文字")
        return None, None

    def find_text_element(self, target, include, need_ocr=True, extract=None, is_log=False):
        """

        :param is_log:
        :param target:
        :param include:
        :param need_ocr:
        :param extract: 是否提取文字，[(文字rgb颜色),threshold数值]
        :return:
        """
        target_texts = [target] if isinstance(target, str) else list(target)  # 确保目标文本是列表格式
        if need_ocr:
            self.perform_ocr(extract, is_log=is_log)
        return self.search_text_in_ocr_results(target_texts, include)

    @atoms
    def find_element(self, target, find_type: str | None = None, threshold: float = 0.5, crop: tuple = (0, 0, 1, 1),
                     take_screenshot=False, include: bool = True, need_ocr: bool = True, extract: list = None,
                     match_method=cv2.TM_SQDIFF_NORMED, is_log=False):
        """
        寻找元素
        :param is_log: 是否显示详细日志
        :param match_method: 模版匹配方法（已废弃：目前的方案是用特征匹配）
        :param target: 寻找目标，图像路径或文字
        :param find_type: 寻找类型
        :param threshold: 置信度
        :param crop: 截图区域，take_screenshot为任何值crop都生效，为true时直接得到裁剪后的截图，为false时将根据crop对current_screenshot进行二次裁剪
        :param take_screenshot: 是否截图
        :param include: 是否允许target含于ocr结果
        :param need_ocr: 是否ocr
        :param extract: 是否使截图转换成白底黑字，只有find_type=="text"且需要ocr的时候才生效，[(文字rgb颜色),threshold数值]
        :return: 查找成功返回（top_left,bottom_right），失败返回None
        """
        resolved = self._maybe_resolve_legacy_target(target, find_type, threshold, crop, include, need_ocr)
        if resolved is None and (find_type is None or isinstance(target, (UIReference, UIDefinition))):
            try:
                resolved = self._resolve_ui_click(
                    target,
                    find_type=find_type,
                    threshold=threshold,
                    roi=crop,
                    include=include,
                    need_ocr=need_ocr,
                )
            except UIResolveError as exc:
                self._log_error_throttled(
                    "ui_find_resolve_error",
                    _(f"[UI_RESOLVE_FAILED] code={exc.code} detail={exc} trace={exc.trace}", msgid="ui_resolve_failed_code_detail_trace"),
                )
                return None
        if resolved is not None:
            target = resolved.target
            find_type = resolved.find_type
            threshold = resolved.threshold
            crop = resolved.roi
            include = resolved.include
            need_ocr = resolved.need_ocr

        top_left = bottom_right = image_threshold = None
        if take_screenshot:
            # 调用take_screenshot更新self.current_screenshot,self.scale_x,self.scale_y,self.relative_pos
            screenshot_result = self.take_screenshot(crop)
            if not screenshot_result:
                return None
        else:
            # 不截图的时候做相应的裁切，使外部可以不写参数
            has_cached_screenshot = self.current_screenshot is not None and self.first_screenshot is not None
            if not has_cached_screenshot:
                screenshot_result = self.take_screenshot(crop)
                if not screenshot_result:
                    self._log_error_throttled(
                        "find_element_no_current_screenshot",
                        "No cached screenshot available, fallback capture failed",
                    )
                    return None
            else:
                # Refresh cropped view from the latest full-frame screenshot cache.
                self.current_screenshot, self.relative_pos = ImageUtils.crop_image(self.first_screenshot, crop, self.hwnd)
        if find_type is None:
            find_type = "text"
        if config.showScreenshot.value:
            signalBus.showScreenshot.emit(self.current_screenshot)
        if find_type in ['image', 'text', 'image_threshold']:
            if find_type == 'image':
                image_result = self.find_image_element(
                    target,
                    threshold,
                    match_method=match_method,
                    extract=extract,
                    is_log=is_log,
                )
                if isinstance(image_result, tuple) and len(image_result) == 3:
                    top_left, bottom_right, image_threshold = image_result
                else:
                    top_left = bottom_right = image_threshold = None
            elif find_type == 'text':
                top_left, bottom_right = self.find_text_element(target, include, need_ocr, extract, is_log)
            if top_left and bottom_right:
                if find_type == 'image_threshold':
                    return image_threshold
                return top_left, bottom_right
        else:
            raise ValueError(f"Invalid find type: {find_type}")
        return None

    def find(self, target, **kwargs):
        return self.find_element(target, **kwargs)

    def wait_text(
        self,
        target,
        *,
        timeout: float = 5.0,
        interval: float = 0.3,
        crop: tuple = (0, 0, 1, 1),
        include: bool = True,
        need_ocr: bool = True,
        is_log: bool = False,
    ) -> bool:
        deadline = time.time() + max(0.1, timeout)
        while time.time() < deadline:
            found = self.find_element(
                target,
                find_type=None,
                threshold=0.5,
                crop=crop,
                take_screenshot=True,
                include=include,
                need_ocr=need_ocr,
                is_log=is_log,
            )
            if found:
                return True
            time.sleep(max(0.05, interval))
        return False

    def click_element_with_pos(self, pos, action="move_click", offset=(0, 0), n=3):
        """
        根据左上和右下坐标确定点击位置并执行点击
        :param pos: （top_left,bottom_right） or (x,y)
        :param action: 执行的动作类型
        :param offset: x,y的偏移量
        :param n: 聚拢值，越大越聚拢
        :return: None
        """
        if not pos:
            return False
        if not self._ensure_input_hwnd():
            return False
        if isinstance(pos[0], int):
            x, y = pos
        else:
            x, y = random_rectangle_point(pos, n)  # 范围内正态分布取点
        # print(f"{x=},{y=}")
        # 加上手动设置的偏移量
        click_x = x + offset[0]
        click_y = y + offset[1]
        # print(f"{x=},{y=}")
        # 动作到方法的映射
        action_map = {
            "mouse_click": self.mouse_click,
            "down": self.mouse_down,
            "move": self.move_to,
            "move_click": self.move_click,
        }
        if action in action_map:
            action_map[action](click_x, click_y)
            # print(f"点击{click_x},{click_y}")
        else:
            raise ValueError(f"未知的动作类型: {action}")
        return True

    def click_element(self, target, find_type: str, threshold: float = 0.5, crop: tuple = (0, 0, 1, 1),
                      take_screenshot=False, include: bool = True, need_ocr: bool = True, extract: list = None,
                      action: str = 'move_click', offset: tuple = (0, 0), n: int = 3,
                      match_method=cv2.TM_SQDIFF_NORMED, is_log=False):
        coordinates = self.find_element(target, find_type, threshold, crop, take_screenshot, include, need_ocr, extract,
                                        match_method, is_log)
        if not coordinates:
            return False

        before_click = self.current_screenshot.copy() if self.current_screenshot is not None else None
        if not self.click_element_with_pos(coordinates, action, offset, n):
            return False

        if not self._should_verify_click(find_type, action):
            return True

        if self._verify_click_success(before_click, coordinates, target, find_type, threshold, crop, include,
                                      need_ocr, extract, match_method, delay=self._click_verify_first_delay):
            return True

        if is_log:
            self.logger.debug(_(f'Target {target} initial verification unconfirmed, retrying click', msgid='target_target_initial_verification_unconfirmed_r'))

        coordinates_retry = self.find_element(target, find_type, threshold, crop, take_screenshot=False,
                                              include=include, need_ocr=need_ocr, extract=extract,
                                              match_method=match_method, is_log=False)
        if not coordinates_retry:
            return True

        before_retry = self.current_screenshot.copy() if self.current_screenshot is not None else None
        if not self.click_element_with_pos(coordinates_retry, action, offset, n):
            return False

        return self._verify_click_success(before_retry, coordinates_retry, target, find_type, threshold, crop, include,
                                          need_ocr, extract, match_method, delay=self._click_verify_second_delay)

    @staticmethod
    def _should_verify_click(find_type, action):
        return find_type in {'text', 'image'} and action in {'move_click', 'mouse_click'}

    @staticmethod
    def _is_screen_changed(before_image, after_image, threshold=1.0):
        if before_image is None or after_image is None:
            return False
        if before_image.shape != after_image.shape:
            return True
        diff = cv2.absdiff(before_image, after_image)
        mean_change = sum(cv2.mean(diff)[:3]) / 3
        return mean_change >= threshold

    def _is_roi_changed(self, before_image, after_image, coordinates):
        if before_image is None or after_image is None or coordinates is None:
            return False
        if before_image.shape != after_image.shape:
            return True

        if not isinstance(coordinates, tuple) or len(coordinates) != 2:
            return self._is_screen_changed(before_image, after_image, self._click_verify_change_threshold)

        if self.relative_pos is None:
            return self._is_screen_changed(before_image, after_image, self._click_verify_change_threshold)

        (x1, y1), (x2, y2) = coordinates
        offset_x, offset_y = self.relative_pos[0], self.relative_pos[1]

        lx1 = int(x1 - offset_x) - self._click_verify_roi_padding
        ly1 = int(y1 - offset_y) - self._click_verify_roi_padding
        lx2 = int(x2 - offset_x) + self._click_verify_roi_padding
        ly2 = int(y2 - offset_y) + self._click_verify_roi_padding

        h, w = before_image.shape[:2]
        lx1 = max(0, min(w, lx1))
        lx2 = max(0, min(w, lx2))
        ly1 = max(0, min(h, ly1))
        ly2 = max(0, min(h, ly2))

        if lx2 <= lx1 or ly2 <= ly1:
            return self._is_screen_changed(before_image, after_image, self._click_verify_change_threshold)

        before_roi = before_image[ly1:ly2, lx1:lx2]
        after_roi = after_image[ly1:ly2, lx1:lx2]
        return self._is_screen_changed(before_roi, after_roi, self._click_verify_change_threshold)

    def _verify_click_success(self, before_click, coordinates, target, find_type, threshold, crop, include,
                              need_ocr, extract, match_method, delay):
        time.sleep(delay)
        screenshot_result = self.take_screenshot(crop)
        if not screenshot_result:
            return False

        still_exists = self.find_element(target, find_type, threshold, crop, take_screenshot=False,
                                         include=include, need_ocr=need_ocr, extract=extract,
                                         match_method=match_method, is_log=False)
        if not still_exists:
            return True

        return self._is_roi_changed(before_click, self.current_screenshot, coordinates)

    @atoms
    def find_target_near_source(self, target, source_pos, need_update_ocr: bool = True, crop=(0, 0, 1, 1), include=True,
                                n=30, is_log=False):
        """
        查找距离源最近的目标文本的中心坐标。
        :param is_log:
        :param n: 聚拢度
        :param include: 是否包含
        :param target:目标文本
        :param need_update_ocr: 是否需要重新截图更新self.ocr_result
        :param crop: 截图区域,只有need_update_ocr为true时才生效
        :param source_pos:源的位置坐标，用于计算与目标的距离,格式：（x,y）
        :return:相对窗口的最近目标文本的中心坐标，格式(x,y)
        """
        target_texts = [target] if isinstance(target, str) else list(target)  # 确保目标文本是列表格式
        min_distance = float('inf')
        target_pos = None
        if need_update_ocr:
            # 更新self.current_screenshot
            self.take_screenshot(crop)
            # 更新self.ocr_result
            self.perform_ocr(is_log=is_log)
        for result in self.ocr_result:
            text = result[0]
            match, matched_text = self.is_text_match(text, target_texts, include)
            if match:
                # 计算出相对屏幕的坐标后再计算中心坐标，用于后续与传入的source_pos计算距离
                result_x, result_y = random_rectangle_point(self.calculate_text_position(result), n)
                # 计算距离
                distance = math.sqrt((source_pos[0] - result_x) ** 2 + (source_pos[1] - result_y) ** 2)
                if distance < min_distance:
                    min_distance = distance
                    target_pos = (result_x, result_y)
        if target_pos is None:
            # self.logger.error(f"目标文字：{target_texts} 未找到匹配文字")
            return None, min_distance
        return target_pos, min_distance

    def stop(self):
        self.running = False
        try:
            self.input_handler.restore_window_position()
        except Exception as e:
            self._log_error_throttled(
                "restore_window_failed",
                _(f'Failed to restore window position: {e}', msgid='failed_to_restore_window_position_e'),
            )

    def start(self):
        self.running = True

    def pause(self):
        self.is_paused = True
        # 清除事件，线程会暂停
        self.pause_event.clear()

    def resume(self):
        self.is_paused = False
        # 设置事件，线程会继续
        self.pause_event.set()

    def get_crop_form_first_screenshot(self, crop=(0, 0, 1, 1), is_resize=False):
        """
        从完整图中裁剪出局部图
        """
        if self.first_screenshot is None:
            self._log_error_throttled(
                "crop_from_first_no_screenshot",
                _('No first_screenshot currently, crop failed', msgid='no_first_screenshot_currently_crop_failed'),
            )
            return None

        crop_image, crop_relative_pos = ImageUtils.crop_image(self.first_screenshot, crop, self.hwnd)
        if config.showScreenshot.value:
            signalBus.showScreenshot.emit(crop_image)
        if is_resize:
            crop_image = ImageUtils.resize_image(crop_image, (self.scale_x, self.scale_y))
        return crop_image

    @atoms
    def read_text_from_crop(self, crop=(0, 0, 1, 1), extract=None, is_screenshot=False, is_log=False):
        """
        通过crop找对应的文本内容
        """
        if is_screenshot:
            self.take_screenshot()
        if self.first_screenshot is None:
            self._log_error_throttled(
                "read_text_no_screenshot",
                _('No screenshot currently, unable to read text', msgid='no_screenshot_currently_unable_to_read_text'),
                level="warning",
            )
            self.ocr_result = []
            return self.ocr_result
        crop_image, crop_relative_pos = ImageUtils.crop_image(self.first_screenshot, crop, self.hwnd)
        self.perform_ocr(image=crop_image, extract=extract, is_log=is_log)
        return self.ocr_result

    @atoms
    def find_image_and_count(self, target, template: str, threshold=0.6, extract=None, is_show=False, is_log=False):
        try:
            if isinstance(target, str):
                target = cv2.imread(target)
            if target is None:
                self._log_error_throttled(
                    "find_image_and_count_no_target",
                    _('Target image is empty, skipping match counting', msgid='target_image_is_empty_skipping_match_counting'),
                )
                return None
            temp = target
            if extract:
                letter = extract[0]
                thr = extract[1]
                temp = ImageUtils.extract_letters(temp, letter, thr)
            module_ctx = self._callsite_module_context(skip_min=3, skip_max=40)
            if (module_ctx is None or module_ctx.module_dir is None) and isinstance(template, str):
                inferred = self._module_context_from_template_prefix(template)
                if inferred is not None:
                    module_ctx = inferred
            resolved_template = self._resolve_template_path(template, module_ctx=module_ctx) if isinstance(template, str) else None
            template_input = str(resolved_template) if resolved_template is not None else template
            matches = matcher.match(template_input, temp)
            if is_log:
                template_name = self._template_log_name(str(template_input), module_ctx=module_ctx)
                if len(matches) > 0:
                    for i in range(len(matches)):
                        x, y, w, h, conf = matches[i]
                        self.logger.debug(_(f'Target image: {template_name} Similarity: {conf:.2f}', msgid='target_image_template_name_similarity_conf_2'))
                self.logger.debug(_(f'Count of image {template_name} is {len(matches)}', msgid='count_of_image_template_name_is_value'))
            if is_show:
                for idx, (x, y, w, h, conf) in enumerate(matches):
                    cv2.rectangle(temp,
                                  (x, y),
                                  (x + w, y + h),
                                  (0, 255, 0), 2)
                    text = f"{conf:.2f}"
                    cv2.putText(temp, text,
                                (x, y - 5),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0, 255, 0), 2)
                ImageUtils.show_ndarray(temp)
            return len(matches)
        except Exception as e:
            self._log_error_throttled(
                "find_image_and_count_error",
                _(f'Error finding image and counting: {e}', msgid='error_finding_image_and_counting_e'),
            )
            return None

    def calculate_power_time(self):
        """
        Calculate current stamina recovery completion time based on OCR value.
        """
        try:
            ocr_result = self.read_text_from_crop(crop=(900 / 1920, 0, 1076 / 1920, 70 / 1080))
            if not ocr_result or not isinstance(ocr_result, list) or not isinstance(ocr_result[0], (list, tuple)):
                self.logger.warning(_('Unable to recognize stamina from screenshot', msgid='unable_to_recognize_stamina_from_screenshot'))
                return None

            text = str(ocr_result[0][0]) if ocr_result[0] else ""
            if "/" in text:
                num = int(text.split("/")[0])
                now = datetime.now()
                if num >= 240:
                    return now.strftime('%m-%d %H:%M')
                minutes_to_add = max(0, 6 * (240 - num))
                future_time = now + timedelta(minutes=minutes_to_add)
                return future_time.strftime('%m-%d %H:%M')

            self.logger.warning(_(f'Recognition result error: {text}', msgid='recognition_result_error_text'))
            return None
        except Exception as e:
            self.logger.warning(_(f'Failed to recognize stamina: {e}', msgid='failed_to_recognize_stamina_e'))
            return None


if __name__ == '__main__':
    pass





