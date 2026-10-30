/* 生成进度卡：点了「生成」之后，页面右侧浮现一张小的竖向圆角卡片（紫→靛蓝渐变，顶部一道浅色波浪，
   中间是六边形音符图标、百分比和当前阶段）。卡片里的水按进度往上涨，涨满 = 生成完成（图标变成对勾）。
   几个音符沿倾斜的椭圆轨道立体地绕着卡片转：在前面时清晰；转到卡片后面时透过半透明的卡片隐约可见，
   被水流折射（随水波扭曲）并且发虚。
   进度读的是页面原有的进度条（#meter 里的百分比、阶段文字、失败状态），不改页面自己的逻辑；原来的横线进度条隐藏，错误日志照常显示。
   用法：WaterProgress.attach({ meter: "#meter", pct: "#pctText", stage: "#stageText" })   样式由本文件注入。 */
(function () {
  const CW = 236, CH = 300;                                   // 画布（卡片 + 音符轨道的空间）
  const C = { x: 50, y: 52, w: 136, h: 186, r: 18 };          // 卡片
  const CSS = `
.wp { position: fixed; z-index: 60; right: 4px; bottom: 76px; width: ${CW}px; height: ${CH}px; pointer-events: none;
  opacity: 0; transform: translateX(40px) scale(.88); transition: opacity .45s, transform .65s cubic-bezier(.2,.8,.2,1.2); }
.wp.on { opacity: 1; transform: none; }
.wp canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
.wp .frost { position: absolute; z-index: 0; left: ${C.x}px; top: ${C.y}px; width: ${C.w}px; height: ${C.h}px; border-radius: ${C.r}px;
  backdrop-filter: blur(14px) saturate(1.2); -webkit-backdrop-filter: blur(14px) saturate(1.2); }
.wp .back { z-index: 1; } .wp .front { z-index: 3; }
.wp .face { position: absolute; z-index: 2; left: ${C.x}px; top: ${C.y}px; width: ${C.w}px; height: ${C.h}px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 6px; padding: 0 10px; text-align: center; color: #fff;
  font-family: "Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei UI", sans-serif; }
.wp .face svg { width: 42px; height: 42px; margin-bottom: 8px; fill: none; stroke: #fff; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round;
  filter: drop-shadow(0 4px 10px rgba(0,0,0,.25)); }
.wp .face .ok { display: none; }
.wp.done .face .ok { display: block; } .wp.done .face .mark { display: none; }
.wp .face b { font-size: 22px; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; text-shadow: 0 2px 10px rgba(0,0,0,.2); }
.wp .face small { font-size: 11.5px; opacity: .82; line-height: 1.35; max-height: 3.2em; overflow: hidden; }
@media (max-width: 700px) { .wp { transform-origin: right center; scale: .72; } }`;
  const GLYPHS = ["♪", "♫", "♩", "♬"];

  window.WaterProgress = {
    attach(opts = {}) {
      const meter = document.querySelector(opts.meter || "#meter");
      if (!meter) return;
      // 原来的横线进度条和状态行隐藏（按 id 写规则：有的页面开始生成时会整个重写 className）
      const sel = opts.meter || "#meter";
      const st = document.createElement("style");
      st.textContent = CSS + `\n${sel} .staff, ${sel} .bar, ${sel} .status { display: none !important; }`;
      document.head.appendChild(st);
      const pctEl = document.querySelector(opts.pct || "#pctText"), stageEl = document.querySelector(opts.stage || "#stageText");
      const box = document.createElement("div");
      box.className = "wp"; box.setAttribute("role", "progressbar"); box.setAttribute("aria-valuemin", "0"); box.setAttribute("aria-valuemax", "100");
      box.innerHTML = `<i class="frost"></i><canvas class="back"></canvas>
        <div class="face">
          <svg class="mark" viewBox="0 0 48 48"><path d="M24 4.5 41 14.3v19.4L24 43.5 7 33.7V14.3z"/><path d="M21 31.5a3.6 3.6 0 1 1-2.4-3.4V16.5l10-2.2v11.4a3.6 3.6 0 1 1-2.4-3.4v-5.2l-5.2 1.1z" fill="#fff" stroke="none"/></svg>
          <svg class="ok" viewBox="0 0 48 48"><path d="M24 4.5 41 14.3v19.4L24 43.5 7 33.7V14.3z"/><path d="m16 24.5 6 6 11-12"/></svg>
          <b>0%</b><small>准备中</small></div>
        <canvas class="front"></canvas>`;
      document.body.appendChild(box);
      const dpr = Math.min(devicePixelRatio || 1, 2);
      const [back, front] = [...box.querySelectorAll("canvas")].map((c) => { c.width = CW * dpr; c.height = CH * dpr; const g = c.getContext("2d"); g.scale(dpr, dpr); return g; });
      const cx = C.x + C.w / 2, cy = C.y + C.h / 2;
      const notes = Array.from({ length: 7 }, (_, i) => ({
        a: 84 + Math.random() * 18, b: 18 + Math.random() * 16, tilt: (Math.random() - 0.5) * 1.0,
        yo: (Math.random() - 0.5) * C.h * 0.85, sp: (0.45 + Math.random() * 0.55) * (Math.random() < 0.3 ? -1 : 1),
        ph: Math.random() * Math.PI * 2, glyph: GLYPHS[i % GLYPHS.length], size: 15 + Math.random() * 9,
      }));
      const bubbles = Array.from({ length: 10 }, () => ({ x: Math.random(), s: 0.3 + Math.random() * 0.7, r: 1 + Math.random() * 2, ph: Math.random() }));
      let target = 0, level = 0, state = "idle", raf = 0, hideT = 0, t0 = performance.now();

      const card = (g) => { g.beginPath(); g.roundRect(C.x, C.y, C.w, C.h, C.r); };
      function pos(n, t) {
        const th = n.ph + t * n.sp, x0 = Math.cos(th) * n.a, z = Math.sin(th), y0 = n.yo + Math.sin(th) * n.b;
        return { x: cx + x0 * Math.cos(n.tilt), y: cy + y0 + x0 * Math.sin(n.tilt) * 0.35, z };
      }
      function note(g, n, p, behind, waterY, t) {
        const sc = 0.7 + 0.3 * (p.z + 1) / 2;
        let { x, y } = p, a = behind ? 0.35 + 0.25 * (p.z + 1) : 0.95;
        const inside = x > C.x - 6 && x < C.x + C.w + 6 && y > C.y - 4 && y < C.y + C.h + 4;
        g.save();
        if (behind && inside) {                     // 隔着卡片：折射（水里扭得更厉害）+ 发虚 + 透出来的光变弱
          const wet = y > waterY;
          x += Math.sin(y * 0.11 + t * 3.2) * (wet ? 6 : 2.5) + (x - cx) * (wet ? -0.2 : -0.1);
          y += wet ? Math.sin(x * 0.08 + t * 2) * 2 : 0;
          g.filter = `blur(${wet ? 2.6 : 1.6}px)`;
          a *= wet ? 0.75 : 0.6;
          g.fillStyle = wet ? `rgba(205,235,255,${a})` : `rgba(255,255,255,${a})`;
        } else {
          if (behind) g.filter = "blur(.7px)";
          g.fillStyle = `rgba(255,255,255,${a})`;
          if (!behind) { g.shadowColor = "rgba(160,140,255,.8)"; g.shadowBlur = 10; }
        }
        g.font = `${(n.size * sc).toFixed(1)}px "Segoe UI Symbol", "Segoe UI", sans-serif`;
        g.textAlign = "center"; g.textBaseline = "middle";
        g.fillText(n.glyph, x, y);
        g.restore();
      }
      function frame(now) {
        const t = (now - t0) / 1000;
        level += (target - level) * 0.06;
        const fail = state === "fail", waterY = C.y + C.h * (1 - level);
        const pts = notes.map((n) => ({ n, p: pos(n, t) }));
        back.clearRect(0, 0, CW, CH); front.clearRect(0, 0, CW, CH);
        // 卡片外、后面的音符（在卡片之前画，被卡片挡住）
        pts.filter((o) => o.p.z < 0).forEach((o) => note(back, o.n, o.p, true, waterY, t));
        // 卡片：紫 → 靛蓝渐变（失败时变红），略透明，能透出后面的音符
        back.save();
        back.shadowColor = "rgba(40,20,90,.55)"; back.shadowBlur = 28; back.shadowOffsetY = 14;
        card(back);
        const gr = back.createLinearGradient(C.x, C.y + C.h, C.x + C.w, C.y);
        if (fail) { gr.addColorStop(0, "rgba(225,29,72,.9)"); gr.addColorStop(1, "rgba(244,114,128,.9)"); }
        else { gr.addColorStop(0, "rgba(124,58,237,.93)"); gr.addColorStop(0.6, "rgba(99,72,230,.93)"); gr.addColorStop(1, "rgba(79,110,245,.93)"); }
        back.fillStyle = gr; back.fill();
        back.restore();
        back.save(); card(back); back.clip();
        // 透过卡片看到的后面的音符（折射、发虚）
        pts.filter((o) => o.p.z < 0).forEach((o) => note(back, o.n, o.p, true, waterY, t));
        // 顶部一道浅色的大波浪（参考图的造型）
        back.beginPath(); back.moveTo(C.x, C.y + C.h * 0.36);
        back.bezierCurveTo(C.x + C.w * 0.3, C.y + C.h * 0.1, C.x + C.w * 0.7, C.y + C.h * 0.02, C.x + C.w, C.y + C.h * 0.12);
        back.lineTo(C.x + C.w, C.y); back.lineTo(C.x, C.y); back.closePath();
        back.fillStyle = "rgba(255,255,255,.1)"; back.fill();
        back.beginPath(); back.moveTo(C.x, C.y + C.h * 0.44);
        back.bezierCurveTo(C.x + C.w * 0.35, C.y + C.h * 0.16, C.x + C.w * 0.7, C.y + C.h * 0.1, C.x + C.w, C.y + C.h * 0.2);
        back.strokeStyle = "rgba(255,255,255,.12)"; back.lineWidth = 6; back.stroke();
        // 水：两层波浪往上涨 + 气泡
        if (level > 0.003) {
          for (const [top, amp, k, sp, off] of [["rgba(170,220,255,.26)", 4.5, 0.075, 2.2, -3], ["rgba(120,190,255,.32)", 3.4, 0.06, -1.6, 0]]) {
            back.beginPath(); back.moveTo(C.x, C.y + C.h);
            for (let x = C.x; x <= C.x + C.w; x += 2) back.lineTo(x, waterY + off + Math.sin(x * k + t * sp) * amp * (level < 0.995 ? 1 : 0.25));
            back.lineTo(C.x + C.w, C.y + C.h); back.closePath();
            const wg = back.createLinearGradient(0, waterY, 0, C.y + C.h);
            wg.addColorStop(0, top); wg.addColorStop(1, fail ? "rgba(120,0,30,.35)" : "rgba(40,60,200,.35)");
            back.fillStyle = wg; back.fill();
          }
          back.strokeStyle = "rgba(255,255,255,.35)"; back.lineWidth = 1.2; back.beginPath();
          for (let x = C.x; x <= C.x + C.w; x += 2) back.lineTo(x, waterY + Math.sin(x * 0.06 - t * 1.6) * 3.4 * (level < 0.995 ? 1 : 0.25));
          back.stroke();
          for (const bb of bubbles) {
            const yy = C.y + C.h - ((t * 20 * bb.s + bb.ph * C.h) % (C.h * level + 1));
            if (yy < waterY + 5) continue;
            back.beginPath(); back.arc(C.x + 10 + bb.x * (C.w - 20) + Math.sin(t * 2 + bb.ph * 9) * 2, yy, bb.r, 0, Math.PI * 2);
            back.fillStyle = "rgba(255,255,255,.4)"; back.fill();
          }
        }
        back.restore();
        // 卡片的细边
        back.save(); card(back); back.lineWidth = 1; back.strokeStyle = "rgba(255,255,255,.22)"; back.stroke(); back.restore();
        // 前面的音符（盖在卡片和文字上）
        pts.filter((o) => o.p.z >= 0).forEach((o) => note(front, o.n, o.p, false, waterY, t));
        raf = box.classList.contains("on") ? requestAnimationFrame(frame) : 0;
      }
      function show() {
        clearTimeout(hideT);
        if (!box.classList.contains("on")) { level = 0; t0 = performance.now(); }
        box.classList.add("on");
        if (!raf) raf = requestAnimationFrame(frame);
      }
      function sync() {
        const visible = meter.classList.contains("on") || getComputedStyle(meter).display !== "none";
        if (!visible) return;
        const pct = Math.max(0, Math.min(100, parseFloat((pctEl && pctEl.textContent) || "0") || 0));
        const failed = meter.classList.contains("failed");
        const msg = (stageEl && stageEl.textContent.trim()) || "";
        state = failed ? "fail" : pct >= 100 ? "done" : "run";
        target = failed ? Math.max(level, 0.25) : pct / 100;
        box.querySelector("b").textContent = failed ? "失败" : pct >= 100 ? "完成" : `${Math.round(pct)}%`;
        box.querySelector("small").textContent = failed ? (msg || "生成失败，详见日志") : pct >= 100 ? "已存进文件包" : (msg || "生成中");
        box.classList.toggle("done", state === "done"); box.classList.toggle("fail", failed);
        box.setAttribute("aria-valuenow", String(Math.round(pct)));
        show();
        if (state !== "run") { clearTimeout(hideT); hideT = setTimeout(() => box.classList.remove("on"), failed ? 6000 : 3500); }
      }
      new MutationObserver(sync).observe(meter, { attributes: true, childList: true, subtree: true, characterData: true });
      sync();
      this._test = { box, meter };
    },
  };
})();
