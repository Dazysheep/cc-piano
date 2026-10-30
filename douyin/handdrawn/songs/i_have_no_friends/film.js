// 《i have no friends》全片（38 秒，17 镜）：每镜用 scenes.js 里对应节点的画面本体（NODEFN.node_NN）+ 轻微运镜，
// 转场照剧本「转场」一栏逐个画（都在剪切点前后，卡在节拍上），字幕按逐字时间亮起（英文 + 中文翻译）。
// 分层：转场 tagged('trans')，字幕 tagged('subs')（分层工程里字幕不渲染，改成剪辑器里可编辑的网页片段）。
const SH = FILM.shots, LYR = FILM.lines, CUT = .22, BIG = .45;    // 第二遍开头的「倒带」转场更长

// 每镜运镜：[起始缩放, 结束缩放, 中心 x, 中心 y]（缩放 ≥ 1，不露边）
const CAMS = [[1, 1.07, 700, 560], [1, 1, 960, 540], [1, 1.04, 960, 600], [1.02, 1.07, 900, 560], [1.06, 1.06, 900, 600], [1, 1.03, 960, 600],
              [1, 1.05, 960, 620], [1.03, 1.03, 960, 560], [1, 1.07, 760, 560], [1, 1.02, 960, 540], [1, 1.04, 1000, 600], [1.02, 1.08, 1000, 520],
              [1.06, 1.06, 1100, 600], [1, 1.04, 1000, 560], [1, 1.05, 980, 600], [1.02, 1, 1000, 560], [1.12, 1, 960, 640]];
function shotAt(t) { let i = 0; while (i + 1 < SH.length && t >= SH[i + 1].from) i++; return i; }
function drawShot(i, lt) {
  const s = SH[i], d = s.to - s.from, [z0, z1, cx, cy] = CAMS[i], k = ease(clamp(lt / d));
  let x = cx, y = cy;
  if (i === 4 || i === 12) x = lerp(cx - 70, cx + 70, k);                 // 面具走廊：横移
  if (i === 7) { const [dx, dy] = shakeXY(lt, 7 * pulse(s.from + lt, 5)); x += dx; y += dy; }   // 笑声：跟着节拍震
  camBegin(x, y, lerp(z0, z1, k));
  NODEFN[`node_${String(i + 1).padStart(2, '0')}`](lt);
  camEnd();
}

// ================================================================ 转场（p：0 → 1，0.5 = 剪切点；cover：0 → 1 → 0）
function transition(type, p, idx) { return tagged('trans', () => transitionRaw(type, p, idx)); }
function transitionRaw(type, p, idx) {
  const cover = 1 - Math.abs(p - .5) * 2, c = ease(cover);
  if (type === 'page') {                                          // 撕下的日历页横扫过画面
    const x = lerp(W + 1300, -1300, p), y = H / 2 + 60 * Math.sin(p * 3);
    push(); translate(x, y); rotate(-.12 + p * .2);
    const edge = []; for (let i = 0; i <= 16; i++) edge.push([-1250 + (i % 2 ? 26 : 0), -900 + i * 112]);
    paint([[1250, -900], [1250, 900], ...edge.reverse()], { wash: PAL.cream, fill: '#E8DFCB', fillOp: 70, ink: PAL.ink, sw: 1.4 });
    paint(rectPts(-1250, -900, 2500, 240), { wash: '#C8323C', ink: null });
    pop();
    letter('29', x, y + 60, 520, '#B9B3A8', { ink: false, font: HAND(520), rot: -.12 + p * .2 });
    return;
  }
  if (type === 'lid') {                                           // 玻璃罐的盖子（铁皮卷帘）咚地砸下来
    const h = (H + 80) * (p < .5 ? easeIn(cover) : c);
    if (h > 4) {
      paint(rectPts(-40, -40, W + 80, h, 2), { wash: '#9AA3AD', fill: '#7D8691', fillOp: 80, ink: PAL.ink, sw: 1.4 });
      for (let i = 0; i < 24; i++) inkLine([[i * 84, -40], [i * 84, h - 50]], .6, '#5E6670', 'inkfine', 0);
    }
    if (cover > .85) sfx('咚！', W / 2, H / 2, 160, PAL.ink, (p - .4) * 3, { font: HAND(160), life: .5 });
    return;
  }
  if (type === 'flash') { flash(c, '#E2EEFF'); return; }        // 推进屏幕的冷光
  if (type === 'ding') {                                          // 「叮」：暖色白闪 + 声波圈
    flash(c, '#FFF3DA');
    for (let i = 0; i < 3; i++) { const r = 80 + (p * 900 + i * 160) % 700; paint(ellPts(1340, 420, r, r, 30), { ink: '#E8A04A', sw: 1.6 * cover }); }
    return;
  }
  if (type === 'mask') {                                          // 一张笑脸面具翻过整个画面
    if (c < .01) return;
    push(); translate(W / 2, H / 2); scale(Math.max(.15, Math.abs(Math.cos((p - .5) * Math.PI * 1.6))), 1); translate(-W / 2, -H / 2);   // 横向翻面
    maskAtRaw(W / 2, H / 2, 300 * c);
    pop();
    return;
  }
  if (type === 'masks') {                                         // 面具一个个掉下来
    for (let i = 0; i < 26; i++) {
      const x = hash(i + 3) * W, y = lerp(-500, H + 500, clamp(p * 1.4 - hash(i) * .4)) , u = 32 + hash(i + 9) * 26;
      if (y > -300 && y < H + 300) maskAtRaw(x, y, u);
    }
    flash(c * .85, '#FFF8EA');
    return;
  }
  if (type === 'dark') { flash(c, '#15131B'); if (cover > .6) sfx('啪', W / 2, H / 2, 90, '#EDE6DA', (p - .35) * 3, { font: HAND(90), life: .5 }); return; }   // 关灯
  if (type === 'rain') {                                          // 雨丝从上往下刷过
    paint(rectPts(-40, -40, W + 80, (H + 80) * clamp(p * 2), 1), { wash: '#6F7F98', washOp: 230 * c, ink: null });
    for (let i = 0; i < 70; i++) { const x = hash(i) * W, y = lerp(-300, H + 300, clamp(p * 1.6 - hash(i + 5) * .6)); inkLine([[x, y], [x - 14, y + 120]], .8, '#D6E4F2', 'inkfine', 0); }
    return;
  }
  if (type === 'bubbles') {                                       // 笑声气泡一个接一个砸进来 + 震
    [[300, 260], [1600, 220], [960, 560], [380, 860], [1560, 860], [960, 120], [960, 980]].forEach(([x, y], i) => {
      const r = 780 * ease(clamp(cover * 1.6 - i * .1));
      if (r > 8) { paint(starPts(x, y, r, .82, 13, i), { wash: '#FFF8EA', ink: PAL.ink, sw: 1.2 }); letter(['哈', 'HA', '哈哈', 'lol', '哈', '笑', 'HA'][i], x, y, r * .5, '#C8323C', { ink: false, font: HAND(Math.round(r * .5)) }); }
    });
    return;
  }
  if (type === 'rewind') {                                        // 磁带倒带：横条乱跳，冷灰褪成暖色
    const n = 16, col = mixCol('#9DA6B3', '#F2C38C', ease(p));
    for (let i = 0; i < n; i++) {
      const y = i * H / n - 10, off = (hash(i + Math.floor(p * 40)) - .5) * 260 * cover, w = (W + 400) * c;
      if (w > 10) paint(rectPts(W / 2 - w / 2 + off, y, w, H / n + 22), { wash: i % 2 ? col : mixCol(col, '#FFFFFF', .25), ink: null });
    }
    if (cover > .3) {
      letter('◀◀', W / 2, H / 2 - 40, 220, PAL.ink, { ink: false, alpha: c });
      letter('REWIND', W / 2, H / 2 + 130, 70, PAL.ink, { ink: false, font: HAND(70), alpha: c });
    }
    return;
  }
  if (type === 'swing') {                                         // 甩镜：横向速度线 + 一道橙色残影
    paint(rectPts(-40, -40, W + 80, H + 80), { wash: '#F6DDB0', washOp: 235 * c, ink: null });
    for (let i = 0; i < 40; i++) { const y = hash(i) * H, x = lerp(W + 300, -900, clamp(p * 1.3 - hash(i + 2) * .3)); inkLine([[x, y], [x + 500 + hash(i + 4) * 600, y]], .9, '#C9A26C', 'inkfine', 0); }
    paint(rrPts(lerp(W, -600, p), 420, 600, 180, 60), { fill: PAL.clay, fillOp: 160 * cover, bleed: .3, ink: null });
    return;
  }
  if (type === 'crack') {                                         // 玻璃裂纹蔓延满屏，再碎开往下掉
    if (p < .5) {
      flash(c * .7, '#F4FAFF');
      for (let i = 0; i < 14; i++) {
        const a = i / 14 * TAU + hash(i) * .3, L = 2200 * easeIn(p * 2), pts = [[1218, 700]];
        for (let k = 1; k <= 6; k++) pts.push([1218 + Math.cos(a + (hash(i * 7 + k) - .5) * .5) * L * k / 6, 700 + Math.sin(a + (hash(i * 7 + k) - .5) * .5) * L * k / 6]);
        inkLine(pts, 1.4, PAL.ink, 'ink', 0);
      }
    } else {
      for (let i = 0; i < 40; i++) {
        const x = hash(i) * W, y = hash(i + 9) * H + easeIn((p - .5) * 2) * (600 + hash(i + 4) * 600), r = 80 + hash(i + 2) * 120;
        paint([[x, y - r], [x + r * .9, y + r * .4], [x - r * .7, y + r * .6]], { wash: '#F4FAFF', washOp: 255 * c, ink: PAL.ink, sw: .8 * c });
      }
    }
    return;
  }
  if (type === 'torch') {                                         // 手电光：从把手孔圈开
    const r = 1400 * (1 - c);
    iris(960, 750, Math.max(r, 2), '#1E1820');
    if (r > 20 && r < 1300) paint(ellPts(960, 750, r + 14, r + 14, 40), { ink: '#FFD27A', sw: 2.4 });
    return;
  }
  if (type === 'leaf') {                                          // 一片大叶子从右边甩进来
    const x = lerp(W + 1500, -1500, p);
    push(); translate(x, H / 2); rotate(-.25 + p * .3);
    paint([[-1500, 0], [-700, -760], [500, -880], [1500, -60], [600, 760], [-700, 720]], { wash: '#6FAE5A', fill: '#4F8A45', fillOp: 90, ink: PAL.ink, sw: 1.6, curv: .6 });
    inkLine([[-1450, 0], [1450, -40]], 2.4, '#3E6B33', 'ink', .3);
    for (let i = 0; i < 6; i++) inkLine([[-900 + i * 380, -10 - i * 6], [-600 + i * 380, -520 + i * 40]], 1.2, '#3E6B33', 'ink', .4);
    pop();
    return;
  }
  if (type === 'confetti') {                                      // 气泡啵地炸成彩纸
    flash(c * .7, '#FFF3DA');
    const n = Math.floor(420 * c);
    for (let i = 0; i < n; i++) {
      const x = hash(i) * W, y = hash(i + 11) * H + p * 200;
      push(); translate(x, y); rotate(hash(i + 5) * TAU + p * 6); paint(rectPts(-14, -22, 28, 44), { wash: PEOPLE[i % 8], ink: null }); pop();
    }
    return;
  }
  if (type === 'cable') {                                         // 耳机线拉成一条线，把画面带到黄昏公园
    paint(rectPts(-40, -40, W + 80, H + 80), { wash: '#F4C590', washOp: 230 * c, ink: null });
    const k = clamp(p * 1.6), pts = [];
    for (let i = 0; i <= 20; i++) { const x = -60 + i / 20 * (W + 120) * k; pts.push([x, H / 2 + 120 * Math.sin(i * .7 + p * 4)]); }
    if (k > .02) inkLine(pts, 2.6, '#FFFFFF', 'ink', .5);
    if (k > .02) paint(ellPts(pts[pts.length - 1][0], pts[pts.length - 1][1], 16, 16, 10), { wash: '#FFFFFF', ink: PAL.ink, sw: .8 });
    return;
  }
  flash(c);
}
function opening(t) {                                             // 片头：从黑场里撕开一个口子
  const k = easeOut(clamp(t / .5));
  if (k < 1) tagged('trans', () => irisShape(starPts(W / 2, H / 2, Math.max(2, 1500 * k), .86, 18, k), '#1E1820'));
}
function ending(t) {                                              // 片尾 0.9 秒淡出
  const k = clamp((t - (FILM.dur - .9)) / .9);
  if (k > 0) tagged('trans', () => flash(k, '#1E1820'));
}

// ================================================================ 字幕（平面成片用；分层工程里是可编辑的网页片段）
function filmSubs(t, shot) { return tagged('subs', () => filmSubsRaw(t, shot)); }
function filmSubsRaw(t, shot) {
  const i = LYR.findIndex((l, j) => { const nx = LYR[j + 1]; return t >= l.s - .12 && t < (nx ? Math.min(l.e + .5, nx.s - .02) : l.e + .6); });
  if (i < 0) return;
  const l = LYR[i], [en, zh] = l.text.split('，'), [x, y] = SUBPOS[shot.sub] || SUBPOS.bottom;
  const on = l.w.filter(w => w[1] <= t + 1e-3).length, nEn = en.replace(/\s/g, '').length;
  const fade = clamp((t - l.s + .12) / .15) * (1 - clamp((t - l.e - .35) / .15));
  const st = (sz) => ({ screen: true, ink: false, stroke: 'rgba(43,34,51,.9)', font: HAND(sz), alpha: fade });
  const upto = (s, n) => { let k = 0, j = 0; while (j < s.length && k < n) { if (!/\s/.test(s[j])) k++; j++; } return j; };   // 前 n 个非空格字符在字符串里的长度
  const enOn = Math.min(on, nEn), zhOn = l.w.slice(nEn).filter(w => w[1] <= t + 1e-3).length;
  letter(en, x, y, 54, PAL.cream, st(54));
  if (enOn > 0) letter(en, x, y, 54, '#FFD36B', { ...st(54), clipChars: upto(en, enOn) });
  letter(zh, x, y + 60, 34, '#EDE6DA', st(34));
  if (zhOn > 0) letter(zh, x, y + 60, 34, '#FFD36B', { ...st(34), clipChars: zhOn });
}

// ================================================================ 全片
scene('film', { w: 1920, h: 1080, dur: FILM.dur, bpm: FILM.bpm, off: FILM.beat0, zh: '整段歌词动画（全手绘，17 镜）' }, t => {
  const i = shotAt(t), s = SH[i];
  drawShot(i, t - s.from);
  CAM = null; flushLetters();
  const nxt = SH[i + 1], prev = SH[i], half = j => (SH[j].tr === 'rewind' ? BIG : CUT);
  if (nxt && nxt.from - t < half(i + 1)) transition(nxt.tr, (t - (nxt.from - half(i + 1))) / (2 * half(i + 1)), i + 1);
  else if (i > 0 && t - prev.from < half(i)) transition(prev.tr, (t - (prev.from - half(i))) / (2 * half(i)), i);
  opening(t); ending(t);
  flushLetters();
  filmSubs(t, s);
});
// 转场预览：tr_NN（剪切点前后各 0.6 秒）
SH.forEach((s, i) => { if (i > 0) scene(`tr_${String(i).padStart(2, '0')}`, { w: 1920, h: 1080, dur: 1.2, bpm: FILM.bpm, off: FILM.beat0, zh: '转场 ' + s.tr },
  lt => SCENES.film.fn(s.from - .6 + lt)); });
