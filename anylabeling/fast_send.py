"""
秒级转发器：FindWindow + SendMessage(WM_COPYDATA)。
只依赖 ctypes + stdlib，无需 PyQt/conda。
"""
import sys
import ctypes

WM_COPYDATA = 0x004A
APP_TITLE = "Hmogai_260619_X-AnyLabeling"


class COPYDATASTRUCT(ctypes.Structure):
    _fields_ = [
        ("dwData", ctypes.c_void_p),
        ("cbData", ctypes.c_uint32),
        ("lpData", ctypes.c_void_p),
    ]


if len(sys.argv) < 2:
    sys.exit(2)

user32 = ctypes.WinDLL("user32", use_last_error=True)

hwnd = user32.FindWindowW(None, APP_TITLE)
if not hwnd:
    sys.exit(2)  # 窗口不存在 → BAT 走完整启动

path = sys.argv[1].strip('"')
try:
    print(f"已发送路径到已有窗口: {path}")
except OSError:
    pass  # pythonw.exe 无控制台，静默忽略

data = path.encode("utf-8")
buf = ctypes.create_string_buffer(data)
cds = COPYDATASTRUCT(0, len(data), ctypes.cast(buf, ctypes.c_void_p))
user32.SendMessageW(hwnd, WM_COPYDATA, 0, ctypes.byref(cds))
sys.exit(0)
