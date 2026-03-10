from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ModuleContext:
    module_id: str | None = None
    module_name: str | None = None
    module_dir: Path | None = None
    assets_dir: Path | None = None
    images_root: Path | None = None
    ocr_root: Path | None = None
    ui_manifest_path: Path | None = None
    generated_manifest_path: Path | None = None
    callsite_file: str | None = None
    callsite_line: int | None = None

    @classmethod
    def from_callsite(cls, *, skip: int = 2) -> "ModuleContext":
        frame = inspect.currentframe()
        for _ in range(skip):
            if frame is not None:
                frame = frame.f_back
        file_name = getattr(getattr(frame, "f_code", None), "co_filename", None)
        line_no = getattr(frame, "f_lineno", None)

        if not file_name:
            return cls(None, None, None, None, None, None, None, None, None)

        path = Path(file_name).resolve()
        parts = [p.lower() for p in path.parts]
        try:
            idx = parts.index("modules")
            module_id = path.parts[idx + 1]
            module_dir = Path(*path.parts[: idx + 2])
            assets_dir = module_dir / "assets"
            return cls(
                module_id=module_id,
                module_name=module_id,
                module_dir=module_dir,
                assets_dir=assets_dir,
                images_root=assets_dir / "images",
                ocr_root=assets_dir / "ocr",
                ui_manifest_path=assets_dir / "ui.json",
                generated_manifest_path=assets_dir / "ui.generated.json",
                callsite_file=str(path),
                callsite_line=int(line_no) if isinstance(line_no, int) else None,
            )
        except Exception:
            return cls(
                module_id=None,
                module_name=None,
                module_dir=None,
                assets_dir=None,
                images_root=None,
                ocr_root=None,
                ui_manifest_path=None,
                generated_manifest_path=None,
                callsite_file=str(path),
                callsite_line=int(line_no) if isinstance(line_no, int) else None,
            )
