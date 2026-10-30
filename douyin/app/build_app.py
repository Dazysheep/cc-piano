"""把琴房打包成 Windows 软件：dist\\QinfangStudio\\（可直接运行）+ dist\\installer\\cc-piano_v<版本>_安装程序.exe。

用法: .venv\\Scripts\\python app\\build_app.py [--skip-runtime] [--skip-project] [--no-installer]
步骤：
  1. runtime\\：官方嵌入版 Python 3.13（放在 D:\\cc-engine\\.tmp\\pkg\\python-embed.zip）+ 项目 venv 的全部依赖
  2. douyin\\：项目文件（不含 .venv、成片、上传、中间文件、发布平台登录信息 publish\\profile）
  3. cc-piano.exe：app\\launcher.py 用 PyInstaller 打成单文件
  4. Inno Setup 生成安装程序（超过 2GB 自动分卷：setup.exe + .bin）
"""
import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = ROOT / "dist" / "QinfangStudio"
TMP = Path("D:/cc-engine/.tmp/pkg")
EMBED = TMP / "python-embed.zip"
SITE = ROOT / ".venv" / "Lib" / "site-packages"
ISCC = Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe")

SKIP_SITE = {"pip", "pyinstaller", "pyinstaller_hooks_contrib", "altgraph", "pefile", "pywin32_ctypes"}
SKIP_PROJECT_DIRS = {".venv", "dist", "build", "output", "uploads", "待上传",
                     "__pycache__", ".pytest_cache", ".ruff_cache"}
# publish/profile 里是各平台的登录信息，绝不能打包；app_settings.json 是这台电脑的个人设置（保存位置等）；
# 3D 建模：Blender 的个人配置（blender3d/home）、3D 建模库（models3d）、启用开关和库位置（model3d.json）都是这台电脑的，
# Blender 本体（tools/blender/blender-*）随安装包，下载下来的 zip 不用
SKIP_PROJECT_PATHS = {Path("publish/profile"), Path("app/build"), Path("app_settings.json"),
                      Path("blender3d/home"), Path("models3d"), Path("model3d.json"), Path("tools/blender/download")}

SITECUSTOMIZE = '''"""琴房内置 Python：在无窗口模式（pythonw）下运行时，子进程（ffmpeg 等命令行程序）不弹出黑色窗口。"""
import subprocess
import sys

if sys.platform == "win32" and sys.executable.lower().endswith("pythonw.exe"):
    _init = subprocess.Popen.__init__

    def _no_window(self, *args, **kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = 0x08000000      # CREATE_NO_WINDOW
        _init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _no_window
'''


def log(msg: str) -> None:
    print(msg, flush=True)


def build_runtime() -> None:
    rt = DIST / "runtime"
    if rt.exists():
        shutil.rmtree(rt)
    rt.mkdir(parents=True)
    with zipfile.ZipFile(EMBED) as z:
        z.extractall(rt)
    (rt / "python313._pth").write_text("python313.zip\n.\nLib\\site-packages\nimport site\n", encoding="ascii")
    dst = rt / "Lib" / "site-packages"
    log(f"复制依赖 {SITE} → {dst}")

    def ignore(d, names):
        top = Path(d) == SITE
        out = set()
        for n in names:
            base = n.split("-")[0].lower()
            if top and (base in SKIP_SITE or n.lower().startswith(("pyinstaller", "pip-"))):
                out.add(n)
        return out
    shutil.copytree(SITE, dst, ignore=ignore)
    (dst / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")


def build_project() -> None:
    dst = DIST / "douyin"
    if dst.exists():
        shutil.rmtree(dst)

    def ignore(d, names):
        rel = Path(d).resolve().relative_to(ROOT)
        out = set()
        for n in names:
            if n in SKIP_PROJECT_DIRS or rel / n in SKIP_PROJECT_PATHS or n.endswith((".bat", ".pyc")):
                out.add(n)
        return out
    log(f"复制项目 {ROOT} → {dst}")
    shutil.copytree(ROOT, dst, ignore=ignore)
    for d in ("uploads", "output", "待上传"):
        (dst / d).mkdir(exist_ok=True)


def make_icon() -> Path:
    """软件图标用 app/icon.ico（抱着音符哼歌的 Claude 小人，app/make_icon.py 生成）；没有时现场画一个。"""
    ico = HERE / "icon.ico"
    if not ico.exists():
        subprocess.run([sys.executable, str(HERE / "make_icon.py")], check=True)
    shutil.copy(ico, TMP / "icon.ico")
    return TMP / "icon.ico"


def build_launcher(icon: Path) -> None:
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
                    "--name", "cc-piano", "--icon", str(icon), "--distpath", str(DIST),
                    "--workpath", str(TMP / "build"), "--specpath", str(TMP), str(HERE / "launcher.py")], check=True)
    (DIST / "douyin" / "app").mkdir(parents=True, exist_ok=True)
    shutil.copy(icon, DIST / "douyin" / "app" / "icon.ico")


def version() -> str:
    return (HERE / "VERSION").read_text(encoding="utf-8").strip()


def build_installer(icon: Path) -> None:
    out = ROOT / "dist" / "installer"
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(ISCC), f"/DSourceDir={DIST}", f"/DOutDir={out}", f"/DIconFile={icon}", f"/DAppVer={version()}",
                    str(HERE / "installer.iss")], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-runtime", action="store_true")
    ap.add_argument("--skip-project", action="store_true")
    ap.add_argument("--no-installer", action="store_true")
    a = ap.parse_args()
    DIST.mkdir(parents=True, exist_ok=True)
    if not a.skip_runtime:
        build_runtime()
    if not a.skip_project:
        build_project()
    icon = make_icon()
    build_launcher(icon)
    size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1e9
    log(f"软件目录：{DIST}（{size:.2f} GB，版本 {version()}）")
    if not a.no_installer:
        build_installer(icon)
        log(f"安装程序：{ROOT / 'dist' / 'installer'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
