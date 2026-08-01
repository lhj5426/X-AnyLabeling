"""
秒级转发器：EnumWindows + SendMessage(WM_COPYDATA)。
只依赖 ctypes + stdlib，无需 PyQt/conda。

使用 EnumWindows 确保在有多个子窗口（横向/垂直/瀑布流 viewer）
打开时也能精确找到主窗口 HWND，避免向错误的窗口发送 WM_COPYDATA。
"""
import sys
import ctypes

from app_info import __appname__

WM_COPYDATA = 0x004A
APP_TITLE = __appname__

class COPYDATASTRUCT(ctypes.Structure):
    _fields_ = [
        ("dwData", ctypes.c_void_p),
        ("cbData", ctypes.c_uint32),
        ("lpData", ctypes.c_void_p),
    ]


def _find_main_window():
    """使用 EnumWindows 精确查找主窗口 HWND。

    FindWindowW 在 viewer dialog 打开时可能返回错误的窗口（如 viewer 窗口），
    使用 EnumWindows 遍历所有顶层窗口，按标题 + 可见性 + 窗口类名精确匹配。
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    GWL_STYLE = -16
    WS_VISIBLE = 0x10000000

    found = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    @WNDENUMPROC
    def enum_proc(hwnd, lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value != APP_TITLE:
            return True
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        if not (style & WS_VISIBLE):
            return True
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        class_name = class_buf.value or ""
        is_main = class_name.startswith("Qt") and "Dialog" not in class_name
        found.append((hwnd, class_name, is_main))
        return True

    user32.EnumWindows(enum_proc, 0)

    if not found:
        return None
    # 优先返回主窗口（非 Dialog 的 Qt 窗口）
    for hwnd, _, is_main in found:
        if is_main:
            return hwnd
    return found[0][0]


if len(sys.argv) < 2:
    sys.exit(2)

user32 = ctypes.WinDLL("user32", use_last_error=True)

hwnd = _find_main_window()
if not hwnd:
    hwnd = user32.FindWindowW(None, APP_TITLE)
if not hwnd:
    sys.exit(2)

path = sys.argv[1].strip('"')
try:
    print(f"已发送路径到已有窗口: {path}")
except OSError:
    pass

data = path.encode("utf-8")
buf = ctypes.create_string_buffer(data)
cds = COPYDATASTRUCT(0, len(data), ctypes.cast(buf, ctypes.c_void_p))
user32.SendMessageW(hwnd, WM_COPYDATA, 0, ctypes.byref(cds))
sys.exit(0)
