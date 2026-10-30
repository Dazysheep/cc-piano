// 《i have no friends》（s0rrow）歌词动画（全手绘）——用户 2026-10-30 发来录屏 + 封面图：「把这个图片中的男孩加到制作里面，根据歌词来联想」。
// 男孩照封面画：棕色乱卷发、半睁的灰蓝眼睛、小撇嘴、白色有线耳机、蓝色拉链卫衣 + 白 T、宽松的棕色裤子（白点）、黑鞋。
// 录屏 38 秒 = 主歌 4 句唱两遍 + 半句「Seeing couples walk right past me」。
// 叙事：第一遍是男孩眼里的世界（冷灰）；第二遍同一句歌词、同一个构图，画面里多了一只橙色的 CC 一直在旁边（变暖），
// 他到第 12 镜才发现；结尾情侣走过时，他把一只耳机分给 CC。

const N = { w: 1920, h: 1080, dur: 3, bpm: 117.5, off: .08 };
const HAND = s => `${s}px "ZCOOL KuaiLe", "KaiTi", cursive`;
const PEOPLE = ['#7FA7D9', '#9BC48B', '#C9A0DC', '#E8B86B', '#8FC9C2', '#D98C8C', '#A7A7B8', '#E0A3B8'];
const shade = (c, k = .35) => mixCol(c, PAL.ink, k);
const tone = (cold, warm, w) => mixCol(cold, warm, clamp(w));      // w = 0 冷（第一遍）… 1 暖（第二遍）

// ---------- 男孩 ----------
const BOY = { hair: '#7A5332', hairDk: '#4E321D', skin: '#FBE6C6', skinDk: '#E8C39A', hood: '#3F6F9F', hoodDk: '#2B4F78', tee: '#F7F4EC',
              pants: '#6E5C40', pantsDk: '#4A3D2B', shoe: '#2A2530', iris: '#8C9BB5', bud: '#F4F4F0' };
// (x, y) 站着 = 两脚中间的地面；坐着（o.sit）= 屁股所在的座面，脚垂到 y + legDrop。全高约 23u。
// o: eyes sleepy|open|wide|closed|happy|look（lookX/lookY）、mouth frown|flat|smile|grin|o、aL/aR 手臂外摆角、armL/armR 手里的道具钩子、
//    armLen、walk、sit、legDrop、kick、hood（戴帽子）、buds both|left|right|none、blush、tears、emote、flip、tag
function boy(x, y, u, o = {}) { return tagged(o.tag || 'male', () => boyRaw(x, y, u, o)); }
function boyRaw(x, y, u, o = {}) {
  const sw = clamp(u / 15, .45, 2.4), J = u * .04, seed = o.seed || 3, sit = !!o.sit, up = sit ? 7.6 * u : 0;   // 坐着：上半身往下挪到座面
  if (!o.noShadow && !ALPHA && !sit) paint(ellPts(x, y + u * .2, u * 4.6, u * .8, 22), { fill: PAL.ink, fillOp: 80, bleed: .25, ink: null });
  push(); translate(x, y + (o.dy || 0) * u); if (o.rot) rotate(o.rot); scale(o.flip ? -1 : 1, 1);

  // 腿
  if (sit) {
    const drop = (o.legDrop ?? 5.6) * u, kick = o.kick || 0;
    for (const s of [-1, 1]) {
      paint([[s * .1 * u, -.9 * u], [s * 3 * u, -.9 * u], [s * 3.1 * u, .9 * u], [s * .2 * u, .9 * u]], { wash: BOY.pants, fill: BOY.pantsDk, fillOp: 80, tex: .6, ink: PAL.ink, sw: sw * .8 });
      push(); translate(s * 1.6 * u, .6 * u); rotate(kick * (s < 0 ? 1 : .7));
      paint([[-1.4 * u, 0], [1.4 * u, 0], [1.6 * u, drop - .5 * u], [-1.6 * u, drop - .5 * u]], { wash: BOY.pants, fill: BOY.pantsDk, fillOp: 60, tex: .6, ink: PAL.ink, sw: sw * .8 });
      paint(ellPts(s * .3 * u, drop - .2 * u, 1.7 * u, .65 * u, 14), { wash: BOY.shoe, ink: PAL.ink, sw: sw * .7 });
      pop();
    }
  } else {
    const wk = o.walk != null ? Math.sin(o.walk * TAU) : 0;
    for (const s of [-1, 1]) {
      const lift = o.walk != null ? Math.max(0, s * wk) * .9 * u : 0, a = s < 0 ? [-3.0, -.1] : [.1, 3.0];
      paint([[a[0] * u, -8.4 * u], [a[1] * u, -8.4 * u], [(a[1] + s * .3) * u, -.9 * u - lift], [(a[0] + s * .35) * u, -.9 * u - lift]],
            { wash: BOY.pants, fill: BOY.pantsDk, fillOp: 70, tex: .6, ink: PAL.ink, sw: sw * .8 });
      paint(ellPts(s * 1.9 * u, -.55 * u - lift, 1.75 * u, .65 * u, 14), { wash: BOY.shoe, ink: PAL.ink, sw: sw * .7 });
    }
  }
  for (let k = 0; k < 9; k++) {                                     // 裤子上的白点（封面里的做旧斑点）
    const s = k % 2 ? 1 : -1, px = s * (.6 + hash(seed + k * 3) * 2) * u, py = sit ? (-.6 + hash(seed + k * 7) * 5) * u : (-7.6 + hash(seed + k * 7) * 6) * u;
    paint(ellPts(px, py, .16 * u, .11 * u, 6), { wash: '#EDE6D6', ink: null });
  }

  push(); translate(0, up);
  // 卫衣
  paint(ellPts(0, -14.5 * u, 3.3 * u, 1.1 * u, 16), { wash: BOY.hoodDk, ink: PAL.ink, sw: sw * .6 });
  const torso = [[-3.4 * u, -14.7 * u], [3.4 * u, -14.7 * u], [3.35 * u, -7.5 * u], [-3.35 * u, -7.5 * u]];
  paint(torso, { wash: BOY.hood, fill: BOY.hoodDk, fillOp: 90, tex: .6, ink: PAL.ink, sw });
  paint([[-1.1 * u, -14.6 * u], [1.1 * u, -14.6 * u], [.75 * u, -7.6 * u], [-.75 * u, -7.6 * u]], { wash: BOY.tee, ink: null });
  for (const s of [-1, 1]) {
    inkLine([[s * 1.1 * u, -14.5 * u], [s * .75 * u, -7.6 * u]], sw * .7, PAL.ink, 'ink', 0);
    inkLine([[s * 2.7 * u, -9.4 * u], [s * 1.2 * u, -9.7 * u]], sw * .45, BOY.hoodDk, 'inkfine', 0);   // 口袋
  }
  paint(rectPts(-3.4 * u, -8.2 * u, 6.8 * u, .7 * u), { wash: BOY.hoodDk, ink: null });                // 下摆罗纹
  paint(rectPts(-.8 * u, -15.8 * u, 1.6 * u, 1.4 * u), { wash: BOY.skin, ink: PAL.ink, sw: sw * .6 });   // 脖子

  // 手臂（肩膀在 ±3.1u, -14u；angle 往外摆为正）
  const L = (o.armLen ?? 6.3) * u;
  const arm = (s, a, hook) => {
    push(); translate(s * 3.1 * u, -14 * u); rotate(-s * a);
    paint(rrPts(-.85 * u, -.3 * u, 1.7 * u, L, .6 * u), { wash: BOY.hood, fill: BOY.hoodDk, fillOp: 80, ink: PAL.ink, sw: sw * .8 });
    paint(ellPts(0, L + .4 * u, .75 * u, .8 * u, 12), { wash: BOY.skin, ink: PAL.ink, sw: sw * .6 });
    if (hook) { translate(0, L + .4 * u); rotate(s * a); hook(u, sw); }
    pop();
  };
  arm(-1, o.aL ?? .12, o.armL); arm(1, o.aR ?? .12, o.armR);

  // 头
  const hy = -18.6 * u, buds = o.buds || 'both';
  if (buds !== 'none') {                                            // 耳机线：从耳朵垂到胸口汇成一根，塞进口袋
    const wire = (s) => inkLine([[s * 3.4 * u, hy + 1.1 * u], [s * 2.6 * u, -14.8 * u], [s * .6 * u, -12 * u], [0, -11.2 * u]], sw * .55, BOY.bud, 'ink', .5);
    if (buds !== 'right') wire(-1);
    if (buds !== 'left') wire(1);
    inkLine([[0, -11.2 * u], [.3 * u, -10 * u], [1.6 * u, -9.4 * u]], sw * .55, BOY.bud, 'ink', .5);
  }
  for (const s of [-1, 1]) paint(ellPts(s * 3.55 * u, hy + .3 * u, .6 * u, .85 * u, 10), { wash: BOY.skin, ink: PAL.ink, sw: sw * .6 });
  if (o.hood) paint(ellPts(0, hy - .6 * u, 4.9 * u, 5.2 * u, 26, J), { wash: BOY.hood, fill: BOY.hoodDk, fillOp: 90, ink: PAL.ink, sw });
  paint(ellPts(0, hy, 3.6 * u, 3.9 * u, 26, J), { wash: BOY.skin, fill: BOY.skinDk, fillOp: 45, tex: .5, ink: PAL.ink, sw });
  // 头发：乱蓬蓬的一团，刘海锯齿
  const hp = [], n = 26;
  for (let i = 0; i <= n; i++) {
    const a = Math.PI + i / n * Math.PI, r = (i % 2 ? 1.13 : .99) * (1 + (hash(seed * 13 + i) - .5) * .16);
    hp.push([Math.cos(a) * 4.8 * u * r, hy - 1.2 * u + Math.sin(a) * 4.3 * u * r]);
  }
  hp.push([4 * u, hy + .5 * u], [3.3 * u, hy - .5 * u]);
  for (let i = 0; i <= 9; i++) hp.push([3 * u - i / 9 * 6 * u, hy - (i % 2 ? 1.05 : 1.95) * u + (hash(seed + i) - .5) * .3 * u]);
  hp.push([-3.3 * u, hy - .5 * u], [-4 * u, hy + .5 * u]);
  paint(hp, { wash: BOY.hair, fill: BOY.hairDk, fillOp: 70, tex: .7, ink: PAL.ink, sw: sw * .9, curv: .35 });
  for (let i = 0; i < 8; i++) {
    const a = Math.PI * 1.08 + i / 7 * Math.PI * .84;
    inkLine([[Math.cos(a) * 2 * u, hy - 1.3 * u + Math.sin(a) * 1.8 * u], [Math.cos(a + .14) * 4 * u, hy - 1.3 * u + Math.sin(a + .14) * 3.7 * u]], sw * .45, BOY.hairDk, 'inkfine', .3);
  }
  if (o.hood) paint([...ellPts(0, hy - .6 * u, 4.9 * u, 5.2 * u, 26).slice(13), ...ellPts(0, hy - .4 * u, 3.9 * u, 3.8 * u, 26).slice(13).reverse()],
                    { wash: BOY.hood, fill: BOY.hoodDk, fillOp: 70, ink: PAL.ink, sw: sw * .8 });
  if (buds !== 'none') for (const s of [-1, 1]) if (buds === 'both' || (buds === 'left') === (s < 0)) paint(ellPts(s * 3.6 * u, hy + .7 * u, .55 * u, .55 * u, 10), { wash: BOY.bud, ink: PAL.ink, sw: sw * .5 });

  // 脸
  const e = o.eyes || 'sleepy', ey = hy + .3 * u, lx = o.lookX || 0, ly = o.lookY || 0;
  for (const s of [-1, 1]) {
    const ex = s * 1.45 * u;
    if (e === 'closed') inkLine([[ex - .9 * u, ey], [ex, ey + .45 * u], [ex + .9 * u, ey]], sw * 1.1, PAL.ink, 'ink', .4);
    else if (e === 'happy') inkLine([[ex - .9 * u, ey + .35 * u], [ex, ey - .4 * u], [ex + .9 * u, ey + .35 * u]], sw * 1.2, PAL.ink, 'ink', .4);
    else {
      const open = e === 'wide' ? 1 : e === 'open' || e === 'look' ? .78 : .42, r = e === 'wide' ? 1.12 : 1;
      paint(ellPts(ex, ey, 1 * u * r, .74 * u * r, 16), { wash: '#FFFFFF', ink: PAL.ink, sw: sw * .55 });
      paint(ellPts(ex + lx * .35 * u, ey + .12 * u + ly * .2 * u, .5 * u, .55 * u, 12), { wash: BOY.iris, ink: null });
      paint(ellPts(ex + lx * .35 * u, ey + .18 * u + ly * .2 * u, .22 * u, .25 * u, 8), { wash: PAL.ink, ink: null });
      if (e === 'wide') paint(ellPts(ex + lx * .35 * u + .15 * u, ey - .05 * u, .1 * u, .12 * u, 6), { wash: '#FFFFFF', ink: null });
      if (open < .9) {                                              // 半耷拉的眼皮
        const lidY = ey - .74 * u + (1 - open) * 1.15 * u;
        paint([[ex - 1.15 * u, ey - 1 * u], [ex + 1.15 * u, ey - 1 * u], [ex + 1.08 * u, lidY], [ex - 1.08 * u, lidY]], { wash: BOY.skin, ink: null });
        inkLine([[ex - 1.08 * u, lidY + .06 * u], [ex, lidY - .1 * u], [ex + 1.08 * u, lidY + .06 * u]], sw * 1.1, PAL.ink, 'ink', .4);
      }
      inkLine([[ex - .7 * u, ey + 1 * u], [ex, ey + 1.12 * u], [ex + .6 * u, ey + .98 * u]], sw * .35, BOY.skinDk, 'inkfine', .4);   // 眼袋
    }
  }
  inkLine([[.15 * u, hy + 1.2 * u], [-.05 * u, hy + 1.6 * u]], sw * .45, BOY.skinDk, 'inkfine', 0);
  const my = hy + 2.35 * u, m = o.mouth || 'frown';
  if (m === 'frown') inkLine([[-.6 * u, my + .15 * u], [0, my - .1 * u], [.6 * u, my + .15 * u]], sw * .7, PAL.ink, 'ink', .5);
  else if (m === 'flat') inkLine([[-.5 * u, my], [.5 * u, my]], sw * .7, PAL.ink, 'ink', 0);
  else if (m === 'smile') inkLine([[-.7 * u, my - .1 * u], [0, my + .25 * u], [.7 * u, my - .1 * u]], sw * .75, PAL.ink, 'ink', .5);
  else if (m === 'grin') paint([[-1 * u, my - .25 * u], [1 * u, my - .25 * u], [.6 * u, my + .55 * u], [-.6 * u, my + .55 * u]], { wash: '#7A3040', ink: PAL.ink, sw: sw * .6, curv: .4 });
  else if (m === 'o') paint(ellPts(0, my, .35 * u, .42 * u, 10), { wash: '#7A3040', ink: PAL.ink, sw: sw * .5 });
  if (o.blush) for (const s of [-1, 1]) paint(ellPts(s * 2.3 * u, hy + 1.5 * u, .7 * u, .35 * u, 12), { fill: PAL.rose, fillOp: 140, bleed: .2, ink: null });
  if (o.tears) for (const s of [-1, 1]) paint([[s * 1.6 * u, ey + .9 * u], [s * 1.9 * u, ey + 1.9 * u], [s * 1.6 * u, ey + 2.2 * u], [s * 1.35 * u, ey + 1.9 * u]], { wash: '#9CC9EE', ink: PAL.ink, sw: sw * .35 });
  pop();
  pop();
  if (o.emote) emote(o.emote, x + (o.flip ? -1 : 1) * 4.6 * u, y + up - 23 * u, u * .9, o.emoteK ?? 1);
}
const phoneIn = (glow = 0, col = '#BFE3FF') => (u, sw) => {          // 男孩手里的手机（钩在手上）
  paint(rrPts(-.9 * u, -.6 * u, 1.8 * u, 3.1 * u, .3 * u), { wash: '#33384A', ink: PAL.ink, sw: sw * .6 });
  paint(rrPts(-.7 * u, -.4 * u, 1.4 * u, 2.6 * u, .2 * u), { wash: mixCol('#20263A', col, glow), ink: null });
};

// ---------- 通用 ----------
function bg(col, col2, op = 120) { paint(rectPts(-40, -40, W + 80, H + 80), { wash: col, fill: col2 || col, fillOp: op, tex: .6, ink: null }); }
function person(x, y, u, i, t, o = {}) {
  const col = o.col || PEOPLE[i % PEOPLE.length];
  clawd(x, y, u, { col, dk: shade(col), lt: PAL.cream, eyes: 'normal', mouth: hash(i) < .5 ? 'flat' : 'o', aL: .2 + .3 * Math.sin(t * 3 + i), aR: .2,
    flip: hash(i * 7) < .5, dy: -Math.abs(Math.sin(t * 2.5 + i)) * .12, noShadow: true, seed: i, ...o });
}

// 分层：男孩 = male，CC = cc（这首歌 CC 是第二主角，单独一条轨道），路人 / 情侣 = others，挡在人物前面的东西 = props
function friend(x, y, u, o = {}) { return tagged('cc', () => clawdRaw(x, y, u, o)); }

scene('boy_test', { ...N, zh: '男孩定妆' }, t => {
  bg('#E9E2D2', '#D9CDB4');
  paint(rectPts(-40, 860, W + 80, 260), { wash: '#B8C29F', ink: null });
  boy(260, 900, 24, {});
  boy(640, 900, 24, { eyes: 'wide', mouth: 'o', aR: .5, emote: '!' });
  boy(1000, 900, 24, { eyes: 'happy', mouth: 'grin', blush: true, aL: .6, aR: .6, walk: t });
  boy(1350, 780, 24, { sit: true, eyes: 'look', lookX: 1, mouth: 'flat', aR: -.45, armR: phoneIn(1) });
  boy(1720, 900, 24, { hood: true, eyes: 'sleepy', mouth: 'frown', tears: true, buds: 'left', armLen: 4.6, aL: 2.9, aR: 2.9 });
  friend(1540, 900, 12, { eyes: 'normal', mouth: 'smile', aR: 1 });
});

// ====================================================================== 关键节点（= 17 个镜头）
// ---------- 字幕：英文逐字变暖黄 + 中文翻译（照网易云页面上的译文），都用手写体 ----------
const SUBPOS = { top: [960, 92], bottom: [960, 955], top_left: [600, 96], top_right: [1320, 96], bottom_left: [600, 955], bottom_right: [1320, 955], center: [960, 520] };
function subtitle(en, zh, pos, k, size = 54) {
  if (!en) return;
  const [x, y] = SUBPOS[pos] || SUBPOS.bottom, done = Math.floor(clamp(k) * en.length);
  const st = { screen: true, ink: false, stroke: 'rgba(43,34,51,.9)', font: HAND(size) };
  letter(en, x, y, size, PAL.cream, st);
  if (done > 0) letter(en, x, y, size, '#FFD36B', { ...st, clipChars: done });
  if (zh) letter(zh, x, y + size * 1.12, size * .62, '#EDE6DA', { ...st, font: HAND(Math.round(size * .62)) });
}
const LY = {
  a1: ['Today I realized', '今天我意识到'], a2: ["that I have no friends and I'm so alone", '我没有朋友而且很孤独'],
  b1: ['I feel so isolated', '我感到被孤立'], b2: ["no one's ever texted my phone", '没有人给我发过短信'],
  c1: ['Everyone is so fake', '每个人都很虚伪'], c2: ['I wanna hide away', '我想躲藏起来'],
  d1: ['Cause no one cares about me', '因为没有人关心我'], d2: ['all they do is laugh in my face', '他们仅仅在我面前嘲笑我'],
  e1: ['Seeing couples walk right past me', '我看到情侣们从我身边走过'],
};
const NODEFN = {};      // 不带字幕的画面本体，全片拿来当布景复用
// 每镜 [开始, 结束, 这句开始唱, 唱完]（秒，整段录屏的时间；来自 output/writer/i_have_no_friends/lyric_v1.json + lyrics_full.json）
const SHOT = [[0.00, 2.21, 0.00, 2.16], [2.21, 4.81, 2.16, 4.90], [4.81, 6.87, 4.90, 6.70], [6.87, 8.96, 7.06, 9.06], [8.96, 11.01, 9.06, 11.00], [11.01, 13.17, 11.14, 13.10],
              [13.17, 15.23, 13.10, 15.20], [15.23, 17.30, 15.24, 17.52], [17.30, 18.88, 17.52, 18.86], [18.88, 21.48, 18.86, 21.60], [21.48, 23.57, 21.60, 23.40], [23.57, 25.66, 23.72, 25.76],
              [25.66, 27.75, 25.76, 27.72], [27.75, 29.84, 28.04, 29.78], [29.84, 31.93, 29.78, 31.92], [31.93, 34.02, 31.92, 33.96], [34.02, 38.17, 33.96, 37.06]];
// 节点场景的时长 = 这一镜的长度，字幕按这句真实的演唱时间逐字变黄
function node(id, zh, ly, pos, fn) {
  const [a, b, ls, le] = SHOT[+id.slice(5) - 1];
  NODEFN[id] = fn;
  scene(id, { ...N, dur: +(b - a).toFixed(2), zh }, t => { fn(t); subtitle(ly[0], ly[1], pos, (t - (ls - a)) / Math.max(.3, le - ls)); });
}

// ---------- 小道具 ----------
const phoneC = (glow = 1) => (u, sw) => {                            // 路人（CC 方块人）手里的手机
  paint(rrPts(-.2 * u, -1.6 * u, 1.6 * u, 2.8 * u, .3 * u), { wash: '#3A3F55', ink: PAL.ink, sw: sw * .7 });
  paint(rrPts(0, -1.35 * u, 1.2 * u, 2.2 * u, .2 * u), { wash: mixCol('#20263A', '#BFE3FF', glow), ink: null });
};
const flowerC = (u, sw) => {
  inkLine([[0, 0], [.8 * u, -2.6 * u]], sw, '#4F7A44', 'ink', .3);
  paint(starPts(.8 * u, -3.1 * u, 1.2 * u, .55, 5), { wash: '#FFD34E', ink: PAL.ink, sw: sw * .5 });
  paint(ellPts(.8 * u, -3.1 * u, .42 * u, .42 * u, 8), { wash: '#E58A3A', ink: null });
};
const torchC = (u, sw) => {
  paint([[1.5 * u, -.35 * u], [11 * u, -3.4 * u], [11 * u, 3.4 * u], [1.5 * u, .35 * u]], { fill: '#FFE9A0', fillOp: 110, bleed: .3, ink: null });
  paint(rrPts(-.2 * u, -.45 * u, 1.9 * u, .9 * u, .2 * u), { wash: '#5A6070', ink: PAL.ink, sw: sw * .6 });
};
function palm(x, y, s, w) {
  paint([[x - 12 * s, y + 330 * s], [x + 12 * s, y + 330 * s], [x + 16 * s, y + 120 * s], [x + 4 * s, y], [x - 6 * s, y], [x - 2 * s, y + 120 * s]], { wash: tone('#7C736A', '#8A6440', w), ink: PAL.ink, sw: .6 });
  for (let i = 0; i < 7; i++) {
    const a = -Math.PI + i / 6 * Math.PI, L = 140 * s;
    paint([[x, y], [x + Math.cos(a - .14) * L * .6, y + Math.sin(a - .14) * L * .45 - 12 * s], [x + Math.cos(a) * L, y + Math.sin(a) * L * .5 + 46 * s], [x + Math.cos(a + .14) * L * .6, y + Math.sin(a + .14) * L * .45 + 12 * s]],
          { wash: tone('#66765F', '#4F8A45', w), ink: PAL.ink, sw: .6 });
  }
}
function bubble(...a) { return tagged('props', () => bubbleRaw(...a)); }
function bubbleRaw(x, y, r, txt, rot, col = '#FFF8EA', size) {             // 锯齿的笑声气泡
  paint(starPts(x, y, r, .8, 11, rot), { wash: col, ink: PAL.ink, sw: 1 });
  letter(txt, x, y, size || r * .55, '#C8323C', { ink: false, font: HAND(Math.round(size || r * .55)), rot: rot * .3 });
}
function maskAt(...a) { return tagged('props', () => maskAtRaw(...a)); }
function maskAtRaw(x, y, u) {                                            // 举在脸前的笑脸面具（y = 脸中心）
  inkLine([[x + 3 * u, y + 2.4 * u], [x + 5.2 * u, y + 6.6 * u]], 1.3, '#7A5A3A', 'ink', 0);
  paint(ellPts(x, y, 4.8 * u, 3.1 * u, 22), { wash: '#FFF8EA', ink: PAL.ink, sw: .9 });
  for (const s of [-1, 1]) inkLine([[x + s * 2 * u - .8 * u, y - .4 * u], [x + s * 2 * u, y - 1.1 * u], [x + s * 2 * u + .8 * u, y - .4 * u]], 1, PAL.ink, 'ink', .4);
  inkLine([[x - 2 * u, y + .8 * u], [x, y + 2 * u], [x + 2 * u, y + .8 * u]], 1.1, '#C8323C', 'ink', .5);
  for (const s of [-1, 1]) paint(ellPts(x + s * 3.2 * u, y + .7 * u, .8 * u, .45 * u, 10), { fill: PAL.rose, fillOp: 120, bleed: .2, ink: null });
}
function cloudAt(x, y, s, col) { for (const [dx, dy, r] of [[-1.1, .2, .7], [-.4, -.3, .9], [.5, -.2, .85], [1.2, .25, .65], [0, .35, .9]]) paint(ellPts(x + dx * 100 * s, y + dy * 100 * s, r * 100 * s, r * 70 * s, 16), { wash: col, ink: null }); }

// ---------- 1 / 9 卧室（今天我意识到）：灰色清晨，坐在床边看手机；日历撕下一页。第二遍：窗外窗台上探出一只橙色 CC 在挥手 ----------
function bedroom(t, w, cc) {
  bg(tone('#C9CDD3', '#F1DFC2', w), tone('#B5BCC6', '#E6C99E', w));
  const fl = tone('#9DA3AA', '#C99E72', w);
  paint(rectPts(-40, 840, W + 80, 280), { wash: fl, fill: shade(fl, .12), fillOp: 80, ink: null });
  for (let i = 0; i < 10; i++) inkLine([[i * 220 - 60, 840], [i * 250 - 200, 1090]], .5, shade(fl, .3), 'inkfine', 0);
  paint(rectPts(1180, 150, 420, 390, 2), { wash: tone('#AEB8C2', '#FFD49A', w), fill: tone('#C9D2DA', '#FFE7B8', w), fillOp: 90, ink: null });   // 窗外
  if (w > .5) paint(ellPts(1500, 250, 46, 46, 16), { wash: '#FFE08A', ink: PAL.ink, sw: .6 });
  for (let i = 0; i < 3; i++) cloudAt(1270 + i * 130, 250 + (i % 2) * 50, .45, tone('#DDE2E6', '#FFF3DC', w));
  if (cc) friend(1290, 566, 17, { eyes: 'normal', mouth: 'smile', aR: 1.5 + .25 * Math.sin(t * 9), aL: .2, noShadow: true, emote: 'heart', emoteK: clamp(t - .6) });
  paint(rectPts(1180, 150, 420, 390), { ink: PAL.ink, sw: 1.3 });
  inkLine([[1390, 150], [1390, 540]], 1.4, PAL.ink, 'ink', 0); inkLine([[1180, 345], [1600, 345]], 1.4, PAL.ink, 'ink', 0);
  paint(rectPts(1160, 530, 460, 28, 1), { wash: '#E8E2D6', ink: PAL.ink, sw: .8 });
  if (cc) tagged('cc', () => paint(rectPts(1160, 530, 460, 28, 1), { wash: '#E8E2D6', ink: PAL.ink, sw: .8 }));   // CC 层也画窗台，单独挪 CC 时仍被挡住
  const cur = tone('#8E9AAE', '#E59A6B', w);
  inkLine([[1080, 128], [1700, 128]], 1.6, PAL.ink, 'ink', 0);
  paint([[1100, 128], [1215, 128], [1195, 610], [1090, 620]], { wash: cur, fill: shade(cur, .2), fillOp: 70, ink: PAL.ink, sw: .8 });
  paint([[1565, 128], [1680, 128], [1690, 620], [1585, 610]], { wash: cur, fill: shade(cur, .2), fillOp: 70, ink: PAL.ink, sw: .8 });
  if (w > .5) paint([[1180, 540], [1600, 540], [1300, 1080], [700, 1080]], { fill: '#FFE6A8', fillOp: 70, bleed: .3, ink: null });   // 照进来的阳光
  // 墙上：钟（7:02）、日历（30 号，被撕下的一页飘走）、书架
  paint(ellPts(330, 210, 62, 62, 20), { wash: PAL.cream, ink: PAL.ink, sw: .9 });
  inkLine([[330, 210], [330, 160]], 1.4, PAL.ink, 'ink', 0); inkLine([[330, 210], [338, 196]], 1.4, PAL.ink, 'ink', 0);
  paint(rectPts(880, 210, 170, 210, 2), { wash: PAL.cream, ink: PAL.ink, sw: .9 });
  paint(rectPts(880, 210, 170, 48), { wash: '#C8323C', ink: null });
  letter('10 月', 965, 234, 30, PAL.cream, { ink: false, font: HAND(30) });
  letter('30', 965, 335, 84, PAL.ink, { ink: false, font: HAND(84) });
  if (w > .5) paint(heartPts(1010, 390, 16), { wash: '#E2476E', ink: PAL.ink, sw: .5 });
  const fly = clamp(t / 2.4);
  push(); translate(965 + fly * 260, 320 + fly * 330); rotate(fly * 2.2);
  paint(rectPts(-80, -90, 160, 175, 2), { wash: PAL.cream, ink: PAL.ink, sw: .8 }); pop();
  letter('29', 965 + fly * 260, 330 + fly * 330, 60, '#9A9AA2', { ink: false, font: HAND(60), rot: fly * 2.2 });
  paint(rectPts(560, 300, 240, 16, 1), { wash: '#9A6B47', ink: PAL.ink, sw: .7 });
  [['#C0504D', 30], ['#4A6FA5', 26], ['#E8B86B', 34], ['#6E9F58', 24], ['#7B5CA8', 30]].forEach(([c, ww], i) => paint(rectPts(580 + i * 38, 300 - 70 - (i % 2) * 10, ww, 70 + (i % 2) * 10, 1), { wash: tone(shade(c, .1), c, w), ink: PAL.ink, sw: .5 }));
  // 床
  paint(rectPts(60, 470, 60, 420, 2), { wash: '#8A6448', ink: PAL.ink, sw: 1 });
  paint(rectPts(110, 650, 720, 140, 3), { wash: '#ECE8E0', ink: PAL.ink, sw: 1 });
  paint(rectPts(110, 780, 720, 60, 2), { wash: '#8A6448', ink: PAL.ink, sw: .9 });
  paint(ellPts(230, 640, 110, 46, 18), { wash: '#F6F3EC', ink: PAL.ink, sw: .8 });
  const blk = tone('#8C99AD', '#E6A27C', w);
  paint([[330, 610], [800, 630], [830, 800], [300, 790]], { wash: blk, fill: shade(blk, .2), fillOp: 80, ink: PAL.ink, sw: .9, curv: .2 });
  for (let i = 0; i < 4; i++) for (let j = 0; j < 2; j++) paint(ellPts(400 + i * 110, 680 + j * 60, 16, 10, 10), { wash: shade(blk, .15), ink: null });
  // 床头柜 + 台灯
  paint(rectPts(880, 700, 190, 160, 2), { wash: '#A88262', ink: PAL.ink, sw: .9 }); inkLine([[880, 780], [1070, 780]], .8, PAL.ink, 'ink', 0);
  paint([[930, 600], [1020, 600], [1000, 540], [950, 540]], { wash: tone('#B9C1CC', '#FFE09A', w), ink: PAL.ink, sw: .8 }); inkLine([[975, 600], [975, 700]], 1.2, PAL.ink, 'ink', 0);
  // 地上：书包、袜子
  paint(rrPts(1210, 860, 150, 130, 26), { wash: '#4E5E7A', ink: PAL.ink, sw: .9 }); paint(rrPts(1240, 900, 90, 40, 10), { wash: '#3D4B63', ink: PAL.ink, sw: .6 });
  paint([[1460, 990], [1530, 980], [1540, 1010], [1470, 1020]], { wash: '#F2F2EE', ink: PAL.ink, sw: .6 });
  // 男孩坐在床边，低头看手机（第二遍还是没发现窗外）
  boy(700, 760, 19, { sit: true, legDrop: 6.4, eyes: 'look', lookY: 1, lookX: .3, mouth: 'frown', aR: -.42, armR: phoneIn(w > .5 ? .5 : .15), aL: .1 });
}
// ---------- 2 / 10 秋千（我没有朋友而且很孤独）：封面里的白色秋千架，空秋千自己在晃，远处一群人在玩球。第二遍：CC 坐在空秋千上荡、冲他挥手 ----------
function playground(t, w, cc) {
  bg(tone('#C6CED6', '#F6DDB0', w), tone('#B4BEC9', '#F0C890', w));
  if (w > .5) paint(ellPts(1560, 150, 60, 60, 18), { wash: '#FFE08A', ink: PAL.ink, sw: .6 });
  for (const [x, r] of [[480, 120], [800, 150], [1240, 130], [1500, 160]]) paint(ellPts(x, 360, r, r * .75, 22, 5), { wash: tone('#71806F', '#6E9A57', w), fill: tone('#5E6B5E', '#557F43', w), fillOp: 90, ink: PAL.ink, sw: .7 });
  palm(200, 230, 1.1, w); palm(1760, 260, .95, w);
  paint(rectPts(-40, 400, W + 80, 220, 6), { wash: tone('#5F6E5E', '#4F7A44', w), fill: tone('#4E5B4E', '#3E6535', w), fillOp: 110, tex: .8, ink: PAL.ink, sw: .8 });
  const gr = tone('#8F9A8A', '#93B26F', w);
  paint(rectPts(-40, 600, W + 80, 520), { wash: gr, fill: shade(gr, .1), fillOp: 90, tex: .7, ink: null });
  for (let i = 0; i < 46; i++) { const x = hash(i) * W, y = 640 + hash(i + 50) * 420; inkLine([[x - 6, y], [x, y - 14], [x + 6, y]], .5, shade(gr, .35), 'inkfine', 0); }
  // 远处一群玩球的人
  const ball = 1660 + 70 * Math.sin(t * 2.4);
  [[1560, 0], [1640, 2], [1760, 4], [1840, 6]].forEach(([x, i]) => person(x, 690, 8, i, t, { mouth: 'smile', eyes: 'happy', aL: .8, aR: .8 }));
  paint(ellPts(ball, 610 - 40 * Math.abs(Math.sin(t * 4.8)), 9, 9, 10), { wash: '#E2476E', ink: PAL.ink, sw: .5 });
  // 沙坑 + 小桶
  paint(ellPts(330, 860, 220, 60, 22), { wash: tone('#C9C2B0', '#EBD19C', w), ink: PAL.ink, sw: .8 });
  paint([[300, 830], [340, 830], [335, 870], [305, 870]], { wash: '#E2476E', ink: PAL.ink, sw: .6 });
  // 秋千架
  const fc = tone('#DADDD8', '#F4F0E4', w);
  for (const x0 of [560, 1400]) for (const s of [-1, 1]) paint([[x0 - 14, 262], [x0 + 14, 262], [x0 + s * 120 + 14, 900], [x0 + s * 120 - 14, 900]], { wash: fc, ink: PAL.ink, sw: .9 });
  for (const x0 of [560, 1400]) paint(rectPts(x0 - 90, 560, 180, 18, 1), { wash: fc, ink: PAL.ink, sw: .7 });
  paint(rectPts(500, 240, 960, 34, 2), { wash: fc, ink: PAL.ink, sw: 1 });
  const ang = cc ? Math.sin(t * 3.1) * .38 : Math.sin(t * 1.7) * .12, sx = 800 + Math.sin(ang) * 420, sy = 274 + Math.cos(ang) * 420;
  for (const s of [-1, 1]) inkLine([[800 + s * 34, 274], [sx + s * 40, sy]], .9, '#6F737A', 'inkfine', 0);
  if (cc) friend(sx, sy - 6, 13, { eyes: 'happy', mouth: 'smile', aR: 1.4 + .3 * Math.sin(t * 8), aL: .4, rot: ang * .4, noShadow: true, emote: 'music', emoteK: 1 });
  paint(rrPts(sx - 56, sy - 8, 112, 18, 6), { wash: '#3E3A40', ink: PAL.ink, sw: .8 });
  for (const s of [-1, 1]) inkLine([[1150 + s * 30, 274], [1150 + s * 30, 520]], .9, '#6F737A', 'inkfine', 0);
  paint([[1110, 520], [1190, 520], [1150, 556]], { wash: '#F2C53D', ink: PAL.ink, sw: .9 });          // 封面里那个黄色吊环
  boy(1160, 940, 21, { eyes: 'look', lookX: -.9, lookY: .7, mouth: 'frown', aL: .06, aR: .06 });
}
// ---------- 3 / 11 玻璃罐（我感到被孤立）：街上的人都低头看手机走过，他被关在一只大玻璃罐里。第二遍：CC 在外面敲玻璃，敲出一道带光的裂纹 ----------
function streetJar(t, w, cc) {
  bg(tone('#C3C8CF', '#F2D9B5', w), tone('#AEB5BF', '#E8C493', w));
  for (let i = 0; i < 7; i++) {
    const x = -40 + i * 290, h = 380 + hash(i + 3) * 260, col = tone(['#9AA2AD', '#A9A3A0', '#8F99A6'][i % 3], ['#E3A77A', '#D9B48A', '#C98F6A'][i % 3], w);
    paint(rectPts(x, 820 - h, 250, h, 3), { wash: col, fill: shade(col, .15), fillOp: 60, ink: PAL.ink, sw: .8 });
    for (let r = 0; r < Math.floor(h / 90) - 1; r++) for (let c = 0; c < 3; c++) paint(rectPts(x + 30 + c * 72, 820 - h + 40 + r * 90, 44, 54, 1), { wash: tone('#C9D1DA', hash(i * 9 + r * 3 + c) < .5 ? '#FFE3A3' : '#F6E9D2', w), ink: PAL.ink, sw: .4 });
  }
  paint(rectPts(-40, 800, W + 80, 320), { wash: tone('#A7A9AC', '#CDB79A', w), ink: null });
  for (let i = 0; i < 9; i++) inkLine([[i * 240, 800], [i * 260 - 120, 1080]], .5, '#7E8084', 'inkfine', 0);
  for (let i = 0; i < 5; i++) { const x = ((i * 450 + t * 120) % 2300) - 180; person(x, 850, 14, i, t, { walk: t * 2.2, flip: true, eyes: 'look', lookY: 1, aR: .9, armR: phoneC(.9) }); }
  boy(960, 960, 21, { eyes: cc ? 'open' : 'sleepy', lookX: cc ? 1 : 0, lookY: cc ? 0 : 1, mouth: cc ? 'o' : 'frown', aL: .05, aR: .05 });
  tagged('props', () => {                                             // 玻璃罐罩在男孩前面
  paint(rrPts(700, 300, 520, 720, 80), { fill: '#CFE6F2', fillOp: 50, bleed: .05, ink: PAL.ink, sw: 1.4 });
  paint(rrPts(730, 256, 460, 60, 14), { wash: '#9AA3AD', fill: '#7D8691', fillOp: 70, ink: PAL.ink, sw: 1 });
  for (let i = 0; i < 9; i++) inkLine([[750 + i * 50, 262], [750 + i * 50, 310]], .5, '#5E6670', 'inkfine', 0);
  inkLine([[752, 400], [744, 760]], 2.4, '#FFFFFF', 'ink', .3); inkLine([[778, 420], [776, 520]], 1.4, '#FFFFFF', 'ink', .3);
  });
  for (const [x, i] of [[180 + t * 40, 5], [1700 - t * 40, 6]]) person(x, 1050, 20, i, t, { walk: t * 2.5, flip: i === 6, eyes: 'look', lookY: 1, aR: .9, armR: phoneC(.9) });
  if (cc) {
    friend(1320, 1000, 15, { eyes: 'normal', mouth: 'O', aL: .9 + .5 * Math.abs(Math.sin(t * 9)), aR: .2, flip: true });
    const k = clamp(t / 1.2);
    tagged('props', () => {
    for (let i = 0; i < 6; i++) { const a = i / 6 * TAU + .3; inkLine([[1218, 700], [1218 + Math.cos(a) * 70 * k, 700 + Math.sin(a) * 70 * k]], .9, PAL.ink, 'inkfine', 0); }
    paint(ellPts(1218, 700, 46 * k + 1, 46 * k + 1, 14), { fill: '#FFE6A0', fillOp: 120, bleed: .4, ink: null });
    sfx('咚 咚', 1330, 720, 46, PAL.ink, t % 1.2, { font: HAND(46) });
    });
  }
}
// ---------- 4 / 12 手机特写（没有人给我发过短信）：黑屋里只有屏幕亮着，「暂无新消息」，只有电量低提醒。第二遍：弹出第一条消息「CC：嗨，在吗？」，他睁大眼睛 ----------
function phoneClose(t, w, cc) {
  bg(tone('#2B3042', '#4A3A3A', w), tone('#232838', '#5A4234', w));
  if (cc) paint(ellPts(1340, 560, 700, 520, 24), { fill: '#FFC98A', fillOp: 50, bleed: .4, ink: null });
  else paint(ellPts(1340, 560, 600, 480, 24), { fill: '#9FC4E8', fillOp: 30, bleed: .4, ink: null });
  paint(rectPts(140, 120, 260, 220, 2), { wash: tone('#3A4256', '#6A5040', w), ink: PAL.ink, sw: .8 });       // 墙上的窗（夜）
  for (const [x, y] of [[200, 180], [330, 240], [260, 290]]) paint(starPts(x, y, 8), { wash: '#FFE9A8', ink: null });
  boy(560, 1650, 50, { eyes: cc ? 'wide' : 'sleepy', lookX: 1, lookY: cc ? 0 : .5, mouth: cc ? 'o' : 'flat', emote: cc ? '!' : null, emoteK: clamp((t - .4) * 3) });
  const X = 1090, Y = 130, scr = tone('#DCE6EE', '#FFF4E2', w);
  paint(rrPts(X, Y, 500, 880, 56), { wash: '#262A36', ink: PAL.ink, sw: 1.6 });
  paint(rrPts(X + 25, Y + 30, 450, 820, 40), { wash: scr, ink: null });
  paint(rectPts(X + 25, Y + 70, 450, 80), { wash: tone('#B9C6D2', '#F2C9A0', w), ink: null });
  letter('消息', X + 250, Y + 110, 38, PAL.ink, { ink: false, font: HAND(38) });
  letter('9:41', X + 250, Y + 50, 22, PAL.ink, { ink: false, font: HAND(22) });
  [['订阅号', '本周精选文章'], ['系统通知', '电量低（10%）']].forEach(([a, b], i) => {
    const yy = Y + 200 + (i + (cc ? 1 : 0)) * 110;
    paint(rrPts(X + 50, yy - 36, 72, 72, 16), { wash: '#B8BEC6', ink: PAL.ink, sw: .5 });
    letter(a, X + 150, yy - 12, 28, PAL.ink, { ink: false, font: HAND(28), align: 'left' });
    letter(b, X + 150, yy + 22, 22, '#7A808A', { ink: false, font: HAND(22), align: 'left' });
  });
  if (!cc) {
    paint(rrPts(X + 170, Y + 480, 160, 110, 14), { wash: '#C9CFD6', ink: PAL.ink, sw: .8 });
    inkLine([[X + 170, Y + 490], [X + 250, Y + 545], [X + 330, Y + 490]], .9, PAL.ink, 'ink', .2);
    letter('暂无新消息', X + 250, Y + 650, 36, '#7A808A', { ink: false, font: HAND(36) });
  } else {
    const sl = backOut(clamp(t / .5)), by = Y + 150;                // 列表最上面多出一条新消息（弹进来）
    push(); translate(X + 250, by + 70); scale(sl); translate(-X - 250, -by - 70);
    paint(rrPts(X + 35, by + 10, 430, 120, 22), { wash: '#FFE9C8', ink: PAL.ink, sw: 1 });
    clawdRaw(X + 92, by + 108, 5.5, { eyes: 'happy', mouth: 'smile', noShadow: true });
    pop();
    if (sl > .6) {
      letter('CC', X + 150, by + 48, 34, PAL.ink, { ink: false, font: HAND(34), align: 'left' });
      letter('嗨，在吗？:)', X + 150, by + 94, 30, '#5A4A3A', { ink: false, font: HAND(30), align: 'left' });
      letter('刚刚', X + 425, by + 44, 20, '#9A8A7A', { ink: false, font: HAND(20) });
    }
    paint(ellPts(X + 470, Y + 40, 24 * (1 + .2 * pulse(t)), 24 * (1 + .2 * pulse(t)), 14), { wash: '#E2476E', ink: PAL.ink, sw: .6 });
    letter('1', X + 470, Y + 42, 28, '#FFFFFF', { ink: false, font: HAND(28) });
  }
  paint(ellPts(X + 30, Y + 760, 70, 110, 18), { wash: BOY.skin, ink: PAL.ink, sw: 1 });      // 握手机的手
}
// ---------- 5 / 13 走廊里的面具（每个人都很虚伪）：一排人举着笑脸面具，面具后面在交头接耳。第二遍：CC 没戴面具，举着一朵小黄花 ----------
function masks(t, w, cc) {
  bg(tone('#C8CBCF', '#F0DCC0', w), tone('#B9BDC3', '#E8C9A0', w));
  for (let i = 0; i < 17; i++) {
    const col = tone('#8E9BAA', ['#E59A7A', '#8FC0A6', '#F2CC8F', '#7FA7D9'][i % 4], w * .8);
    paint(rectPts(i * 116 - 20, 250, 112, 560, 2), { wash: col, fill: shade(col, .12), fillOp: 60, ink: PAL.ink, sw: .8 });
    for (let k = 0; k < 4; k++) inkLine([[i * 116 + 20, 290 + k * 16], [i * 116 + 70, 290 + k * 16]], .5, shade(col, .4), 'inkfine', 0);
    paint(rectPts(i * 116 + 72, 520, 10, 40, 1), { wash: '#555', ink: null });
    if (i < 12 && hash(i * 5) < .6) paint(ellPts(i * 116 + 36, 430 + hash(i) * 80, 14, 14, 10), { wash: PEOPLE[i % 8], ink: PAL.ink, sw: .4 });   // 别人柜门上的贴纸
  }
  paint(rectPts(-40, 810, W + 80, 320), { wash: tone('#A3A6AA', '#D9B98F', w), ink: null });
  for (let i = 0; i < 8; i++) inkLine([[-40, 840 + i * 34], [W + 40, 840 + i * 34]], .4, '#8A8E92', 'inkfine', 0);
  [[150, 0], [370, 1], [590, 2], [810, 3], [1030, 4]].forEach(([x, i]) => {
    const u = 21, low = i === 2 ? .5 + .5 * Math.sin(t * 2) : 0;
    person(x, 990, u, i, t, { eyes: 'look', lookX: 1, mouth: 'flat', aR: .5, dy: 0 });
    maskAt(x - .5 * u, 990 - 6 * u + low * 3 * u, u);
    if (i % 2) bubble(x + 120, 990 - 12 * u, 40, ['…', '嘘', '哈'][i % 3], .2 * i);
  });
  boy(1560, 1000, 20, { eyes: cc ? 'look' : 'sleepy', lookX: -1, lookY: cc ? .4 : .2, mouth: cc ? 'flat' : 'frown', aL: .05, aR: .05 });
  if (cc) friend(1330, 1000, 13, { eyes: 'normal', mouth: 'smile', aL: .2, aR: 1.1, armR: flowerC, emote: 'spark', emoteK: clamp(t) });
}
// ---------- 6 / 14 纸箱（我想躲藏起来）：昏暗的房间角落，一个「易碎」纸箱，把手孔里露出一双半睁的眼。第二遍：箱子里透出暖光，CC 举着手电从箱口探出头，地上塞出来一张画 ----------
function boxHide(t, w, cc) {
  bg(tone('#6E7684', '#E2BE92', w), tone('#5E6573', '#D8AD7C', w));
  paint(rectPts(-40, 760, W + 80, 360), { wash: tone('#59606C', '#B98A5E', w), ink: null });
  if (!cc) paint([[1500, 760], [1560, 760], [1700, 1080], [1560, 1080]], { fill: '#D9DEE6', fillOp: 70, bleed: .2, ink: null });   // 门缝漏进来的一道光
  paint(rectPts(1500, 120, 260, 640, 3), { wash: tone('#646B78', '#C99A6A', w), ink: PAL.ink, sw: .9 });
  paint(ellPts(1530, 470, 12, 12, 8), { wash: '#B9A27A', ink: PAL.ink, sw: .5 });
  const bx = 600, by = 470, bw = 720, bh = 470, card = '#C49A6C';
  paint([[bx + bw, by], [bx + bw + 150, by - 70], [bx + bw + 150, by + bh - 70], [bx + bw, by + bh]], { wash: shade(card, .25), ink: PAL.ink, sw: 1 });
  paint([[bx, by], [bx + 150, by - 70], [bx + bw + 150, by - 70], [bx + bw, by]], { wash: '#3A2A20', ink: PAL.ink, sw: .9 });
  if (cc) {
    paint(ellPts(bx + bw / 2 + 80, by - 40, 380, 70, 18), { fill: '#FFE3A0', fillOp: 140, bleed: .3, ink: null });
    friend(bx + bw - 150, by + 30, 14, { eyes: 'happy', mouth: 'smile', aR: .9, armR: torchC, aL: 1.3 + .2 * Math.sin(t * 7), noShadow: true });
  }
  paint(rectPts(bx, by, bw, bh, 3), { wash: card, fill: shade(card, .12), fillOp: 80, tex: .7, ink: PAL.ink, sw: 1.2 });
  paint([[bx - 10, by], [bx + 120, by - 120], [bx + 300, by - 110], [bx + 200, by]], { wash: shade(card, .08), ink: PAL.ink, sw: 1 });            // 翘起的盖子
  if (cc) tagged('cc', () => paint(rectPts(bx + bw - 240, by, 200, 46), { wash: card, fill: shade(card, .12), fillOp: 80, tex: .7, ink: null }));   // CC 层的箱沿
  paint(rectPts(bx + bw / 2 - 40, by, 80, bh, 1), { wash: '#D8B98C', ink: null });                                                              // 胶带
  push(); translate(bx + 170, by + 120); rotate(-.12); paint(rectPts(-120, -40, 240, 80, 2), { ink: '#C8323C', sw: 1.2 }); pop();
  letter('易碎 FRAGILE', bx + 170, by + 120, 34, '#C8323C', { ink: false, font: HAND(34), rot: -.12 });
  letter('↑ ↑', bx + bw - 120, by + 120, 44, PAL.ink, { ink: false, font: HAND(44) });
  inkLine([[bx + 250, by], [bx + 280, by + 40], [bx + 262, by + 80]], 1, BOY.tee, 'ink', .5);                                                 // 卫衣帽绳伸出来
  const sx = bx + bw / 2, sy = by + 280;
  paint(rrPts(sx - 120, sy - 40, 240, 80, 40), { wash: '#1E1820', ink: PAL.ink, sw: 1 });
  if (cc) paint(rrPts(sx - 120, sy - 40, 240, 80, 40), { fill: '#FFC97A', fillOp: 120, bleed: .2, ink: null });
  tagged('male', () => { for (const s of [-1, 1]) {                 // 把手孔里男孩的眼睛
    const ex = sx + s * 44;
    paint(ellPts(ex, sy + 4, 26, 18, 12), { wash: '#FFFFFF', ink: PAL.ink, sw: .5 });
    paint(ellPts(ex + (cc ? 6 : 0), sy + 8, 12, 13, 10), { wash: BOY.iris, ink: null });
    paint(ellPts(ex + (cc ? 6 : 0), sy + 9, 5, 6, 8), { wash: PAL.ink, ink: null });
    if (!cc) { paint([[ex - 30, sy - 22], [ex + 30, sy - 22], [ex + 28, sy + 2], [ex - 28, sy + 2]], { wash: '#1E1820', ink: null }); inkLine([[ex - 28, sy + 2], [ex + 28, sy + 2]], 1.2, PAL.ink, 'ink', .3); }
  } });
  // 地上：缠成一团的耳机、扣着的手机、一双鞋、纸团
  const loop = []; for (let i = 0; i < 18; i++) { const a = i * .9; loop.push([300 + Math.cos(a) * (30 + i * 2), 1000 + Math.sin(a) * (14 + i)]); }
  inkLine(loop, .9, BOY.bud, 'ink', .6);
  paint(rrPts(380, 960, 140, 70, 10), { wash: '#33384A', ink: PAL.ink, sw: .8 });
  for (const x of [1500, 1600]) paint(ellPts(x, 1000, 56, 22, 14), { wash: BOY.shoe, ink: PAL.ink, sw: .7 });
  for (const [x, y] of [[160, 900], [1380, 1040]]) paint(ellPts(x, y, 26, 22, 9, 4), { wash: '#F2EFE6', ink: PAL.ink, sw: .6 });
  if (cc) {                                                              // 从箱子底下塞出来的一张画：男孩 + 橙色方块 + 爱心
    paint(rectPts(1130, 930, 230, 150, 2), { wash: '#FFFDF6', ink: PAL.ink, sw: .8 });
    paint(ellPts(1190, 980, 18, 18, 10), { ink: '#7A5332', sw: .8 }); inkLine([[1190, 998], [1190, 1050]], .8, '#3F6F9F', 'ink', 0);
    paint(rectPts(1250, 1000, 50, 36), { wash: PAL.clay, ink: PAL.ink, sw: .5 });
    paint(heartPts(1225, 960, 12), { wash: '#E2476E', ink: null });
  }
}
// ---------- 7 / 15 只淋他的雨（因为没有人关心我）：大晴天，别人戴墨镜吃冰淇淋，只有他头顶一朵乌云在下雨。第二遍：CC 站在木箱上举一片大叶子替他挡雨，云边露出太阳 ----------
function rainOnly(t, w, cc) {
  bg(tone('#D6DCE2', '#F9E4B8', w), '#F3DFA8', 90);
  paint(ellPts(260, 180, 80, 80, 18), { wash: '#FFE08A', ink: PAL.ink, sw: .6 });
  for (let i = 0; i < 6; i++) { const x = 1300 + i * 110, h = 140 + hash(i) * 160; paint(rectPts(x, 640 - h, 100, h, 2), { wash: '#C7B9A7', ink: PAL.ink, sw: .6 }); }
  paint(rectPts(-40, 640, W + 80, 480), { wash: '#BDB6AA', ink: null });
  for (let i = 0; i < 7; i++) paint(rectPts(160 + i * 240, 900, 150, 34, 1), { wash: '#F2EEE4', ink: null });   // 斑马线
  const cone = (u, sw) => { paint([[0, 0], [.7 * u, -.2 * u], [.35 * u, 1.4 * u]], { wash: '#E8C48A', ink: PAL.ink, sw: sw * .5 }); paint(ellPts(.35 * u, -.4 * u, .55 * u, .5 * u, 10), { wash: '#F5B3C6', ink: PAL.ink, sw: sw * .5 }); };
  [[220, 0, 1], [470, 3, -1], [1450, 1, -1], [1720, 4, 1]].forEach(([x, i, d]) => person(x + d * t * 40, 1000, 18, i, t, { walk: t * 2, flip: d < 0, eyes: 'shades', mouth: 'smile', aR: .7, armR: i === 3 ? cone : undefined }));
  const puddle = 1 + .1 * Math.sin(t * 6);
  paint(ellPts(960, 975, 190 * puddle, 34, 22), { wash: '#9DB4C6', ink: PAL.ink, sw: .6 });
  for (let k = 0; k < 3; k++) { const r = ((t * 60 + k * 40) % 120) + 2; paint(ellPts(900 + k * 60, 975, r, r * .2, 16), { ink: '#E8F0F6', sw: .4 }); }
  boy(960, 970, 22, { eyes: cc ? 'open' : 'sleepy', lookY: cc ? -1 : 1, mouth: cc ? 'o' : 'frown', aL: .05, aR: .05 });
  cloudAt(960, 230, 1, tone('#7D8590', '#9AA2AC', w));
  if (cc) paint(ellPts(1130, 190, 50, 50, 16), { wash: '#FFE08A', ink: PAL.ink, sw: .6 });
  cloudAt(960, 250, .85, tone('#8E96A0', '#A9B0B8', w));
  const leafY = 430;
  tagged('props', () => { for (let i = 0; i < 30; i++) {          // 雨丝
    const x = 790 + hash(i) * 340, y0 = 320 + ((hash(i + 9) * 600 + t * 900) % 620);
    if (cc && x > 800 && x < 1120 && y0 > leafY) continue;
    inkLine([[x, y0], [x - 6, y0 + 34]], .6, '#6F8DB0', 'inkfine', 0);
  } });
  if (cc) {
    paint(rectPts(1120, 860, 150, 120, 2), { wash: '#B07A4A', ink: PAL.ink, sw: .9 }); inkLine([[1120, 860], [1270, 980]], .6, PAL.ink, 'inkfine', 0);
    friend(1190, 862, 13, { eyes: 'normal', mouth: 'smile', aL: 1.9, aR: .3, noShadow: true, emote: 'sweat', emoteK: 1 });
    tagged('cc', () => {                                              // CC 举的叶子
    inkLine([[1118, 760], [1060, 520], [980, leafY + 10]], 1.4, '#4F7A44', 'ink', .4);
    paint([[760, leafY + 20], [880, leafY - 70], [1040, leafY - 80], [1160, leafY + 10], [960, leafY + 40]], { wash: '#6FAE5A', fill: '#4F8A45', fillOp: 90, ink: PAL.ink, sw: 1, curv: .5 });
    inkLine([[780, leafY + 18], [1140, leafY + 6]], .7, '#3E6B33', 'inkfine', .3);
    });
  }
}
// ---------- 8 / 16 哈哈哈（他们只会嘲笑我）：四周探出大嘴巴和「哈哈哈」气泡，他捂着耳朵闭着眼。第二遍：气泡被戳破，CC 做鬼脸（大嘴巴打开），他终于笑出来 ----------
function laughFace(t, w, cc) {
  bg(tone('#4A4E5C', '#F3D9A8', w), tone('#3B3F4C', '#EDC488', w));
  if (!cc) {
    [[120, 300], [180, 860], [1800, 280], [1760, 880], [960, -40]].forEach(([x, y]) => {
      const mx = x + (x < 960 ? 60 : -60);
      paint(ellPts(x, y, 230, 230, 22), { wash: '#2E3240', ink: PAL.ink, sw: 1 });
      paint(ellPts(mx, y + 40, 110, 80 * (1 + .25 * pulse(t, 4)), 18), { wash: '#7A2F3A', ink: PAL.ink, sw: 1 });
      for (let k = 0; k < 5; k++) paint(rectPts(mx - 80 + k * 32, y - 30, 26, 24, 1), { wash: '#FFF8EA', ink: null });
    });
    [[420, 220, 120, '哈哈哈'], [1500, 200, 110, 'HAHA'], [380, 640, 100, 'lol'], [1530, 640, 120, '哈哈'], [960, 160, 90, '笑死']].forEach(([x, y, r, s], i) =>
      bubble(x, y, r * (1 + .12 * pulse(t + i * .13, 5)), s, (i - 2) * .12));
    boy(960, 1000, 24, { eyes: 'closed', mouth: 'frown', armLen: 4.6, aL: 2.9, aR: 2.9, emote: 'sweat', emoteK: 1 });
  } else {
    for (let i = 0; i < 40; i++) paint(rectPts(hash(i) * W, (hash(i + 7) * 1200 + t * 160) % 1200 - 60, 14, 22, 2), { wash: PEOPLE[i % 8], ink: null });   // 彩纸
    tagged('props', () => [[420, 220], [1500, 200], [380, 640], [1530, 640]].forEach(([x, y], i) => {
      for (let k = 0; k < 6; k++) { const a = k / 6 * TAU + i, d = 60 + t * 50; const fx = x + Math.cos(a) * d, fy = y + Math.sin(a) * d;     // 气泡碎片
        paint([[fx - 16, fy - 8], [fx + 6, fy - 18], [fx + 18, fy + 4], [fx - 4, fy + 14]].map(([px, py]) => [fx + (px - fx) * Math.cos(a) - (py - fy) * Math.sin(a), fy + (px - fx) * Math.sin(a) + (py - fy) * Math.cos(a)]), { wash: '#FFF8EA', ink: PAL.ink, sw: .6 }); }
      sfx('啵!', x, y, 54, '#C8323C', t - i * .15, { font: HAND(54), life: 1.6 });
    }));
    boy(820, 1000, 24, { eyes: 'happy', mouth: 'grin', blush: true, aL: .5, aR: -.35, emote: 'music', emoteK: 1 });
    friend(1260, 1000, 19, { lid: .55 + .15 * Math.sin(t * 10), eyes: 'swirl', aL: 1.2 + .4 * Math.sin(t * 8), aR: 1.2 - .4 * Math.sin(t * 8), dy: -Math.abs(Math.sin(t * 5)) * .4 });
  }
}
// ---------- 17 情侣走过（我看到情侣们从我身边走过）：傍晚公园长椅，情侣牵手走过；这一次他把一只耳机分给了旁边的 CC ----------
function park(t) {
  bg('#F4C590', '#E99A7A', 140);
  paint(ellPts(1500, 600, 120, 120, 20), { wash: '#FFD27A', fill: '#FFB45A', fillOp: 80, ink: PAL.ink, sw: .6 });
  for (const [x, y] of [[300, 120], [620, 80], [1180, 140], [1700, 100]]) paint(starPts(x, y, 9 + 3 * Math.sin(t * 3 + x)), { wash: '#FFF2C4', ink: null });
  for (let i = 0; i < 12; i++) { const x = -40 + i * 170, h = 90 + hash(i + 2) * 150; paint(rectPts(x, 600 - h, 150, h, 2), { wash: '#B9787A', fill: '#9C6070', fillOp: 60, ink: PAL.ink, sw: .5 }); }
  paint(rectPts(-40, 590, W + 80, 530), { wash: '#8FA36A', fill: '#6E8A55', fillOp: 90, tex: .7, ink: null });
  paint([[-40, 1080], [520, 700], [760, 700], [700, 1080]], { wash: '#E2C9A0', ink: PAL.ink, sw: .6 });
  for (const [x, r] of [[180, 140], [1760, 160]]) { paint(rectPts(x - 14, 470, 28, 200, 2), { wash: '#7A5A3A', ink: PAL.ink, sw: .6 }); paint(ellPts(x, 420, r, r * .8, 20, 5), { wash: '#6E8A55', fill: '#4F6B45', fillOp: 90, ink: PAL.ink, sw: .7 }); }
  inkLine([[1320, 980], [1320, 420]], 2.2, '#3A3A44', 'ink', 0);                                 // 路灯
  paint(rrPts(1290, 380, 60, 50, 10), { wash: '#FFE9A0', ink: PAL.ink, sw: .8 });
  paint(ellPts(1320, 420, 120, 90, 18), { fill: '#FFE9A0', fillOp: 60, bleed: .4, ink: null });
  const px = 1700 - t * 150;                                                                     // 后面一对情侣从右往左走过
  person(px, 700, 11, 7, t, { walk: t * 2, flip: true, eyes: 'happy', mouth: 'smile', aL: .5 }); person(px + 120, 700, 11, 0, t, { walk: t * 2, flip: true, eyes: 'happy', mouth: 'smile', aR: .5 });
  emote('heart', px + 60, 580, 12, 1);
  paint(rectPts(560, 700, 800, 40, 2), { wash: '#9A6B47', ink: PAL.ink, sw: .9 }); paint(rectPts(560, 760, 800, 40, 2), { wash: '#9A6B47', ink: PAL.ink, sw: .9 });   // 长椅
  paint(rectPts(540, 830, 840, 30, 2), { wash: '#8A5E3E', ink: PAL.ink, sw: 1 });
  for (const x of [600, 1300]) paint(rectPts(x, 860, 24, 140, 1), { wash: '#3A3A44', ink: PAL.ink, sw: .7 });
  boy(860, 840, 20, { sit: true, legDrop: 6.4, eyes: 'happy', mouth: 'smile', buds: 'left', aL: .1, aR: -.3, blush: true });
  friend(1090, 842, 13, { eyes: 'happy', mouth: 'smile', aL: .3, aR: .3, noShadow: true, emote: 'music', emoteK: 1 });
  tagged('male', () => inkLine([[862, 840 + 7.6 * 20 - 11.2 * 20], [960, 820], [1028, 760], [1028, 790]], .9, BOY.bud, 'ink', .5));    // 分出去的那根耳机线
  tagged('cc', () => paint(ellPts(1026, 792, 7, 7, 8), { wash: BOY.bud, ink: PAL.ink, sw: .5 }));
  const qx = 100 + t * 90;                                                                      // 前面一对情侣牵着手走过
  person(qx, 1060, 17, 2, t, { walk: t * 2, eyes: 'happy', mouth: 'smile', aR: .6 }); person(qx + 190, 1060, 17, 5, t, { walk: t * 2, eyes: 'happy', mouth: 'smile', aL: .6 });
  emote('heart', qx + 95, 870, 16, 1);
  for (let i = 0; i < 4; i++) { const k = (t * .6 + i * .25) % 1; emote('music', 900 + i * 50 + 40 * Math.sin(k * 6), 640 - k * 260, 9, 1 - k); }
}

node('node_01', '醒来', LY.a1, 'bottom', t => bedroom(t, 0, false));
node('node_02', '一个人的秋千', LY.a2, 'top', t => playground(t, 0, false));
node('node_03', '玻璃罐', LY.b1, 'top', t => streetJar(t, 0, false));
node('node_04', '零条消息', LY.b2, 'top_left', t => phoneClose(t, 0, false));
node('node_05', '笑脸面具', LY.c1, 'top', t => masks(t, 0, false));
node('node_06', '纸箱', LY.c2, 'top', t => boxHide(t, 0, false));
node('node_07', '只淋他的雨', LY.d1, 'top_left', t => rainOnly(t, 0, false));
node('node_08', '哈哈哈', LY.d2, 'bottom', t => laughFace(t, 0, false));
node('node_09', '窗台上的橙色', LY.a1, 'bottom', t => bedroom(t, 1, true));
node('node_10', '秋千上的CC', LY.a2, 'top', t => playground(t, 1, true));
node('node_11', '敲玻璃', LY.b1, 'top', t => streetJar(t, 1, true));
node('node_12', '第一条消息', LY.b2, 'top_left', t => phoneClose(t, 1, true));
node('node_13', '没戴面具的', LY.c1, 'top', t => masks(t, 1, true));
node('node_14', '纸箱里的光', LY.c2, 'top', t => boxHide(t, 1, true));
node('node_15', '一片叶子', LY.d1, 'top_left', t => rainOnly(t, 1, true));
node('node_16', '鬼脸', LY.d2, 'top', t => laughFace(t, 1, true));
node('node_17', '一人一只耳机', LY.e1, 'top', t => park(t));
