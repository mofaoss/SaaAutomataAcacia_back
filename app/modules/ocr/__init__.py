# 读取 OCR 替换配置
import os
import json
import logging
import sys

from app.modules.ocr.ocr import OCR


logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

json_path = os.path.join(base_dir, "AppData", "ocr_replacements.json")
os.makedirs(os.path.dirname(json_path), exist_ok=True)
if not os.path.exists(json_path):
    with open(json_path, 'w', encoding='utf-8') as file:
        json.dump({'direct': {}, 'conditional': {}}, file, ensure_ascii=False, indent=4)

with open(json_path, 'r', encoding='utf-8') as file:
    replacements = json.load(file)

# 初始化 OCR 对象
ocr = OCR(logger, replacements)
