"""生成「音轨剪辑」页面上三套主题的预览图（web/assets/themes/<主题>.jpg）。

用法: python tracks/theme_previews.py <分析目录>   （任一首已分析过的歌，例如 One More Light 的工作目录）
"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import daw  # noqa: E402
import stage  # noqa: E402
import themes  # noqa: E402

LIB = ROOT / "flick" / "library"
DEMO = {"sunset": ("016.jpg", "One More Light", "Linkin Park", False),
        "tech": ("013.jpg", "Faded Light", "PYLOT", True),
        "classical": ("011.jpg", "Sacred Play Secret Place", "Matryoshka", True)}


def main(work: Path) -> None:
    out = ROOT / "web" / "assets" / "themes"
    out.mkdir(parents=True, exist_ok=True)
    t = 14.45
    text = "Night will come soon and swallow everything"
    line = {"start": 12.6, "end": 18.0, "text": text, "zh": "黑夜很快降临，吞没一切",
            "words": [[w, 12.6 + i * 0.45, 13.0 + i * 0.45] for i, w in enumerate(text.split())]}
    for key, (img, title, artist, glass) in DEMO.items():
        th = themes.get(key)
        cover = Image.open(LIB / img) if (LIB / img).exists() else None
        bd = daw.make_backdrop(cover) if glass and cover else None
        v = daw.DawView(work, title, artist, 60.0, theme=key, backdrop=bd, bottom=190)
        band = daw.H - 190
        area = (daw.TL_X, daw.LANE_TOP, daw.W, band)
        v.overlays.append(stage.Fireworks([[14.0, 20.0]], v.beats, th["fireworks"], area))
        vocals = v.env["vocals"].max(axis=1)
        v.overlays.append(stage.Singer([dict(line)], th, vocals, v.rate, v.beats, [[12.0, 20.0]], band))
        im = v.frame(t)
        im.resize((640, 360), Image.LANCZOS).save(out / f"{key}.jpg", quality=88)
        print(key, out / f"{key}.jpg")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
