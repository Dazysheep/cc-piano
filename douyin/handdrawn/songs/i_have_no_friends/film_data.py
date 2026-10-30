"""由剧本 output/writer/i_have_no_friends/lyric_v<N>.json + lyrics_full.json 生成 film_data.js（歌词逐字时间、17 个镜头、转场类型、分层轨道）。

  python handdrawn/songs/i_have_no_friends/film_data.py [剧本版本]
字幕一句两行：英文（逐词时间，词里的字母平均分）+ 网易云页面上的中文翻译（在这句唱的时间里平均分），用「，」分行。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                                           # douyin/
STEM = "i_have_no_friends"
# 进入每一镜的转场（和剧本「转场」一栏对应；film.js 里画）
TR = ["open", "page", "lid", "flash", "mask", "dark", "rain", "bubbles", "rewind", "swing", "crack", "ding", "masks", "torch", "leaf", "confetti", "cable"]


def main(ver: int = 1) -> Path:
    sc = json.loads((ROOT / "output" / "writer" / STEM / f"lyric_v{ver}.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "output" / f"tracks_{STEM}" / "work" / "lyrics_full.json").read_text(encoding="utf-8"))
    lines = []
    for ln in full["lines"]:
        w = []
        for word, (_, s, e) in zip(ln["text"].split(), ln["words"]):
            n = len(word)
            w += [[c, round(s + (e - s) * k / n, 3)] for k, c in enumerate(word)]
        zh = ln["zh"].replace(" ", "")
        w += [[c, round(ln["start"] + (ln["end"] - ln["start"]) * k / len(zh), 3)] for k, c in enumerate(zh)]
        lines.append({"s": ln["start"], "e": ln["end"], "text": f"{ln['text']}，{zh}", "w": w})
    shots = [{"from": s["from"], "to": s["to"], "sub": s["sub_pos"], "zh": n["title"], "tr": TR[i], "lines": s["lines"]}
             for i, (s, n) in enumerate(zip(sc["shots"], sc["key_nodes"]))]
    data = {"dur": full["duration"], "bpm": round(full["tempo"], 2), "beat0": full["beats"][0], "lines": lines, "shots": shots,
            "tracks": ["trans", "subs", "props", "cc", "male", "others", "bg", "vocals", "accomp"],
            "zh": {"male": "人物 · 男孩", "cc": "人物 · CC", "others": "人物 · 路人 / 情侣", "props": "道具（玻璃罐 / 面具 / 雨 / 气泡）"},
            "audio_cuts": [0, shots[8]["from"], shots[16]["from"], full["duration"]], "sub_size": 56}
    out = HERE / "film_data.js"
    out.write_text(f"// 由 film_data.py（剧本 lyric_v{ver}.json + lyrics_full.json）生成，不要手改。\nconst FILM = "
                   + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
