from app.infrastructure.config.app_config import is_non_chinese_ui_language


# 在文件最末尾添加该函数
def ui_text(zh_text: str, en_text: str) -> str:
    """
    全局多语言适配工具函数
    """
    if is_non_chinese_ui_language():
        return en_text
    return zh_text


def get_all_children(widget):
    children = []
    for child in widget.children():
        children.append(child)
        children.extend(get_all_children(child))
    return children

