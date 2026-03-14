#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   build.py
@Time    :   2024/07/05 11:19:32
@Author  :   KmBase
@Version :   1.0
@License :   (C)Copyright 2022, KmBase
@Desc    :   使用前需要先安装InnoSetup,应用更新时请不要修改app_id
"""
import glob
import os
import platform
import subprocess
import sys
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from perfect_build import Config
import uuid
try:
    from prepare_build import (
        cleanup_stage_dir,
        merge_release_from_stage,
        prepare_nuitka_stage,
    )
except ModuleNotFoundError:
    from PerfectBuild.prepare_build import (
        cleanup_stage_dir,
        merge_release_from_stage,
        prepare_nuitka_stage,
    )

# python .\PerfectBuild\build.py --n


def find_iss_compiler() -> str:
    # 1. 优先环境变量
    for env in ("INNO_SETUP_COMPILER", "ISCC_PATH"):
        p = os.environ.get(env)
        if p and Path(p).exists():
            return p

    # 2. PATH 中查找
    for exe in ("ISCC.exe", "Compil32.exe"):
        p = shutil.which(exe)
        if p:
            return p

    # 3. 常见安装目录
    base_dirs = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        Path.home() / "AppData/Local/Programs",
    ]

    for base in filter(None, base_dirs):
        base = Path(base)
        for exe in ("ISCC.exe", "Compil32.exe"):
            p = base / "Inno Setup 6" / exe
            if p.exists():
                return str(p)

    return ""


iss_compiler = find_iss_compiler()


# subprocess.call(['pip', 'install', '-U', 'nuitka'])
# subprocess.call(['pip', 'install', '-r', 'requirements-prod.txt'])
# subprocess.call(['pip', 'freeze', '>', 'equirements.txt'])

def generate_new_id(mode):
    if mode:
        print(str(uuid.uuid4()).upper())
    else:
        return "EF37701A-BF20-4C1C-8459-34041F620CFE"


class PerfectBuild:
    # 系统信息
    system = platform.system()
    arch = platform.architecture()[0][:2]
    # 配置信息
    app_ver = Config.app_ver
    app_name = Config.app_name
    app_publisher = Config.app_publisher
    app_url = Config.app_url
    app_icon = Config.app_icon
    app_exec = Config.app_exec
    app_dir = Config.app_dir

    def __init__(self, app_id, mode="--p"):
        """
        初始化变量
        """
        self.app_id = app_id
        self.mode = mode.replace("--", "")
        self.dist = f"{self.app_exec}.dist"
        if self.mode == "p":
            self.dist = f"dist//{self.app_exec}"
        self.app_dir = Path(self.app_dir)
        self.build_dir = Path.joinpath(self.app_dir, "build")
        if not self.build_dir.exists():
            self.build_dir.mkdir()
        self.release_dir = Path.joinpath(
            self.app_dir, "release", f"{self.app_ver}-{self.mode}"
        )
        if not self.release_dir.exists():
            if not self.release_dir.parent.exists():
                self.release_dir.parent.mkdir()
            self.release_dir.mkdir()

    def nbuild(self, env: dict | None = None):
        """
        官方文档 : https://nuitka.net/
        使用Nuitka构建example:
        nuitka_cmd = [
            "python",
            "-m",
            "nuitka",
            "--show-progress",
            "--show-memory",
            "--standalone",
            "--include-data-dir=output=output",
            "--include-data-dir=icon=icon",
            "--plugin-enable=pyside6",
            f"--output-dir={output_dir}",
            f"--include-data-files=example.db=example.db",
        ]
        """
        output_dir = Path.joinpath(self.app_dir, "build", f"{self.system}-{self.arch}")
        optional_data_mappings = [
            ("PerfectBuild/assets/shapely.libs/.load-order-shapely-2.0.7", "shapely.libs/.load-order-shapely-2.0.7", "file"),
            ("resources", "resources", "dir"),
            ("docs/help.md", "docs/help.md", "file"),
            ("docs/help_en.md", "docs/help_en.md", "file"),
            ("update_data.txt", "update_data.txt", "file"),
            ("asset", "asset", "dir"),
            ("app/framework/i18n", "app/framework/i18n", "dir"),
        ]

        def _include_arg(src: str, dst: str, kind: str) -> str | None:
            src_path = Path(self.app_dir, src)
            if kind == "dir":
                if src_path.is_dir():
                    return f"--include-data-dir={src}={dst}"
                print(f"[build] warning: skip missing data dir: {src}")
                return None
            if src_path.is_file():
                return f"--include-data-file={src}={dst}"
            print(f"[build] warning: skip missing data file: {src}")
            return None

        def _collect_dynamic_python_modules() -> list[str]:
            modules_root = Path(self.app_dir, "app", "features", "modules")
            if not modules_root.exists():
                return []
            patterns = [
                "*/usecase/*_usecase.py",
                "*/ui/*.py",
                "*/ui/**/*.py",
            ]
            modules: set[str] = set()
            for pattern in patterns:
                for py_file in modules_root.glob(pattern):
                    if not py_file.is_file():
                        continue
                    if py_file.name == "__init__.py":
                        continue
                    rel = py_file.relative_to(self.app_dir).with_suffix("")
                    module_name = ".".join(rel.parts)
                    modules.add(module_name)
            return sorted(modules)

        def _collect_module_data_mappings() -> list[tuple[str, str, str]]:
            modules_root = Path(self.app_dir, "app", "features", "modules")
            if not modules_root.exists():
                return []
            mappings: list[tuple[str, str, str]] = []
            for module_dir in modules_root.iterdir():
                if not module_dir.is_dir():
                    continue
                for data_dir_name in ("assets", "i18n"):
                    src_path = module_dir / data_dir_name
                    if not src_path.is_dir():
                        continue
                    rel_src = str(src_path.relative_to(self.app_dir)).replace("\\", "/")
                    mappings.append((rel_src, rel_src, "dir"))
            return mappings

        cmd_args = [
            sys.executable,
            "-m",
            "nuitka",
            "--show-progress",
            "--show-memory",
            "--standalone",
            "--assume-yes-for-downloads",
            "--plugin-enable=pyside6",
            "--plugin-enable=numpy",
            f"--output-dir={output_dir}",
            "--windows-uac-admin",
            "--windows-console-mode=disable",
            "--include-package=app.features.modules",

            # === 1. 精简 Qt 插件 (精准剔除废料，保留 xml 确保 SVG 图标正常) ===
            "--noinclude-qt-plugins=qml,webengine,network,multimedia,sql,test,sensorkit,position,location,bluetooth,nfc,serialport,websockets,printsupport,dbus,pdf,tls",

            # === 2. 核心模块的 Python 层拦截 (斩断没用的巨兽) ===
            "--nofollow-import-to=PySide6.QtNetwork",
            "--nofollow-import-to=PySide6.QtPdf",
            "--nofollow-import-to=PySide6.QtPdfWidgets",
            "--nofollow-import-to=PySide6.QtWebEngine",
            "--nofollow-import-to=PySide6.QtWebEngineCore",
            "--nofollow-import-to=PySide6.QtWebEngineWidgets",
            "--nofollow-import-to=PySide6.QtQml",
            "--nofollow-import-to=PySide6.QtQuick",
            "--nofollow-import-to=PySide6.Qt3DCore",
            # 同步补齐多媒体和数据库的 Python 层拦截
            "--nofollow-import-to=PySide6.QtMultimedia",
            "--nofollow-import-to=PySide6.QtMultimediaWidgets",
            "--nofollow-import-to=PySide6.QtSql",
            "--nofollow-import-to=PySide6.QtTest",

            # === 3. 底层 DLL (与 Python 层拦截一一对应) ===
            "--noinclude-dlls=*mfc140*.dll",              # 微软老古董界面库
            "--noinclude-dlls=*qt6network*.dll",
            "--noinclude-dlls=*qt6pdf*.dll",
            "--noinclude-dlls=*qpdf*.dll",
            "--noinclude-dlls=*qt6webengine*.dll",
            "--noinclude-dlls=*qt6qml*.dll",
            "--noinclude-dlls=*qt6quick*.dll",
            "--noinclude-dlls=*qt63dcore*.dll",
            "--noinclude-dlls=*qt6multimedia*.dll",       # 多媒体底层
            "--noinclude-dlls=*qt6sql*.dll",              # 数据库底层
            "--noinclude-dlls=*qt6test*.dll",             # 测试模块底层

            # === 4. 仅拦截没人用的奇葩图片格式，坚决保留 WebP/JPEG/PNG/SVG/GIF/ICO ===
            "--noinclude-dlls=*qicns*.dll",               # 苹果 Mac 图标格式
            "--noinclude-dlls=*qtiff*.dll",               # TIFF 传真格式
            "--noinclude-dlls=*qtga*.dll",                # TGA 格式
            "--noinclude-dlls=*qwbmp*.dll",               # 古董手机 WAP 网页图片格式

            # === 5. 清理无用的 Win32gui 底层 API ===
            "--nofollow-import-to=win32print",            # 打印机 API (控制和调用物理打印机)
            "--nofollow-import-to=win32ras",              # 拨号上网 API (老式调制解调器拨号连接)
            "--nofollow-import-to=win32inet",             # IE 浏览器网络 API (古董级 HTTP/FTP 封装)
            "--nofollow-import-to=win32help",             # 早期 WinHelp 帮助文件 API (调用 .chm/.hlp 文件)
            "--nofollow-import-to=win32ts",               # 终端服务 API (远程桌面会话管理)
            "--nofollow-import-to=win32wnet",             # Windows 局域网 API (共享文件夹/网络驱动器映射)
            "--nofollow-import-to=win32security",         # 安全与权限底层 API (系统底层 ACL/Token 权限验证)
            "--nofollow-import-to=win32pdh",              # 性能数据助手 API (系统级 CPU/内存等性能监控)
            "--nofollow-import-to=win32lz",               # 古董 Lempel-Ziv 压缩 API (极其古老的微软压缩算法)
            "--nofollow-import-to=win32job",              # 任务对象 API (管理 Windows 进程组/Job Objects)
            "--nofollow-import-to=win32net",              # 网络管理 API (管理本地或远程计算机的网络用户/群组)
            "--nofollow-import-to=win32pipe",             # 命名管道 API (进程间极其底层的本地通信)
            "--nofollow-import-to=win32profile",          # 用户配置文件 API (加载/卸载 Windows 账户配置文件)
            "--nofollow-import-to=win32transaction",      # 事务管理器 API (内核级文件/注册表事务回滚)
            "--nofollow-import-to=win32uiole",            # OLE 对象界面 API (早期的微软对象链接与嵌入技术)
            "--nofollow-import-to=win32trace",            # 调试跟踪 API (Windows 内核和服务的底层日志抓取)
            "--nofollow-import-to=win32crypt",            # Windows 底层加密与证书 API (DPAPI 数据保护等)
            "--nofollow-import-to=win32cred",             # Windows 凭据管理器 API (存取控制面板里的系统凭据)
            "--nofollow-import-to=win32service",          # Windows 后台服务 API (编写/控制无界面的系统自启服务)
            "--nofollow-import-to=servicemanager",        # Windows 服务管理器模块 (配合 win32service 使用)
            "--nofollow-import-to=win32evtlog",           # Windows 事件日志 API (向系统自带的事件查看器写日志)

            # === 6. 清理 Pillow 的 Tkinter 废料 ===
            "--nofollow-import-to=tkinter",
            "--nofollow-import-to=PIL._imagingtk",

            # 精简 OpenCV / onnxruntime 相关 DLL
            "--noinclude-dlls=cv2/opencv_videoio_ffmpeg*.dll",
            "--noinclude-dlls=cv2/opencv_video*.dll",
            "--noinclude-data-files=cv2/opencv_videoio_ffmpeg*.dll",
            "--noinclude-data-files=cv2/opencv_video*.dll",
            "--noinclude-data-files=resources/models/backup_ppocrv5/*", # 排除 OCR 模型不需要的 cls 模型文件

            # 排除加载动画相关的 GIF 文件
            "--noinclude-data-files=resources/logo/*.gif",

            ]


        for module_name in _collect_dynamic_python_modules():
            cmd_args.append(f"--include-module={module_name}")

        for src, dst, kind in optional_data_mappings:
            include = _include_arg(src, dst, kind)
            if include:
                cmd_args.append(include)

        for src, dst, kind in _collect_module_data_mappings():
            include = _include_arg(src, dst, kind)
            if include:
                cmd_args.append(include)

        if platform.system() == "Windows":
            cmd_args.extend((
                f"--windows-icon-from-ico={self.app_icon}",
                "--msvc=latest",
            ))

        cmd_args.append(f"{self.app_dir}/{self.app_exec}.py")

        print("[build] running:", " ".join(map(str, cmd_args)))
        process = subprocess.run(cmd_args, shell=False, env=env)

        if process.returncode != 0:
            raise ChildProcessError("Nuitka building failed.")

        dist_root = output_dir / f"{self.app_exec}.dist"
        if dist_root.exists():
            removed_files: list[Path] = []
            for pattern in ("cv2/opencv_videoio_ffmpeg*.dll", "cv2/opencv_video*.dll"):
                for matched in sorted(dist_root.glob(pattern)):
                    if matched.is_file():
                        matched.unlink()
                        removed_files.append(matched)
            if removed_files:
                print("[build] pruned excluded binaries:")
                for removed in removed_files:
                    rel = removed.relative_to(dist_root).as_posix()
                    print(f"  - {rel}")

        print("Nuitka Building done.")

    def pbuild(self):
        """
        官方文档 : https://pyinstaller.org/
        使用Pyinstaller构建example:
        """
        output_dir = Path.joinpath(self.app_dir, "build", f"{self.system}-{self.arch}")
        build_dir = Path.joinpath(output_dir, "build")
        dist_dir = Path.joinpath(output_dir, "dist")
        cmd_args = [
            "pyinstaller",
            "--onedir",
            "--add-data=icon:icon",
            f"--distpath={dist_dir}",
            f"--workpath={build_dir}",
            "--contents-directory=.",
        ]
        if platform.system() == "Windows":
            cmd_args.extend((f"-i{self.app_icon}",))
        # '-w',
        cmd_args.append(f"{self.app_dir}/{self.app_exec}.py")
        print(cmd_args)
        process = subprocess.run(cmd_args, shell=True)
        if process.returncode != 0:
            raise ChildProcessError("Pyinstaller building failed.")
        print("Pyinstaller Building done.")

    def create_setup(self):
        iss_work = self.update_iss()
        if not iss_compiler:
            raise FileNotFoundError(
                "Inno Setup compiler not found. Please install Inno Setup or set INNO_SETUP_COMPILER."
            )
        if Path(iss_compiler).exists():
            print("Creating Windows Installer...", end="")
            compiler_name = Path(iss_compiler).name.lower()
            if compiler_name == "iscc.exe":
                compiler_cmd = [str(iss_compiler), str(iss_work)]
            else:
                compiler_cmd = [str(iss_compiler), "/cc", str(iss_work)]
            process = subprocess.run(compiler_cmd)
            if process.returncode != 0:
                raise ChildProcessError("Creating Windows installer failed.")
            print("done")

    def update_iss(self):
        settings = {
            "AppId": self.app_id,
            "AppName": self.app_name,
            "AppVersion": self.app_ver,
            "AppMode": self.mode,
            "System": self.system,
            "Arch": self.arch,
            "AppPublisher": self.app_publisher,
            "AppURL": self.app_url,
            "AppIcon": self.app_icon,
            "AppExeName": self.app_exec + ".exe",
            "ProjectDir": str(self.app_dir),
            "BuildDir": str(self.build_dir),
            "ReleaseDir": str(self.release_dir),
            "Dist": str(self.dist),
            "ARCH_MODE": (
                "ArchitecturesInstallIn64BitMode=x64" if self.arch == "64" else ""
            ),
        }

        iss_template = f"PerfectBuild/nuitka-setup-template.iss"
        iss_work = Path.joinpath(
            self.build_dir, f"{self.app_name}-{self.arch}-{self.mode}.iss"
        )
        with open(iss_template) as template:
            iss_script = template.read()

        for key in settings:
            iss_script = iss_script.replace(f"%%{key}%%", settings.get(key))

        with open(iss_work, "w") as iss:
            iss.write(iss_script)
        return iss_work

    def create_portable(self):
        file_list = glob.glob(
            f"{self.build_dir}/{self.system}-{self.arch}/{self.dist}/**",
            recursive=True,
        )
        file_list.sort()
        portable_file = (
                self.release_dir
                / f"{self.app_exec}-{self.app_ver}-{self.mode}-Portable-{self.system}-{self.arch}.zip"
        )
        print("Creating portable package...")
        with ZipFile(portable_file, "w", compression=ZIP_DEFLATED) as zf:
            for file in file_list:
                file = Path(file)
                name_in_zip = f'{self.app_exec}/{"/".join(file.parts[6:])}'
                print(name_in_zip)
                if file.is_file():
                    zf.write(file, name_in_zip)
        print("Creating portable package done.")


def _run_nuitka_in_stage(app_id: str, mode: str) -> None:
    project_root = Path(__file__).resolve().parent.parent
    stage_dir = project_root / ".nuitka_stage"

    cwd = Path.cwd()
    original_app_dir = PerfectBuild.app_dir
    try:
        stage_result = prepare_nuitka_stage(
            project_root=project_root,
            stage_dir_name=".nuitka_stage",
        )
        stage_dir = stage_result.stage_dir
        print(
            "[build] nuitka stage ready: "
            f"{stage_dir} "
            f"(changed {stage_result.py_files_changed}/{stage_result.py_files_scanned} .py files, "
            f"remaining dynamic _(fstring) calls: {stage_result.remaining_dynamic_fstring_calls})"
        )

        os.chdir(stage_dir)
        PerfectBuild.app_dir = str(stage_dir)

        # Isolation: Ensure Nuitka and subprocesses prioritize the transformed stage directory
        # over the original project root if it was installed in the environment.
        env = os.environ.copy()
        env["PYTHONPATH"] = str(stage_dir) + os.pathsep + env.get("PYTHONPATH", "")

        pb = PerfectBuild(app_id, mode)
        # Pass the isolated env to nbuild if needed, or rely on os.chdir + PYTHONPATH
        pb.nbuild(env=env)
        pb.create_portable()
        if pb.system == "Windows":
            pb.create_setup()

        merge_release_from_stage(project_root=project_root, stage_dir=stage_dir)
    finally:
        os.chdir(cwd)
        PerfectBuild.app_dir = original_app_dir
        cleanup_stage_dir(stage_dir)


def main(args):
    """
    :param args:
        --n:Nuitka building
        --p:Pyinstaller building
        --g:Generate APPID
    :return:
    """
    if len(sys.argv) < 2:
        mode = "--p"
    else:
        mode = args[1]
        if mode == "--g":
            generate_new_id(True)
            return

    app_id = generate_new_id(False)

    if mode == "--n":
        _run_nuitka_in_stage(app_id, mode)
        return

    pb = PerfectBuild(app_id, mode)
    pb.pbuild()
    pb.create_portable()
    if pb.system == "Windows":
        pb.create_setup()


if __name__ == "__main__":
    main(sys.argv)
