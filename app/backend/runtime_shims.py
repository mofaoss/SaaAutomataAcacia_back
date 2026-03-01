import json
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional

from app.common.setting import CONFIG_FILE


class SimpleSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            try:
                callback(*args, **kwargs)
            except Exception:
                pass


class RuntimeConfigItem:
    def __init__(self, section: str, key: str, value: Any):
        self.section = section
        self.key = key
        self.value = value


class RuntimeConfig:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._raw: Dict[str, Dict[str, Any]] = {}
        self._items: Dict[str, RuntimeConfigItem] = {}
        self.reload()

    def reload(self):
        if self.file_path.exists():
            with self.file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        self._raw = data if isinstance(data, dict) else {}
        self._items.clear()
        for section, section_map in self._raw.items():
            if isinstance(section_map, dict):
                for key, value in section_map.items():
                    self._items[key] = RuntimeConfigItem(section, key, value)

    def _ensure_item(self, name: str) -> RuntimeConfigItem:
        if name not in self._items:
            self._items[name] = RuntimeConfigItem("runtime", name, None)
            self._raw.setdefault("runtime", {})[name] = None
        return self._items[name]

    def __getattr__(self, name: str) -> RuntimeConfigItem:
        return self._ensure_item(name)

    def get(self, item_or_name: Any):
        if isinstance(item_or_name, RuntimeConfigItem):
            return item_or_name.value
        if isinstance(item_or_name, str):
            return self._ensure_item(item_or_name).value
        return None

    def set(self, item_or_name: Any, value: Any):
        if isinstance(item_or_name, RuntimeConfigItem):
            item = item_or_name
        else:
            item = self._ensure_item(str(item_or_name))
        item.value = value
        self._raw.setdefault(item.section, {})[item.key] = value
        self.save()

    def save(self):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(self._raw, f, ensure_ascii=False, indent=4)

    def toDict(self):
        return json.loads(json.dumps(self._raw, ensure_ascii=False))


class Stream:
    def __init__(self, original_stream):
        self.original_stream = original_stream
        self.message = SimpleSignal()

    def write(self, message):
        self.original_stream.write(message)
        self.message.emit(str(message))

    def flush(self):
        self.original_stream.flush()


class TextStreamHandler(logging.Handler):
    def __init__(self, stream: Stream):
        super().__init__()
        self.stream = stream
        self.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record)
        self.stream.write(msg + "\n")


class _SignalBus:
    _default_names = [
        "checkUpdateSig",
        "micaEnableChanged",
        "switchToSampleCard",
        "updatePiecesNum",
        "jigsawDisplaySignal",
        "showMessageBox",
        "updateFishKey",
        "showScreenshot",
        "sendHwnd",
    ]

    def __init__(self):
        self._signals: Dict[str, SimpleSignal] = {}
        for name in self._default_names:
            self._signals[name] = SimpleSignal()

    def __getattr__(self, item):
        if item not in self._signals:
            self._signals[item] = SimpleSignal()
        return self._signals[item]


def _install_config_module(config_path: Optional[Path] = None):
    module = ModuleType("app.common.config")
    runtime_config = RuntimeConfig(config_path or Path(CONFIG_FILE))

    def is_non_chinese_ui_language() -> bool:
        language = runtime_config.get("Language")
        if not language:
            return False
        return not str(language).replace("-", "_").startswith("zh")

    module.config = runtime_config
    module.is_non_chinese_ui_language = is_non_chinese_ui_language
    module.resolve_configured_locale = lambda *_args, **_kwargs: None
    sys.modules["app.common.config"] = module


def _install_signal_bus_module():
    module = ModuleType("app.common.signal_bus")
    module.signalBus = _SignalBus()
    sys.modules["app.common.signal_bus"] = module


def _install_logger_module():
    module = ModuleType("app.common.logger")

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stdout_stream = Stream(original_stdout)
    stderr_stream = Stream(original_stderr)

    logger = logging.getLogger("saa.backend")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False
    logger.addHandler(TextStreamHandler(stdout_stream))

    module.original_stdout = original_stdout
    module.original_stderr = original_stderr
    module.stdout_stream = stdout_stream
    module.stderr_stream = stderr_stream
    module.logger = logger
    module.Stream = Stream

    class Logger:
        def __init__(self, _log_widget=None):
            pass

        def redirectOutput(self):
            return None

        def updateDisplay(self, _message):
            return None

    module.Logger = Logger
    sys.modules["app.common.logger"] = module


def install_runtime_shims(config_path: Optional[Path] = None):
    _install_config_module(config_path=config_path)
    _install_signal_bus_module()
    _install_logger_module()
