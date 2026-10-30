"""音轨剪辑的模板库：模板只存「怎么做」，歌曲 json 只存「做哪首」。

模板文件：tracks/templates/<名称>/v<N>.json，一旦保存就不再修改；改进时另存为下一个版本。
歌曲 json 写 "template": "daw-hook@v2" 引用模板（不写版本号时用最新版），歌曲里写的同名字段优先。
没有 template 字段的旧歌曲 json 原样使用，出片与以前完全相同。

模板字段（都可选，缺省即旧行为）：
  theme / backdrop / grain / fireworks / lyrics / loop / intro / intro_from_library   原有效果
  duration          目标总时长（秒，start 为 "auto" 时选片段用）
  vertical          true：竖屏 1080×1920
  cold_open         true：片段从副歌开头切入（有歌词时）
  snap_beats        true：片段起止吸附到重拍、开头时长取整数小节、转场对齐节拍
  intro_bars        开头占几个小节（snap_beats 时用，默认按 intro 秒数取最接近的整小节）
  fade_in_beats / fade_out_beats   音乐淡入 / 淡出几拍（不写时为旧的 1 秒 / 1.5 秒）
  pulse             重拍时画面推近的幅度，如 0.015
  hook_text         开头 0~3 秒的大字钩子文案（歌曲里也可以写，歌曲优先）
"""
import json
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent / "templates"
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
try:
    import db as _studioDb
except ImportError:
    _studioDb = None


def versions(name: str) -> list[int]:
    d = DIR / name
    return sorted(int(p.stem[1:]) for p in d.glob("v*.json") if p.stem[1:].isdigit()) if d.is_dir() else []


def parse_ref(ref: str) -> tuple[str, int | None]:
    name, _, ver = ref.partition("@")
    return name, int(ver.lstrip("v")) if ver else None


def load(ref: str) -> dict:
    name, ver = parse_ref(ref)
    vs = versions(name)
    if not vs:
        raise FileNotFoundError(f"没有这个模板：{name}")
    ver = ver or vs[-1]
    if ver not in vs:
        raise FileNotFoundError(f"模板 {name} 没有 v{ver}（现有 {', '.join(f'v{v}' for v in vs)}）")
    data = json.loads((DIR / name / f"v{ver}.json").read_text(encoding="utf-8"))
    data.pop("note", None)
    return data


def resolve(song: dict) -> dict:
    """歌曲 json + 它引用的模板 → 实际使用的配置（歌曲字段优先）。"""
    ref = song.get("template")
    if not ref:
        return dict(song)
    return {**load(ref), **song}


def load_song(path: Path) -> dict:
    return resolve(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def listing() -> list[dict]:
    """[{name, versions, latest: {...模板内容, note}}]，给网页的模板下拉框用。"""
    out = []
    for d in sorted(p for p in DIR.iterdir() if p.is_dir()) if DIR.is_dir() else []:
        vs = versions(d.name)
        if vs:
            latest = json.loads((d / f"v{vs[-1]}.json").read_text(encoding="utf-8"))
            out.append({"name": d.name, "versions": vs, "latest": latest})
    return out


def save_new_version(name: str, data: dict) -> int:
    """另存为下一个版本，返回版本号（旧版本永不覆盖）。"""
    if not NAME_RE.match(name):
        raise ValueError("模板名只能用字母、数字、- 和 _")
    vs = versions(name)
    ver = (vs[-1] + 1) if vs else 1
    (DIR / name).mkdir(parents=True, exist_ok=True)
    (DIR / name / f"v{ver}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    if _studioDb:
        try:
            _studioDb.save_template(name, ver, data)
        except Exception:
            pass
    return ver
