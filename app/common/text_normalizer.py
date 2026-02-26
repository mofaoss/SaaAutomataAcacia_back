from functools import lru_cache

_FALLBACK_MAP = {
    "點": "点",
    "擊": "击",
    "領": "领",
    "獎": "奖",
    "勵": "励",
    "證": "证",
    "務": "务",
    "詳": "详",
    "細": "细",
    "獲": "获",
    "達": "达",
    "時": "时",
    "裝": "装",
    "級": "级",
    "提": "提",
    "升": "升",
    "確": "确",
    "認": "认",
    "繼": "继",
    "續": "续",
    "關": "关",
    "閉": "闭",
    "購": "购",
    "買": "买",
    "還": "还",
    "開": "开",
    "啟": "启",
    "請": "请",
    "選": "选",
    "擇": "择",
    "設": "设",
    "置": "置",
    "華": "华",
    "語": "语",
    "錄": "录",
    "戰": "战",
    "鬥": "斗",
}


@lru_cache(maxsize=1)
def _build_opencc_converter():
    try:
        from opencc import OpenCC
        return OpenCC("t2s")
    except Exception:
        return None


def normalize_chinese_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text

    converter = _build_opencc_converter()
    if converter is not None:
        try:
            return converter.convert(text)
        except Exception:
            pass

    return "".join(_FALLBACK_MAP.get(ch, ch) for ch in text)
