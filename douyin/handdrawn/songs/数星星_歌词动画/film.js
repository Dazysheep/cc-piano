// 《你有多久没有抬起头认真的数过星星》歌词动画 · 全片（场景名 film，268 秒）。
// 镜头表、歌词逐字时间来自 film_data.js（由 lyric_v3.json + lyrics_full.json 生成）；画法 / 小物件 / 15 个关键节点来自 scenes.js（NODEFN）。
// 每个镜头 SHOT[i](lt, d)：lt = 镜头内时间，d = 镜头长度；剪切点前后 0.2 秒画转场（在剪切点正好盖满画面）；字幕按歌词逐字亮起。
// 帧必须是时间的纯函数（渲染会并行、乱序）。

const SH = FILM.shots, LY = FILM.lines, CUT = .2;
const SHOT = [];
const S = (i, fn) => { SHOT[i] = fn; };
const RED = '#C0504D';
function withCam(cx, cy, z, draw) { camBegin(cx, cy, z); draw(); camEnd(); }
function camMove(a, b, k, draw) { withCam(lerp(a[0], b[0], k), lerp(a[1], b[1], k), lerp(a[2], b[2], k), draw); }
const K = (lt, d) => ease(clamp(lt / Math.max(d, .01)));
function me(x, y, u, o = {}) { clawd(x, y, u, { draw: backpack(RED), ...o }); }      // 主角男生 CC（红书包）
function girl(x, y, u, o = {}) { clawdGirl(x, y, u, o); }
function ground(y, col, col2) { paint(rectPts(-40, y, W + 80, H - y + 60, 3), { wash: col, fill: col2 || shade(col, .15), fillOp: 70, ink: null }); }
function bubble(x, y, w, h, txt, size = 32, col = PAL.cream) { return tagged('props', () => bubbleRaw(x, y, w, h, txt, size, col)); }
function bubbleRaw(x, y, w, h, txt, size = 32, col = PAL.cream) {
  paint(rrPts(x - w / 2, y - h / 2, w, h, h / 2.4), { wash: col, ink: PAL.ink, sw: .8 });
  paint([[x - 16, y + h / 2 - 2], [x + 6, y + h / 2 - 2], [x - 20, y + h / 2 + 22]], { wash: col, ink: null });
  if (txt) letter(txt, x, y + 2, size, PAL.ink, { ink: false, font: HAND(size) });
}
function car(x, y, s, col) {
  push(); translate(x, y); scale(s);
  paint(rrPts(-150, -90, 300, 70, 20), { wash: col, ink: PAL.ink, sw: .9 }); paint(rrPts(-90, -140, 170, 60, 18), { wash: col, ink: PAL.ink, sw: .9 });
  paint(rectPts(-70, -128, 60, 40, 2), { wash: '#BFE0E6', ink: PAL.ink, sw: .5 }); paint(rectPts(0, -128, 60, 40, 2), { wash: '#BFE0E6', ink: PAL.ink, sw: .5 });
  for (const wx of [-90, 90]) paint(ellPts(wx, -20, 30, 30, 14), { wash: '#2B2233', ink: PAL.ink, sw: .6 });
  pop();
}
function building(x, y, w, h, col, label, lit = .35, seed = 1) {
  paint(rectPts(x, y - h, w, h, 3), { wash: col, fill: shade(col, .15), fillOp: 60, ink: PAL.ink, sw: 1 });
  for (let i = 0; i < Math.floor(w / 70); i++) for (let j = 0; j < Math.floor((h - 90) / 80); j++)
    paint(rectPts(x + 20 + i * 70, y - h + 90 + j * 80, 40, 46, 1.5), { wash: hash(seed * 13 + i * 7 + j) < lit ? '#FFD27A' : '#BFD9E6', ink: PAL.ink, sw: .4 });
  if (label) board(label, x + w / 2, y - h + 45, Math.min(w - 30, 260), 54, '#2F4F8F', PAL.cream, 30);
}
function nightCity(skyA, skyB, haze = '#6B4E7E', seed = 0) {
  bg(skyA, skyB); paint(ellPts(960, 220, 900, 240, 24), { fill: haze, fillOp: 60, bleed: .35, ink: null });
  tower(-20, 300, 760, '#2F2A44', 1 + seed, .3, C.neon1); tower(280, 240, 560, '#352E4C', 2 + seed, .35);
  tower(1380, 280, 700, '#2F2A44', 3 + seed, .3, C.neon2); tower(1660, 300, 820, '#3A3252', 4 + seed, .35, C.neon3);
}
function blobs(n, t, seed, y0 = 500, y1 = 1000, op = 90) {       // 糊成色块的人群
  for (let i = 0; i < n; i++) { const x = (hash(seed + i) * 2200 + t * 60 * (hash(i + 3) - .5)) % 2100 - 90, y = lerp(y0, y1, hash(seed + i * 5));
    paint(ellPts(x, y, 70 + 40 * hash(i), 90 + 30 * hash(i + 1), 14), { fill: PEOPLE[i % 8], fillOp: op, bleed: .4, ink: null }); }
}
function windLines(t, n = 6, col = '#E8EEF5', y0 = 200) { for (let i = 0; i < n; i++) { const x = ((t * 900 + i * 400) % 2400) - 300, y = y0 + i * 90 + 30 * Math.sin(t + i);
  inkLine([[x, y], [x + 160, y - 20], [x + 320, y + 10]], 1, col, 'dry', .6); } }
function notes(x, y, t, n = 4, col = PAL.ink) { for (let i = 0; i < n; i++) { const k = (t * .6 + i / n) % 1; letter(i % 2 ? '♪' : '♫', x + 60 * Math.sin(i * 2 + t) + i * 30, y - k * 260, 44, col, { ink: false, alpha: 1 - k }); } }
function stars(n, t, seed, k = 1, y0 = 40, y1 = 560) { for (let i = 0; i < n; i++) starAt(hash(seed + i * 3) * W, lerp(y0, y1, hash(seed + i * 5 + 1)), 5 + 11 * Math.pow(hash(i * 11 + seed), 2), t, i, k); }
function sepia() { bg(C.sepia, '#DDBB86', 150); for (let i = 0; i < 16; i++) paint(ellPts(hash(i) * W, hash(i + 3) * H, 60 + 80 * hash(i + 5), 40 + 60 * hash(i + 7), 12), { fill: C.sepiaDk, fillOp: 26, bleed: .3, ink: null }); }
function dayStreet(seed = 0, base = 900, sky = '#DCE6EE') {      // 白天街景：远处的楼、云、树、路灯
  for (let i = 0; i < 3; i++) paint(ellPts(200 + i * 650 + 80 * hash(seed + i), 140 + 40 * hash(seed + i + 2), 140, 50, 14), { wash: PAL.cream, ink: PAL.ink, sw: .5 });
  for (let i = 0; i < 7; i++) { const w = 160 + 120 * hash(seed + i * 3), h = 220 + 260 * hash(seed + i * 5);
    paint(rectPts(i * 290 - 60, base - h, w, h, 2), { wash: mixCol(sky, '#8C9AAE', .45), fill: mixCol(sky, '#7A889E', .5), fillOp: 50, ink: mixCol(sky, PAL.ink, .5), sw: .6 });
    for (let j = 0; j < 4; j++) paint(rectPts(i * 290 - 30 + (j % 2) * 60, base - h + 40 + Math.floor(j / 2) * 70, 30, 34, 1), { wash: mixCol(sky, '#FFFFFF', .4), ink: null }); }
  tree(140, base, .8); tree(1800, base, .9, '#7FAE6A');
  inkLine([[1640, base], [1640, base - 380], [1700, base - 400]], 1.6, '#555', 'ink', .2); paint(ellPts(1704, base - 396, 16, 10, 10), { wash: '#EEE', ink: PAL.ink, sw: .5 });
}
function indoor(wall = '#EADFC8', seed = 0) {                     // 室内：窗、书架、绿植、海报
  bg(wall, shade(wall, .08), 100);
  windowFrame(1380, 140, 400, 330, '#BFE0F2', (x, y, w, h) => { paint(ellPts(x + 300, y + 80, 34, 34, 12), { wash: '#FFE08A', ink: PAL.ink, sw: .5 }); tree(x + 120, y + h, .6); });
  paint(rectPts(120, 220, 360, 22, 1), { wash: C.wood, ink: PAL.ink, sw: .6 }); paint(rectPts(120, 360, 360, 22, 1), { wash: C.wood, ink: PAL.ink, sw: .6 });
  for (let i = 0; i < 9; i++) paint(rectPts(130 + i * 38, 220 - 70 - 30 * hash(seed + i), 30, 70 + 30 * hash(seed + i), 1), { wash: PEOPLE[(i + seed) % 8], ink: PAL.ink, sw: .4 });
  for (let i = 0; i < 6; i++) paint(rectPts(140 + i * 52, 360 - 90, 40, 90, 1), { wash: PEOPLE[(i + seed + 3) % 8], ink: PAL.ink, sw: .4 });
  plant(1820, 900, 1.2); poster(700, 180, 220, 160, PAL.cream, (x, y) => letter(['加油', '梦想', '2024', '晴天'][seed % 4], x + 110, y + 85, 40, PAL.ink, { ink: false, font: HAND(40) }));
}
function stair(y) { for (let i = 0; i < 4; i++) paint(rectPts(-40, y + i * 50, W + 80, 50, 2), { wash: mixCol('#C9BDA3', '#A89A80', i / 4), ink: PAL.ink, sw: .6 }); }

// ================================================================ 镜头（编号 = 镜头表顺序；注释是这一镜唱到的歌词）
// 0 前奏：白纸上铅笔画出地平线和楼，片名写出来，CC 低头看着手机从纸边走进来，纸飞机第一次出现
S(0, (lt, d) => {
  bg('#F3EBDC', '#E9DFC8', 60);
  const draw = clamp(lt / 4);
  inkLine([[0, 860], [W * draw, 860]], 1.4, '#8C7B66', 'HB', 0);
  [[160, 220, 300], [420, 160, 220], [1300, 200, 340], [1560, 240, 260]].forEach(([x, w, h], i) => {
    const k = clamp((lt - 4 - i * .9) / 1.6); if (k <= 0) return;
    paint(rectPts(x, 860 - h * k, w, h * k, 2), { ink: '#8C7B66', sw: .8 });
    for (let j = 0; j < 3 * k; j++) inkLine([[x + 20, 860 - h * k + 40 + j * 60], [x + w - 20, 860 - h * k + 40 + j * 60]], .5, '#B8AA90', 'HB', 0);
  });
  const tk = clamp((lt - 3) / 2.5) * (1 - clamp((lt - 15.5) / 1.5));
  if (tk > 0) { letter('你有多久没有抬起头', 960, 380, 92, PAL.ink, { ink: false, font: HAND(92), alpha: tk }); letter('认真的数过星星', 960, 500, 92, PAL.ink, { ink: false, font: HAND(92), alpha: tk });
    letter('圣代 / 石玺彤', 960, 610, 40, '#8C7B66', { ink: false, font: HAND(40), alpha: tk }); }
  const wk = clamp((lt - 9) / 8);
  if (wk > 0) me(lerp(-120, 960, wk), 860, 30, { walk: lt * 1.6, eyes: 'look', lookY: 1, mouth: 'flat', aR: .9, armR: phone(1) });
  if (lt > 11) paperPlane(lerp(1900, 1040, clamp((lt - 11) / 6)), lerp(200, 820, clamp((lt - 11) / 6)) + 30 * Math.sin(lt * 2), .8, .35);
});
// 1 早高峰的地铁今天又有多少人没赶上
S(1, (lt, d) => camMove([960, 600, 1], [960, 640, 1.08], K(lt, d), () => NODEFN.node_01(lt)));
// 2 车厢一如既往争吵和拥挤
S(2, (lt, d) => { camMove([960, 760, 1.5], [940, 780, 1.6], K(lt, d), () => NODEFN.node_01(lt + 3));
  emote('anger', 560, 620, 30, 1); emote('anger', 1380, 600, 30, 1); emote('sweat', 1100, 520, 30, 1);
  bubble(470, 420, 170, 80, '让让!', 34); bubble(1460, 400, 170, 80, '挤什么', 30); });
// 3 沿途到达每一站的停靠时间短暂
S(3, (lt, d) => {
  bg('#4E566B', '#3A4154');
  const gap = 30 + 40 * Math.sin(clamp(lt / d) * Math.PI);
  paint(rectPts(960 - gap / 2, 120, gap, 860, 2), { wash: '#FFF3D0', fill: '#FFE3A0', fillOp: 150, bleed: .2, ink: null });
  for (const s of [-1, 1]) { const x = s < 0 ? 200 : 960 + gap / 2; paint(rectPts(x, 120, 760 - gap / 2, 860, 3), { wash: '#B9C2CF', fill: '#8F99A8', fillOp: 70, ink: PAL.ink, sw: 1.2 });
    paint(rrPts(x + 160, 260, 440, 300, 20), { wash: '#2B3048', ink: PAL.ink, sw: .8 }); }
  withCam(960, 540, 1, () => me(560, 560, 22, { eyes: 'look', lookY: lt < d / 2 ? -.6 : 1, mouth: 'flat', aR: .9, armR: phone(1), noLegs: true }));
  clock(1720, 180, 70, 7, 59);
  inkLine([[1720, 180], [1720 + 60 * Math.cos(lt * 6 - 1.57), 180 + 60 * Math.sin(lt * 6 - 1.57)]], 1, '#C8323C', 'ink', 0);
});
// 4 人潮里面声音来自天南和地北
S(4, (lt, d) => { camMove([960, 640, 1.05], [960, 560, 1.12], K(lt, d), () => NODEFN.node_01(lt + 1));
  ['吃了吗', '侬好', '咋整', '巴适', '雷猴', '得劲', '中不中'].forEach((s, i) => { const k = (lt * .35 + i / 7) % 1;
    bubble(200 + i * 250, 820 - k * 560, 150, 70, s, 30, PEOPLE[i]); }); });
// 5 他们大多数要去的目的地是公司还有学校
S(5, (lt, d) => {
  bg('#E9E2D2', '#D9CDB4'); ground(860, '#C9BDA3');
  building(120, 860, 520, 600, '#BFD0E0', '公 司', .4, 3); building(1280, 860, 520, 520, '#F2D6A2', '学 校', .3, 5);
  paint([[960, 860], [700, 1080], [1220, 1080]], { wash: '#B8AE9E', ink: null });
  for (const s of [-1, 1]) inkLine([[960, 980], [960 + s * 360, 900], [960 + s * 320, 880]], 3, PAL.ink, 'ink', .3);
  [0, 1, 2].forEach(i => person(820 - i * 150 - lt * 60, 1000, 22, i + 1, lt, { walk: lt * 2, flip: true }));
  [0, 1, 2].forEach(i => person(1100 + i * 150 + lt * 60, 1000, 22, i + 4, lt, { walk: lt * 2, draw: backpack(PEOPLE[i + 2]) }));
  me(960, 1010, 30, { eyes: 'look', lookX: Math.sin(lt * 2), mouth: 'flat', emote: '?', emoteK: 1 });
});
// 6 车门打开就会各奔东西
S(6, (lt, d) => NODEFN.node_02(lt));
// 7 有的为了工资
S(7, (lt, d) => {
  bg('#DCE6EE', '#C2D2DE'); dayStreet(7); building(1100, 900, 700, 760, '#BFD0E0', '公 司', .45, 9); ground(900, '#B8AE9E');
  person(700 + lt * 300, 1000, 30, 3, lt, { walk: lt * 3, aR: 1.2, armR: (u, sw) => { paint(rectPts(-.2 * u, -1.6 * u, 2.2 * u, 1.5 * u, 2), { wash: '#E8D9A8', ink: PAL.ink, sw: sw * .6 }); letter('工资', 0, 0, 20, PAL.ink, { ink: false, font: HAND(20) }); } });
  me(260, 1010, 26, { eyes: 'look', lookX: 1, mouth: 'o' });
});
// 8 有的为了学会答题的诀窍
S(8, (lt, d) => {
  bg('#F6E7C8', '#EBD2A4'); dayStreet(11, 900, '#F6E7C8'); building(120, 900, 640, 640, '#F2D6A2', '学 校', .3, 11); ground(900, '#C9B28A');
  person(1000 - lt * 260, 1000, 26, 5, lt, { walk: lt * 3, flip: true, aL: 1.3, draw: backpack('#2F6F5A'),
    armL: (u, sw) => { paint(rectPts(-.4 * u, -2.4 * u, 2 * u, 2.6 * u, 2), { wash: PAL.cream, ink: PAL.ink, sw: sw * .6 }); for (let i = 0; i < 4; i++) paint(ellPts(.2 * u + (i % 2) * .8 * u, -1.8 * u + Math.floor(i / 2) * .9 * u, .25 * u, .25 * u, 8), { ink: PAL.ink, sw: sw * .4 }); } });
  person(1500 + lt * 120, 1000, 26, 2, lt, { walk: lt * 3, armR: bag('#5E4A3A') });
  me(1240, 1010, 30, { eyes: 'look', lookX: Math.sin(lt * 4), mouth: 'wobble', sq: .06 * Math.sin(lt * 8) });
});
// 9 尽管累但从没感到空虚
S(9, (lt, d) => { bg('#C9C2D6', '#B3AAC4'); blobs(14, lt, 3, 300, 1000, 70);
  paint(ellPts(960, 820, 160 + 30 * Math.sin(lt * 4), 140, 18), { fill: '#FFC27A', fillOp: 110, bleed: .3, ink: null });
  me(960, 1100, 62, { eyes: 'closed', mouth: 'o', emote: 'sweat', emoteK: 1, aL: -.4, aR: -.4, noShadow: true });
  paint(ellPts(960, 860, 40 + 8 * Math.sin(lt * 5), 40 + 8 * Math.sin(lt * 5), 14), { wash: '#FFD06B', fill: '#FF9A4D', fillOp: 80, ink: null }); });
// 10 有的赚钱买了新车和新房
S(10, (lt, d) => {
  bg('#E8DFCF', '#D8CBB4'); ground(880, '#B8AE9E');
  paint(rectPts(160, 220, 1600, 640, 3), { wash: '#BFE0E6', fill: '#9FCAD3', fillOp: 60, ink: PAL.ink, sw: 1.2 });            // 橱窗
  board('新 楼 盘', 520, 300, 260, 64, '#C8323C', PAL.cream, 36);
  [[400, 640, 160, 220], [620, 600, 200, 260]].forEach(([x, y, w, h]) => { paint(rectPts(x, y - h + 140, w, h, 2), { wash: '#F2D6A2', ink: PAL.ink, sw: .7 }); paint([[x - 10, y - h + 140], [x + w / 2, y - h + 60], [x + w + 10, y - h + 140]], { wash: '#C8603C', ink: PAL.ink, sw: .7 }); });
  car(lerp(2100, -300, K(lt, d)), 980, 1, '#E8473C');
  me(1380, 860, 28, { eyes: 'look', lookX: -.6, mouth: 'o', aL: 1.6, aR: 1.6, noShadow: true });
  me(1380, 520, 14, { col: '#B7D3E0', dk: '#9FBFCE', lt: '#D8EAF2', eyes: 'look', mouth: 'o', noShadow: true, draw: null });      // 玻璃里小小的自己
});
// 11 娶了别人来不及羡慕的新娘
S(11, (lt, d) => {
  bg('#F6E1E6', '#EBC7CF'); paint([[760, 1100], [1160, 1100], [1040, 600], [880, 600]], { wash: '#C8323C', fill: '#9E2430', fillOp: 70, ink: PAL.ink, sw: .9 });
  for (let i = 0; i < 18; i++) { const x = hash(i) * W, y = ((lt * 140 + hash(i + 4) * 1100) % 1100) - 20; paint(ellPts(x, y, 12, 8, 10, 0, lt * 2 + i), { wash: i % 2 ? PAL.rose : '#FFD3E0', ink: PAL.ink, sw: .3 }); }
  person(900, 760, 26, 0, lt, { col: '#7FA7D9', eyes: 'happy', mouth: 'smile', draw: (u, sw) => paint(rrPts(-1 * u, -2.4 * u, 2 * u, .8 * u, .3 * u), { wash: PAL.ink, ink: null }) });
  person(1060, 760, 26, 7, lt, { col: '#FFF5F7', eyes: 'happy', mouth: 'smile', blush: true, draw: (u, sw) => paint([[-5 * u, -8 * u], [5 * u, -8 * u], [6 * u, -1 * u], [-6 * u, -1 * u]], { wash: '#FFFFFF', washOp: 140, ink: PAL.ink, sw: sw * .4 }) });
  [300, 450, 1450, 1620].forEach((x, i) => person(x, 1000, 24, i + 2, lt, { aL: 1.4, aR: 1.4, eyes: 'happy', mouth: 'grin' }));
  me(1750, 960, 22, { dy: -.6 - .3 * Math.abs(Math.sin(lt * 5)), eyes: 'look', lookX: -1, mouth: 'o' });
});
// 12 有的却连普通工作都差点没了指望
S(12, (lt, d) => {
  bg('#AEB6C2', '#98A1B0'); dayStreet(13, 900, '#AEB6C2'); building(200, 900, 760, 800, '#8F9BAE', '公 司', .25, 13); ground(900, '#8E8F98');
  paint(ellPts(1240, 380, 170, 80, 16), { wash: '#4A4660', fill: '#2E2A40', fillOp: 90, ink: PAL.ink, sw: .6 });
  for (let i = 0; i < 8; i++) { const y = 460 + ((lt * 400 + i * 60) % 220); inkLine([[1150 + i * 24, y], [1144 + i * 24, y + 20]], .6, '#9FB2CC', 'inkfine', 0); }
  person(1240, 900, 30, 6, lt, { eyes: 'look', lookY: 1, mouth: 'wobble', aL: .9, aR: .9, armR: (u, sw) => paint(rectPts(-2.4 * u, -1.4 * u, 3 * u, 2.2 * u, 2), { wash: '#C9A06C', ink: PAL.ink, sw: sw * .7 }) });
  me(1700, 1000, 22, { eyes: 'look', lookX: -1, mouth: 'flat' });
});
// 13 也逐渐成了别人口中厌恶的对象
S(13, (lt, d) => camMove([960, 540, 1], [1000, 560, 1.06], K(lt, d), () => NODEFN.node_03(lt)));
// 14 有的人是家里面的骄傲
S(14, (lt, d) => {
  bg('#FFF1D6', '#F6DDB0');
  board('恭喜考了第一名!', 900, 200, 600, 90, '#C8323C', PAL.cream, 48);
  for (let i = 0; i < 26; i++) { const x = hash(i * 3) * W, y = ((lt * 220 + hash(i) * 900) % 900); paint(rectPts(x, y, 14, 24, 1), { wash: PEOPLE[i % 8], ink: null }); }
  person(760, 900, 30, 3, lt, { aL: 1.5, aR: 1.5, eyes: 'happy', mouth: 'grin' }); person(1060, 900, 30, 1, lt, { aL: 1.5, aR: 1.5, eyes: 'happy', mouth: 'grin' });
  person(910, 620 - 30 * Math.abs(Math.sin(lt * 4)), 22, 5, lt, { aL: 1.6, aR: 1.6, eyes: 'happy', mouth: 'grin', emote: 'spark', emoteK: 1 });
  me(1640, 960, 24, { eyes: 'look', lookX: -1, mouth: 'flat', aL: -.4, aR: -.4 });
});
// 15 拼命上着补习班要蝉联班级里的第一名
S(15, (lt, d) => {
  bg('#2A2A45', '#1E1E36'); ground(940, '#1F1F30');
  paint(rectPts(240, 160, 1100, 700, 3), { wash: '#FFE3A0', fill: '#F2C77A', fillOp: 90, ink: PAL.ink, sw: 1.4 });           // 亮着的补习班窗
  for (let i = 0; i < 6; i++) poster(280 + i * 170, 190, 140, 110, '#FFF6E4', (x, y) => letter('第一名', x + 70, y + 60, 26, '#C8323C', { ink: false, font: HAND(26) }));
  paint(rectPts(340, 640, 900, 40, 2), { wash: C.wood, ink: PAL.ink, sw: .8 });
  person(760, 650, 30, 5, lt, { eyes: 'narrow', mouth: 'flat', aL: .9, aR: .9 + .2 * Math.sin(lt * 10), noShadow: true });
  for (let i = 0; i < 4; i++) paint(rectPts(560 + i * 40, 600 - i * 8, 110, 40, 1), { wash: PAL.cream, ink: PAL.ink, sw: .5 });
  inkLine([[240, 510], [1340, 510]], 1.4, PAL.ink, 'ink', 0); inkLine([[790, 160], [790, 860]], 1.4, PAL.ink, 'ink', 0);
  me(1560, 950, 28, { eyes: 'look', lookX: -1, lookY: -.4, mouth: 'o', aL: 1.2 });
});
// 16 有人却在大把挥霍着钞票
S(16, (lt, d) => {
  bg('#E6F0DE', '#CFE2C2'); dayStreet(16, 900, '#E6F0DE'); ground(900, '#B8C9A8');
  for (let i = 0; i < 34; i++) { const x = hash(i * 7) * W + 40 * Math.sin(lt * 2 + i), y = ((lt * 180 + hash(i) * 1100) % 1100) - 40;
    push(); translate(x, y); rotate(lt * 2 + i); paint(rectPts(-36, -18, 72, 36, 1), { wash: '#9BC48B', ink: PAL.ink, sw: .5 }); pop(); letter('¥', x, y, 22, '#3E6B4A', { ink: false }); }
  person(560, 900, 34, 3, lt, { eyes: 'happy', mouth: 'grin', aL: 1.6 + .3 * Math.sin(lt * 6), aR: 1.6 - .3 * Math.sin(lt * 6), draw: (u, sw) => paint(rectPts(-4 * u, -9.2 * u, 8 * u, 1.2 * u, 2), { wash: '#F2C53D', ink: PAL.ink, sw: sw * .5 }) });
  me(1420, 960, 30, { eyes: 'look', lookY: -1, mouth: 'o', aR: 1.5, aL: .2 });
});
// 17 他说都不喜欢只想晋级赛能够继续赢
S(17, (lt, d) => {
  bg('#20203A', '#16162A');
  paint(rectPts(560, 240, 800, 470, 3), { wash: '#2B3048', ink: PAL.ink, sw: 1.2 }); paint(rectPts(590, 270, 740, 410, 2), { wash: mixCol('#3ED6E8', '#FF5C8A', .5 + .5 * Math.sin(lt * 6)), washOp: 200, ink: null });
  letter('晋级赛  3 : 2', 960, 470, 64, PAL.cream, { ink: false, font: HAND(64) });
  paint(ellPts(960, 820, 700, 260, 22), { fill: '#3ED6E8', fillOp: 40, bleed: .35, ink: null });
  person(800, 1000, 32, 1, lt, { eyes: 'spark', mouth: 'grin', aL: .8, aR: .8, noShadow: true });
  me(1180, 1000, 30, { eyes: 'look', lookX: -.6, mouth: 'flat', emote: '?', emoteK: 1, noShadow: true });
});
// 18 我们总是被人不停做着对比
S(18, (lt, d) => {
  indoor('#EDE7DC', 1); ground(920, '#C9BDA3');
  for (let i = 0; i < 12; i++) inkLine([[120, 360 + i * 40], [180, 360 + i * 40]], .8, PAL.ink, 'inkfine', 0);
  const xs = [360, 640, 960, 1280, 1560]; xs.forEach((x, i) => i === 2 ? me(x, 930, 26, { eyes: 'look', lookY: -1, mouth: 'wobble' }) : person(x, 930, 22 + 8 * hash(i + 2), i, lt, { dy: -.5 * hash(i) }));
  const rx = lerp(260, 1660, (Math.sin(lt * 2) + 1) / 2); paint(rectPts(rx - 20, 280, 40, 520, 2), { wash: '#F2C53D', ink: PAL.ink, sw: .8 });
  for (let i = 0; i < 10; i++) inkLine([[rx - 20, 300 + i * 50], [rx, 300 + i * 50]], .6, PAL.ink, 'inkfine', 0);
  letter('比一比', rx, 250, 40, '#C8323C', { ink: false, font: HAND(40) });
});
// 19 总是在和别人谈心时依赖上了酒精
S(19, (lt, d) => {
  bg('#3A3550', '#2A2640'); paint(rectPts(260, 820, 1400, 50, 2), { wash: C.wood, fill: C.woodDk, fillOp: 80, ink: PAL.ink, sw: 1 });
  paint(rrPts(1040, 690, 90, 130, 14), { wash: '#BFD9E6', washOp: 170, ink: PAL.ink, sw: .8 });
  for (let i = 0; i < 3; i++) { const k = (lt * .4 + i / 3) % 1; paint(ellPts(1085 + 50 * Math.sin(i + lt), 640 - k * 380, 50 + 90 * k, 30 + 50 * k, 16), { wash: '#4A4660', washOp: 210 * (1 - k * .5), fill: '#2E2A40', fillOp: 90, ink: PAL.ink, sw: .5 }); }
  me(820, 830, 34, { eyes: 'narrow', mouth: 'flat', aL: .4, aR: .9, noShadow: true });
  ['要合群', '跟上', '别想太多', '喝一个'].forEach((s, i) => { const a = i / 4 * TAU + lt * .6; bubble(820 + Math.cos(a) * 360, 460 + Math.sin(a) * 140, 170, 70, s, 28); });
});
// 20 总是点燃烦心事抽进肺里
S(20, (lt, d) => camMove([960, 560, 1.05], [1100, 460, 1.25], K(lt, d), () => NODEFN.node_04(lt)));
// 21 总是被人反复叮嘱着要跟上队形
S(21, (lt, d) => {
  bg('#DCE3EA', '#C6D0DB'); dayStreet(21, 900, '#DCE3EA'); ground(900, '#AFB8C4');
  board('跟 上 →', 1500, 300, 300, 90, '#E8473C', PAL.cream, 50);
  for (let i = 0; i < 6; i++) person(1500 - i * 190, 980, 22, i, lt, { ...move('run', lt * 1.4), flip: false, eyes: 'narrow' });
  me(260, 990, 24, { ...move('run', lt * .9), eyes: 'closed', mouth: 'O', emote: 'sweat', emoteK: 1 });
  for (let i = 0; i < 3; i++) inkLine([[160 - i * 30, 860 + i * 30], [80 - i * 30, 860 + i * 30]], 1, PAL.ink, 'dry', 0);
});
// 22 可究竟什么时候我们才能停止奔跑
S(22, (lt, d) => NODEFN.node_05(lt * .9));
// 23 停止那些没所谓的针锋相对
S(23, (lt, d) => {
  bg('#EDE2D2', '#DDCCB4'); dayStreet(23, 900, '#EDE2D2'); ground(900, '#C9B28A');
  const apart = ease(clamp((lt - .5) / 1));
  person(820 - 160 * apart, 960, 28, 1, lt, { eyes: 'angry', mouth: 'flat', rot: .2 * (1 - apart), flip: false });
  person(1100 + 160 * apart, 960, 28, 5, lt, { eyes: 'angry', mouth: 'flat', rot: -.2 * (1 - apart), flip: true });
  if (apart < .6) for (let i = 0; i < 6; i++) { const a = i / 6 * TAU + lt * 8; paint(starPts(960 + Math.cos(a) * 60, 700 + Math.sin(a) * 50, 18, .4, 4), { wash: '#FFC24B', ink: PAL.ink, sw: .4 }); }
  me(960, 980, 30, { aL: lerp(.2, 1.1, apart), aR: lerp(.2, 1.1, apart), eyes: 'narrow', mouth: 'flat' });
});
// 24 或许你也真的不需要比别人过得更好
S(24, (lt, d) => {
  bg('#F3E3C6', '#E6CFA6'); dayStreet(24, 760, '#F3E3C6'); stair(760);
  me(760, 790, 28, { eyes: 'look', lookY: 1, mouth: 'flat', noLegs: true }); me(1160, 790, 28, { eyes: 'look', lookY: -1, mouth: 'smile', noLegs: true });
  const lx = 960 + 40 * Math.sin(lt * 2), ly = lerp(300, 760, K(lt, d)); push(); translate(lx, ly); rotate(lt * 1.5);
  paint(ellPts(0, 0, 34, 16, 12), { wash: '#E8A55A', fill: '#C8742E', fillOp: 80, ink: PAL.ink, sw: .6 }); pop();
  paperPlane(1500, 760, .5, -.1);
});
// 25 窗外的景色才弥足珍贵
S(25, (lt, d) => {
  bg('#EAE0CC', '#D9CBAF');
  camMove([960, 540, 1], [960, 460, 1.18], K(lt, d), () => {
    windowFrame(460, 160, 1000, 600, '#BFE0F2', (x, y, w, h) => { for (let i = 0; i < 3; i++) paint(ellPts(x + 200 + i * 300, y + 120 + 30 * i, 120, 50, 14), { wash: PAL.cream, ink: PAL.ink, sw: .5 });
      tree(x + 260, y + h, .9); tree(x + 720, y + h, 1.1, '#7FAE6A'); paint(rectPts(x, y + h - 60, w, 60, 1), { wash: '#9BC48B', ink: null }); });
    for (let i = 0; i < 4; i++) paint([[460 + i * 260, 160], [300 + i * 300, 1080], [420 + i * 300, 1080]], { fill: '#FFF6D6', fillOp: 40, bleed: .2, ink: null });
    me(960, 1000, 34, { eyes: 'look', lookY: -.5, mouth: 'o', aL: .4, aR: .4 });
  });
});
// 26 副歌 1 · 你有多久没有抬起头，认真地数过星星（城市里只有霓虹，没有星）
S(26, (lt, d) => camMove([960, 640, 1.12], [960, 540, 1], K(lt, d), () => NODEFN.node_06(lt)));
// 27 多久没有抬起头，看清眼前的风景（玻璃幕墙里一闪而过的小时候）
S(27, (lt, d) => {
  bg('#5A6A86', '#47566F');
  for (let i = 0; i < 6; i++) paint(rectPts(80 + i * 300, 80, 290, 900, 2), { wash: '#7F93B2', fill: '#A9BDD6', fillOp: 70 + 30 * Math.sin(i + lt), tex: .5, ink: PAL.ink, sw: .9 });
  for (let i = 0; i < 6; i++) inkLine([[120 + i * 300, 120], [300 + i * 300, 400]], .8, '#E8EEF5', 'dry', 0);
  const flash = Math.max(0, Math.sin(lt * 1.6)); if (flash > .2) { clawd(1180, 760, 16, { eyes: 'spark', mouth: 'grin', noShadow: true, col: '#F2A283', aL: 1.3 }); paperPlane(1260, 560, .45, -.3); }
  me(760, 1000, 32, { eyes: 'look', lookX: .8, mouth: 'flat', aR: .6, armR: phone(.6) });
});
// 28 多久没有抬起头，找寻最初的自己（人群糊成色块，只有他清楚）
S(28, (lt, d) => { bg('#4B4466', '#3A3452'); blobs(22, lt * 3, 11, 200, 1050, 110); me(960, 960, 34, { eyes: 'look', lookY: -.3, mouth: 'flat', aL: -.3, aR: -.3 }); });
// 29 多久没有抬起头，去倾听风的声音（天桥上闭眼听风，落叶变成音符）
S(29, (lt, d) => {
  nightCity('#2A2245', '#43365F', '#6B4E7E', 5);
  paint(rectPts(-40, 820, W + 80, 60, 2), { wash: '#5A5470', ink: PAL.ink, sw: 1 }); for (let i = 0; i < 20; i++) inkLine([[i * 100, 720], [i * 100, 820]], 1, '#8A84A0', 'ink', 0); inkLine([[-40, 720], [W + 40, 720]], 2, '#8A84A0', 'ink', 0);
  windLines(lt, 6, '#C9C2E6', 200);
  for (let i = 0; i < 6; i++) { const x = ((lt * 300 + i * 340) % 2200) - 140, y = 300 + 80 * Math.sin(lt * 2 + i); letter(lt % 2 > 1 || i % 2 ? '♪' : '♫', x, y, 44, '#FFE3A0', { ink: false }); }
  me(960, 830, 32, { eyes: 'closed', mouth: 'smile', aL: .5, aR: .5, rot: .03 * Math.sin(lt * 2) });
});
// 30 多久没有抬起头，认真地数过星星（霓虹闪成假星星）
S(30, (lt, d) => { NODEFN.node_06(lt + 2); for (let i = 0; i < 9; i++) { const on = Math.sin(lt * 9 + i * 2) > 0; if (on) paint(starPts(200 + i * 190, 120 + 60 * hash(i), 22, .3, 4), { wash: [C.neon1, C.neon2, C.neon3][i % 3], ink: PAL.ink, sw: .4 }); }
  letter('假的', 1500, 140, 40, '#B9C6FF', { ink: false, font: HAND(40), alpha: .8 }); });
// 31 多久没有抬起头，看清眼前的风景（天桥看车流，广告牌挡住半边）
S(31, (lt, d) => {
  bg('#1E1E36', '#2A2A45');
  for (let i = 0; i < 10; i++) { const y = 520 + i * 48, x = ((i % 2 ? 1 : -1) * lt * 900 + i * 300) % 2400; inkLine([[x - 300, y], [x + 200, y]], 4, i % 2 ? '#FF6B6B' : '#FFE3A0', 'dry', 0); }
  paint(rectPts(960, 80, 920, 420, 3), { wash: '#FF7FA8', fill: '#7A3CFF', fillOp: 80, ink: PAL.ink, sw: 1.2 }); letter('限时抢购', 1420, 290, 80, PAL.cream, { ink: false, font: HAND(80) });
  for (let i = 0; i < 8; i++) starAt(120 + i * 100, 120 + 60 * hash(i + 30), 4, lt, i, .25);
  paint(rectPts(-40, 980, W + 80, 30, 2), { wash: '#5A5470', ink: PAL.ink, sw: .8 });
  me(420, 990, 26, { eyes: 'look', lookY: .6, mouth: 'flat' });
});
// 32 多久没有抬起头，找寻最初的自己（积水里的倒影更小更亮）
S(32, (lt, d) => {
  bg('#3B3550', '#2C2840'); ground(560, '#4A4660', '#3A3650');
  paint(ellPts(960, 820, 520, 150, 26), { wash: '#6B7AA0', fill: '#9FB2CC', fillOp: 90, ink: PAL.ink, sw: .9 });
  for (let i = 0; i < 3; i++) { const r = ((lt * 120 + i * 120) % 360); paint(ellPts(960, 820, r + 40, (r + 40) * .28, 22), { ink: '#C9D6E6', sw: .5 }); }
  push(); translate(960, 760); scale(1, -1); clawd(0, 0, 18, { eyes: 'spark', mouth: 'grin', col: '#F2A283', noShadow: true, aL: 1.2, aR: 1.2 }); pop();
  me(960, 640, 28, { eyes: 'look', lookY: 1, mouth: 'o' });
});
// 33 多久没有抬起头，去倾听风的声音（张开手接风，天空仍只有霓虹）
S(33, (lt, d) => { nightCity('#2A2245', '#43365F', '#7A5A8E', 9); windLines(lt, 7, '#E8E0FF', 300); ground(880, '#24203A');
  me(960, 900, 36, { eyes: 'closed', mouth: 'smile', aL: 1.5, aR: 1.5 }); });
// 34 他们总在互联网上讨论哪个综艺节目流行
S(34, (lt, d) => {
  bg('#0F1428', '#0A0E1E'); const g = K(lt, d);
  paint(rrPts(560 - 300 * (1 - g), 60, 800 + 600 * (1 - g), 1000, 60), { wash: '#1E2540', ink: PAL.ink, sw: 1.4 });
  [['爆笑综艺', '#FF5C8A'], ['热搜 第 1', '#FFC24B'], ['这期太好笑了', '#3ED6E8'], ['你看了吗', '#9BC48B']].forEach(([s, c], i) => {
    const k = clamp((lt - i * .35) * 3); if (k > 0) { paint(rrPts(640, 140 + i * 210, 640 * backOut(k), 160, 20), { wash: c, ink: PAL.ink, sw: .8 }); letter(s, 960, 220 + i * 210, 50, PAL.ink, { ink: false, font: HAND(50), alpha: k }); } });
  paint(ellPts(960, 1060, 400, 120, 20), { fill: '#6FB6FF', fillOp: 90, bleed: .3, ink: null });
});
// 35 哪个女明星的梗最近又火了
S(35, (lt, d) => {
  bg('#141A30', '#0F1428');
  for (let i = 0; i < 9; i++) { const a = i * 1.7 + lt, x = 960 + Math.cos(a) * (300 + 120 * hash(i)), y = 480 + Math.sin(a) * 260;
    bubble(x, y, 220, 80, ['哈哈哈', '笑死', '绝了', '名场面', '又上热搜', '这梗', 'yyds', '哈哈', '谁懂'][i], 30, PEOPLE[i % 8]); }
  me(960, 1020, 34, { eyes: 'look', lookY: 1, mouth: 'flat', aR: 1, armR: phone(1), emote: '?', emoteK: 1, noShadow: true });
});
// 36 当你忙碌一天回到家里发现手机响个不停
S(36, (lt, d) => {
  bg('#1A1828', '#14121F');
  const op = ease(clamp(lt / .8)); paint([[300, 120], [300 + 300 * op, 120], [300 + 300 * op, 1000], [300, 1000]], { wash: '#FFE7B0', fill: '#F2C77A', fillOp: 90, ink: PAL.ink, sw: .9 });
  paint([[300 + 300 * op, 1000], [1400, 1080], [300, 1080]], { fill: '#FFE7B0', fillOp: 40, bleed: .2, ink: null });
  me(450, 1000, 30, { eyes: 'narrow', mouth: 'flat', noShadow: true });
  paint(rectPts(1100, 760, 500, 40, 2), { wash: C.woodDk, ink: PAL.ink, sw: .8 });
  const sh = 6 * Math.sin(lt * 40); paint(rrPts(1300 + sh, 700, 70, 60, 10), { wash: '#9FD0FF', ink: PAL.ink, sw: .7 });
  for (let i = 0; i < 3; i++) inkLine([[1270 - i * 16, 690 - i * 14], [1260 - i * 16, 670 - i * 14]], .8, '#9FD0FF', 'ink', 0);
});
// 37 回不完的消息让人无处躲藏
S(37, (lt, d) => {
  bg('#2A2236', '#1E1828');
  for (let i = 0; i < 40; i++) { const x = hash(i * 3) * W, y = ((lt * 500 + hash(i) * 1100) % 1100) - 40; paint(ellPts(x, y, 18, 18, 10), { wash: '#E8473C', ink: PAL.ink, sw: .4 }); letter(String(1 + (i % 9)), x, y, 18, PAL.cream, { ink: false }); }
  me(960, 980, 34, { eyes: 'closed', mouth: 'wobble', aL: 1.9, aR: 1.9, sq: .15, dy: .4, emote: 'sweat', emoteK: 1 });
});
// 38 母亲节时一定零点发条朋友圈
S(38, (lt, d) => { camMove([960, 640, 1.3], [980, 660, 1.4], K(lt, d), () => NODEFN.node_07(lt));
  paint(rrPts(1420, 140, 380, 300, 30), { wash: '#1E2540', ink: PAL.ink, sw: 1 }); letter('00:00', 1610, 210, 60, PAL.cream, { ink: false, font: HAND(60) }); letter('母亲节快乐 🎁', 1610, 320, 34, '#FFD36B', { ink: false, font: HAND(34) }); });
// 39 文案最好就用发红包的截图代替
S(39, (lt, d) => { camMove([760, 640, 1.5], [760, 620, 1.6], K(lt, d), () => NODEFN.node_07(lt + 1));
  paint(rrPts(1300, 160, 420, 520, 30), { wash: '#1E2540', ink: PAL.ink, sw: 1 }); paint(rrPts(1360, 240, 300, 360, 16), { wash: '#E8473C', ink: PAL.ink, sw: .8 });
  paint(ellPts(1510, 420, 60, 60, 16), { wash: '#F2C53D', ink: PAL.ink, sw: .6 }); letter('¥520', 1510, 540, 40, PAL.cream, { ink: false, font: HAND(40) }); });
// 40 可她每天始终坐在你的左手边
S(40, (lt, d) => camMove([960, 560, 1], [960, 600, 1.05], K(lt, d), () => NODEFN.node_07(lt)));
// 41 你却从没想过亲口对她说声「妈我爱你」
S(41, (lt, d) => { camMove([960, 640, 1.35], [960, 650, 1.45], K(lt, d), () => NODEFN.node_07(lt + 2));
  const k = Math.sin(clamp(lt / d) * Math.PI); bubble(640, 280, 360 * k + 40, 90, k > .6 ? '妈…' : '', 44); emote('heart', 740, 380, 26, k); });
// 42 好像只是多了几个点赞之交
S(42, (lt, d) => {
  indoor('#EDE7DC', 2); ground(920, '#C9BDA3');
  const gone = ease(clamp((lt - .8) / 1.2));
  for (let i = 0; i < 5; i++) { const x = 600 + i * 230; paint(rectPts(x - 110, 700 - 50 * gone, 220, 150, 3), { ink: mixCol(PAL.ink, '#EDE7DC', gone), sw: 1.2 });
    paint(ellPts(x, 640 - 60 * gone, 34, 34, 12), { ink: mixCol('#E8473C', '#EDE7DC', gone), sw: 1 }); letter('👍', x, 640 - 60 * gone, 30, PAL.ink, { ink: false, alpha: 1 - gone }); }
  me(340, 940, 30, { eyes: 'look', lookX: 1, mouth: 'o', aR: 1.2 });
});
// 43 遇到困难没有人会为你支招
S(43, (lt, d) => {
  bg('#C9B8C8', '#B3A0B3'); ground(860, '#8E8094');
  me(760, 920, 30, { rot: .5, dy: .3, eyes: 'x', mouth: 'wobble', emote: '?', emoteK: 1 });
  paint(rrPts(1120, 300, 360, 600, 36), { wash: '#1E2540', ink: PAL.ink, sw: 1.2 });
  for (let i = 0; i < 7; i++) { const y = 360 + ((i * 80 - lt * 160) % 560 + 560) % 560; paint(ellPts(1180, y, 22, 22, 10), { wash: PEOPLE[i], ink: null }); inkLine([[1220, y], [1400, y]], 1, '#9FD0FF', 'inkfine', 0); }
  letter('无人接听', 1300, 960, 40, '#E8473C', { ink: false, font: HAND(40) });
});
// 44 每天对朋友们重复最多遍的话是
S(44, (lt, d) => {
  bg('#E6E0F0', '#D2CAE2'); dayStreet(44, 920, '#E6E0F0'); ground(920, '#B8B0C8');
  me(400, 960, 28, { eyes: 'normal', mouth: 'o', aR: .8 });
  [800, 1150, 1500].forEach((x, i) => { person(x, 960, 24, i + 2, lt); bubble(x, 560 + 20 * Math.sin(lt * 3 + i), 260, 80, '今年最大的愿望…', 26); });
  for (let i = 0; i < 3; i++) { const a = lt * 4 + i * 2.1; inkLine([[560 + Math.cos(a) * 40, 600 + Math.sin(a) * 40], [600 + Math.cos(a + .6) * 40, 600 + Math.sin(a + .6) * 40]], 1, PAL.ink, 'ink', .4); }
});
// 45 今年最大的愿望是能够养一只猫
S(45, (lt, d) => {
  indoor('#F3E3C6', 3); ground(900, '#C9B28A');
  me(700, 940, 32, { eyes: 'look', lookX: .7, lookY: -.6, mouth: 'smile', noLegs: true, aL: -.8, aR: -.8 });
  thoughtDots(860, 640, 30, 1);
  paint(ellPts(1240, 380, 330, 230, 22), { wash: PAL.cream, ink: PAL.ink, sw: 1 });
  push(); translate(1240, 470); rotate(.3 * Math.sin(lt * 3)); cat(0, 0, 1.3, { t: lt }); pop();
  emote('heart', 1460, 230, 30, .8);
});
// 46 总把没实现的梦想都归结于现实还有工作
S(46, (lt, d) => {
  indoor('#D8CDB4', 0); paint(rectPts(160, 800, 1600, 50, 2), { wash: C.wood, ink: PAL.ink, sw: .9 });
  for (let i = 0; i < 6; i++) paint(rectPts(240 + i * 20, 760 - i * 40, 420, 40, 1), { wash: i % 2 ? '#F2F2EE' : '#E6E0D2', ink: PAL.ink, sw: .6 });
  letter('工作', 450, 520, 44, PAL.ink, { ink: false, font: HAND(44) });
  const fly = ease(clamp((lt - d + 1.2) / 1.2));
  paperPlane(1100 + 600 * fly, 640 - 400 * fly, 1.6 - .6 * fly, -.2 - .4 * fly); letter('梦想', 1100 + 600 * fly, 650 - 400 * fly, 36, '#C8323C', { ink: false, font: HAND(36), alpha: 1 - fly });
  me(1500, 980, 30, { eyes: 'look', lookX: -1, mouth: 'flat', noShadow: true });
});
// 47 却有大把时间用来追剧和攻略
S(47, (lt, d) => {
  bg('#262236', '#1C1A2A'); paint(rectPts(160, 300, 600, 380, 3), { wash: '#2B3048', ink: PAL.ink, sw: 1.2 });
  paint(rectPts(190, 330, 540, 320, 2), { wash: mixCol('#3ED6E8', '#FFC24B', .5 + .5 * Math.sin(lt * 7)), washOp: 210, ink: null });
  paint(ellPts(760, 700, 700, 300, 20), { fill: '#6FB6FF', fillOp: 30 + 20 * Math.sin(lt * 7), bleed: .3, ink: null });
  paint(rrPts(980, 760, 760, 200, 50), { wash: '#7A5A8E', fill: '#5A4070', fillOp: 70, ink: PAL.ink, sw: 1 });         // 沙发
  me(1300, 830, 30, { eyes: 'narrow', mouth: 'flat', aR: .9, armR: phone(1), noLegs: true, noShadow: true });
  const c = 1560; paint(ellPts(c, 200, 70, 70, 20), { wash: PAL.cream, ink: PAL.ink, sw: .9 });
  inkLine([[c, 200], [c + 50 * Math.cos(lt * 12), 200 + 50 * Math.sin(lt * 12)]], 1, PAL.ink, 'ink', 0); inkLine([[c, 200], [c + 30 * Math.cos(lt), 200 + 30 * Math.sin(lt)]], 1.4, PAL.ink, 'ink', 0);
});
// 48 也时常感到后悔在孤独的深夜
S(48, (lt, d) => {
  bg('#141830', '#0E1226');
  windowFrame(1300, 160, 420, 360, '#1E2350', (x, y, w, h) => { paint(ellPts(x + 300, y + 90, 40, 40, 14), { wash: '#FFF2C4', ink: PAL.ink, sw: .6 }); });
  paint([[1300, 520], [1720, 520], [1400, 1080], [700, 1080]], { fill: '#C9D6FF', fillOp: 40, bleed: .2, ink: null });
  paint(rrPts(300, 760, 1100, 160, 30), { wash: '#3B4470', fill: '#2B3258', fillOp: 70, ink: PAL.ink, sw: 1 }); paint(rrPts(320, 720, 220, 80, 30), { wash: PAL.cream, ink: PAL.ink, sw: .8 });
  push(); translate(760, 790); rotate(-Math.PI / 2); clawd(0, 0, 24, { eyes: 'look', lookX: -1, mouth: 'flat', noShadow: true, emote: lt < d / 2 ? 'zzz' : '?', emoteK: 1 }); pop();
});
// 49 听一首感性的音乐
S(49, (lt, d) => {
  bg('#2B2350', '#3A2E62');
  me(960, 1120, 58, { eyes: 'closed', mouth: 'smile', noShadow: true, draw: (u, sw) => { inkLine([[-5 * u, -6 * u], [0, -9.4 * u], [5 * u, -6 * u]], sw * 1.6, '#2B2233', 'ink', .6); for (const s of [-1, 1]) paint(ellPts(s * 5.1 * u, -5.6 * u, .7 * u, 1.1 * u, 10), { wash: '#E27A92', ink: PAL.ink, sw: sw * .5 }); } });
  notes(1200, 520, lt, 5, '#FFE3A0'); notes(560, 560, lt + .5, 4, '#FFE3A0');
  paint(starPts(1110, 640, 10, .3, 4), { wash: '#BFE3FF', ink: null });
});
// 50 副歌 2 · 楼缝里出现一两颗星
S(50, (lt, d) => camMove([960, 600, 1.1], [960, 520, 1], K(lt, d), () => NODEFN.node_08(lt)));
// 51 看清眼前的风景（广告牌暗了一点，远处山影露出来）
S(51, (lt, d) => {
  bg('#232A5A', '#323A72'); const k = K(lt, d);
  paint([[0, 700], [300, 480], [620, 640], [980, 430], [1400, 620], [1920, 470], [1920, 760], [0, 760]], { wash: mixCol('#232A5A', '#3E4A7A', k), ink: mixCol('#232A5A', PAL.ink, k), sw: .8 });
  tower(-20, 280, 620, '#2A2840', 81, .3); tower(1600, 340, 680, '#2A2840', 82, .3);
  paint(rectPts(700, 300, 520, 260, 3), { wash: mixCol('#FF7FA8', '#3B3550', k), ink: PAL.ink, sw: 1 });
  starAt(1300, 220, 18, lt, 1); starAt(560, 160, 12, lt, 2, k); ground(880, '#24203A');
  me(960, 900, 30, { eyes: 'look', lookY: -.6, mouth: 'o', armR: phone(.3), aR: .2 });
});
// 52 找寻最初的自己（橱窗倒影里小时候的自己在挥手）
S(52, (lt, d) => {
  bg('#3A3654', '#2C2842'); paint(rectPts(260, 140, 1400, 760, 3), { wash: '#5A6A96', fill: '#7F93C2', fillOp: 60, ink: PAL.ink, sw: 1.2 });
  for (let i = 0; i < 4; i++) inkLine([[300 + i * 340, 180], [460 + i * 340, 420]], .8, '#E8EEF5', 'dry', 0);
  clawd(1160, 780, 18, { eyes: 'happy', mouth: 'grin', col: '#F2A283', noShadow: true, ...move('wave', lt) });
  me(760, 1000, 32, { eyes: 'look', lookX: 1, mouth: 'o', aR: 1.1 + .1 * Math.sin(lt * 2) });
});
// 53 去倾听风的声音（树下听风，两颗星在枝头间闪）
S(53, (lt, d) => {
  bg('#1E2350', '#2B3270'); starAt(820, 220, 18, lt, 1); starAt(1180, 300, 14, lt, 2);
  push(); translate(960, 1100); scale(2.4); tree(0, 0, 1, '#3E6B4A'); pop();
  for (let i = 0; i < 6; i++) { const x = 700 + i * 90 + 30 * Math.sin(lt * 3 + i), y = ((lt * 160 + i * 140) % 700) + 200; paint(ellPts(x, y, 16, 8, 10, 0, lt + i), { wash: '#6E9F58', ink: PAL.ink, sw: .3 }); }
  ground(940, '#24203A'); me(960, 960, 30, { eyes: 'closed', mouth: 'smile', aL: .3, aR: .3 });
});
// 54 认真地数过星星（星星多了一点，他眼睛变成星星眼）
S(54, (lt, d) => { bg('#1E2350', '#2B3270'); stars(7, lt, 40, K(lt, d) * 1.2, 60, 420);
  me(960, 1140, 64, { eyes: 'spark', mouth: 'O', noShadow: true, rot: -.05 }); });
// 55 看清眼前的风景（天桥上风把云吹开）
S(55, (lt, d) => {
  bg('#2B3270', '#3B4488'); const k = K(lt, d);
  for (const s of [-1, 1]) paint(ellPts(960 + s * (200 + 600 * k), 260, 500, 140, 20), { wash: '#4A5390', fill: '#6670A8', fillOp: 70, ink: PAL.ink, sw: .6 });
  paint(ellPts(960, 240, 60, 60, 16), { wash: '#FFF2C4', ink: PAL.ink, sw: .6 }); stars(10, lt, 60, k, 60, 380);
  paint(rectPts(-40, 820, W + 80, 60, 2), { wash: '#5A5470', ink: PAL.ink, sw: 1 }); inkLine([[-40, 720], [W + 40, 720]], 2, '#8A84A0', 'ink', 0);
  me(lerp(500, 1300, k), 830, 28, { walk: lt * 1.5, eyes: 'look', lookY: -.5, mouth: 'smile' });
});
// 56 找寻最初的自己（接住纸飞机，尾迹连成一颗星）
S(56, (lt, d) => {
  bg('#1E2350', '#2B3270'); stars(10, lt, 70, 1, 60, 500); ground(900, '#24203A');
  const k = K(lt, d), px = lerp(1700, 1080, clamp(k * 1.4)), py = lerp(160, 640, clamp(k * 1.4));
  const tr = []; for (let i = 0; i < 10; i++) { const q = clamp(k * 1.4) * i / 10; tr.push([lerp(1700, 1080, q), lerp(160, 640, q) - 60 * Math.sin(q * Math.PI)]); }
  if (tr.length > 1) inkLine(tr, 1.2, '#FFE9A8', 'inkfine', .6);
  if (k > .75) starAt(1400, 300, 30 * (k - .75) * 4, lt, 9);
  paperPaperPlaneGuard(px, py);
  me(960, 920, 32, { eyes: 'spark', mouth: 'grin', aR: 1.5, aL: .2 });
});
function paperPaperPlaneGuard(x, y) { paperPlane(x, y, .9, -.6); }
// 57 去倾听风的声音（闭眼听风，风里有音符，星星微微亮）
S(57, (lt, d) => { bg('#22296A', '#2E3880'); stars(14, lt, 90, .9, 60, 520); windLines(lt, 5, '#C9C2E6', 260); notes(1300, 600, lt, 5, '#FFE3A0');
  me(960, 1100, 56, { eyes: 'closed', mouth: 'smile', noShadow: true, rot: .04 * Math.sin(lt * 2) }); });
// 58 那个时候微博没有清一色的控评（旧暖色纸，推近老电脑）
S(58, (lt, d) => camMove([960, 540, 1], [820, 500, 1.3], K(lt, d), () => NODEFN.node_09(lt)));
// 59 你的 QQ 宠物没有停止运营（小企鹅跳出来）
S(59, (lt, d) => camMove([820, 560, 1.5], [860, 600, 1.4], K(lt, d), () => NODEFN.node_09(lt + 1)));
// 60 当你鼓起勇气想要第一次拿起笔时
S(60, (lt, d) => {
  sepia(); poster(120, 140, 220, 280, '#E8B86B', (x, y) => letter('乐队', x + 110, y + 60, 36, PAL.ink, { ink: false, font: HAND(36) })); plant(1800, 1000, 1.1);
  for (let i = 0; i < 5; i++) paint([[1920, 100 + i * 80], [600 + i * 100, 1080], [700 + i * 100, 1080]], { fill: '#FFF2C4', fillOp: 45, bleed: .2, ink: null });
  paint(rectPts(400, 380, 1000, 560, 2), { wash: '#F6EEDC', ink: PAL.ink, sw: 1 });
  for (let i = 0; i < 6; i++) { const k = clamp((lt - i * .25) * 2); if (k > 0) inkLine([[480, 460 + i * 70], [480 + 700 * k * (.6 + .4 * hash(i)), 460 + i * 70 + 8 * Math.sin(i)]], 1.2, PAL.ink, 'HB', .3); }
  push(); translate(480 + 600 * clamp(lt / d), 520 + 70 * Math.floor(lt * 2.4)); rotate(-.7);
  paint(rectPts(0, -14, 260, 28, 3), { wash: '#F2C53D', ink: PAL.ink, sw: .8 }); paint([[0, -14], [0, 14], [-40, 0]], { wash: '#F2D6A2', ink: PAL.ink, sw: .6 }); pop();
});
// 61 写出的歌不是为了赚钱或者出名（折成纸飞机飞出窗）
S(61, (lt, d) => {
  sepia(); windowFrame(1300, 160, 460, 400, '#BFE0F2', (x, y, w, h) => tree(x + 300, y + h, .8, '#9BC48B'));
  paint(rectPts(200, 820, 1400, 50, 2), { wash: '#A47A52', ink: PAL.ink, sw: 1 });
  const f = ease(clamp(lt / 1)), fly = ease(clamp((lt - 1) / (d - 1)));
  if (fly <= 0) { paint(rectPts(600, 700 - 60 * f, 360, 240 * (1 - f) + 40, 2), { wash: '#F6EEDC', ink: PAL.ink, sw: .8 }); letter('♪ ♫ ♪', 780, 760, 40, PAL.ink, { ink: false }); }
  else paperPlane(lerp(780, 1530, fly), lerp(760, 300, fly) - 80 * Math.sin(fly * Math.PI), lerp(1.4, .5, fly), -.4);
  me(500, 830, 30, { eyes: 'happy', mouth: 'grin', aR: 1.2, noShadow: true, draw: null });
});
// 62 看到老人跌倒你也不会躲远
S(62, (lt, d) => NODEFN.node_10(lt));
// 63 不在意电视上有什么节目可选（老电视雪花屏，围坐笑）
S(63, (lt, d) => {
  sepia(); paint(rrPts(700, 260, 520, 420, 40), { wash: '#B98E5A', ink: PAL.ink, sw: 1.2 }); paint(rrPts(750, 300, 360, 320, 30), { wash: '#C9C9C9', ink: PAL.ink, sw: .8 });
  for (let i = 0; i < 160; i++) { const x = 760 + hash(i + Math.floor(lt * 12) * 7) * 340, y = 310 + hash(i * 3 + Math.floor(lt * 12)) * 300; paint(rectPts(x, y, 6, 4), { wash: hash(i) < .5 ? '#555' : '#EEE', ink: null }); }
  for (let i = 0; i < 3; i++) paint(ellPts(1160, 360 + i * 70, 16, 16, 10), { wash: '#8C6A40', ink: PAL.ink, sw: .5 });
  inkLine([[860, 260], [800, 160]], 1.2, PAL.ink, 'ink', 0); inkLine([[1000, 260], [1060, 160]], 1.2, PAL.ink, 'ink', 0);
  ground(880, '#C9A06C'); [520, 960, 1400].forEach((x, i) => i === 1 ? me(x, 960, 30, { eyes: 'happy', mouth: 'grin', noShadow: true, draw: null, dy: -Math.abs(Math.sin(lt * 4)) * .3 }) : person(x, 960, 28, i + 2, lt, { eyes: 'happy', mouth: 'grin' }));
});
// 64 当你情绪泛滥以后（河边，情绪变成水波漫上来）
S(64, (lt, d) => {
  bg('#9FB8D6', '#86A2C6'); const k = K(lt, d); dayStreet(64, 700, '#9FB8D6');
  for (let i = 0; i < 5; i++) { const y = 1080 - (200 + i * 60) * k; inkLine([[-40, y], [480, y - 20], [960, y], [1440, y - 20], [1960, y]], 2, i % 2 ? '#5A7AAA' : '#E8EEF5', 'dry', .6); }
  paint(rectPts(-40, 900 - 260 * k, W + 80, 400, 2), { wash: '#6E8FC0', washOp: 160, ink: null });
  me(960, 900, 32, { eyes: 'closed', mouth: 'o', aL: .3, aR: .3 });
});
// 65 不用浏览那些毒鸡汤也能够轻松与自己和解（手机反扣在草地，云变成笑脸）
S(65, (lt, d) => {
  bg('#BFE0F2', '#9FCDEB'); const k = K(lt, d);
  paint(ellPts(1200, 300, 300, 150, 20), { wash: PAL.cream, ink: PAL.ink, sw: .8 });
  if (k > .3) { for (const ex of [1130, 1270]) paint(ellPts(ex, 280, 14, 18, 10), { wash: PAL.ink, ink: null }); inkLine([[1120, 340], [1200, 380], [1280, 340]], 1.6 * clamp((k - .3) * 3), PAL.ink, 'ink', .6); }
  ground(860, '#7FAE6A', '#6E9F58'); for (let i = 0; i < 30; i++) inkLine([[40 + i * 64, 880], [50 + i * 64, 850]], .7, '#4E7A44', 'inkfine', .4);
  push(); translate(1300, 930); rotate(.2); paint(rrPts(-60, -30, 120, 60, 10), { wash: '#3A3F55', ink: PAL.ink, sw: .7 }); pop();
  me(800, 900, 32, { eyes: 'look', lookY: -1, mouth: 'smile', aL: -.6, aR: -.6, noLegs: true, draw: null });
});
// 66 什么时候我们开始变得没有表情
S(66, (lt, d) => camMove([1030, 760, 1.4], [960, 600, 1.05], K(lt, d), () => NODEFN.node_11(lt)));
// 67 总爱把感情都围成三角形
S(67, (lt, d) => {
  bg('#B9BAC0', '#9FA0A8'); dayStreet(67, 920, '#B9BAC0'); ground(920, '#8E8F98');
  const tri = (cx, cy, r, a) => { const p = []; for (let i = 0; i < 3; i++) { const q = a + i * TAU / 3; p.push([cx + Math.cos(q) * r, cy + Math.sin(q) * r]); } paint(p, { ink: PAL.ink, sw: 1.6 }); };
  tri(960, 640, 420, lt * .5 - Math.PI / 2);
  [[960, 330], [640, 860], [1280, 860]].forEach(([x, y], i) => i === 0 ? me(x, y + 40, 24, { col: mixCol('#D97757', '#A9AAB2', .5), eyes: 'dot', mouth: 'flat' }) : person(x, y, 24, i, lt, { col: '#A9AAB2', eyes: 'dot', mouth: 'flat' }));
});
// 68 总是想把同样的誓发给不同人听
S(68, (lt, d) => {
  bg('#D5D6DC', '#BFC0C8'); dayStreet(68, 920, '#D5D6DC'); ground(920, '#A9AAB2');
  me(360, 960, 28, { col: mixCol('#D97757', '#A9AAB2', .45), eyes: 'dot', mouth: 'flat', aR: 1 });
  [800, 1150, 1500].forEach((x, i) => { person(x, 960, 24, i + 3, lt, { col: '#B9BAC0', eyes: 'dot', mouth: 'flat' });
    const k = clamp((lt - i * .4) * 2.5); if (k > 0) { const bx = lerp(520, x, k), by = lerp(640, 560, k); bubble(bx, by, 260, 80, '我只对你说', 28); } });
});
// 69 重复这种没意义的演习（跑步机上同一个动作，像卡带循环）
S(69, (lt, d) => { NODEFN.node_05((lt % .25) * .5); for (let i = 0; i < 3; i++) inkLine([[0, 200 + i * 300 + 40 * Math.sin(lt * 30)], [W, 200 + i * 300 + 40 * Math.sin(lt * 30)]], 2, '#FFFFFF', 'dry', 0); });
// 70 可所幸我们同样还在为了生活奔波（夜路上一起跑，路灯一盏盏亮）
S(70, (lt, d) => {
  bg('#1E2350', '#2B3270'); ground(900, '#2A2840');
  for (let i = 0; i < 6; i++) { const x = 160 + i * 320, on = lt > i * .45; inkLine([[x, 900], [x, 520], [x + 60, 500]], 1.6, PAL.ink, 'ink', .2);
    if (on) { paint(ellPts(x + 64, 506, 16, 10, 10), { wash: '#FFD27A', ink: PAL.ink, sw: .5 }); paint(ellPts(x + 64, 900, 140, 30, 16), { fill: '#FFD27A', fillOp: 60, bleed: .3, ink: null }); } }
  for (let i = 0; i < 4; i++) person(400 + i * 260 + lt * 80, 960, 22, i, lt, { ...move('run', lt), eyes: 'narrow', emote: i === 2 ? 'sweat' : null, emoteK: 1 });
  me(1460 + lt * 80, 970, 26, { ...move('run', lt), eyes: 'happy', mouth: 'grin' });
});
// 71 同样还在等待周杰伦的新歌（耳机，屏幕倒计时）
S(71, (lt, d) => {
  bg('#2B2350', '#3A2E62'); paint(rrPts(1100, 260, 560, 360, 30), { wash: '#1E2540', ink: PAL.ink, sw: 1 });
  letter('新歌倒计时', 1380, 340, 40, PAL.cream, { ink: false, font: HAND(40) }); letter(`00:00:0${Math.max(0, 9 - Math.floor(lt * 3))}`, 1380, 470, 72, '#FFD36B', { ink: false, font: HAND(72) });
  me(620, 1080, 50, { eyes: 'look', lookX: 1, mouth: 'smile', noShadow: true, draw: (u, sw) => { inkLine([[-5 * u, -6 * u], [0, -9.4 * u], [5 * u, -6 * u]], sw * 1.6, '#2B2233', 'ink', .6); for (const s of [-1, 1]) paint(ellPts(s * 5.1 * u, -5.6 * u, .7 * u, 1.1 * u, 10), { wash: '#E27A92', ink: PAL.ink, sw: sw * .5 }); } });
  notes(860, 560, lt, 4, '#FFE3A0');
});
// 72 同样还是没有得到老板的赏识
S(72, (lt, d) => {
  indoor('#C9D0DA', 2); paint(rectPts(860, 660, 800, 50, 2), { wash: C.woodDk, ink: PAL.ink, sw: 1 });
  person(1300, 670, 30, 6, lt, { col: '#6E7787', eyes: 'narrow', mouth: 'flat', noShadow: true, rot: .08 * Math.sin(lt * 6), draw: (u, sw) => paint(rrPts(-1 * u, -2.4 * u, 2 * u, .8 * u, .3 * u), { wash: '#C8323C', ink: null }) });
  me(520, 980, 30, { eyes: 'look', lookY: 1, mouth: 'wobble', emote: 'sweat', emoteK: 1, aL: .9, aR: .9, armR: (u, sw) => { for (let i = 0; i < 3; i++) paint(rectPts(-2 * u, -1.6 * u - i * .4 * u, 2.6 * u, .5 * u, 1), { wash: PAL.cream, ink: PAL.ink, sw: sw * .4 }); } });
  poster(200, 160, 300, 200, PAL.cream, (x, y) => letter('KPI', x + 150, y + 100, 60, '#C8323C', { ink: false, font: HAND(60) }));
});
// 73 同样也会感动在那首歌奏响时（livehouse）
S(73, (lt, d) => {
  bg('#1A1428', '#120E1E');
  for (let i = 0; i < 5; i++) { const a = -1.2 + i * .6 + .2 * Math.sin(lt * 1.5 + i); paint([[960, 0], [960 + Math.cos(a + Math.PI / 2) * 1400 - 200, 1080], [960 + Math.cos(a + Math.PI / 2) * 1400 + 200, 1080]], { fill: [C.neon1, C.neon2, C.neon3, '#FFD27A', '#9D6BFF'][i], fillOp: 40, bleed: .3, ink: null }); }
  for (let i = 0; i < 9; i++) person(120 + i * 210, 1080, 26, i, lt, { aL: 1.6 + .2 * Math.sin(lt * 5 + i), aR: 1.6, col: '#2B2440', dk: '#1E1830', noShadow: true });
  me(960, 1020, 34, { eyes: 'closed', mouth: 'smile', noShadow: true }); tears(960, 1020, 34, (lt * 1.2) % 1);
});
// 74 还在期待某部动漫下一季的播放（台阶上看投影）
S(74, (lt, d) => {
  bg('#1E2350', '#2B3270'); paint(rectPts(360, 120, 1200, 560, 3), { wash: '#F6EEDC', fill: '#BFE0F2', fillOp: 60, ink: PAL.ink, sw: 1 });
  clawd(720 + 400 * Math.sin(lt), 440 - 80 * Math.abs(Math.sin(lt * 2)), 20, { col: '#9FD0FF', eyes: 'spark', mouth: 'grin', aL: 1.6, aR: 1.6, noShadow: true });
  letter('第二季 · 敬请期待', 960, 620, 40, PAL.ink, { ink: false, font: HAND(40) });
  stair(820); me(840, 840, 26, { eyes: 'look', lookY: -1, noLegs: true, flip: true }); girl(1080, 840, 26, { eyes: 'look', lookY: -1, noLegs: true });
});
// 75 还是愿意为了家人乘风破浪（船头，浪花）
S(75, (lt, d) => {
  bg('#7FA7D9', '#5E8AC8');
  for (let i = 0; i < 6; i++) { const y = 700 + i * 60, sh = 60 * Math.sin(lt * 2 + i); inkLine([[-40, y + sh * .3], [480, y - 30 + sh * .2], [960, y + sh * .3], [1440, y - 30], [1960, y]], 2.4, i % 2 ? '#E8EEF5' : '#3E6AAE', 'dry', .7); }
  paint([[300, 860], [1500, 860], [1300, 1040], [500, 1040]], { wash: C.wood, fill: C.woodDk, fillOp: 80, ink: PAL.ink, sw: 1.2 });
  windLines(lt, 4, '#FFFFFF', 160);
  me(1000, 870, 32, { eyes: 'narrow', mouth: 'grin', aR: 1.4, aL: .3, rot: -.05 });
  clawd(760, 870, 26, { col: '#D99A76', dk: '#AE6E50', lt: '#F2C1A2', eyes: 'happy', mouth: 'smile', aL: .9, draw: (u, sw) => { paint(rrPts(-3.2 * u, -4.6 * u, 6.4 * u, 2.7 * u, .5 * u), { wash: PAL.cream, ink: PAL.ink, sw: sw * .6 }); paint(ellPts(1.2 * u, -8.6 * u, 1.3 * u, 1 * u, 14), { wash: '#4A3428', ink: PAL.ink, sw: sw * .6 }); } });
});
// 76 还是记得梦的形状（纸飞机举高，变成发光的梦）
S(76, (lt, d) => {
  bg('#2B2350', '#3A2E62'); stars(12, lt, 120, .8, 60, 400); ground(900, '#24203A'); const k = K(lt, d);
  paint(ellPts(960, 300, 120 * k + 20, 120 * k + 20, 16), { fill: '#FFE9A8', fillOp: 90 * k, bleed: .35, ink: null });
  paperPlane(960, lerp(600, 300, k), lerp(1, 1.4, k), -1.5, mixCol(PAL.cream, '#FFE9A8', k));
  me(960, 920, 32, { eyes: 'look', lookY: -1, mouth: 'grin', aL: 1.6, aR: 1.6 });
});
// 77 愿你永远年轻（情绪最高点：女生 CC 为他祈祷）
S(77, (lt, d) => camMove([960, 620, 1.15], [960, 640, 1.25], K(lt, d), () => NODEFN.node_12(lt)));
// 78 永远都热泪盈眶（她伸手替他擦泪，泪光变成小星星）
S(78, (lt, d) => { camMove([960, 700, 1.6], [960, 720, 1.7], K(lt, d), () => NODEFN.node_12(lt + 1));
  for (let i = 0; i < 4; i++) starAt(1080 + i * 40, 520 - i * 60 - lt * 60, 10, lt, i + 50); });
// 79 I pray for you（我为你祈祷）：白光里两人的剪影，一颗星落在中间
S(79, (lt, d) => {
  const k = K(lt, d);
  NODEFN.node_12(lt + 2);
  flash(.25 + .55 * k, '#FFF8E8');
  starAt(960, lerp(200, 700, k), 30 + 20 * k, lt, 7);
});
// 80 副歌 3 · 满天星星一颗颗亮起
S(80, (lt, d) => camMove([960, 760, 1.25], [960, 540, 1], K(lt, d), () => NODEFN.node_13(lt * .6)));
// 81 看清眼前的风景（山顶，云海在脚下）
S(81, (lt, d) => {
  bg('#141A44', '#22296A'); stars(90, lt, 200, 1, 30, 600);
  paint(ellPts(980, 300, 980, 140, 30, 20, -.2), { fill: '#7A68C0', fillOp: 70, bleed: .35, tex: .8, ink: null });
  for (let i = 0; i < 6; i++) paint(ellPts(((i * 380 + lt * 40) % 2400) - 200, 820 + 30 * (i % 2), 360, 80, 18), { wash: '#C9C2E6', fill: '#A9A2D6', fillOp: 60, ink: PAL.ink, sw: .5 });
  paint([[700, 1080], [960, 760], [1220, 1080]], { wash: '#2C3A4A', ink: PAL.ink, sw: 1 });
  me(960, 770, 22, { eyes: 'spark', mouth: 'O', aL: 1.5, aR: 1.5 });
});
// 82 找寻最初的自己（湖面星空倒影里的小时候，两人挥手）
S(82, (lt, d) => {
  bg('#141A44', '#22296A'); stars(60, lt, 300, 1, 30, 480);
  paint(rectPts(-40, 560, W + 80, 560, 2), { wash: '#1A2258', fill: '#22296A', fillOp: 80, ink: null });
  for (let i = 0; i < 40; i++) starAt(hash(300 + i * 3) * W, 1120 - lerp(30, 480, hash(300 + i * 5 + 1)) * .9, 6, lt, i, .6);
  inkLine([[-40, 560], [W + 40, 560]], 1.2, '#8A84C0', 'ink', 0);
  me(960, 560, 30, { ...move('wave', lt), eyes: 'happy', mouth: 'grin' });
  push(); translate(960, 580); scale(1, -1); clawd(0, 0, 18, { ...move('wave', lt + .3), eyes: 'happy', mouth: 'grin', col: '#F2A283', noShadow: true }); pop();
});
// 83 去倾听风的声音（整片星海被风吹得流动，音符满天）
S(83, (lt, d) => {
  bg('#141A44', '#22296A');
  for (let i = 0; i < 80; i++) { const x = ((hash(i * 3) * W + lt * 120 * (1 + hash(i))) % (W + 100)) - 50; starAt(x, 40 + hash(i * 5) * 620, 5 + 10 * Math.pow(hash(i * 11), 2), lt, i); }
  windLines(lt, 6, '#C9C2E6', 160); notes(600, 700, lt, 4, '#FFE3A0'); notes(1300, 650, lt + .4, 4, '#FFE3A0');
  paint(ellPts(960, 1060, 1300, 260, 30), { wash: '#2C4A3A', fill: C.grass, fillOp: 120, tex: .6, ink: PAL.ink, sw: .9 });
  me(960, 900, 34, { eyes: 'closed', mouth: 'smile', aL: .6, aR: .6 });
});
// 84 认真地数过星星（躺在草地上一颗颗数）
S(84, (lt, d) => camMove([800, 600, 1.15], [880, 560, 1.05], K(lt, d), () => NODEFN.node_14(lt)));
// 85 看清眼前的风景（两人一起看星空）
S(85, (lt, d) => camMove([1000, 640, 1.2], [960, 540, 1], K(lt, d), () => NODEFN.node_14(lt + 2)));
// 86 找寻最初的自己（星空里浮出小时候拿纸飞机的 CC，和现在重叠）
S(86, (lt, d) => { NODEFN.node_13(3); const k = Math.sin(clamp(lt / d) * Math.PI);
  paint(ellPts(960, 420, 260, 260, 20), { fill: '#FFE9A8', fillOp: 70 * k, bleed: .35, ink: null });
  if (k > .1) { clawd(960, 560, 20, { eyes: 'happy', mouth: 'grin', col: mixCol('#22296A', '#F2A283', k), dk: mixCol('#22296A', '#C8603C', k), noShadow: true, aR: 1.4 }); paperPlane(1060, 360, .5 * k + .1, -.3); } });
// 87 去倾听风的声音（纸飞机飞向星海，两人并肩，画面渐白）
S(87, (lt, d) => { camMove([960, 640, 1.12], [960, 540, 1], K(lt, d), () => NODEFN.node_14(lt + 3)); flash(ease(clamp((lt - d + 2.5) / 2.5)), '#F3EBDC'); });
// 88 尾奏：星星合上
S(88, (lt, d) => NODEFN.node_15(lt * .8));

// ================================================================ 转场（剪切点正好盖满，前后各 CUT 秒）
const WIPE_PAL = [['#C0504D', '#E8A55A'], ['#2F4F8F', '#7B5CA8'], ['#3E6B4A', '#9BC48B'], ['#7B5CA8', '#E27A92'], ['#E8AA38', '#C0504D']];
function brushWipe(p, idx) {
  const [c1, c2] = WIPE_PAL[idx % WIPE_PAL.length], n = 5, bh = (H + 420) / n + 40;
  push(); translate(W / 2, H / 2); rotate(-.1); translate(-W / 2, -H / 2);
  for (let i = 0; i < n; i++) {
    const y0 = -230 + i * (H + 420) / n, dl = [0, .14, .06, .18, .1][i];
    const q = p < .5 ? easeOut(clamp((p * 2 - dl) / (1 - dl))) : ease(clamp(((p - .5) * 2 - dl) / (1 - dl)));
    const x0 = p < .5 ? -300 : lerp(-300, W + 400, q), x1 = p < .5 ? lerp(-300, W + 400, q) : W + 400;
    if (x1 - x0 < 30) continue;
    paint([[x0, y0], [x1, y0 + 10], [x1 - 40, y0 + bh], [x0, y0 + bh]], { wash: i % 2 ? c1 : c2, washOp: 255, fill: i % 2 ? c2 : c1, fillOp: 70, tex: .8, ink: null });
  }
  pop();
}
function transition(type, p, idx) { return tagged('trans', () => transitionRaw(type, p, idx)); }
function transitionRaw(type, p, idx) {
  const cover = 1 - Math.abs(p - .5) * 2;               // 0 → 1（剪切点）→ 0
  if (type === 'flash' || type === 'stars') { flash(cover, type === 'stars' ? '#FFF6D6' : '#FFFDF6'); if (type === 'stars') for (let i = 0; i < 12; i++) starAt(hash(i + idx) * W, hash(i * 3 + idx) * H, 30 * cover, p, i, cover); return; }
  if (type === 'iris') { const r = 1300 * (1 - cover); iris(W / 2, H / 2, Math.max(r, 2), '#2B2233'); return; }
  if (type === 'doors') { const w = W / 2 * cover; paint(rectPts(-20, -20, w + 20, H + 40, 2), { wash: '#B9C2CF', ink: PAL.ink, sw: 1.2 }); paint(rectPts(W - w, -20, w + 20, H + 40, 2), { wash: '#B9C2CF', ink: PAL.ink, sw: 1.2 }); return; }
  if (type === 'page') { const x = p < .5 ? lerp(W + 40, -40, p * 2) : -40, x2 = p < .5 ? W + 40 : lerp(W + 40, -40, (p - .5) * 2);
    paint([[x, -40], [x2, -40], [x2, H + 40], [x - 60, H + 40]], { wash: '#F3EBDC', fill: '#E0D3B8', fillOp: 80, ink: PAL.ink, sw: 1 }); return; }
  if (type === 'burn') { const r = 1300 * (1 - cover); if (r < 1250) irisShape(starPts(W / 2, H / 2, Math.max(r, 2), .82, 14), '#2A1A14'); if (r < 1250 && r > 2) paint(starPts(W / 2, H / 2, r + 20, .8, 14), { ink: '#FF8A3D', sw: 2.4 }); return; }
  if (type === 'smoke') { for (let i = 0; i < 9; i++) paint(ellPts(hash(i + idx) * W, hash(i * 7 + idx) * H, 500 * cover, 320 * cover, 18), { wash: '#4A4660', fill: '#2E2A40', fillOp: 90, ink: null }); return; }
  if (type === 'screen') { const w = W * cover * 1.1, h = H * cover * 1.1; if (w > 10) paint(rrPts(W / 2 - w / 2, H / 2 - h / 2, w, h, 40), { wash: '#1E2540', ink: PAL.ink, sw: 1.4 }); return; }
  brushWipe(p, idx);
}

// ================================================================ 字幕（按歌词逐字亮起，位置跟着镜头）
function filmSubs(t, shot) { return tagged('subs', () => filmSubsRaw(t, shot)); }
function filmSubsRaw(t, shot) {
  // 下一句开口时这一句就收掉（不叠两行）；同时出现的两句（I pray for you / 我为你祈祷）一起显示
  const act = LY.filter((l, i) => { const nx = LY.slice(i + 1).find(m => m.s > l.s + .01); return t >= l.s - .12 && t < (nx ? Math.min(l.e + .5, nx.s - .02) : l.e + .5); });
  if (!act.length) return;
  let [x0, y0] = SUBPOS[shot.sub] || SUBPOS.bottom; const size = 62;
  outX.font = HAND(size); const wMax = Math.max(...act.map(l => Math.max(...l.text.split('，').map(p => outX.measureText(p).width))));
  x0 = clamp(x0, wMax / 2 + 50, W - wMax / 2 - 50);      // 长句不出画
  act.forEach((l, j) => {
    const parts = l.text.split('，'), chars = l.w.length ? l.w.filter(w => w[1] <= t).length : Math.floor(clamp((t - l.s) / Math.max(.1, l.e - l.s)) * l.text.replace(/[，\s]/g, '').length);
    let sung = chars;
    const sz = j > 0 ? size * .7 : size, base = y0 + j * size * 1.3 - (act.length > 1 ? size * .4 : 0);
    parts.forEach((p, i) => {
      const yy = base + (i - (parts.length - 1) / 2) * sz * 1.25, n = p.replace(/\s/g, '').length, done = Math.max(0, Math.min(p.length, sung)); sung -= n;
      const fade = clamp((t - l.s + .12) / .15) * (1 - clamp((t - l.e - .35) / .15));
      letter(p, x0, yy, sz, PAL.cream, { screen: true, ink: false, stroke: 'rgba(43,34,51,.9)', font: HAND(sz), alpha: fade });
      if (done > 0) letter(p, x0, yy, sz, '#FFD36B', { screen: true, ink: false, stroke: 'rgba(43,34,51,.9)', font: HAND(sz), clipChars: done, alpha: fade });
    });
  });
}

// ================================================================ 全片
function shotAt(t) { let i = 0; while (i + 1 < SH.length && t >= SH[i + 1].from) i++; return i; }
scene('film', { w: 1920, h: 1080, dur: FILM.dur, bpm: FILM.bpm, off: FILM.beat0, zh: '整首歌词动画（全手绘，89 镜）' }, t => {
  const i = shotAt(t), s = SH[i];
  (SHOT[i] || ((lt) => NODEFN.node_15(lt)))(t - s.from, s.to - s.from, t);
  CAM = null; flushLetters();
  const nxt = SH[i + 1], prev = SH[i];
  if (nxt && nxt.from - t < CUT) transition(nxt.tr, (t - (nxt.from - CUT)) / (2 * CUT), i + 1);
  else if (i > 0 && t - prev.from < CUT) transition(prev.tr, (t - (prev.from - CUT)) / (2 * CUT), i);
  flushLetters();
  filmSubs(t, s);
});
// 单镜预览：shot_00…shot_88（只渲染这一镜，方便检查）
SH.forEach((s, i) => scene(`shot_${String(i).padStart(2, '0')}`, { w: 1920, h: 1080, dur: s.to - s.from, bpm: FILM.bpm, off: FILM.beat0, zh: s.zh },
  lt => { (SHOT[i])(lt, s.to - s.from, s.from + lt); CAM = null; flushLetters(); filmSubs(s.from + lt, s); }));
