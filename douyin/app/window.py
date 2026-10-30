r"""cc-piano 的软件窗口（pywebview，系统自带的 Edge WebView2 内核）。

无边框窗口：左上角红黄绿三点由网页画出（web/ui/winctl.js），点了调用这里的接口：
  红 = 关闭，黄 = 最小化，绿 = 最大化 / 还原；按住左上角的标题区域拖动窗口，双击最大化。
网页数据（主题、强调色等设置）保存在 douyin\uploads\webview，关掉再打开还在。
用法: pythonw app\window.py http://127.0.0.1:8765/
"""
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
# WebView2 的启动参数：开端页钢琴声、胶片音效不用先点一下页面才响；页面光栅化和合成交给显卡（启动和滚动更顺）；
# 环境变量会盖掉 pywebview 自己在代码里设的参数，所以把它原来的 --disable-features=ElasticOverscroll 也带上
os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
                      "--autoplay-policy=no-user-gesture-required --enable-gpu-rasterization --enable-zero-copy "
                      "--ignore-gpu-blocklist --disable-features=ElasticOverscroll")

import webview  # noqa: E402


def work_area() -> tuple[int, int, int, int]:
    """主屏幕去掉任务栏后的区域 (x, y, 宽, 高)，按系统缩放换算成窗口用的逻辑像素。"""
    import ctypes
    from ctypes import wintypes
    r = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)      # SPI_GETWORKAREA（物理像素）
    try:
        scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    except (AttributeError, OSError):
        scale = 1.0
    w, h = r.right - r.left, r.bottom - r.top
    return round(r.left / scale), round(r.top / scale), round(w / scale), round(h / scale)


class Api:
    """暴露给网页的窗口控制（window.pywebview.api.*）。下划线开头的属性不会暴露给网页。"""

    def __init__(self):
        self._win = None
        self._maxed = False
        self._prev = None

    def minimize(self):
        self._win.minimize()

    def toggle_maximize(self):
        """无边框窗口直接最大化会盖住任务栏，所以「最大化」= 铺满屏幕的可用区域（不含任务栏），
        再点还原到原来的位置和大小。"""
        if self._maxed and self._prev:
            x, y, w, h = self._prev
            self._win.resize(w, h)
            self._win.move(x, y)
            self._maxed = False
        else:
            self._prev = (self._win.x, self._win.y, self._win.width, self._win.height)
            x, y, w, h = work_area()
            self._win.move(x, y)
            self._win.resize(w, h)
            self._maxed = True
        return self._maxed

    def is_maximized(self):
        return self._maxed

    def close(self):
        self._win.destroy()


ICON = Path(__file__).resolve().parent / "icon.ico"     # 抱着音符哼歌的 Claude 小人（app/make_icon.py）


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
    try:   # 任务栏按「cc-piano」单独显示，用自己的图标，而不是 Python 的
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("cc-engine.cc-piano")
    except (AttributeError, OSError):
        pass
    api = Api()
    win = webview.create_window("cc-piano", url, js_api=api, width=1560, height=980, min_size=(1080, 680),
                                frameless=True, easy_drag=False, resizable=True, background_color="#000000")
    api._win = win
    store = PROJECT / "uploads" / "webview"
    store.mkdir(parents=True, exist_ok=True)
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(store),
                  icon=str(ICON) if ICON.exists() else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
