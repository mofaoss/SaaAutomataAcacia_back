# coding:utf-8
"""统一路径管理模块，兼容开发环境与打包环境"""
import sys
from pathlib import Path
import shutil
import logging


logger = logging.getLogger(__name__)


def _get_project_root():
    """
    获取项目根目录，兼容开发环境和 Nuitka/PyInstaller 打包环境。
    """
    if getattr(sys, 'frozen', False):
        # 打包后，sys.executable 指向 exe 文件，runtime 目录应在 exe 同级
        return Path(sys.executable).parent
    else:
        # 开发环境：当前文件在 app/framework/infra/runtime/paths.py
        # 需要向上回退 4 层到项目根目录
        return Path(__file__).resolve().parents[4]


PROJECT_ROOT = _get_project_root()
RUNTIME_DIR = PROJECT_ROOT / "runtime"
APPDATA_DIR = RUNTIME_DIR / "appdata"
APPDATA_OLD_DIR = PROJECT_ROOT / "AppData"  # 旧版本的用户数据目录，兼容迁移
LOG_DIR = RUNTIME_DIR / "log"
TEMP_DIR = RUNTIME_DIR / "temp"


def ensure_runtime_dirs():
    """创建运行时目录，如果不存在"""
    for p in (RUNTIME_DIR, APPDATA_DIR, LOG_DIR, TEMP_DIR):
        p.mkdir(parents=True, exist_ok=True)


def copy_user_data(source_path: Path | str = None, target_path: Path | str = APPDATA_DIR, recursive: bool = False, **kwargs):
    """
    备份用户数据到目标路径。
    兼顾输入是文件还是目录的各个情况，目录级复制必须开启递归 (recursive=True)。
    """
    ensure_runtime_dirs()

    # 兼容旧版本关键字参数调用 (user_file_path, backup_dir)
    src = source_path if source_path is not None else kwargs.get("user_file_path")
    tgt = target_path if "backup_dir" not in kwargs else kwargs.get("backup_dir")

    if src is None or tgt is None:
        return

    src = Path(src)
    tgt = Path(tgt)

    if not src.exists():
        logger.debug(f"源路径不存在: {src}")
        return

    try:
        # 防止自我复制
        if src.resolve() == tgt.resolve():
            return
    except Exception:
        pass

    if src.is_file():
        # 判断目标是否应被当作"目录"（已存在目录、通过 backup_dir 传参，或以路径分隔符结尾）
        is_tgt_dir = tgt.is_dir() or "backup_dir" in kwargs or str(target_path).endswith(('/', '\\'))

        if is_tgt_dir:
            tgt.mkdir(parents=True, exist_ok=True)
            dest_file = tgt / src.name
        else:
            # 否则视为明确的"目标文件路径"（如果存在即覆盖，如果不存在即以该文件名创建）
            tgt.parent.mkdir(parents=True, exist_ok=True)
            dest_file = tgt

        try:
            if src.resolve() != dest_file.resolve():
                shutil.copy2(src, dest_file)
        except Exception as e:
            logger.error(f"复制文件失败 {src} 到 {dest_file}: {e}")

    elif src.is_dir():
        if not recursive:
            logger.debug(f"跳过目录复制 (未开启递归): {src}")
            return

        if tgt.is_file():
            logger.error(f"无法将目录 {src} 复制到文件 {tgt}")
            return

        tgt.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            # 递归复制子项，确保目录结构不会被展平
            copy_user_data(source_path=item, target_path=tgt / item.name, recursive=recursive)
