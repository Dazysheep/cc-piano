// 《你有多久没有抬起头认真的数过星星》的手绘画面（2026-10-28）。每个场景 = 男生读完一条评论后，头顶云朵里浮现的那段往事，
// 按 2 倍尺寸画（1044×610），导出时缩成 522×305 放进云朵。时间 t 从云朵展开算起，场景放完停在最后一帧。
// 节拍：107.7 BPM（douyin 分析结果）。画面只为这首歌画，不复用旧的像素画面。

const V = { w: 1044, h: 610, dur: 12, bpm: 107.7, off: 0 };
const NIGHT = '#1E2350', NIGHT2 = '#2B3270', DUSK = '#5B4C8A', STAR = '#FFE9A8', LAMP = '#FFD27A';

// ---------- 小工具 ----------
function skyWash(top, bottom, op = 255) {
  paint(rectPts(-30, -30, W + 60, H * .62, 6), { wash: top, washOp: op, ink: null });
  paint(rectPts(-30, H * .45, W + 60, H * .7, 6), { wash: bottom, washOp: op, fill: top, fillOp: 70, bleed: .25, tex: .5, ink: null });
}
function star(x, y, r, t, seed, k = 1) {
  if (k <= .02) return;
  const tw = .7 + .3 * Math.sin(t * 4 + seed * 9);
  paint(ellPts(x, y, r * 2.2 * k, r * 2.2 * k, 14), { fill: STAR, fillOp: 45, bleed: .3, ink: null });
  paint(starPts(x, y, r * tw * backOut(k), .32, 4), { wash: STAR, washOp: 255, ink: PAL.ink, sw: .35 });
}
function moon(x, y, r) {
  paint(ellPts(x, y, r * 1.8, r * 1.8, 20), { fill: '#FFF2C4', fillOp: 50, bleed: .3, ink: null });
  paint(ellPts(x, y, r, r, 22), { wash: '#FFF2C4', ink: PAL.ink, sw: .7 });
  paint(ellPts(x + r * .45, y - r * .2, r * .85, r * .9, 22), { wash: NIGHT2, ink: null });
}
function building(x, w, h, col, seed, lit = .35) {
  const top = H - h;
  paint(rectPts(x, top, w, h + 20, 3), { wash: col, fill: PAL.ink, fillOp: 40, tex: .6, ink: PAL.ink, sw: .8 });
  const cols = Math.max(2, Math.floor(w / 46)), rows = Math.max(2, Math.floor(h / 58));
  for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
    const on = hash(seed * 31 + i * 7 + j * 13) < lit, wx = x + 14 + i * (w - 28) / cols, wy = top + 18 + j * (h - 30) / rows;
    paint(rectPts(wx, wy, 22, 26, 1.5), { wash: on ? LAMP : '#232744', washOp: on ? 235 : 200, ink: null });
  }
  for (let k = 0; k < 3; k++) inkLine([[x + w * .2 + k * 10, top + 6], [x + w * .2 + k * 10, top - 16]], .5, PAL.ink, 'inkfine', 0);  // 天线 / 晾衣杆
}
function lamp(x, y, h, on = 1) {
  inkLine([[x, y], [x, y - h], [x + 34, y - h - 6]], 1.4, PAL.ink, 'ink', .2);
  if (on > 0) paint([[x + 30, y - h + 4], [x - 30, y + 2], [x + 100, y + 2]], { wash: LAMP, washOp: 34 * on, ink: null });   // 淡淡的暖光，不要灰色光锥
  paint(ellPts(x + 36, y - h - 2, 12, 7, 10), { wash: on ? LAMP : '#555', ink: PAL.ink, sw: .5 });
}
const fanHook = (u, sw) => {               // 蒲扇
  paint(ellPts(1.2 * u, -1.6 * u, 1.5 * u, 1.7 * u, 16), { wash: '#E8C77A', fill: PAL.ochre, fillOp: 70, ink: PAL.ink, sw: sw * .6 });
  inkLine([[0, 0], [1.1 * u, -.4 * u]], sw * .8, '#8A5A2B', 'ink', 0);
};
const backpackDraw = col => (u, sw) => paint(rrPts(-6.6 * u, -7 * u, 2.4 * u, 4.4 * u, .6 * u), { wash: col, fill: PAL.ink, fillOp: 40, ink: PAL.ink, sw: sw * .8 });
const momDraw = (u, sw) => {                // 妈妈：围裙 + 头顶的发髻
  paint(rrPts(-3.2 * u, -4.6 * u, 6.4 * u, 2.7 * u, .5 * u), { wash: PAL.cream, fill: '#E9D7B8', fillOp: 70, ink: PAL.ink, sw: sw * .6 });
  paint(rrPts(-1 * u, -3.8 * u, 2 * u, 1.2 * u, .3 * u), { wash: '#F6C9D2', ink: PAL.ink, sw: sw * .4 });
  paint(ellPts(1.2 * u, -8.6 * u, 1.3 * u, 1 * u, 14), { wash: '#4A3428', ink: PAL.ink, sw: sw * .6 });
};

// ---------- 1. 夏夜凉席数星星，数着数着睡着了（开头：Gm仙「小时候夏天会数 数着数着就睡着了」） ----------
scene('summer_mat', { ...V, dur: 10, zh: '小时候夏夜躺凉席数星星，数着数着睡着了' }, t => {
  skyWash(NIGHT, '#33406E');
  paint(ellPts(840, 120, 230, 60, 20, 10), { fill: '#6C5CA8', fillOp: 60, bleed: .3, tex: .7, ink: null });      // 一抹银河
  const S = [[120, 90], [250, 160], [380, 70], [520, 130], [660, 60], [790, 150], [930, 95], [460, 210], [180, 230], [870, 230]];
  S.forEach(([x, y], i) => {
    const k = seg(t, .6 + i * .55, 1 + i * .55);
    star(x, y, 13 + 5 * hash(i), t, i, k);
    const age = t - (.6 + i * .55);
    if (age > 0 && age < 1.4 && t < 6.8) letter(String(i + 1), x + 30, y - 30, 52, '#FFE3A0', { pop: age * 3, alpha: 1 - seg(age, 1, 1.4), stroke: PAL.ink });
  });
  paint(rectPts(-30, 430, W + 60, 220, 6), { wash: '#2E4A3A', fill: '#1F3328', fillOp: 120, tex: .6, ink: null });     // 院子
  for (let i = 0; i < 9; i++) inkLine([[30 + i * 120, 445], [40 + i * 120, 420 - 12 * hash(i)]], .6, '#5E8B5A', 'inkfine', .4);
  push(); translate(520, 500); rotate(-.05);                                                                           // 凉席
  paint(rectPts(-330, -46, 660, 92, 3), { wash: '#D8B26A', hatch: { d: 14, a: Math.PI / 2, b: 'HB', c: '#9C7A3A', w: .6 }, ink: PAL.ink, sw: .8 });
  pop();
  const sleep = ease(seg(t, 6.6, 8.2));
  clawd(520, 488, 20, { eyes: sleep > .5 ? 'closed' : 'look', lookY: -1, lookX: .2 * Math.sin(t * .8), mouth: sleep > .5 ? 'o' : 'smile',
    rot: -sleep * .22, dy: sleep * .2, aR: lerp(.9 + .25 * Math.sin(t * 3), -.1, sleep), aL: lerp(1.2, -.2, sleep), armR: fanHook,
    emote: 'zzz', emoteK: seg(t, 8, 8.5) });
  // 萤火虫
  for (let i = 0; i < 5; i++) { const x = 140 + i * 190 + 30 * Math.sin(t * .9 + i), y = 380 + 25 * Math.sin(t * 1.3 + i * 2); paint(ellPts(x, y, 9, 9, 10), { fill: '#E9F59A', fillOp: 120 * (.5 + .5 * Math.sin(t * 3 + i)), bleed: .3, ink: null }); }
});

// ---------- 2. 黑屏里没有表情的自己，追不上的发光旧照片（13号女听客「追不上以前那个闪闪发光的自己了」） ----------
scene('black_mirror', { ...V, dur: 10, zh: '黑屏手机里没表情的自己，和飘远的闪闪发光的旧照片' }, t => {
  paint(rectPts(-30, -30, W + 60, H + 60), { wash: '#2A2740', fill: '#3A3358', fillOp: 90, tex: .6, ink: null });
  paint(ellPts(300, 300, 260, 220, 20), { fill: '#4C4570', fillOp: 70, bleed: .3, ink: null });
  // 手机（前景，大）
  push(); translate(330, 330); rotate(-.06);
  paint(rrPts(-150, -230, 300, 470, 34, 2), { wash: '#15161F', ink: PAL.ink, sw: 1.4 });
  paint(rrPts(-130, -205, 260, 420, 22, 2), { wash: '#1E2130', fill: '#2C3248', fillOp: 90, tex: .4, ink: null });
  inkLine([[-110, -190], [-40, -120]], .9, '#6B7290', 'dry', 0);                                                       // 屏幕反光
  pop();
  // 屏幕里映出的自己：没有表情（半透明的倒影）
  clawd(330, 470, 17, { eyes: 'dot', mouth: 'flat', aL: -.5, aR: -.5, col: '#5C5470', dk: '#463F5A', lt: '#6E6688', noLegs: true });
  // 发光的旧照片：从右边亮起，伸手去够，它却越飘越远
  const away = ease(seg(t, 5.5, 10)), px = lerp(720, 930, away), py = lerp(300, 150, away), ps = lerp(1, .55, away);
  const show = ease(seg(t, 1.2, 2.6));
  if (show > 0) {
    push(); translate(px, py); scale(ps * show); rotate(.08 + .04 * Math.sin(t * 1.4));
    paint(ellPts(0, 0, 230, 230, 22), { fill: PAL.ochre, fillOp: 60 + 30 * Math.sin(t * 3), bleed: .35, ink: null });
    paint(rectPts(-150, -170, 300, 330, 2), { wash: PAL.cream, ink: PAL.ink, sw: 1 });
    paint(rectPts(-125, -145, 250, 230, 2), { wash: '#9FD3F0', fill: '#FFE3A0', fillOp: 120, bleed: .2, tex: .5, ink: null });
    paint(ellPts(80, -95, 30, 30, 14), { wash: '#FFD45E', ink: PAL.ink, sw: .5 });
    clawd(-10, 70, 14, { eyes: 'spark', mouth: 'grin', aL: 1.5, aR: 1.5, dy: -Math.abs(Math.sin(t * 4)) * .5, noShadow: true });
    pop();
    for (let i = 0; i < 6; i++) { const a = i / 6 * TAU + t * .7, r = 190 * ps; star(px + Math.cos(a) * r, py + Math.sin(a) * r * .8, 9, t, i + 20, show); }
  }
  // 伸出去的手（手机后面的小人伸手）
  const reach = ease(seg(t, 4, 6)) * (1 - ease(seg(t, 8.5, 10)) * .6);
  clawd(560, 560, 12, { eyes: 'look', lookX: 1, lookY: -.6, mouth: 'flat', aR: .4 + reach * 1.1, aL: -.3, noShadow: true });
});

// ---------- 3. 上学天是黑的，放学天也是黑的（kgieusuis） ----------
scene('dark_both_ways', { ...V, dur: 12, zh: '上学天是黑的，放学天也是黑的' }, t => {
  const half = W / 2;
  for (const side of [0, 1]) {
    const x0 = side * half, show = ease(seg(t, side ? 4.5 : .2, side ? 6 : 1.5));
    if (show <= 0) { paint(rectPts(x0, -20, half, H + 40), { wash: '#141629', ink: null }); continue; }
    paint(rectPts(x0 - 10, -20, half + 20, H + 40, 3), { wash: side ? '#171A3A' : '#232A5C', fill: side ? NIGHT : '#3A4486', fillOp: 90, tex: .5, ink: null });
    if (side) moon(x0 + 400, 90, 34); else for (let i = 0; i < 4; i++) star(x0 + 70 + i * 110, 70 + 40 * hash(i + 4), 8, t, i + 40);
    paint(rectPts(x0 - 10, 470, half + 20, 160, 3), { wash: '#3B3A4A', ink: null });                                     // 路
    for (let i = 0; i < 4; i++) inkLine([[x0 + 30 + i * 140, 540], [x0 + 90 + i * 140, 540]], 1.2, '#E9DFC8', 'dry', 0);
    lamp(x0 + 90, 470, 230, 1); lamp(x0 + 380, 470, 230, 1);
    const walk = ((t - (side ? 4.5 : .2)) * .9) % 1, dir = side ? -1 : 1;
    const cx = side ? lerp(x0 + 440, x0 + 120, seg(t, 5, 12)) : lerp(x0 + 60, x0 + 400, seg(t, .5, 7));
    clawd(cx, 500, 13, { walk: walk * 3, flip: side === 1, eyes: side ? 'narrow' : 'look', lookY: 1, mouth: 'flat', dy: -Math.abs(Math.sin(walk * TAU)) * .3,
      draw: backpackDraw(side ? '#5E6FA8' : '#C0504D'), emote: side ? 'sweat' : null, emoteK: .8, noShadow: true });
    letter(side ? '放学 21:50' : '上学 6:10', x0 + half / 2, 560, 34, PAL.cream, { pop: show * 1.5, ink: true });
    void dir;
  }
  inkLine([[half, -20], [half, H + 20]], 2.2, PAL.ink, 'ink', 0);
  if (t > 9) letter('天都是黑的', W / 2, 300, 64, '#FFE3A0', { pop: (t - 9) * 2, rot: -.04 });
});

// ---------- 4. 拆开录取通知书，哭着笑（Romance「这次哭，是因为幸福」） ----------
scene('happy_tears', { ...V, dur: 10, zh: '拆开录取通知书，这次哭是因为幸福' }, t => {
  skyWash('#F2B880', '#F7D8A8');
  paint(ellPts(820, 170, 120, 120, 22), { fill: '#FFE1A0', fillOp: 120, bleed: .35, ink: null });                     // 傍晚的太阳
  paint(rectPts(-30, 430, W + 60, 220, 4), { wash: '#C98E6A', fill: '#A86E52', fillOp: 70, tex: .6, ink: PAL.ink, sw: .8 });   // 阳台栏杆
  for (let i = 0; i < 12; i++) inkLine([[i * 92, 430], [i * 92, 610]], 1, PAL.ink, 'ink', 0);
  const open = ease(seg(t, 1.5, 3)), cry = seg(t, 3.4, 4);
  const m = mood(t, [[0, 'look'], [3.2, 'scared', '!'], [4.2, 'happy']]);
  clawd(470, 520, 24, { ...m, lookY: -.8, mouth: t < 3.2 ? 'flat' : t < 4.2 ? 'O' : 'smile', blush: t > 4.2, aL: 1.45, aR: 1.45,
    dy: t > 4.2 ? -Math.abs(Math.sin(t * 5)) * .4 : 0 });
  if (cry > 0) tears(470, 520, 24, (t * 1.4) % 1);
  // 通知书（双手举过头顶，打开）
  push(); translate(470, 272 - (t > 4.2 ? Math.abs(Math.sin(t * 5)) * 10 : 0));
  paint(rectPts(-120, -70, 240, 140, 2), { wash: '#C8323C', fill: '#8E1F2A', fillOp: 70, ink: PAL.ink, sw: 1 });
  if (open > 0) {
    paint(rectPts(-110, -70 - 150 * open, 220, 150 * open, 2), { wash: PAL.cream, ink: PAL.ink, sw: .8 });
    if (open > .8) { letter('录取通知书', 470, 272 - 150 * open + 40, 30, '#C8323C', { ink: false }); for (let i = 0; i < 3; i++) inkLine([[-80, -170 + 75 + i * 22 - 150 * (open - 1)], [80, -170 + 75 + i * 22 - 150 * (open - 1)]], .5, '#8C7B66', 'inkfine', 0); }
  }
  paint(ellPts(0, 0, 26, 26, 14), { wash: '#F2C53D', ink: PAL.ink, sw: .6 });
  pop();
  // 飘下来的花瓣
  if (t > 4) for (let i = 0; i < 14; i++) {
    const x = (hash(i) * W + Math.sin(t + i) * 40), y = ((t - 4) * (60 + 40 * hash(i + 9)) + hash(i + 3) * 400) % 640 - 30;
    paint(ellPts(x, y, 11, 7, 10, 0, t * 2 + i), { wash: i % 2 ? PAL.rose : '#FFD3E0', ink: PAL.ink, sw: .35 });
  }
});

// ---------- 5. 居民楼间猛然抬头，满天星星为我闪烁（不吃饭的人会饿） ----------
scene('sudden_stars', { ...V, dur: 12, zh: '低头走在老居民楼间，猛然抬头，满天星星为我闪烁' }, t => {
  const up = ease(seg(t, 3.6, 4.6)), sky = seg(t, 4.2, 10);
  skyWash(mixCol('#1B1F3D', NIGHT2, sky), mixCol('#2A2D4A', '#3E3F7A', sky));
  if (sky > 0) paint(ellPts(520, 150, 420 * sky, 70 * sky, 22, 12, -.12), { fill: '#7A68C0', fillOp: 70 * sky, bleed: .35, tex: .8, ink: null });
  for (let i = 0; i < 26; i++) {
    const x = 60 + hash(i * 3) * 920, y = 30 + hash(i * 5 + 1) * 250, k = seg(t, 4.2 + hash(i * 7) * 5, 4.6 + hash(i * 7) * 5);
    star(x, y, 7 + 9 * hash(i * 11), t, i, k);
  }
  building(-20, 250, 430, '#3A3550', 1, .3); building(800, 270, 470, '#34304A', 2, .35); building(230, 140, 300, '#2F2B44', 3, .2);
  paint(rectPts(-20, 540, W + 40, 100, 3), { wash: '#2C2A3A', ink: null });
  lamp(700, 560, 250, 1);
  const walking = t < 3.6, cx = walking ? lerp(380, 520, t / 3.6) : 520;
  clawd(cx, 560, 20, { walk: walking ? t * 2 : null, eyes: up > .5 ? 'spark' : 'look', lookY: lerp(1, -1, up), mouth: up > .5 ? 'O' : 'flat',
    rot: -up * .14, aR: lerp(.8, -.2, up), aL: lerp(-.2, .3, up), armR: phoneHook(1 - up), dy: up > .5 ? -Math.abs(Math.sin(t * 2)) * .2 : 0 });
  if (t > 9.5) letter('原来星星一直都在', W / 2, 330, 46, '#FFE3A0', { pop: (t - 9.5) * 2 });
});

// ---------- 6. 冲进厨房喊「妈我回家啦」，窗外是星空（结尾：宋艾星SIX 389 赞） ----------
scene('home_kitchen', { ...V, dur: 10, zh: '冲进厨房喊「妈我回家啦」，红烧肉冒着热气，窗外是星空' }, t => {
  paint(rectPts(-30, -30, W + 60, H + 60), { wash: '#F3D9A8', fill: '#E7BE84', fillOp: 90, tex: .6, ink: null });          // 暖黄的墙
  // 窗：夜空 + 星星
  paint(rectPts(600, 60, 330, 220, 2), { wash: NIGHT, fill: NIGHT2, fillOp: 90, ink: PAL.ink, sw: 1.2 });
  for (let i = 0; i < 7; i++) star(630 + hash(i + 50) * 270, 85 + hash(i + 60) * 170, 7 + 5 * hash(i), t, i + 50, seg(t, 6 + i * .3, 6.4 + i * .3) + (i < 2 ? 1 : 0));
  inkLine([[765, 60], [765, 280]], 1, PAL.ink, 'ink', 0); inkLine([[600, 170], [930, 170]], 1, PAL.ink, 'ink', 0);
  // 灶台和锅：红烧肉冒热气
  paint(rectPts(560, 380, 460, 240, 3), { wash: '#B9B2A6', fill: '#8F877C', fillOp: 70, tex: .5, ink: PAL.ink, sw: 1 });
  paint(ellPts(760, 380, 120, 34, 18), { wash: '#3A3640', ink: PAL.ink, sw: 1 });
  for (let i = 0; i < 6; i++) paint(rrPts(690 + i * 24, 362 - (i % 2) * 8, 22, 20, 5), { wash: '#8E3B22', fill: '#C0602E', fillOp: 90, ink: PAL.ink, sw: .4 });
  for (let i = 0; i < 3; i++) { const ph = (t * .6 + i / 3) % 1; inkLine([[730 + i * 30, 350 - ph * 120], [745 + i * 30 + 12 * Math.sin(t * 2 + i), 330 - ph * 140], [732 + i * 30, 300 - ph * 160]], 1.2 * (1 - ph), '#FFFFFF', 'dry', .6); }
  // 妈妈（围巾）在灶台前，听到声音回头
  const turn = t > 2.6;
  clawd(840, 560, 20, { col: '#D99A76', dk: '#AE6E50', lt: '#F2C1A2', draw: momDraw, flip: !turn, eyes: turn ? 'happy' : 'look', lookX: -1,
    mouth: turn ? 'smile' : 'flat', aL: turn ? 1.2 : .3, aR: .5, emote: turn ? 'heart' : null, emoteK: seg(t, 2.8, 3.2) });
  // 门 + 冲进来的男生
  paint(rectPts(20, 160, 170, 400, 2), { wash: '#9A6B47', fill: '#7A5236', fillOp: 80, ink: PAL.ink, sw: 1 });
  const run = seg(t, .5, 2.3), bx = lerp(60, 400, easeOut(run));
  clawd(bx, 560, 20, { ...(run < 1 ? move('run', t) : { aL: 1.5, aR: 1.5 }), eyes: 'happy', mouth: 'grin', draw: backpackDraw('#C0504D') });
  if (t > 2.3 && t < 7.6) letter('妈，我回家啦！', bx, 300, 44, PAL.ink, { pop: (t - 2.3) * 2, alpha: 1 - seg(t, 7, 7.6), ink: false, stroke: PAL.cream });
  if (t > 6) letter('抬头看看', 765, 40, 34, '#FFE3A0', { pop: (t - 6) * 2 });
});

// ---------- 整片用的全画幅版本（1920×1080，MV 剧本 v2）：同一套画法用镜头放大，评论按剧本浮现 ----------
// 评论都是录屏原文（长评论取原文中连续的一段，不改字）。
const FK = 1920 / 1044;
function wrapZh(s, n) { const out = []; for (let i = 0; i < s.length; i += n) out.push(s.slice(i, i + n)); return out; }
function filmText(txt, user, x, y, size, k, col = PAL.cream, n = 20) {
  if (k <= .02) return;
  const lines = wrapZh(txt, n), lh = size * 1.4;
  lines.forEach((ln, i) => letter(ln, x, y + (i - (lines.length - 1) / 2) * lh, size, col,
    { screen: true, alpha: ease(k), ink: false, stroke: 'rgba(43,34,51,.85)', font: `${size}px "KaiTi","STKaiti",serif` }));
  if (user) letter('—— ' + user, x, y + (lines.length / 2 + .55) * lh, size * .6, col,
    { screen: true, alpha: ease(k) * .9, ink: false, stroke: 'rgba(43,34,51,.85)', font: `${Math.round(size * .6)}px "KaiTi","STKaiti",serif` });
}
// 整片 14.5–28 秒：3D 星光溶成纸纹之后的童年
scene('film_childhood', { w: 1920, h: 1080, dur: 13.5, bpm: 107.7, zh: '整片：夏夜凉席数星星（手绘，14.5–28 秒）' }, t => {
  camBegin(522, 305, FK); SCENES.summer_mat.fn(Math.min(10, t * .8)); camEnd();
  filmText('好久了 小时候夏天会数 数着数着就睡着了', 'Gm仙 · 2320 赞', 960, 150, 52, seg(t, 2.5, 3.6) * (1 - seg(t, 10.2, 11.2)), '#FFF3D6', 22);
});
// 整片 72.5–84.5 秒：回家（手绘结尾）
scene('film_home', { w: 1920, h: 1080, dur: 12, bpm: 107.7, zh: '整片：妈我回家啦 → 一起看星星（手绘，72.5–84.5 秒）' }, t => {
  camBegin(522, 305, FK); SCENES.home_kitchen.fn(Math.max(0, t - 1)); camEnd();
  filmText('以前一回家就躲进房间的我连包都没放就跑进了厨房对我妈说“妈我回家啦”', '宋艾星SIX · 389 赞', 600, 175, 40, seg(t, 4, 5) * (1 - seg(t, 8, 8.8)), '#FFF6E4', 18);
  filmText('珍惜每一个 能够抬头看星星的夜晚.', 'Pikio_ctave', 960, 470, 64, seg(t, 8.6, 9.6), '#FFE7A8', 30);
  filmText('你上一次抬头数星星，是什么时候？', null, 960, 1000, 46, seg(t, 9.8, 10.6), '#FFF6E4', 30);
});
