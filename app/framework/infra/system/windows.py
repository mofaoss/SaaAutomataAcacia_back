import win32api
import win32con
import win32gui


def is_fullscreen(hwnd):
    window_rect = win32gui.GetWindowRect(hwnd)
    window_width = window_rect[2] - window_rect[0]
    window_height = window_rect[3] - window_rect[1]

    screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

    return window_width == screen_width and window_height == screen_height


def enumerate_child_windows(parent_hwnd):
    def callback(handle, windows):
        windows.append(handle)
        return True

    child_windows = []
    win32gui.EnumChildWindows(parent_hwnd, callback, child_windows)
    return child_windows


def get_hwnd(window_title, window_class):
    """Mirror main-branch lookup order but add strict dimension validation to avoid picking up 65535x0 ghosts."""

    def is_valid_game_window(hwnd):
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False
        if win32gui.IsIconic(hwnd):
            return False
        try:
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            # 过滤掉 65535x0 这种异常尺寸，以及过大的异常坐标
            return 0 < w < 30000 and 0 < h < 30000
        except Exception:
            return False

    def find_class_from_root(root_hwnd, require_valid=True):
        handle_list = [root_hwnd]
        try:
            handle_list.extend(enumerate_child_windows(root_hwnd))
        except Exception:
            pass
            
        for handle in handle_list:
            try:
                if win32gui.GetClassName(handle) != window_class:
                    continue
            except Exception:
                continue
            if not require_valid or is_valid_game_window(handle):
                return handle
        return None

    # 1. 优先尝试 FindWindow (最快，通常是最近活跃窗口)
    root_hwnd = win32gui.FindWindow(None, window_title)
    if root_hwnd:
        matched = find_class_from_root(root_hwnd, require_valid=True)
        if matched:
            return matched

    # 2. 如果 FindWindow 拿到的是无效窗口（比如隐身模式下被置底），则遍历所有同名窗口寻找有效的一个
    def callback(hwnd, results):
        try:
            if win32gui.GetWindowText(hwnd) == window_title:
                results.append(hwnd)
        except Exception:
            pass
        return True

    top_hwnds = []
    win32gui.EnumWindows(callback, top_hwnds)

    for top_hwnd in top_hwnds:
        if top_hwnd == root_hwnd:
            continue
        matched = find_class_from_root(top_hwnd, require_valid=True)
        if matched:
            return matched

    # 3. 最后保底：如果实在找不到有尺寸的，才回退到返回任何匹配类名的窗口
    if root_hwnd:
        matched = find_class_from_root(root_hwnd, require_valid=False)
        if matched:
            return matched

    for top_hwnd in top_hwnds:
        if top_hwnd == root_hwnd:
            continue
        matched = find_class_from_root(top_hwnd, require_valid=False)
        if matched:
            return matched

    return None
