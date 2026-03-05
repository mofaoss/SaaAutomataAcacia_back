import sys
import os
from pathlib import Path


def app_dir():
    """Returns the base application path."""
    if hasattr(sys, "frozen"):
        # Handles PyInstaller/Nuitka frozen execution
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def get_app_version() -> str:
    """
    Dynamically read the application version from update_data.txt.
    Expects a plain text file where the second line contains the version string.
    Ensures Single Source of Truth (SSOT) for versioning.
    """
    default_version = "2.3.1"
    try:
        root_dir = Path(__file__).resolve().parent.parent
        update_file = root_dir / "update_data.txt"

        if not update_file.exists():
            print(f"Warning: {update_file.name} not found. Using default version: {default_version}")
            return default_version

        with open(update_file, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

            # 校验文件是否至少包含两行内容
            if len(lines) >= 2:
                version_str = lines[1].strip()
                if version_str:
                    return version_str

            print(f"Warning: Unexpected format in {update_file.name}. Using default version: {default_version}")

    except Exception as e:
        print(f"Error parsing version from update_data.txt: {e}. Using default version: {default_version}")

    return default_version


class Config:
    app_ver = get_app_version()
    app_name = "SaaAutomataAcacia"
    app_exec = "SAA"
    app_publisher = "mofaoss"
    app_url = "https://github.com/mofaoss/SaaAutomataAcacia"
    app_icon = "app/resource/images/logo.ico"
    app_dir = os.getenv("SAA_APP_DIR", str(app_dir()))