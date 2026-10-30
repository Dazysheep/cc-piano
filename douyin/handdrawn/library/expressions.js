// 手绘表情库：男生 / 女生小人的表情动作，每个是 3 秒无缝循环（80 BPM = 4 拍），透明底。
// 场景名 = <male|female>_<名字>；导出到 douyin/assets/clawd/handdrawn/<male|female>/<名字>.webp（tools 见 export.py）。
// 画法见 engine/ANIMATION_GUIDE_原版.md：clawd() / clawdGirl() 的 eyes、mouth、emote、mood、move。

const EX = { w: 460, h: 400, dur: 3, alpha: true, bpm: 80, off: 0 };
const GX = 230, GY = 352, GU = 25;                       // 地面点和身体单位
const loop = t => (t % 3) / 3;                           // 0..1 一个循环
const sinL = (t, n = 1, ph = 0) => Math.sin((loop(t) * n + ph) * TAU);

function expr(who, name, zh, fn) {
  scene(`${who}_${name}`, { ...EX, zh, who }, t => fn(t, who === 'female' ? clawdGirl : clawd));
}
// 手机道具（拿在右手）
const phoneHook = (glow = 0) => (u, sw) => {
  paint(rrPts(-.2 * u, -1.6 * u, 1.6 * u, 2.8 * u, .3 * u), { wash: '#3A3F55', ink: PAL.ink, sw: sw * .7 });
  paint(rrPts(.0 * u, -1.35 * u, 1.2 * u, 2.2 * u, .2 * u), { wash: glow > 0 ? mixCol('#20263A', '#BFE3FF', glow) : '#20263A', ink: null });
};
// 头顶的回忆小圆点（往右上冒三个）
function thoughtDots(x, y, u, k) { return tagged('male', () => thoughtDotsRaw(x, y, u, k)); }
function thoughtDotsRaw(x, y, u, k) {
  [[0, 0, .5], [1.2, -1.3, .75], [2.8, -2.9, 1.05]].forEach(([dx, dy, r], i) => {
    const p = clamp(k * 3 - i); if (p <= 0) return;
    paint(ellPts(x + dx * u, y + dy * u, r * u * backOut(p), r * u * backOut(p), 14), { wash: PAL.cream, washOp: 235, ink: PAL.ink, sw: .6 });
  });
}
function twinkle(x, y, r, t, seed) {
  const k = .55 + .45 * Math.sin(t * 5 + seed * 7);
  paint(starPts(x, y, r * k, .35, 4), { wash: '#FFE9A8', fill: PAL.ochre, fillOp: 60, ink: PAL.ink, sw: .45 });
}

// ---------------------------------------------------------------- 男生（读评论、想起往事的那个）
expr('male', 'read_comment', '低头读评论（手机）', (t, C) => {
  const nod = Math.max(0, sinL(t, 2)) * .25;
  C(GX, GY, GU, { eyes: 'look', lookX: .3, lookY: .8, mouth: 'flat', aR: .9, aL: -.2, dy: -nod * .3, armR: phoneHook(.6), seed: 1 });
});
expr('male', 'remember', '想起往事（冒回忆泡泡）', (t, C) => {
  const k = loop(t);
  C(GX - 30, GY, GU, { eyes: 'look', lookX: .7, lookY: -.9, mouth: k > .5 ? 'smile' : 'flat', aL: -.3, aR: 1.2, rot: -.04 * sinL(t), blush: k > .55 });
  thoughtDots(GX + 120, GY - 230, GU * .9, clamp(k * 1.6));
});
expr('male', 'daze', '发呆、没有表情', (t, C) => {
  C(GX, GY, GU, { eyes: 'dot', mouth: 'flat', aL: -.6, aR: -.6, rot: .03 * sinL(t), sq: .02 * sinL(t, 2) });
});
expr('male', 'head_down_walk', '低头赶路（天还黑着）', (t, C) => {
  const m = move('walk', t);
  C(GX, GY, GU, { ...m, eyes: 'look', lookY: 1, mouth: 'flat', emote: 'sweat', emoteK: .8, rot: .05 });
});
expr('male', 'look_up_stars', '猛然抬头看见星星', (t, C) => {
  const k = loop(t), up = ease(seg(k, .1, .35));
  C(GX, GY, GU, { eyes: k > .45 ? 'spark' : 'look', lookY: lerp(.8, -1, up), mouth: k > .45 ? 'O' : 'flat', dy: -up * .4, rot: -up * .12, aL: lerp(-.3, .5, up), aR: lerp(-.3, .5, up) });
  if (k > .4) [[90, 70], [370, 60], [60, 160], [400, 150], [230, 30]].forEach(([x, y], i) => twinkle(x, y, 13 + 5 * hash(i), t, i));
});
expr('male', 'tears_smile', '哭着笑（因为幸福）', (t, C) => {
  C(GX, GY, GU, { eyes: 'happy', mouth: 'smile', blush: true, aL: .9 + .15 * sinL(t, 2), aR: .9 - .15 * sinL(t, 2), dy: -Math.abs(sinL(t, 2)) * .3 });
  tears(GX, GY, GU, loop(t * 2));
});
expr('male', 'yawn', '熬夜、打哈欠', (t, C) => {
  const k = loop(t), y = Math.sin(clamp(k * 1.6) * Math.PI);
  C(GX, GY, GU, { eyes: y > .3 ? 'closed' : 'narrow', mouth: y > .3 ? 'O' : 'flat', aL: .2 + y, aR: .2 + y, sq: -y * .06, emote: 'zzz', emoteK: seg(k, .5, .7) });
});
expr('male', 'surprised', '一愣（!）', (t, C) => {
  const k = loop(t), m = mood(k * 3, [[0, 'normal'], [.5, 'scared', '!'], [1.8, 'spark']]);
  C(GX, GY, GU, { ...m, mouth: k > .17 ? 'O' : 'flat', aL: k > .17 ? .9 : .1, aR: k > .17 ? .9 : .1 });
});
expr('male', 'shy', '害羞（捂脸）', (t, C) => {
  C(GX, GY, GU, { eyes: 'happy', mouth: 'wobble', blush: true, aL: 1.9, aR: 1.9, rot: .05 * sinL(t, 2), sq: .03 * sinL(t, 4) });
});
expr('male', 'run_home', '一路跑回家', (t, C) => {
  const m = move('run', t);
  C(GX, GY, GU, { ...m, eyes: 'happy', mouth: 'grin' });
  for (let i = 0; i < 3; i++) inkLine([[GX - 170 - i * 18, GY - 120 + i * 40], [GX - 230 - i * 18, GY - 120 + i * 40]], .8, PAL.ink, 'dry', 0);
});
expr('male', 'sigh', '叹一口气', (t, C) => {
  const k = loop(t), b = Math.sin(clamp(k * 1.4) * Math.PI);
  C(GX, GY, GU, { eyes: 'closed', mouth: 'o', sq: b * .08, aL: -.5, aR: -.5 });
  if (b > .2) paint(ellPts(GX + 70 + b * 40, GY - 110 - b * 30, 18 * b + 6, 12 * b + 4, 14), { fill: '#FFFFFF', fillOp: 120, bleed: .3, ink: PAL.ink, sw: .4 });
});
expr('male', 'cheer', '欢呼', (t, C) => {
  const m = move('hop', t);
  C(GX, GY, GU, { ...m, aL: 1.6, aR: 1.6, eyes: 'happy', mouth: 'grin', emote: 'spark', emoteK: 1 });
});

// ---------------------------------------------------------------- 女生（左下角唱歌的那个）
expr('female', 'sing', '唱歌', (t, C) => {
  const m = move('sway', t), open = Math.abs(sinL(t, 4)) > .5;
  C(GX, GY, GU, { ...m, mouth: open ? 'O' : 'o', emote: 'music', emoteK: 1 });
});
expr('female', 'sing_closed', '闭眼唱', (t, C) => {
  C(GX, GY, GU, { eyes: 'closed', mouth: Math.abs(sinL(t, 4)) > .5 ? 'O' : 'o', rot: .07 * sinL(t), aL: .5 + .2 * sinL(t), aR: .5 - .2 * sinL(t), blush: true });
});
expr('female', 'clap', '鼓掌', (t, C) => {
  const c = Math.abs(sinL(t, 4));
  C(GX, GY, GU, { eyes: 'happy', mouth: 'grin', aL: .6 + c * .8, aR: .6 + c * .8, dy: -c * .2 });
});
expr('female', 'heart', '比心', (t, C) => {
  C(GX, GY, GU, { eyes: 'heart', mouth: 'smile', blush: true, aL: 1.4, aR: 1.4, emote: 'heart', emoteK: .6 + .4 * Math.abs(sinL(t, 2)) });
});
expr('female', 'wipe_tear', '擦眼泪', (t, C) => {
  C(GX, GY, GU, { eyes: 'closed', mouth: 'wobble', aL: 1.9 + .15 * sinL(t, 4), aR: -.4 });
  tears(GX, GY, GU, loop(t * 1.5));
});
expr('female', 'look_up', '抬头看天', (t, C) => {
  const up = ease(seg(loop(t), 0, .3));
  C(GX, GY, GU, { eyes: 'look', lookY: -up, mouth: 'smile', rot: -up * .1, aL: .3, aR: .3 });
  if (up > .9) [[80, 60], [380, 80], [230, 30]].forEach(([x, y], i) => twinkle(x, y, 14, t, i + 3));
});
expr('female', 'wave', '挥手', (t, C) => {
  const m = move('wave', t);
  C(GX, GY, GU, { ...m, eyes: 'happy', mouth: 'smile' });
});
expr('female', 'comfort', '安慰（摸摸头）', (t, C) => {
  C(GX, GY, GU, { eyes: 'happy', mouth: 'smile', aL: 1.2 + .25 * sinL(t, 4), aR: -.2, blush: true, emote: 'heart', emoteK: .7 });
});
expr('female', 'sway_listen', '听歌轻轻晃', (t, C) => {
  const m = move('sway', t);
  C(GX, GY, GU, { ...m, eyes: 'closed', mouth: 'smile', emote: 'music', emoteK: .8 });
});
expr('female', 'surprised', '惊喜', (t, C) => {
  const k = loop(t), m = mood(k * 3, [[0, 'normal'], [.4, 'spark', '!']]);
  C(GX, GY, GU, { ...m, mouth: k > .13 ? 'O' : 'smile', aL: k > .13 ? 1.3 : .2, aR: k > .13 ? 1.3 : .2 });
});
