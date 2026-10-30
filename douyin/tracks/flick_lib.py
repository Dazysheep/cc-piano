"""拨片开头的图库：图片、顺序、最后停留的主图，以及每张图（专辑）对应的歌曲。

图片放在 flick/library/，顺序和主图记在 flick/library.json：
  {"items": [{"file": "003.jpg", "name": "Patience - TRA$H",
              "songs": [{"title": "Patience", "artist": "TRA$H"}, ...], "song": 0}, ...], "final": "017.jpg"}
导入时播放器截图自动裁出封面，普通图片居中裁成正方形；截图里的歌名、歌手用 Windows OCR 自动认出来（song_ocr.py）。
同一张专辑封面再次导入时不会新增图片，而是把新认出的歌加进这张图的歌曲列表（一张专辑有很多首歌），
name 跟随当前选中的那首（「歌名 - 歌手」）。
"""
import json
from pathlib import Path

import numpy as np
from cover_crop import ALBUM_X0, ALBUM_X1, REF_W, _find_top, crop_cover, is_player_screenshot
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = ROOT / "flick" / "library"
LIB_JSON = ROOT / "flick" / "library.json"
SIZE = 900   # 存储尺寸（够 1080p/竖屏卡片使用）


def load() -> dict:
    if LIB_JSON.exists():
        return json.loads(LIB_JSON.read_text(encoding="utf-8"))
    return {"items": [], "final": None}


def save(lib: dict) -> None:
    """没有手动指定主图（final_pinned）时，主图自动跟随列表最后一张。"""
    files = {it["file"] for it in lib["items"]}
    if not lib.get("final_pinned") or lib.get("final") not in files:
        lib["final"] = lib["items"][-1]["file"] if lib["items"] else None
        lib["final_pinned"] = False
    LIB_JSON.parent.mkdir(parents=True, exist_ok=True)
    LIB_JSON.write_text(json.dumps(lib, ensure_ascii=False, indent=2), encoding="utf-8")


def _fingerprint(img: Image.Image) -> str:
    """缩成 16x16 灰度后按均值二值化，用来判断两张图是否是同一张。"""
    a = np.asarray(img.convert("L").resize((16, 16), Image.BILINEAR), dtype=np.float32)
    return "".join("1" if v else "0" for v in (a > a.mean()).flatten())


def _same(f1: str, f2: str) -> bool:
    return sum(c1 != c2 for c1, c2 in zip(f1, f2)) <= 12


def song_label(s: dict) -> str:
    return " - ".join(x for x in (s.get("title", ""), s.get("artist", "")) if x)


def _songs(it: dict) -> list[dict]:
    """这张图的歌曲列表；旧数据没有列表时，从名称「歌名 - 歌手」拆出第一首。"""
    if it.get("songs"):
        return it["songs"]
    title, _, artist = it.get("name", "").partition(" - ")
    return [{"title": title.strip(), "artist": artist.strip()}] if title.strip() else []


def _recognize(path: Path) -> dict:
    """截图里的歌名、歌手；不是截图或认不出时返回空。"""
    try:
        import song_ocr
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        box = None
        if is_player_screenshot(img):
            k = img.width / REF_W
            side = int((ALBUM_X1 - ALBUM_X0) * k)
            y0 = _find_top(np.asarray(img), k, side)
            box = (int(ALBUM_X0 * k), y0, int(ALBUM_X0 * k) + side, y0 + side)
        return song_ocr.recognize(path, box)
    except Exception:   # noqa: BLE001  OCR 不可用（非 Windows 等）时照常导入
        return {"title": "", "artist": ""}


def add(path: Path, name: str = "") -> dict:
    """导入一张图片（截图或普通图片）。
    返回 {"item":..., "duplicate": bool, "song": 认出的歌或 None, "new_song": bool}。"""
    lib = load()
    cover = crop_cover(path)
    fp = _fingerprint(cover)
    song = _recognize(path)
    song = song if song.get("title") else None
    for it in lib["items"]:
        if it.get("fp") and _same(it["fp"], fp):
            new_song = False
            if song:      # 同一张专辑的另一首歌：加进歌曲列表
                songs = _songs(it)
                if not any(s["title"].lower() == song["title"].lower() for s in songs):
                    songs.append(song)
                    new_song = True
                it["songs"] = songs
                it.setdefault("song", 0)
                save(lib)
            return {"item": it, "duplicate": True, "song": song, "new_song": new_song}
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    used = {it["file"] for it in lib["items"]}
    n = 1
    while f"{n:03d}.jpg" in used or (LIB_DIR / f"{n:03d}.jpg").exists():
        n += 1
    file = f"{n:03d}.jpg"
    cover.resize((SIZE, SIZE), Image.LANCZOS).save(LIB_DIR / file, quality=93)
    item = {"file": file, "name": song_label(song) if song else (name or Path(path).stem), "fp": fp}
    if song:
        item["songs"], item["song"] = [song], 0
    lib["items"].append(item)
    save(lib)
    return {"item": item, "duplicate": False, "song": song, "new_song": bool(song)}


def set_songs(file: str, songs: list[dict], pick: int) -> dict:
    """保存一张图的歌曲列表和选中的那首；名称跟着变成「歌名 - 歌手」。"""
    lib = load()
    it = next((x for x in lib["items"] if x["file"] == file), None)
    if it is None:
        raise ValueError("图库里没有这张图")
    clean = [{"title": str(s.get("title", "")).strip()[:120], "artist": str(s.get("artist", "")).strip()[:120]}
             for s in songs if str(s.get("title", "")).strip()]
    it["songs"] = clean
    it["song"] = min(max(int(pick), 0), len(clean) - 1) if clean else 0
    if clean:
        it["name"] = song_label(clean[it["song"]])
    save(lib)
    return lib


def update(order: list[str], names: dict | None = None, final: str | None = None) -> dict:
    """按给定顺序重排（不在列表里的图片会被移出图库并删除文件），可改名、设主图。"""
    lib = load()
    by_file = {it["file"]: it for it in lib["items"]}
    keep = [by_file[f] for f in order if f in by_file]
    for it in lib["items"]:
        if it["file"] not in order:
            (LIB_DIR / it["file"]).unlink(missing_ok=True)
    for it in keep:
        if names and it["file"] in names:
            it["name"] = names[it["file"]]
    lib["items"] = keep
    if final:
        lib["final"], lib["final_pinned"] = final, True
    save(lib)
    return lib


def sequence(lib: dict | None = None, final: str | None = None) -> tuple[list[Path], Path]:
    """开头要用的图片：(依次滑过的图片, 最后停留的主图)。final：指定图库里哪张当主图（文件名，如 027.jpg），
    不指定时用图库设置的主图。"""
    lib = lib or load()
    if not lib["items"]:
        raise RuntimeError("图库是空的，请先导入图片")
    if final and not any(it["file"] == final for it in lib["items"]):
        final = None                      # 指定的图已经不在图库里：退回图库设置的主图
    final = final or lib.get("final") or lib["items"][-1]["file"]
    others = [LIB_DIR / it["file"] for it in lib["items"] if it["file"] != final]
    return others, LIB_DIR / final
