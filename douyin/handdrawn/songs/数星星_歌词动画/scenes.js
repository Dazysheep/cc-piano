// 《你有多久没有抬起头认真的数过星星》歌词动画（全手绘，剧本 output/writer/<歌>/lyric_v3.json）——15 个关键节点 node_01…node_15。
// v2（2026-10-29，用户：背景饱满一点、增加叙事性和小细节）：每张画远 / 中 / 近三层，加生活小物件；
// 贯穿线索：① 一只纸飞机从开头飞到结尾；② 「今年最大的愿望是能够养一只猫」——猫在路边、窗台反复出现，最后真的陪他数星星；
// ③ 手机前半段一直亮着，抬头以后放下了。字幕用手写体「站酷快乐体」，按分镜表的位置，唱过的字变暖黄。

const N = { w: 1920, h: 1080, dur: 3, bpm: 107.7, off: 1.579 };
const C = { night: '#1E2350', neon1: '#FF5C8A', neon2: '#3ED6E8', neon3: '#FFC24B', sepia: '#E9CFA0', sepiaDk: '#B98E5A',
            grass: '#3E6B4A', star: '#FFE9A8', wood: '#9A6B47', woodDk: '#7A5236' };
const PEOPLE = ['#7FA7D9', '#9BC48B', '#C9A0DC', '#E8B86B', '#8FC9C2', '#D98C8C', '#A7A7B8', '#E0A3B8'];
const HAND = s => `${s}px "ZCOOL KuaiLe", "KaiTi", cursive`;

// ---------- 字幕 ----------
const SUBPOS = { top: [960, 110], bottom: [960, 985], left: [330, 540], right: [1590, 540], top_left: [520, 120], top_right: [1400, 120],
                 bottom_left: [520, 975], bottom_right: [1400, 975], center: [960, 540] };
function subtitle(txt, pos, k, size = 64) {
  if (!txt) return;
  const [x, y] = SUBPOS[pos] || SUBPOS.bottom, parts = txt.split('，'), n = txt.replace(/，/g, '').length;
  let sung = Math.floor(k * n);
  parts.forEach((p, i) => {
    const yy = y + (i - (parts.length - 1) / 2) * size * 1.25, done = Math.max(0, Math.min(p.length, sung)); sung -= p.length;
    letter(p, x, yy, size, PAL.cream, { screen: true, ink: false, stroke: 'rgba(43,34,51,.9)', font: HAND(size) });
    if (done > 0) letter(p, x, yy, size, '#FFD36B', { screen: true, ink: false, stroke: 'rgba(43,34,51,.9)', font: HAND(size), clipChars: done });
  });
}
const NODEFN = {};      // 不带字幕的画面本体，全片（film.js）拿来当布景复用
function node(id, zh, line, pos, fn) { NODEFN[id] = fn; scene(id, { ...N, zh }, t => { fn(t); subtitle(line, pos, Math.min(1, .35 + t * .2)); }); }

// ---------- 通用小物件 ----------
function bg(col, col2, op = 120) { paint(rectPts(-40, -40, W + 80, H + 80), { wash: col, fill: col2 || col, fillOp: op, tex: .6, ink: null }); }
const shade = (c, k = .35) => mixCol(c, PAL.ink, k);
function person(x, y, u, i, t, o = {}) {
  const col = o.col || PEOPLE[i % PEOPLE.length];
  clawd(x, y, u, { col, dk: shade(col), lt: PAL.cream, eyes: 'normal', mouth: hash(i) < .5 ? 'flat' : 'o', aL: .2 + .3 * Math.sin(t * 3 + i), aR: .2,
    flip: hash(i * 7) < .5, dy: -Math.abs(Math.sin(t * 2.5 + i)) * .12, noShadow: true, seed: i, ...o });
}
const phone = (glow = 1) => (u, sw) => {
  paint(rrPts(-.2 * u, -1.6 * u, 1.6 * u, 2.8 * u, .3 * u), { wash: '#3A3F55', ink: PAL.ink, sw: sw * .7 });
  paint(rrPts(0, -1.35 * u, 1.2 * u, 2.2 * u, .2 * u), { wash: mixCol('#20263A', '#BFE3FF', glow), ink: null });
};
const bag = col => (u, sw) => paint(rrPts(-.6 * u, 0, 1.6 * u, 1.9 * u, .3 * u), { wash: col, fill: PAL.ink, fillOp: 30, ink: PAL.ink, sw: sw * .6 });
const cup = (u, sw) => { paint(rrPts(-.1 * u, -1.4 * u, 1 * u, 1.4 * u, .2 * u), { wash: '#F2E6CC', ink: PAL.ink, sw: sw * .6 }); paint(rectPts(-.1 * u, -1 * u, 1 * u, .4 * u), { wash: '#B5703C', ink: null }); };
const backpack = col => (u, sw) => paint(rrPts(-6.6 * u, -7 * u, 2.4 * u, 4.4 * u, .6 * u), { wash: col, fill: PAL.ink, fillOp: 40, ink: PAL.ink, sw: sw * .8 });
function starAt(x, y, r, t, seed, k = 1) {
  if (k <= .02) return;
  const tw = .75 + .25 * Math.sin(t * 4 + seed * 9);
  paint(ellPts(x, y, r * 2.3 * k, r * 2.3 * k, 14), { fill: C.star, fillOp: 50, bleed: .3, ink: null });
  paint(starPts(x, y, r * tw * k, .32, 4), { wash: C.star, ink: PAL.ink, sw: .4 });
}
function paperPlane(x, y, s = 1, rot = 0, col = PAL.cream) { return tagged('props', () => paperPlaneRaw(x, y, s, rot, col)); }
function paperPlaneRaw(x, y, s = 1, rot = 0, col = PAL.cream) {     // 贯穿全片的纸飞机
  push(); translate(x, y); rotate(rot); scale(s);
  paint([[60, 0], [-50, -26], [-30, 0]], { wash: col, ink: PAL.ink, sw: .8 });
  paint([[60, 0], [-30, 0], [-50, 24]], { wash: mixCol(col, '#C9BFA8', .4), ink: PAL.ink, sw: .8 });
  pop();
}
function cat(x, y, s = 1, o = {}) { return tagged('others', () => catRaw(x, y, s, o)); }
function catRaw(x, y, s = 1, o = {}) {                         // 贯穿全片的小猫（灰白）
  push(); translate(x, y); scale(o.flip ? -s : s, s);
  const body = o.col || '#E9E4DA';
  paint(ellPts(0, -34, 46, 34, 18), { wash: body, ink: PAL.ink, sw: .8 });
  paint(ellPts(34, -70, 28, 25, 16), { wash: body, ink: PAL.ink, sw: .8 });
  for (const ex of [20, 46]) paint([[ex - 10, -86], [ex - 4, -106], [ex + 4, -88]], { wash: body, ink: PAL.ink, sw: .7 });
  if (o.sleep) for (const ex of [26, 42]) inkLine([[ex - 5, -70], [ex + 5, -70]], .6, PAL.ink, 'inkfine', 0);
  else for (const ex of [26, 42]) paint(ellPts(ex, -71, 3.5, 4.5, 8), { wash: PAL.ink, ink: null });
  inkLine([[-44, -36], [-70, -60 + 8 * Math.sin((o.t || 0) * 3)], [-64, -84]], 1.1, PAL.ink, 'ink', .6);
  paint(ellPts(10, -14, 16, 7, 8), { wash: '#C9C2B6', ink: null });
  pop();
}
function board(txt, x, y, w, h, bgc, fg = PAL.ink, size = 30, rot = 0) {
  push(); translate(x, y); rotate(rot); paint(rrPts(-w / 2, -h / 2, w, h, 8), { wash: bgc, ink: PAL.ink, sw: .8 }); pop();
  letter(txt, x, y + 2, size, fg, { ink: false, font: HAND(size), rot });
}
function poster(x, y, w, h, col, draw) {
  paint(rectPts(x, y, w, h, 2), { wash: col, fill: shade(col, .15), fillOp: 60, ink: PAL.ink, sw: .8 });
  for (const [px, py] of [[x + 8, y + 8], [x + w - 8, y + 8]]) paint(ellPts(px, py, 4, 4, 6), { wash: '#C8323C', ink: null });
  if (draw) draw(x, y, w, h);
}
function clock(x, y, r, hh, mm, face = PAL.cream) {
  paint(ellPts(x, y, r, r, 20), { wash: face, ink: PAL.ink, sw: .9 });
  const a = (hh % 12 + mm / 60) / 12 * TAU - Math.PI / 2, b = mm / 60 * TAU - Math.PI / 2;
  inkLine([[x, y], [x + Math.cos(a) * r * .5, y + Math.sin(a) * r * .5]], 1.2, PAL.ink, 'ink', 0);
  inkLine([[x, y], [x + Math.cos(b) * r * .8, y + Math.sin(b) * r * .8]], .8, PAL.ink, 'ink', 0);
}
function plant(x, y, s = 1) {
  paint(rrPts(x - 26 * s, y - 40 * s, 52 * s, 40 * s, 6), { wash: '#C46B4A', ink: PAL.ink, sw: .7 });
  for (let i = 0; i < 5; i++) { const a = -Math.PI / 2 + (i - 2) * .45; paint(ellPts(x + Math.cos(a) * 34 * s, y - 40 * s + Math.sin(a) * 40 * s, 12 * s, 26 * s, 10, 0, a + Math.PI / 2), { wash: '#6E9F58', ink: PAL.ink, sw: .5 }); }
}
function tree(x, y, s = 1, col = '#6E9F58') {
  paint(rectPts(x - 12 * s, y - 120 * s, 24 * s, 120 * s, 2), { wash: C.woodDk, ink: PAL.ink, sw: .7 });
  for (const [dx, dy, r] of [[0, -170, 80], [-60, -130, 60], [60, -130, 60]]) paint(ellPts(x + dx * s, y + dy * s, r * s, r * .85 * s, 16), { wash: col, fill: shade(col, .2), fillOp: 70, tex: .6, ink: PAL.ink, sw: .6 });
}
function tower(x, w, h, col, seed, lit = .3, neon = null, base = H) {
  paint(rectPts(x, base - h, w, h + 40, 3), { wash: col, fill: PAL.ink, fillOp: 50, tex: .6, ink: PAL.ink, sw: .9 });
  const cols = Math.max(2, Math.floor(w / 60)), rows = Math.max(2, Math.floor(h / 70));
  for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) if (hash(seed * 31 + i * 7 + j * 13) < lit)
    paint(rectPts(x + 18 + i * (w - 36) / cols, base - h + 22 + j * (h - 40) / rows, 28, 34, 1.5), { wash: hash(i + j + seed) < .2 ? '#9FD0FF' : '#FFD27A', washOp: 220, ink: null });
  if (neon) { paint(rrPts(x + w * .15, base - h + 40, w * .7, 60, 14), { wash: neon, ink: PAL.ink, sw: .8 }); paint(ellPts(x + w / 2, base - h + 70, w * .6, 90, 18), { fill: neon, fillOp: 60, bleed: .3, ink: null }); }
}
function wires(y0, n = 3, sag = 40) { for (let i = 0; i < n; i++) inkLine([[-40, y0 + i * 18], [W / 2, y0 + i * 18 + sag], [W + 40, y0 + i * 18]], .7, PAL.ink, 'inkfine', .8); }
function windowFrame(x, y, w, h, sky, draw) {
  paint(rectPts(x, y, w, h, 2), { wash: sky, fill: shade(sky, .2), fillOp: 60, ink: PAL.ink, sw: 1.1 });
  if (draw) draw(x, y, w, h);
  inkLine([[x + w / 2, y], [x + w / 2, y + h]], 1, PAL.ink, 'ink', 0); inkLine([[x, y + h / 2], [x + w, y + h / 2]], 1, PAL.ink, 'ink', 0);
  paint(rectPts(x - 14, y + h, w + 28, 16, 1), { wash: C.wood, ink: PAL.ink, sw: .8 });
}

// 1 低头挤地铁（第 1 句）：车厢里的广告、线路图、时钟 07:58、窗外隧道灯；有人吃包子、有人戴耳机、有人拎公文包；地上一张掉落的纸飞机
node('node_01', '低头挤地铁', '早高峰的地铁今天又有多少人没赶上', 'top', t => {
  bg('#A3AFC0', '#8794A9');
  paint(rectPts(-40, 170, W + 80, 40, 2), { wash: '#C9CED8', ink: PAL.ink, sw: .8 });                      // 线路图条
  for (let i = 0; i < 12; i++) { const x = 120 + i * 150; paint(ellPts(x, 190, 9, 9, 8), { wash: i === 5 ? '#E8473C' : PAL.cream, ink: PAL.ink, sw: .6 }); if (i) inkLine([[x - 141, 190], [x - 9, 190]], 1.4, '#3E8E5A', 'ink', 0); }
  poster(40, 230, 260, 150, '#F2D6A2', (x, y) => letter('早起的人', x + 130, y + 75, 36, PAL.ink, { ink: false, font: HAND(36) }));
  poster(1620, 230, 260, 150, '#BFD9E6', (x, y) => { letter('买房？', x + 130, y + 60, 34, PAL.ink, { ink: false, font: HAND(34) }); letter('首付只要…', x + 130, y + 105, 24, '#7A6B5A', { ink: false, font: HAND(24) }); });
  paint(rectPts(340, 240, 1240, 230, 3), { wash: '#2B3048', fill: '#1B1F33', fillOp: 120, ink: PAL.ink, sw: 1 });   // 车窗
  for (let i = 0; i < 6; i++) inkLine([[340 + ((i * 260 + t * 700) % 1240), 330], [340 + ((i * 260 + t * 700) % 1240) + 110, 330]], 2, '#FFE3A0', 'dry', 0);
  for (let i = 0; i < 3; i++) paint(ellPts(560 + i * 400, 400, 60, 50, 14), { fill: '#46507A', fillOp: 90, bleed: .3, ink: null });   // 窗上映出的人影
  clock(1500, 110, 34, 7, 58);
  for (const x of [330, 960, 1590]) inkLine([[x, 210], [x, 1000]], 2.2, '#C9CED8', 'ink', 0);
  for (let i = 0; i < 10; i++) { const x = 140 + i * 185, sw = 6 * Math.sin(t * 2 + i); inkLine([[x, 215], [x + sw, 520]], .8, PAL.ink, 'inkfine', 0); paint(ellPts(x + sw, 538, 16, 16, 12), { ink: PAL.ink, sw: .9 }); }
  paint(rectPts(-40, 1010, W + 80, 100, 2), { wash: '#6E7787', ink: null });
  person(160, 1000, 25, 1, t, { aR: 1.1, armR: cup });
  person(400, 1000, 27, 2, t, { eyes: 'closed', draw: (u, sw) => { inkLine([[-5 * u, -6 * u], [0, -9 * u], [5 * u, -6 * u]], sw * 1.4, '#2B2233', 'ink', .6); for (const s of [-1, 1]) paint(ellPts(s * 5.1 * u, -5.6 * u, .7 * u, 1 * u, 10), { wash: '#2B2233', ink: null }); } });
  person(660, 1000, 24, 3, t, { aL: -.4, armL: bag('#5E4A3A') });
  person(1260, 1000, 26, 4, t, { eyes: 'look', lookY: 1, aR: .9, armR: phone(.8) });
  person(1500, 1000, 24, 5, t, { emote: 'zzz', emoteK: .8, eyes: 'closed' });
  person(1760, 1000, 27, 6, t, {});
  clawd(960, 1010, 34, { eyes: 'look', lookY: 1, mouth: 'flat', aR: .9, aL: -.3, armR: phone(1), emote: 'sweat', emoteK: .8, noShadow: true, draw: backpack('#C0504D') });
  paperPlane(1130, 1050, .55, .3);
});
// 2 车门各奔东西（第 6 句）：站台出口指示牌 A/B、黄色安全线、站名牌、广告灯箱；人潮分两股，门外的光；纸飞机被气流卷起
node('node_02', '车门各奔东西', '车门打开就会各奔东西', 'top', t => {
  bg('#E9E2D2', '#D9CDB4');
  const open = ease(clamp(t / 1.5)) * 520;
  paint(rectPts(400, 160, 1120, 900, 3), { wash: '#FFF3D0', fill: '#FFE3A0', fillOp: 140, bleed: .2, ink: null });
  paint(rectPts(420, 860, 1080, 26, 1), { wash: '#F2C53D', ink: PAL.ink, sw: .6 });                                     // 安全线
  board('出口 A  公司 →', 700, 330, 360, 64, '#2F6F5A', PAL.cream, 34); board('← 出口 B  学校', 1220, 330, 360, 64, '#2F4F8F', PAL.cream, 34);
  board('人 民 广 场', 960, 230, 300, 56, PAL.cream, PAL.ink, 32);
  for (let i = 0; i < 7; i++) { const x = 480 + i * 160; paint(ellPts(x, 640, 60, 230, 12), { fill: '#FFF8E0', fillOp: 40, bleed: .3, ink: null }); }   // 光束
  paint(rectPts(400 - open, 160, 560, 900, 3), { wash: '#B9C2CF', fill: '#8F99A8', fillOp: 70, ink: PAL.ink, sw: 1.2 });
  paint(rectPts(960 + open, 160, 560, 900, 3), { wash: '#B9C2CF', fill: '#8F99A8', fillOp: 70, ink: PAL.ink, sw: 1.2 });
  for (const x of [520 - open, 1080 + open]) { paint(rrPts(x, 300, 320, 260, 20), { wash: '#2B3048', ink: PAL.ink, sw: .8 }); paint(rectPts(x + 40, 620, 240, 60, 2), { wash: '#F2D6A2', ink: PAL.ink, sw: .6 }); }
  [[230, 1], [360, 3], [500, 5]].forEach(([x, i]) => person(x, 1010, 25, i, t, { walk: t * 2, flip: true, armL: i === 3 ? bag('#4A4A5A') : undefined }));
  [[1420, 2], [1560, 4], [1700, 6]].forEach(([x, i]) => person(x, 1010, 25, i, t, { walk: t * 2, flip: false, draw: backpack(PEOPLE[(i + 3) % 8]) }));
  for (const s of [-1, 1]) inkLine([[960 + s * 200, 780], [960 + s * 520, 780], [960 + s * 480, 740]], 3, PAL.ink, 'ink', .2);
  clawd(960, 1010, 36, { walk: t * 2, eyes: 'look', lookY: .3, mouth: 'o', aL: .4, aR: .4, emote: '?', emoteK: 1, draw: backpack('#C0504D') });
  paperPlane(1100 + t * 90, 560 - t * 60, .6, -.4 + .2 * Math.sin(t * 4));
});
// 3 圈外的 CC（第 13 句）：街边便利店和公交站，围成圈的人举着手机对他拍；地上的影子拉长；路灯杆上贴着寻猫启事（猫的伏笔）
node('node_03', '圈外的CC', '也逐渐成了别人口中厌恶的对象', 'bottom', t => {
  bg('#D9D3C8', '#C4BBAD');
  paint(rectPts(-40, 180, 820, 560, 3), { wash: '#E6D3B3', fill: '#CDB892', fillOp: 70, ink: PAL.ink, sw: 1 });           // 便利店
  board('24 小时便利店', 370, 230, 420, 70, '#3E8E5A', PAL.cream, 38);
  paint(rectPts(40, 300, 700, 330, 2), { wash: '#BFE0E6', fill: '#9FCAD3', fillOp: 70, ink: PAL.ink, sw: .8 });
  for (let i = 0; i < 4; i++) for (let j = 0; j < 3; j++) paint(rectPts(70 + i * 170, 320 + j * 100, 130, 14, 1), { wash: '#C9A06C', ink: null });
  paint(rectPts(1300, 300, 460, 360, 2), { wash: '#C9D6E6', fill: '#9FB2CC', fillOp: 50, ink: PAL.ink, sw: .9 });          // 公交站
  board('公交站  12 路', 1530, 270, 300, 56, '#2F4F8F', PAL.cream, 30);
  inkLine([[1840, 180], [1840, 820]], 2.2, '#555', 'ink', 0);
  paint(rectPts(1790, 420, 100, 130, 2), { wash: PAL.cream, ink: PAL.ink, sw: .7 }); letter('寻猫', 1840, 450, 26, '#C8323C', { ink: false, font: HAND(26) }); cat(1840, 540, .5);
  paint(rectPts(-40, 760, W + 80, 360, 2), { wash: '#B8AE9E', fill: '#A39885', fillOp: 70, ink: null });
  const cx = 760, cy = 760;
  paint(ellPts(cx, cy + 140, 520, 110, 30), { fill: PAL.ink, fillOp: 50, bleed: .2, ink: null });
  for (let i = 0; i < 7; i++) {
    const a = i / 7 * TAU, x = cx + Math.cos(a) * 380, y = cy + 110 + Math.sin(a) * 80;
    person(x, y, 22, i, t, { eyes: 'narrow', mouth: 'o', aR: 1.1, aL: .1, flip: Math.cos(a) > 0, armR: i % 2 ? phone(.9) : undefined });
    paint(ellPts(x + 30, y - 250, 46, 30, 14), { wash: PAL.cream, ink: PAL.ink, sw: .7 }); letter(['…', '啧', '?', '…'][i % 4], x + 30, y - 252, 30, PAL.ink, { ink: false, font: HAND(30) });
  }
  paint([[1500, 925], [1880, 945], [1880, 975], [1500, 940]], { fill: PAL.ink, fillOp: 40, bleed: .2, ink: null });                                     // 拉长的影子
  clawd(1560, 920, 26, { eyes: 'look', lookY: 1, lookX: -.6, mouth: 'wobble', aL: -.6, aR: -.6, emote: 'sweat', emoteK: 1, sq: .05, draw: backpack('#C0504D') });
});
// 4 点燃烦心事（第 20 句）：深夜书桌，台灯、满墙便利贴（加班 / 房租 / 体检 / DDL）、凌晨 2:13 的闹钟、冷掉的外卖盒；纸被点着，烟变乌云
node('node_04', '点燃烦心事', '总是点燃烦心事抽进肺里', 'top_left', t => {
  bg('#3A3550', '#2A2640');
  windowFrame(1380, 160, 420, 360, '#1E2350', (x, y, w, h) => { tower(x + 20, 120, 220, '#2A2840', 31, .4, null, y + h); tower(x + 180, 160, 300, '#2A2840', 32, .3, null, y + h); paint(ellPts(x + 330, y + 70, 30, 30, 14), { wash: '#FFF2C4', ink: PAL.ink, sw: .6 }); });
  [['加班', '#FFE07A', 120, 200], ['房租', '#FFB3B3', 300, 170], ['DDL!!', '#B3E5FF', 470, 230], ['体检', '#C9F2B3', 180, 360], ['回消息', '#FFD1A3', 380, 330], ['周报', '#E5C9FF', 560, 380]]
    .forEach(([s, c, x, y], i) => { push(); translate(x, y); rotate((hash(i) - .5) * .3); paint(rectPts(-70, -55, 140, 110, 1), { wash: c, ink: PAL.ink, sw: .6 }); pop(); letter(s, x, y, 30, PAL.ink, { ink: false, font: HAND(30), rot: (hash(i) - .5) * .3 }); });
  paint(rectPts(80, 820, 1760, 50, 2), { wash: C.wood, fill: C.woodDk, fillOp: 80, ink: PAL.ink, sw: 1 });              // 书桌
  paint(ellPts(560, 480, 260, 300, 22), { fill: '#FFC27A', fillOp: 50, bleed: .3, ink: null });                       // 台灯光
  inkLine([[460, 820], [460, 640], [560, 520]], 2, '#2C2C33', 'ink', .3); paint([[500, 520], [640, 520], [600, 470], [540, 470]], { wash: '#E8A55A', ink: PAL.ink, sw: .8 });
  clock(1600, 780, 40, 2, 13, '#F2E6CC');
  paint(rrPts(1280, 750, 160, 70, 10), { wash: '#F2F2EE', ink: PAL.ink, sw: .7 }); inkLine([[1300, 760], [1420, 760]], .6, '#B5703C', 'dry', 0);   // 冷掉的外卖盒
  paint(ellPts(1460, 800, 60, 18, 14), { wash: '#BFD9E6', ink: PAL.ink, sw: .6 });
  paint(ellPts(1100, 600, 380, 260, 24), { fill: '#FF9A4D', fillOp: 30 + 20 * Math.sin(t * 6), bleed: .3, ink: null });
  clawd(1100, 830, 32, { eyes: 'narrow', mouth: 'flat', aL: .9, aR: .9, noShadow: true });
  push(); translate(1100, 470); rotate(-.06);
  paint(rectPts(-160, -110, 320, 210, 2), { wash: '#F2E6CC', ink: PAL.ink, sw: .9 });
  ['烦', '累', '比', '急'].forEach((s, i) => letter(s, -110 + i * 72, -20 + 18 * Math.sin(i), 40, '#8C7B66', { ink: false, font: HAND(40) }));
  pop();
  const f = 1 + .15 * Math.sin(t * 9);
  paint([[1170, 380], [1220, 280 - 60 * f], [1250, 330], [1280, 240 - 40 * f], [1320, 380]], { wash: '#FF8A3D', fill: '#FFD06B', fillOp: 120, ink: PAL.ink, sw: .7, curv: .6 });
  for (let i = 0; i < 3; i++) { const k = (t * .5 + i / 3) % 1; paint(ellPts(1250 + 60 * Math.sin(i + t), 230 - k * 200, 60 + k * 70, 34 + k * 40, 16), { wash: '#4A4660', washOp: 200 * (1 - k * .6), fill: '#2E2A40', fillOp: 90, ink: PAL.ink, sw: .5 }); }
});
// 5 停下奔跑（第 22 句）：健身房一样的「生活跑步机」——墙上划满叉的日历、写着「冲」的标语、水杯毛巾；窗外城市飞逝；他突然停下看向我们
node('node_05', '停下奔跑', '可究竟什么时候我们才能停止奔跑', 'top', t => {
  bg('#CFD6DE', '#B4BECB');
  paint(rectPts(260, 200, 1400, 380, 3), { wash: '#8FA3BC', fill: '#6F86A3', fillOp: 90, ink: PAL.ink, sw: 1 });
  for (let i = 0; i < 9; i++) { const x = ((i * 220 - t * 900) % 1600 + 1600) % 1600 + 180; paint(rectPts(x, 330 + 60 * hash(i), 80, 250, 2), { wash: '#55667F', ink: null }); }
  for (let i = 0; i < 5; i++) inkLine([[300, 260 + i * 60], [1620, 260 + i * 60]], .6, '#E8EEF5', 'dry', 0);
  poster(40, 220, 190, 250, PAL.cream, (x, y) => { for (let i = 0; i < 5; i++) for (let j = 0; j < 4; j++) { const cx = x + 30 + i * 32, cy = y + 60 + j * 44; inkLine([[cx - 10, cy - 10], [cx + 10, cy + 10]], .7, '#C8323C', 'inkfine', 0); inkLine([[cx + 10, cy - 10], [cx - 10, cy + 10]], .7, '#C8323C', 'inkfine', 0); } letter('10月', x + 95, y + 28, 26, PAL.ink, { ink: false, font: HAND(26) }); });
  board('冲！别停！', 1790, 300, 200, 70, '#E8473C', PAL.cream, 34, .08);
  paint(rrPts(560, 860, 800, 110, 30), { wash: '#3B3F52', fill: '#23263A', fillOp: 100, ink: PAL.ink, sw: 1.2 });
  for (let i = 0; i < 10; i++) inkLine([[600 + ((i * 80 + t * 300) % 720), 880], [600 + ((i * 80 + t * 300) % 720), 950]], .7, '#6B7088', 'inkfine', 0);
  inkLine([[1300, 860], [1360, 600], [1300, 590]], 2, PAL.ink, 'ink', .2);
  paint(rrPts(1330, 560, 70, 30, 6), { wash: '#2B3048', ink: PAL.ink, sw: .6 }); letter('99km', 1365, 576, 18, '#7FFFB0', { ink: false });
  paint(rrPts(1420, 900, 40, 80, 8), { wash: '#9FD0FF', ink: PAL.ink, sw: .6 }); inkLine([[1450, 860], [1520, 870], [1500, 940]], 6, PAL.cream, 'dry', .5);   // 水杯、毛巾
  paint(rectPts(-40, 960, W + 80, 140, 2), { wash: '#9AA5B4', ink: null });
  const stop = t > .8;
  clawd(960, 870, 36, stop ? { eyes: 'scared', mouth: 'O', aL: .6, aR: .6, emote: '!', emoteK: 1, draw: backpack('#C0504D') } : { ...move('run', t * 2), eyes: 'narrow', mouth: 'flat', draw: backpack('#C0504D') });
  if (stop) for (let i = 0; i < 4; i++) inkLine([[760 - i * 30, 700 + i * 40], [700 - i * 30, 700 + i * 40]], 1.2, PAL.ink, 'dry', 0);
});
// 6 第一次抬头（没有星）（第 26 句，副歌 1）：层层叠叠的楼、大广告屏、电线、红绿灯、车灯拖影、湿地面倒影；天空被灯光染成紫灰，月亮也只剩一圈光晕
node('node_06', '第一次抬头', '你有多久没有抬起头，认真地数过星星', 'bottom', t => {
  bg('#2A2245', '#43365F');
  paint(ellPts(960, 200, 900, 260, 24), { fill: '#6B4E7E', fillOp: 70, bleed: .35, ink: null });
  paint(ellPts(1280, 150, 90, 90, 18), { fill: '#C9B7D9', fillOp: 40, bleed: .4, ink: null });                     // 雾里的月亮
  tower(380, 200, 560, '#3E3658', 41, .2); tower(1180, 200, 600, '#3E3658', 42, .2);                                  // 远景
  tower(-20, 330, 820, '#2F2A44', 1, .3, C.neon1); tower(300, 260, 620, '#352E4C', 2, .35); tower(1380, 300, 760, '#2F2A44', 3, .3, C.neon2);
  tower(1660, 300, 880, '#3A3252', 4, .35, C.neon3);
  paint(rectPts(560, 300, 380, 220, 3), { wash: '#1B1830', ink: PAL.ink, sw: 1 }); paint(rectPts(580, 320, 340, 180, 2), { wash: '#FF7FA8', fill: '#7A3CFF', fillOp: 80, bleed: .2, ink: null });
  letter('新品上市', 750, 410, 48, PAL.cream, { ink: false, font: HAND(48) });                                          // 大广告屏
  wires(520, 3, 60);
  paint(rectPts(-40, 860, W + 80, 260, 3), { wash: '#24203A', ink: null });
  for (let i = 0; i < 6; i++) { const y = 900 + i * 22, x = ((i * 400 + t * 800) % 2400) - 300; inkLine([[x, y], [x + 260, y]], 2.5, i % 2 ? '#FF6B6B' : '#FFE3A0', 'dry', 0); }   // 车灯拖影
  for (let i = 0; i < 5; i++) paint(ellPts(200 + i * 380, 1000, 90, 14, 12), { fill: [C.neon1, C.neon2, C.neon3, '#FFD27A', C.neon1][i], fillOp: 50, bleed: .3, ink: null });   // 湿地面倒影
  inkLine([[1250, 860], [1250, 620]], 2, '#222', 'ink', 0); paint(rrPts(1225, 560, 50, 110, 10), { wash: '#222', ink: PAL.ink, sw: .6 });
  paint(ellPts(1250, 590, 14, 14, 10), { wash: '#FF4D4D', ink: null }); paint(ellPts(1250, 630, 14, 14, 10), { wash: '#553', ink: null });
  clawd(960, 880, 34, { eyes: 'look', lookY: -1, mouth: 'flat', aL: -.2, aR: -.2, rot: -.08, draw: backpack('#C0504D'), armR: phone(.5) });
  letter('?', 1090, 520, 70, '#B9C6FF', { ink: false, pop: 1, font: HAND(70) });
});
// 7 左手边的妈妈（第 40 句）：家里的餐桌——墙上的全家福和日历（「母亲节」画着圈）、窗台上的猫、电饭煲冒热气、两碗饭、门口两双拖鞋；她在他左手边（画面右）择菜
node('node_07', '左手边的妈妈', '可她每天始终坐在你的左手边', 'top', t => {
  bg('#F3D9A8', '#E7BE84');
  windowFrame(80, 230, 380, 300, '#F6B98A', (x, y, w, h) => { paint(ellPts(x + 280, y + 90, 40, 40, 14), { wash: '#FFE08A', ink: PAL.ink, sw: .6 }); tower(x + 20, 140, 120, '#C9886A', 51, .3, null, y + h); });
  cat(300, 528, .95, { sleep: true, t });
  poster(560, 220, 220, 170, '#FFF6E4', (x, y) => { [[60, 110, '#D99A76'], [120, 110, '#D97757'], [170, 120, '#8FA3BC']].forEach(([dx, dy, c], i) => paint(rectPts(x + dx - 22, y + dy - 30, 44, 30, 1), { wash: c, ink: PAL.ink, sw: .5 })); letter('全家福', x + 110, y + 150, 22, PAL.ink, { ink: false, font: HAND(22) }); });
  poster(1500, 200, 280, 230, PAL.cream, (x, y) => { letter('5 月', x + 140, y + 34, 30, '#C8323C', { ink: false, font: HAND(30) }); for (let i = 0; i < 7; i++) for (let j = 0; j < 4; j++) paint(rectPts(x + 20 + i * 36, y + 70 + j * 36, 26, 24, 1), { ink: PAL.ink, sw: .3 });
    paint(ellPts(x + 92, y + 118, 24, 20, 12), { ink: '#C8323C', sw: 1.2 }); letter('母亲节', x + 140, y + 210, 22, '#C8323C', { ink: false, font: HAND(22) }); });
  paint(ellPts(960, 300, 300, 200, 20), { fill: '#FFE7B0', fillOp: 110, bleed: .3, ink: null });
  inkLine([[960, 0], [960, 200]], 1.2, PAL.ink, 'ink', 0); paint([[880, 200], [1040, 200], [1000, 260], [920, 260]], { wash: '#E8A55A', ink: PAL.ink, sw: .9 });
  paint(rrPts(1600, 600, 150, 150, 30), { wash: '#F2F2EE', ink: PAL.ink, sw: .8 }); for (let i = 0; i < 3; i++) { const k = (t * .4 + i / 3) % 1; inkLine([[1660 + i * 14, 590 - k * 120], [1670 + i * 14 + 10 * Math.sin(t * 2 + i), 560 - k * 140]], 1.2 * (1 - k), '#FFFFFF', 'dry', .5); }   // 电饭煲
  paint(rectPts(360, 760, 1200, 60, 2), { wash: C.wood, fill: C.woodDk, fillOp: 90, ink: PAL.ink, sw: 1.1 });
  for (const x of [420, 1500]) paint(rectPts(x, 820, 40, 260, 1), { wash: C.woodDk, ink: PAL.ink, sw: .8 });
  for (const x of [880, 1040]) { paint(ellPts(x, 742, 54, 20, 14), { wash: '#F2F2EE', ink: PAL.ink, sw: .7 }); paint(ellPts(x, 732, 40, 12, 12), { wash: '#FFFDF5', ink: null }); }
  paint(ellPts(1320, 740, 90, 26, 16), { wash: '#F2F2EE', ink: PAL.ink, sw: .7 });
  for (let i = 0; i < 5; i++) paint(ellPts(1280 + i * 18, 728 - 8 * hash(i), 14, 8, 8), { wash: '#6E9F58', ink: null });
  for (const [x, c] of [[160, '#C8323C'], [260, '#2F4F8F']]) { paint(ellPts(x, 1040, 44, 16, 12), { wash: c, ink: PAL.ink, sw: .6 }); paint(ellPts(x + 70, 1046, 44, 16, 12), { wash: c, ink: PAL.ink, sw: .6 }); }   // 门口拖鞋
  clawd(1260, 760, 28, { col: '#D99A76', dk: '#AE6E50', lt: '#F2C1A2', eyes: 'happy', mouth: 'smile', aL: .8, aR: .6, noShadow: true, flip: true,
    draw: (u, sw) => { paint(rrPts(-3.2 * u, -4.6 * u, 6.4 * u, 2.7 * u, .5 * u), { wash: PAL.cream, ink: PAL.ink, sw: sw * .6 }); paint(ellPts(1.2 * u, -8.6 * u, 1.3 * u, 1 * u, 14), { wash: '#4A3428', ink: PAL.ink, sw: sw * .6 }); } });
  clawd(680, 760, 30, { eyes: 'look', lookY: 1, mouth: 'flat', aR: .9, aL: -.2, armR: phone(1), noShadow: true });
  letter('♥', 1260, 520, 40, '#E2476E', { ink: false, alpha: .6 + .4 * Math.sin(t * 3) });
});
// 8 一两颗星（第 50 句，副歌 2）：老楼顶——水箱、晾衣绳上的衣服、几盆花、天线；远处城市的灯；楼缝里第一次出现一两颗星
node('node_08', '一两颗星', '你有多久没有抬起头，认真地数过星星', 'top', t => {
  bg('#1E2350', '#2B3270');
  paint(ellPts(960, 820, 1100, 300, 30), { fill: '#5A4E8A', fillOp: 60, bleed: .35, ink: null });                  // 城市灯光映在天边
  tower(100, 260, 380, '#2F2C4A', 61, .4, null, 900); tower(420, 200, 300, '#2F2C4A', 62, .4, null, 900); tower(1300, 240, 360, '#2F2C4A', 63, .4, null, 900);
  tower(-20, 300, 760, '#2A2840', 11, .25); tower(1580, 360, 820, '#2A2840', 12, .25);
  paint(rectPts(-40, 880, W + 80, 240, 3), { wash: '#3A3650', fill: '#2A2840', fillOp: 80, ink: PAL.ink, sw: 1 });         // 楼顶
  paint(rrPts(1250, 640, 200, 240, 20), { wash: '#6E7787', fill: '#555E70', fillOp: 70, ink: PAL.ink, sw: 1 }); for (const x of [1270, 1430]) paint(rectPts(x, 880, 14, 30), { wash: '#444', ink: null });   // 水箱
  inkLine([[340, 700], [1100, 740]], .8, PAL.ink, 'inkfine', .3);
  [['#E27A92', 420], ['#8EC3E6', 560], ['#F2C53D', 700], ['#FFF5E2', 860]].forEach(([c, x], i) => { const sw = 6 * Math.sin(t * 2 + i); paint(rectPts(x + sw, 712 + i * 3, 90, 110 - 20 * (i % 2), 3), { wash: c, ink: PAL.ink, sw: .6 }); });   // 晾的衣服
  for (const x of [240, 320, 1700]) plant(x, 900, .9);
  inkLine([[1500, 880], [1500, 620], [1460, 640], [1540, 600]], 1.2, PAL.ink, 'ink', 0);                             // 天线
  starAt(960, 300, 26, t, 1); starAt(1080, 420, 15, t, 2, ease(seg(t, .6, 1.4)));
  clawd(960, 900, 32, { eyes: 'spark', mouth: 'o', aL: .3, aR: .3, rot: -.1, armR: phone(.2) });
  cat(760, 900, .95, { t });
});
// 9 旧纸回忆（第 58 句）：老式书桌——显示器里的小企鹅（不画商标）、磁带、随身听、贴满贴纸的笔袋、写歌的本子；墙上手绘乐队海报、窗外午后阳光；纸飞机停在桌角
node('node_09', '旧纸回忆', '那个时候微博没有清一色的控评', 'top', t => {
  bg(C.sepia, '#DDBB86', 150);
  for (let i = 0; i < 20; i++) paint(ellPts(hash(i) * W, hash(i + 3) * H, 40 + 80 * hash(i + 5), 30 + 60 * hash(i + 7), 12), { fill: C.sepiaDk, fillOp: 30, bleed: .3, ink: null });
  windowFrame(1420, 180, 400, 330, '#FFE7B0', (x, y, w, h) => { paint(ellPts(x + 80, y + 80, 50, 50, 16), { wash: '#FFD98A', ink: PAL.ink, sw: .6 }); tree(x + 280, y + h, .7, '#9BC48B'); });
  for (let i = 0; i < 4; i++) paint([[1420 + i * 40, 520], [900 + i * 60, 1080], [980 + i * 60, 1080]], { fill: '#FFF2C4', fillOp: 40, bleed: .2, ink: null });   // 午后阳光
  poster(80, 160, 260, 340, '#E8B86B', (x, y) => { letter('乐队', x + 130, y + 60, 40, PAL.ink, { ink: false, font: HAND(40) }); for (let i = 0; i < 3; i++) clawd(x + 60 + i * 70, y + 280, 8, { col: PEOPLE[i + 2], dk: shade(PEOPLE[i + 2]), noShadow: true, eyes: 'happy', aL: 1.2, aR: 1.2 }); });
  poster(1180, 220, 180, 220, '#BFE0D8', (x, y) => letter('2009', x + 90, y + 110, 40, PAL.ink, { ink: false, font: HAND(40) }));
  paint(rectPts(560, 300, 520, 420, 4), { wash: '#D8CDB4', fill: '#B7A98C', fillOp: 90, ink: PAL.ink, sw: 1.2 });
  paint(rectPts(610, 350, 420, 300, 3), { wash: '#BFE0D8', fill: '#8FC0B6', fillOp: 70, ink: PAL.ink, sw: .9 });
  paint(rectPts(720, 720, 200, 70, 2), { wash: '#C9BDA3', ink: PAL.ink, sw: .9 });
  const hop = Math.abs(Math.sin(t * 4)) * 14;
  paint(ellPts(820, 520 - hop, 70, 85, 18), { wash: '#2B2233', ink: PAL.ink, sw: .8 }); paint(ellPts(820, 545 - hop, 48, 62, 16), { wash: PAL.cream, ink: null });
  for (const ex of [796, 844]) paint(ellPts(ex, 480 - hop, 9, 11, 10), { wash: PAL.cream, ink: null });
  paint([[804, 505 - hop], [836, 505 - hop], [820, 522 - hop]], { wash: '#F2B63D', ink: PAL.ink, sw: .5 });
  paint(rectPts(400, 820, 1100, 50, 2), { wash: '#A47A52', ink: PAL.ink, sw: 1 });
  paint(rectPts(430, 770, 120, 50, 3), { wash: '#3B3F52', ink: PAL.ink, sw: .7 }); for (const x of [462, 518]) paint(ellPts(x, 795, 12, 12, 10), { wash: PAL.cream, ink: PAL.ink, sw: .4 });   // 磁带
  paint(rrPts(1000, 760, 150, 60, 14), { wash: '#E27A92', ink: PAL.ink, sw: .7 }); for (let i = 0; i < 3; i++) paint(starPts(1030 + i * 45, 790, 12, .4, 5), { wash: ['#FFE07A', '#8EC3E6', PAL.cream][i], ink: null });   // 贴满贴纸的笔袋
  clawd(1300, 830, 26, { eyes: 'happy', mouth: 'smile', aR: 1.1, aL: .2, noShadow: true, armR: (u, sw) => inkLine([[0, 0], [1.6 * u, -1.8 * u]], sw * 1.4, '#C8742E', 'ink', 0),
    draw: (u, sw) => { inkLine([[-5 * u, -6 * u], [0, -9 * u], [5 * u, -6 * u]], sw * 1.2, '#2B2233', 'ink', .6); for (const s of [-1, 1]) paint(ellPts(s * 5.1 * u, -5.6 * u, .6 * u, .9 * u, 10), { wash: '#E27A92', ink: null }); } });
  paint(rectPts(1180, 760, 240, 60, 2), { wash: '#F6EEDC', ink: PAL.ink, sw: .7 }); inkLine([[1200, 790], [1300 + 80 * clamp(t / 2), 788]], .9, PAL.ink, 'inkfine', .4);
  letter('♪', 1250, 700 - t * 30, 40, PAL.ink, { ink: false, alpha: .8 });
  paperPlane(1470, 810, .45, -.2);
});
// 10 扶起老人（第 62 句）：老街——小卖部招牌、自行车、大树、鸽子、掉了一地的橘子；老奶奶的拐杖；猫在台阶上看着
node('node_10', '扶起老人', '看到老人跌倒你也不会躲远', 'top_left', t => {
  bg('#EED7A8', '#E2BF80', 140);
  paint(ellPts(1550, 220, 140, 140, 20), { wash: '#FFD98A', fill: '#FFB86B', fillOp: 90, ink: PAL.ink, sw: .8 });
  paint(rectPts(80, 300, 600, 480, 3), { wash: '#E6C99A', fill: '#CDA875', fillOp: 70, ink: PAL.ink, sw: 1 });              // 小卖部
  board('小 卖 部', 380, 340, 360, 70, '#C8323C', PAL.cream, 40);
  paint(rectPts(130, 420, 500, 260, 2), { wash: '#B8D8D0', fill: '#9FC0B6', fillOp: 60, ink: PAL.ink, sw: .8 });
  for (let i = 0; i < 6; i++) paint(rrPts(160 + i * 78, 560, 50, 90, 10), { wash: PEOPLE[i], ink: PAL.ink, sw: .5 });                // 汽水瓶
  paint(rectPts(130, 700, 500, 80, 2), { wash: '#A47A52', ink: PAL.ink, sw: .8 }); cat(540, 700, .9, { t });
  tree(1800, 860, 1.2, '#7FAE6A');
  for (let i = 0; i < 3; i++) { const x = 1300 + i * 80 + 20 * Math.sin(t * 2 + i), y = 300 + 20 * Math.sin(t * 3 + i * 2); inkLine([[x - 20, y], [x, y - 10], [x + 20, y]], 1, PAL.ink, 'ink', .5); }   // 鸽子
  paint(rectPts(-40, 820, W + 80, 300, 3), { wash: '#C9A06C', fill: '#B08454', fillOp: 70, ink: null });
  for (const [x, r] of [[1500, 34], [1620, 30]]) { paint(ellPts(x, 900, r, r, 12), { ink: PAL.ink, sw: 1.4 }); } inkLine([[1500, 900], [1560, 860], [1620, 900], [1580, 850], [1540, 850]], 1.2, '#2F4F8F', 'ink', 0);   // 自行车
  const up = ease(clamp(t / 2.2));
  for (let i = 0; i < 6; i++) paint(ellPts(560 + i * 50 + 80 * (1 - up) * hash(i), 900 + 20 * hash(i + 2), 16, 16, 10), { wash: '#FF9A3D', ink: PAL.ink, sw: .4 });   // 掉的橘子
  paint(rrPts(480, 860, 120, 70, 10), { wash: PAL.cream, ink: PAL.ink, sw: .6 });
  clawd(820, 860, 28, { col: '#A7A7B8', dk: '#7A7A8A', lt: '#D5D5E0', eyes: up > .6 ? 'happy' : 'closed', mouth: up > .6 ? 'smile' : 'o', rot: lerp(.5, 0, up), dy: lerp(.4, 0, up), aR: .8,
    draw: (u, sw) => paint(rrPts(-2.4 * u, -8.8 * u, 4.8 * u, 1 * u, .4 * u), { wash: '#E6E6EC', ink: PAL.ink, sw: sw * .5 }),
    armL: (u, sw) => inkLine([[0, 0], [.2 * u, 3.4 * u]], sw * 1.3, C.woodDk, 'ink', 0) });
  clawd(1120, 860, 30, { eyes: 'look', lookX: -1, mouth: 'smile', aL: 1.0, aR: .4, flip: true, draw: backpack('#2F6F5A') });
});
// 11 没有表情（第 66 句）：一排一模一样的灰色格子间、显示器、窗外下雨；每个人都在打同样的字；只有他胸口还有一点点橙色
node('node_11', '没有表情', '什么时候我们开始变得没有表情', 'top_right', t => {
  bg('#B9BAC0', '#9FA0A8');
  windowFrame(100, 150, 1720, 260, '#8D93A3', (x, y, w, h) => { for (let i = 0; i < 40; i++) { const rx = x + hash(i) * w, ry = y + ((hash(i + 9) * h + t * 300) % h); inkLine([[rx, ry], [rx - 6, ry + 24]], .5, '#E8EEF5', 'inkfine', 0); } });
  for (let i = 0; i < 6; i++) {
    const x = 120 + i * 300;
    paint(rectPts(x, 560, 260, 360, 2), { wash: '#C9CAD2', fill: '#A9AAB2', fillOp: 60, ink: PAL.ink, sw: .8 });          // 隔板
    paint(rectPts(x + 70, 640, 120, 90, 2), { wash: '#4A4C58', ink: PAL.ink, sw: .7 }); paint(rectPts(x + 80, 650, 100, 70, 1), { wash: '#9FD0E0', washOp: 140, ink: null });
    for (let j = 0; j < 3; j++) inkLine([[x + 90, 668 + j * 16], [x + 90 + 60 * hash(i + j + Math.floor(t * 4)), 668 + j * 16]], .5, '#4A4C58', 'inkfine', 0);
    if (i !== 3) person(x + 130, 900, 24, i, t, { col: '#A9AAB2', dk: '#86878F', eyes: 'dot', mouth: 'flat', aL: .6, aR: .6, dy: 0, flip: false });
  }
  clawd(1030, 900, 26, { col: mixCol('#D97757', '#A9AAB2', .6), dk: '#8E7D78', eyes: 'dot', mouth: 'flat', aL: .6, aR: .6, noShadow: true,
    draw: (u, sw) => paint(ellPts(0, -4.6 * u, .9 * u, .9 * u, 12), { wash: '#D97757', ink: null }) });
  paint(rectPts(-40, 920, W + 80, 200, 3), { wash: '#8E8F98', ink: null });
  clock(960, 480, 36, 5, 59, '#D5D6DC');
});
// 12 为你祈祷（第 77 句，情绪最高点）：夜空下的屋顶，女生 CC 合十，金色星尘从地面升起；远处城市一盏盏亮灯；纸飞机绕着两人飞
node('node_12', '为你祈祷', '愿你永远年轻', 'bottom', t => {
  bg('#2B2350', '#4A3672');
  for (let i = 0; i < 3; i++) paint(ellPts(300 + i * 700, 200 + 40 * i, 320, 70, 18), { fill: '#6B5A9A', fillOp: 50, bleed: .35, ink: null });
  tower(-20, 280, 300, '#2A2440', 71, .5, null, 900); tower(260, 220, 220, '#2A2440', 72, .5, null, 900); tower(1420, 260, 260, '#2A2440', 73, .5, null, 900); tower(1680, 280, 340, '#2A2440', 74, .5, null, 900);
  paint(rectPts(-40, 880, W + 80, 240, 3), { wash: '#3A3058', fill: '#2A2440', fillOp: 80, ink: PAL.ink, sw: 1 });
  paint(ellPts(960, 560, 620, 420, 26), { fill: '#FFCF7A', fillOp: 70, bleed: .35, ink: null });
  for (let i = 0; i < 30; i++) { const a = i * 2.4 + t * .6, r = 260 + 220 * hash(i); starAt(960 + Math.cos(a) * r, 560 + Math.sin(a) * r * .6 - t * 20 * hash(i), 7 + 8 * hash(i + 2), t, i, .9); }
  clawdGirl(760, 880, 30, { eyes: 'closed', mouth: 'smile', aL: 1.5, aR: 1.5, blush: true, emote: 'heart', emoteK: .8 });
  clawd(1160, 880, 30, { eyes: 'happy', mouth: 'wobble', aL: .3, aR: .3, flip: true, blush: true });
  tears(1160, 880, 30, (t * 1.2) % 1, true);
  const a = t * 1.2; paperPlane(960 + Math.cos(a) * 360, 600 + Math.sin(a) * 120, .6, a + Math.PI / 2);
});
// 13 满天星星（第 81 句，副歌 3）：山坡上的草地、远处小镇的灯、一颗流星、萤火虫；他张开双臂，手机丢在草地上
node('node_13', '满天星星', '你有多久没有抬起头，认真地数过星星', 'top', t => {
  bg('#141A44', '#22296A');
  paint(ellPts(980, 330, 980, 150, 30, 20, -.2), { fill: '#7A68C0', fillOp: 80, bleed: .35, tex: .8, ink: null });
  for (let i = 0; i < 80; i++) starAt(hash(i * 3) * W, 220 + hash(i * 5 + 1) * 480, 5 + 12 * Math.pow(hash(i * 11), 2), t, i, ease(seg(t, hash(i * 7) * 1.5, hash(i * 7) * 1.5 + .4)));
  const m = seg(t, 1, 2.2); if (m > 0 && m < 1) inkLine([[1500 - 600 * m, 260 + 200 * m], [1500 - 600 * m + 160, 260 + 200 * m - 50]], 2.5, '#FFF2C4', 'dry', 0);   // 流星
  paint(ellPts(400, 940, 900, 200, 30), { wash: '#24402F', fill: '#1E3527', fillOp: 90, ink: PAL.ink, sw: .8 });           // 远山
  for (let i = 0; i < 14; i++) paint(ellPts(220 + i * 40, 800 + 10 * hash(i), 5, 5, 8), { wash: '#FFD27A', ink: null });       // 小镇的灯
  paint(ellPts(960, 1060, 1300, 260, 30), { wash: '#2C4A3A', fill: C.grass, fillOp: 120, tex: .6, ink: PAL.ink, sw: .9 });
  for (let i = 0; i < 34; i++) inkLine([[40 + i * 56, 900 + 20 * hash(i)], [50 + i * 56, 868 + 10 * hash(i + 1)]], .7, '#6E9F78', 'inkfine', .4);
  for (let i = 0; i < 7; i++) { const x = 300 + i * 220 + 30 * Math.sin(t + i), y = 840 + 30 * Math.sin(t * 1.4 + i * 2); paint(ellPts(x, y, 8, 8, 10), { fill: '#E9F59A', fillOp: 120 * (.5 + .5 * Math.sin(t * 3 + i)), bleed: .3, ink: null }); }
  push(); translate(1120, 930); rotate(.3); phone(.1)(18, 1); pop();
  clawd(960, 900, 34, { eyes: 'spark', mouth: 'O', aL: 1.5, aR: 1.5, rot: -.06, draw: backpack('#C0504D') });
});
// 14 数星星（第 88 句）：铺着格子野餐垫的草地，他躺着伸手数，女生坐在旁边，猫蜷在他们中间（愿望实现了）；纸飞机飞向星海；星星连成线
node('node_14', '数星星', '多久没有抬起头，去倾听风的声音', 'bottom', t => {
  bg('#141A44', '#22296A');
  for (let i = 0; i < 60; i++) starAt(hash(i * 13) * W, 40 + hash(i * 17 + 1) * 520, 5 + 10 * Math.pow(hash(i * 19), 2), t, i);
  const pts = [[520, 240], [640, 180], [780, 230], [860, 160]], k = clamp(t / 2.5) * 3;                                     // 他指着连起来的星座
  for (let i = 0; i < 3; i++) if (k > i) inkLine([pts[i], [lerp(pts[i][0], pts[i + 1][0], clamp(k - i)), lerp(pts[i][1], pts[i + 1][1], clamp(k - i))]], .9, '#FFE9A8', 'inkfine', 0);
  paint(ellPts(960, 1000, 1400, 300, 30), { wash: '#2C4A3A', fill: C.grass, fillOp: 120, tex: .6, ink: PAL.ink, sw: .9 });
  push(); translate(960, 810); rotate(-.05); paint(rectPts(-420, -60, 840, 120, 3), { wash: '#E9E2D2', hatch: { d: 30, a: 0, b: 'HB', c: '#C8323C', w: .8 }, ink: PAL.ink, sw: .8 }); pop();   // 野餐垫
  push(); translate(760, 780); rotate(-Math.PI / 2 + .12);
  clawd(0, 0, 26, { eyes: 'look', lookX: 1, mouth: 'smile', aR: 1.4 + .25 * Math.sin(t * 5), aL: .1, noShadow: true });
  pop();
  cat(990, 800, 1.0, { sleep: true, t });
  clawdGirl(1220, 800, 26, { eyes: 'look', lookY: -1, mouth: 'smile', aL: .3, aR: .3, noShadow: true });
  const n = 1 + Math.floor(t * 2.5); letter(String(n), 600 + 40 * Math.sin(n), 330, 70, C.star, { ink: false, pop: (t * 2.5) % 1 * 2, font: HAND(70) });
  paperPlane(1300 + t * 160, 420 - t * 70, .7, -.4);
});
// 15 星星合上（尾奏）：白纸上，全片的小物件铅笔线稿一样淡淡浮现又收回——地铁车门、手机、日历、小企鹅、纸飞机、猫——最后只剩一颗星合上
node('node_15', '星星合上', '', 'center', t => {
  bg('#F3EBDC', '#E9DFC8', 60);
  const k = 1 - ease(clamp((t - .6) / 2)), fade = 1 - ease(clamp((t - .2) / 1.6));
  if (fade > .05) {
    const a = 255 * .35 * fade, ln = col => ({ ink: mixCol('#8C7B66', '#F3EBDC', 1 - fade), sw: .7 });
    paint(rectPts(220, 320, 160, 240, 2), ln()); paint(rectPts(400, 320, 160, 240, 2), ln());                               // 车门
    paint(rrPts(700, 700, 90, 150, 14), ln());                                                                              // 手机
    paint(rectPts(1300, 300, 200, 170, 2), ln());                                                                           // 日历
    paint(ellPts(1600, 720, 60, 75, 16), ln());                                                                             // 小企鹅
    void a;
  }
  cat(1240, 880, 1.0, { sleep: true });
  paint(ellPts(960, 520, 260 * k + 40, 260 * k + 40, 22), { fill: C.star, fillOp: 70, bleed: .35, ink: null });
  paint(starPts(960, 520, 170 * k + 30, .38, 5), { wash: '#FFD36B', fill: PAL.ochre, fillOp: 80, ink: PAL.ink, sw: 1.2 });
  paperPlane(700 + 260 * (1 - k), 820 - 200 * (1 - k), .7, -.5);
  inkLine([[300, 860], [960 - 600 * k, 860]], 1.2, PAL.ink, 'HB', 0);
  letter('抬头看看', 960, 860, 54, PAL.ink, { ink: false, font: HAND(54), alpha: ease(seg(t, 1.6, 2.4)) });
});
