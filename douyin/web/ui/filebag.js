/* 「文件包」：放在「生成」按钮右边，暂存所有生成的视频（就是「待上传」文件夹）。
   - 生成完成：一个文件从「生成」按钮弹出，沿弧线跳进文件包（只看最终成片，预览不算）
   - 点击文件包：打开「待上传」文件夹
   - 鼠标停在文件包上：最近 5 个视频依次向上滑出；鼠标移上去：卡片外框是这条视频开头的虚化动画，信息层错位浮起（3D）
   - 点击某个视频：弹出并播放
   用法：FileBag.attach("#生成按钮", { kinds: ["render"] })   kinds：render（钢琴）/ tracks（音轨）/ flick（开头）
   样式由本文件注入，不依赖页面自己的 CSS；按钮外面套一层 flex 容器，原按钮的事件和样式不受影响。 */
(function () {
  const CSS = `
.fb-wrap { display: flex; gap: 10px; align-items: stretch; min-width: 0; }
.fb-wrap > :first-child { flex: 1 1 auto; min-width: 0; }
.fb-bag { position: relative; flex: none; width: 48px; min-height: 44px; border-radius: 14px; border: 1px solid rgba(255,255,255,.16); cursor: pointer;
  background: linear-gradient(180deg, rgba(255,255,255,.12), rgba(255,255,255,.04)); color: #fff; display: grid; place-items: center; padding: 0;
  transition: transform .25s cubic-bezier(.2,.8,.2,1), background .2s; }
.fb-bag:hover { background: linear-gradient(180deg, rgba(255,255,255,.2), rgba(255,255,255,.06)); }
.fb-bag svg { width: 24px; height: 24px; }
.fb-bag.gulp { animation: fb-gulp .5s cubic-bezier(.2,.8,.2,1); }
@keyframes fb-gulp { 0% { transform: scale(1); } 35% { transform: scale(1.22, .86); } 65% { transform: scale(.92, 1.1); } 100% { transform: scale(1); } }
.fb-badge { position: absolute; top: -6px; right: -6px; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 999px; background: #fff; color: #111;
  font: 700 11px/18px "Segoe UI", sans-serif; text-align: center; display: none; box-shadow: 0 2px 8px rgba(0,0,0,.4); }
.fb-badge.on { display: block; animation: fb-pop .4s cubic-bezier(.2,.8,.2,1.4); }
@keyframes fb-pop { from { transform: scale(.3); } to { transform: scale(1); } }
.fb-fly { position: fixed; z-index: 9999; left: 0; top: 0; width: 44px; height: 56px; pointer-events: none; will-change: transform; }
.fb-fly .doc { position: absolute; inset: 0; border-radius: 6px 14px 6px 6px; background: #fff; box-shadow: 0 10px 24px rgba(0,0,0,.5); overflow: hidden; }
.fb-fly .doc i { position: absolute; left: 4px; right: 4px; top: 6px; height: 26px; border-radius: 3px; background: #222 center / cover no-repeat; }
.fb-fly .doc b { position: absolute; left: 6px; right: 10px; height: 3px; border-radius: 2px; background: #ccc; }
.fb-pop { position: fixed; z-index: 9990; display: flex; flex-direction: column-reverse; gap: 12px; pointer-events: none; }
.fb-pop.on { pointer-events: auto; }
.fb-pop.down { flex-direction: column; }
.fb-card { position: relative; width: 236px; height: 133px; border-radius: 18px; overflow: visible; cursor: pointer; flex: none;
  opacity: 0; transform: translateY(46px) scale(.7); transition: opacity .3s, transform .45s cubic-bezier(.2,.8,.2,1.15); transition-delay: calc(var(--i) * 55ms); }
.fb-pop.down .fb-card { transform: translateY(-46px) scale(.7); }
.fb-pop.compact { gap: 10px; }
.fb-pop.compact .fb-card { width: 180px; height: 102px; }
.fb-pop.on .fb-card { opacity: 1; transform: none; }
.fb-frame { position: absolute; inset: 0; border-radius: 18px; overflow: hidden; background: #222 center / cover no-repeat; }
.fb-frame video, .fb-frame .still { position: absolute; inset: -12%; width: 124%; height: 124%; object-fit: cover; filter: blur(7px) saturate(1.3); background: center / cover no-repeat; }
.fb-info { position: absolute; width: 96%; height: 96%; left: 2%; top: 2%; border-radius: 16px; background: rgb(24, 22, 22); transition: .3s;
  display: flex; flex-direction: column; justify-content: flex-end; padding: 12px 14px; gap: 2px; color: #fff; box-shadow: 0 10px 30px -12px rgba(0,0,0,.8); }
.fb-info .th { position: absolute; inset: 0; border-radius: inherit; background: center / cover no-repeat; opacity: .5; transition: opacity .3s; }
.fb-info::after { content: ""; position: absolute; inset: 0; border-radius: inherit; background: linear-gradient(180deg, transparent 30%, rgba(0,0,0,.8)); }
.fb-info b, .fb-info small { position: relative; z-index: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fb-info b { font: 700 14px/1.3 "Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei UI", sans-serif; }
.fb-info small { font: 12px "Segoe UI", "Microsoft YaHei UI", sans-serif; opacity: .65; }
.fb-card:hover .fb-info { width: 100%; height: 100%; left: 20px; top: 20px; background-color: rgba(0, 0, 0, .822); backdrop-filter: blur(12px); }
.fb-card:hover .fb-info .th { opacity: .82; }
.fb-card:hover { z-index: 2; }
.fb-player { position: fixed; inset: 0; z-index: 9995; display: grid; place-items: center; background: rgba(0,0,0,0); transition: background .35s; }
.fb-player.on { background: rgba(0,0,0,.82); }
.fb-player .box { width: min(1100px, 92vw); transform-origin: top left; transition: transform .45s cubic-bezier(.2,.8,.2,1); }
.fb-player video { width: 100%; max-height: 74vh; border-radius: 16px; background: #000; display: block; box-shadow: 0 40px 90px -30px rgba(0,0,0,1); }
.fb-player .bar { display: flex; align-items: center; gap: 10px; margin-top: 14px; color: #fff; font: 14px "Segoe UI", "Microsoft YaHei UI", sans-serif;
  opacity: 0; transition: opacity .3s .2s; }
.fb-player.on .bar { opacity: 1; }
.fb-player .bar b { flex: 1; font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fb-player .bar button { padding: 8px 16px; border-radius: 999px; border: 1px solid rgba(255,255,255,.2); background: rgba(255,255,255,.08); color: #fff; cursor: pointer; font: inherit; }
.fb-player .bar button:hover { background: rgba(255,255,255,.16); }
@media (prefers-reduced-motion: reduce) { .fb-card, .fb-info, .fb-player .box { transition-duration: .01ms !important; } }`;
  const BAG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M3 7.5a2 2 0 0 1 2-2h4.2l2 2H19a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 10.5h18"/></svg>';
  const KIND = { piano: "钢琴", tracks: "音轨", intro: "开头" };
  let injected = false, items = [], loadedAt = 0;

  async function recent() {
    if (Date.now() - loadedAt > 8000) {
      try { items = (await (await fetch("/api/library?all=1")).json()).slice(0, 5); loadedAt = Date.now(); } catch (e) { /* 服务没开 */ }
    }
    return items;
  }
  const post = (url, body) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

  // ---------- 播放：卡片放大飞到屏幕中央 ----------
  function play(it, fromRect) {
    const p = document.createElement("div");
    p.className = "fb-player";
    p.innerHTML = `<div class="box"><video controls playsinline autoplay></video>
      <div class="bar"><b></b><button type="button" class="open">打开所在文件夹</button><button type="button" class="close">关闭（Esc）</button></div></div>`;
    p.querySelector("b").textContent = it.title;
    const v = p.querySelector("video");
    v.poster = it.cover || ""; v.src = it.video;
    document.body.appendChild(p);
    const box = p.querySelector(".box"), to = box.getBoundingClientRect();
    if (fromRect) {
      box.style.transition = "none";
      box.style.transform = `translate(${fromRect.left - to.left}px, ${fromRect.top - to.top}px) scale(${fromRect.width / to.width})`;
      void box.offsetWidth;
      box.style.transition = "";
    }
    requestAnimationFrame(() => { p.classList.add("on"); box.style.transform = "none"; });
    const close = () => { v.pause(); v.removeAttribute("src"); v.load(); p.remove(); removeEventListener("keydown", esc); };
    const esc = (e) => { if (e.key === "Escape") close(); };
    addEventListener("keydown", esc);
    p.addEventListener("click", (e) => { if (e.target === p) close(); });
    p.querySelector(".close").addEventListener("click", close);
    p.querySelector(".open").addEventListener("click", () => post("/api/open", { path: it.folder }));
  }

  // ---------- 一个文件从按钮弹出，跳进文件包 ----------
  function fly(fromEl, bag, cover, done) {
    const a = fromEl.getBoundingClientRect(), b = bag.getBoundingClientRect();
    const el = document.createElement("div");
    el.className = "fb-fly";
    el.innerHTML = '<div class="doc"><i></i><b style="top:38px"></b><b style="top:45px;right:18px"></b></div>';
    if (cover) el.querySelector("i").style.backgroundImage = `url("${cover}")`;
    document.body.appendChild(el);
    const x0 = a.left + a.width / 2 - 22, y0 = a.top + a.height / 2 - 28, x1 = b.left + b.width / 2 - 22, y1 = b.top + b.height / 2 - 28;
    const peak = Math.min(y0, y1) - 120, t0 = performance.now(), D = 1100;
    const quad = (p0, c, p1, t) => (1 - t) * (1 - t) * p0 + 2 * (1 - t) * t * c + t * t * p1;
    (function step(now) {
      const u = Math.min(1, (now - t0) / D);
      let x, y, s, r;
      if (u < 0.3) {                        // 先从按钮里弹出来
        const k = u / 0.3, e = 1 - (1 - k) ** 3;
        x = x0; y = y0 - 70 * e; s = 0.3 + 0.9 * e; r = -8 * e;
      } else {                              // 再沿弧线跳进文件包，越来越小
        const k = (u - 0.3) / 0.7, e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
        x = quad(x0, (x0 + x1) / 2, x1, e); y = quad(y0 - 70, peak, y1, e); s = 1.2 - 0.85 * e; r = -8 + 368 * e;
      }
      el.style.transform = `translate(${x}px, ${y}px) rotate(${r}deg) scale(${s})`;
      el.style.opacity = u > 0.93 ? String((1 - u) / 0.07) : "1";
      if (u < 1) requestAnimationFrame(step);
      else { el.remove(); bag.classList.remove("gulp"); void bag.offsetWidth; bag.classList.add("gulp"); done && done(); }
    })(t0);
  }

  window.FileBag = {
    attach(sel, opts = {}) {
      const btn = typeof sel === "string" ? document.querySelector(sel) : sel;
      if (!btn) return;
      if (!injected) { const s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s); injected = true; }
      const cs = getComputedStyle(btn);
      const wrap = document.createElement("div");
      wrap.className = "fb-wrap";
      wrap.style.gridColumn = cs.gridColumn; wrap.style.flex = cs.flex; wrap.style.marginTop = cs.marginTop;
      btn.style.marginTop = "0";
      btn.replaceWith(wrap);
      const bag = document.createElement("button");
      bag.type = "button"; bag.className = "fb-bag"; bag.title = "文件包：生成的视频都在这里（点击打开视频文件夹，位置可在设置 → 存储里改）";
      bag.setAttribute("aria-label", "文件包");
      bag.innerHTML = BAG + '<span class="fb-badge"></span>';
      wrap.append(btn, bag);
      const badge = bag.querySelector(".fb-badge");
      let unseen = 0;
      bag.addEventListener("click", () => post("/api/open-deliver"));

      // ---- 悬停：最近的视频依次向上滑出
      const pop = document.createElement("div");
      pop.className = "fb-pop";
      document.body.appendChild(pop);
      let hideT = 0, live = null;
      const hide = () => { hideT = setTimeout(() => { pop.classList.remove("on"); if (live) { live.pause(); live.remove(); live = null; } }, 260); };
      const keep = () => clearTimeout(hideT);
      async function show() {
        keep();
        unseen = 0; badge.classList.remove("on");
        const list = await recent();
        if (!list.length) return;
        const r = bag.getBoundingClientRect();
        // 往上滑出；上方放不下 4 个而下方空间更大时改为往下
        const up = r.top - 16, below = innerHeight - r.bottom - 16, down = up < 4 * 145 && below > up;
        const room = down ? below : up, compact = room / 145 < Math.min(4, list.length);   // 放不下 4 个就用小一号的卡片
        const n = Math.max(1, Math.min(list.length, Math.floor(room / (compact ? 112 : 145))));
        pop.classList.toggle("compact", compact);
        pop.classList.toggle("down", down);
        pop.style.left = `${Math.max(12, Math.min(innerWidth - 268, r.left + r.width / 2 - 118))}px`;
        pop.style.top = down ? `${r.bottom + 12}px` : "";
        pop.style.bottom = down ? "" : `${innerHeight - r.top + 12}px`;
        if (pop.dataset.n !== String(n) || pop.dataset.k !== list.map((x) => x.folder).join("|")) {
          pop.innerHTML = "";
          list.slice(0, n).forEach((it, i) => {
            const c = document.createElement("div");
            c.className = "fb-card"; c.style.setProperty("--i", i); c.tabIndex = 0;
            c.innerHTML = '<div class="fb-frame"><div class="still"></div></div><div class="fb-info"><i class="th"></i><b></b><small></small></div>';
            if (it.cover) { c.querySelector(".still").style.backgroundImage = `url("${it.cover}")`; c.querySelector(".th").style.backgroundImage = `url("${it.cover}")`; }
            c.querySelector("b").textContent = it.title;
            c.querySelector("small").textContent = `${KIND[it.kind] || "作品"} · ${it.time}`;
            // 鼠标停留：外框换成这条视频开头的虚化动画（只有停留的那张在播放）
            c.addEventListener("mouseenter", () => {
              if (live) { live.pause(); live.remove(); }
              const v = document.createElement("video");
              v.muted = true; v.loop = false; v.playsInline = true; v.src = it.video;
              v.addEventListener("timeupdate", () => { if (v.currentTime > 4) v.currentTime = 0; });
              v.addEventListener("ended", () => { v.currentTime = 0; v.play().catch(() => {}); });
              c.querySelector(".fb-frame").appendChild(v); v.play().catch(() => {}); live = v;
            });
            c.addEventListener("mouseleave", () => { if (live) { live.pause(); live.remove(); live = null; } });
            const open = () => { const fr = c.getBoundingClientRect(); pop.classList.remove("on"); if (live) { live.pause(); live.remove(); live = null; } play(it, fr); };
            c.addEventListener("click", open);
            c.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
            pop.appendChild(c);
          });
          pop.dataset.n = String(n); pop.dataset.k = list.map((x) => x.folder).join("|");
        }
        requestAnimationFrame(() => pop.classList.add("on"));
      }
      bag.addEventListener("mouseenter", show);
      bag.addEventListener("mouseleave", hide);
      pop.addEventListener("mouseenter", keep);
      pop.addEventListener("mouseleave", hide);

      // ---- 生成完成：文件跳进文件包
      const kinds = opts.kinds || ["render", "tracks", "flick"];
      let seen = null;
      async function poll() {
        if (!document.hidden) {
          try {
            const jobs = await (await fetch("/api/jobs")).json();
            const done = jobs.filter((j) => j.status === "done" && j.video_url && !j.preview && kinds.includes(j.kind));
            if (seen === null) seen = new Set(done.map((j) => j.id));
            for (const j of done) {
              if (seen.has(j.id)) continue;
              seen.add(j.id);
              loadedAt = 0;                                       // 下次悬停重新读最近的视频
              fly(btn, bag, j.cover_url, () => { unseen++; badge.textContent = unseen; badge.classList.remove("on"); void badge.offsetWidth; badge.classList.add("on"); });
            }
          } catch (e) { /* 服务没开 */ }
        }
        setTimeout(poll, 2500);
      }
      poll();
      this._test = { fly: (cover) => fly(btn, bag, cover, () => { unseen++; badge.textContent = unseen; badge.classList.add("on"); }), show };
    },
  };
})();
