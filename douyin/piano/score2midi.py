"""五线谱(PDF/图片) → MIDI：Audiveris 光学乐谱识别 + music21 导出。

用法: python piano/score2midi.py 乐谱.pdf [更多页.png ...] --out songs/曲名.mid [--bpm 92]

识别不可能 100% 准确，脚本最后会列出「拍数不对」的小节（多为长音符/连音丢失、谱号切换处读错），
请对照原谱检查这些小节；其余小节一般没问题。Audiveris 解压在 tools/audiveris（不安装到系统）。
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIVERIS = ROOT / "tools" / "audiveris" / "Audiveris" / "Audiveris.exe"


def to_pdf(inputs: list[Path], out: Path) -> Path:
    """把输入统一成一个多页 PDF：网页生成的 PDF 里每页是一张图，先抽出来再合并，保证分辨率。"""
    import pymupdf
    from PIL import Image
    pages = []
    for p in inputs:
        if p.suffix.lower() == ".pdf":
            doc = pymupdf.open(p)
            seen = set()
            for page in doc:
                for img in page.get_images():
                    if img[0] in seen:
                        continue
                    seen.add(img[0])
                    pix = pymupdf.Pixmap(doc, img[0])
                    if pix.width >= 1000:
                        pages.append(Image.frombytes("RGB" if pix.n < 4 else "RGBA", (pix.width, pix.height),
                                                     pix.samples).convert("RGB"))
            if not seen:   # 矢量 PDF：按 250dpi 渲染
                for page in doc:
                    pix = page.get_pixmap(dpi=250)
                    pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        else:
            pages.append(Image.open(p).convert("RGB"))
    if not pages:
        raise RuntimeError("没有找到乐谱页面")
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=250)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="五线谱 PDF/图片 → MIDI")
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bpm", type=float, default=92)
    args = ap.parse_args()
    if not AUDIVERIS.exists():
        print(f"没有找到 Audiveris：{AUDIVERIS}", file=sys.stderr)
        return 1

    from music21 import bar, converter, tempo

    work = Path(tempfile.mkdtemp(dir=ROOT.parent / ".tmp"))
    pdf = to_pdf(args.inputs, work / "score.pdf")
    print(f"识别中（{pdf.name}）…")
    subprocess.run([str(AUDIVERIS), "-batch", "-export", "-output", str(work), str(pdf)],
                   check=True, capture_output=True)
    mxl = next(work.glob("*.mxl"), None)
    if mxl is None:
        print("Audiveris 没有导出乐谱，可能图片太模糊", file=sys.stderr)
        return 1

    s = converter.parse(mxl)
    problems = []
    for pi, part in enumerate(s.parts):
        for m in part.getElementsByClass("Measure"):
            for side in ("leftBarline", "rightBarline"):   # 不完整的反复记号会让导出失败，按不反复处理
                if isinstance(getattr(m, side), bar.Repeat):
                    setattr(m, side, bar.Barline("regular"))
            ts = m.getContextByClass("TimeSignature")
            expect = ts.barDuration.quarterLength if ts else 4
            for v in (m.voices or [m]):
                d = sum(n.quarterLength for n in v.notesAndRests)
                if m.number > 1 and abs(d - expect) > 0.02:
                    problems.append(f"{'右手' if pi == 0 else '左手'} 第 {m.number} 小节（{d:g}/{expect:g} 拍）")
    for el in s.recurse().getElementsByClass(tempo.MetronomeMark):
        el.activeSite.remove(el)
    s.parts[0].measure(1).insert(0, tempo.MetronomeMark(number=args.bpm))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    s.write("midi", fp=str(args.out))
    measures = len(s.parts[0].getElementsByClass("Measure"))
    notes = sum(1 for _ in s.recurse().notes)
    print(f"完成：{args.out}（{measures} 小节，{notes} 个音/和弦）")
    print(f"MusicXML 保留在 {mxl}，可用 MuseScore 打开手动修正")
    if problems:
        print("请对照原谱检查这些小节：\n  " + "\n  ".join(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
