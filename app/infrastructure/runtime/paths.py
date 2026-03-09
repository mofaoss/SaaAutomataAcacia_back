# coding:utf-8
"""统一路径管理模块，兼容开发环境与打包环境"""
import sys
from pathlib import Path


def _get_project_root():
    """
    获取项目根目录，兼容开发环境和 Nuitka/PyInstaller 打包环境。
    """
    if getattr(sys, 'frozen', False):
        # 打包后，sys.executable 指向 exe 文件，runtime 目录应在 exe 同级
        return Path(sys.executable).parent
    else:
        # 开发环境：当前文件在 app/infrastructure/runtime/paths.py
        # 需要向上回退 3 层到项目根目录 (app/infrastructure/runtime -> app/infrastructure -> app -> root)
        return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _get_project_root()
RUNTIME_DIR = PROJECT_ROOT / "runtime"
APPDATA_DIR = RUNTIME_DIR / "appdata"
LOG_DIR = RUNTIME_DIR / "log"
TEMP_DIR = RUNTIME_DIR / "temp"


def ensure_runtime_dirs():
    for p in (RUNTIME_DIR, APPDATA_DIR, LOG_DIR, TEMP_DIR):
        p.mkdir(parents=True, exist_ok=True)