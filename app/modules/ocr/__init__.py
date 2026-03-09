# 读取 OCR 替换配置
import os
import json
import logging
import sys

from app.modules.ocr.ocr import OCR
from app.infrastructure.runtime.paths import APPDATA_DIR, ensure_runtime_dirs


logger = logging.getLogger(__name__)

ensure_runtime_dirs()
json_path = str(APPDATA_DIR / "ocr_replacements.json")
os.makedirs(os.path.dirname(json_path), exist_ok=True)
if not os.path.exists(json_path):
    with open(json_path, 'w', encoding='utf-8') as file:
        json.dump({'direct': {}, 'conditional': {}}, file, ensure_ascii=False, indent=4)

with open(json_path, 'r', encoding='utf-8') as file:
    replacements = json.load(file)

# 初始化 OCR 对象
ocr = OCR(logger, replacements)

