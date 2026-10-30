"""音轨剪辑画面的主题：日落（One More Light 原版）/ 科技 / 古典。

每个主题给出底色、面板、轨道配色、字体；有背景图（封面虚化）时面板按 glass 透明度做成毛玻璃效果。
歌曲 json 里写 "theme": "sunset" | "tech" | "classical"。
"""
F = "C:/Windows/Fonts/"

THEMES = {
    "sunset": {
        "name": "日落",
        "bg": (20, 12, 16), "panel": (28, 18, 23), "lane_a": (33, 21, 27), "lane_b": (27, 17, 22),
        "ivory": (246, 233, 226), "muted": (184, 154, 154),
        "colors": {"mix": (243, 181, 143), "vocals": (255, 143, 163), "piano": (201, 160, 255),
                   "guitar": (255, 179, 107), "bass": (255, 122, 107), "other": (232, 160, 200)},
        "ruler_bg": (24, 15, 19), "ruler_line": (60, 38, 46), "btn": (80, 56, 64), "meter_bg": (18, 11, 14),
        "bar_tick": (150, 112, 120), "beat_tick": (90, 64, 72), "playhead": (255, 250, 246),
        "ph_glow": (255, 236, 228), "rec": (255, 110, 110), "ink": (10, 6, 8),
        "font_semi": F + "seguisb.ttf", "font_reg": F + "segoeui.ttf", "font_cjk": F + "msyhbd.ttc",
        "font_num": F + "bahnschrift.ttf",
        "lyric_en": F + "segoeuil.ttf", "lyric_zh": F + "msyh.ttc",
        "glass": 0.58,
        "fireworks": [((255, 196, 120), (255, 120, 90)), ((255, 150, 190), (255, 230, 200)),
                      ((200, 160, 255), (255, 200, 240)), ((255, 220, 140), (255, 255, 230))],
    },
    "tech": {
        "name": "科技",
        "bg": (7, 11, 19), "panel": (12, 19, 31), "lane_a": (15, 24, 39), "lane_b": (11, 18, 30),
        "ivory": (226, 241, 255), "muted": (118, 146, 178),
        "colors": {"mix": (84, 204, 255), "vocals": (255, 84, 196), "piano": (150, 124, 255),
                   "guitar": (60, 255, 186), "bass": (255, 204, 64), "other": (112, 168, 255)},
        "ruler_bg": (9, 15, 25), "ruler_line": (34, 62, 92), "btn": (46, 74, 104), "meter_bg": (5, 9, 15),
        "bar_tick": (90, 150, 200), "beat_tick": (40, 70, 100), "playhead": (220, 250, 255),
        "ph_glow": (90, 210, 255), "rec": (255, 70, 120), "ink": (3, 6, 12),
        "font_semi": F + "bahnschrift.ttf", "font_reg": F + "bahnschrift.ttf", "font_cjk": F + "msyhbd.ttc",
        "font_num": F + "consola.ttf",
        "lyric_en": F + "bahnschrift.ttf", "lyric_zh": F + "msyh.ttc",
        "glass": 0.62,
        "fireworks": [((84, 220, 255), (200, 250, 255)), ((255, 84, 200), (255, 190, 240)),
                      ((60, 255, 180), (200, 255, 230)), ((170, 130, 255), (230, 210, 255))],
    },
    "classical": {
        "name": "古典",
        "bg": (17, 14, 11), "panel": (27, 22, 18), "lane_a": (31, 26, 21), "lane_b": (25, 21, 17),
        "ivory": (241, 231, 212), "muted": (172, 152, 124),
        "colors": {"mix": (214, 186, 130), "vocals": (214, 92, 76), "piano": (236, 222, 196),
                   "guitar": (128, 172, 152), "bass": (124, 146, 182), "other": (196, 156, 176)},
        "ruler_bg": (21, 17, 14), "ruler_line": (66, 54, 42), "btn": (92, 76, 60), "meter_bg": (14, 11, 9),
        "bar_tick": (160, 136, 104), "beat_tick": (92, 78, 62), "playhead": (248, 238, 220),
        "ph_glow": (240, 214, 170), "rec": (200, 70, 56), "ink": (12, 10, 8),
        "font_semi": F + "georgiab.ttf", "font_reg": F + "georgia.ttf", "font_cjk": F + "STZHONGS.TTF",
        "font_num": F + "georgia.ttf",
        "lyric_en": F + "georgiai.ttf", "lyric_zh": F + "STZHONGS.TTF",
        "glass": 0.5,
        # 每次烟花换一个色系：金、朱砂、青瓷、黛蓝、藕荷
        "fireworks": [((255, 206, 120), (255, 244, 210)), ((235, 84, 64), (255, 190, 150)),
                      ((110, 220, 180), (220, 255, 240)), ((110, 160, 255), (210, 230, 255)),
                      ((230, 140, 210), (255, 220, 245))],
    },
}


def get(name: str | None) -> dict:
    return THEMES.get(name or "sunset", THEMES["sunset"])
