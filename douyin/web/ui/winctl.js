/* 软件窗口左上角的红黄绿三点（仿 macOS / iOS）：红 = 关闭，黄 = 最小化，绿 = 最大化 / 还原。
   只在软件窗口（pywebview，见 app/window.py）里出现；普通浏览器里不显示（网页控制不了浏览器窗口）。
   同时放一块可以拖动窗口的区域（.pywebview-drag-region），双击最大化 / 还原。样式由本文件注入。
   页面在 <html> 上得到 class="winctl"，可以据此给三点留出位置。
   用法：WinCtl.attach({ dragWidth: "236px", dragHeight: "46px" })   dragWidth 默认整条顶部 */
(function () {
  const CSS = `
.tl { position: fixed; z-index: 10000; left: 16px; top: 15px; display: flex; gap: 8px; }
.tl button { width: 13px; height: 13px; padding: 0; border-radius: 50%; border: .5px solid rgba(0,0,0,.25); cursor: pointer; display: grid; place-items: center;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.35); transition: filter .15s; }
.tl .c { background: #ff5f57; } .tl .m { background: #febc2e; } .tl .x { background: #28c840; }
.tl svg { width: 7px; height: 7px; opacity: 0; transition: opacity .12s; stroke: rgba(60,0,0,.75); stroke-width: 1.6; stroke-linecap: round; fill: none; }
.tl .m svg { stroke: rgba(90,50,0,.8); } .tl .x svg { stroke: rgba(0,60,0,.8); }
.tl:hover svg, .tl button:focus-visible svg { opacity: 1; }
.tl button:active { filter: brightness(.82); }
.tl button:focus-visible { outline: 2px solid rgba(255,255,255,.7); outline-offset: 2px; }
html.winctl-blur .tl button { background: #5a5a5f; border-color: rgba(255,255,255,.08); }
.tl-drag { position: fixed; z-index: 9999; left: 0; top: 0; }
/* 独立的标题栏（bar: true）：跟随外观设置（深色 / 浅色），底边一道强调色的线把它和内容分开 */
html.winctl-bar body { padding-top: 40px; }
html.winctl-bar .tl { top: 13.5px; left: 15px; }
.tl-bar { position: fixed; z-index: 9998; left: 0; right: 0; top: 0; height: 40px; display: flex; align-items: center; justify-content: center;
  background: var(--card-solid, #1c1c1e); color: var(--label-2, rgba(235,235,245,.62));
  font: 600 12.5px/1 var(--font, "Segoe UI", "Microsoft YaHei UI", sans-serif); letter-spacing: .05em; user-select: none;
  box-shadow: 0 8px 22px -16px color-mix(in srgb, var(--accent, #8b5cf6) 85%, #000), inset 0 -1px 0 var(--sep, rgba(84,84,88,.55)); }
[data-glass="on"] .tl-bar { background: var(--card, rgba(28,28,30,.78)); backdrop-filter: blur(26px) saturate(170%); -webkit-backdrop-filter: blur(26px) saturate(170%); }
.tl-bar::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 2px; pointer-events: none;
  background: linear-gradient(90deg, transparent, var(--accent, #8b5cf6) 22%, color-mix(in srgb, var(--accent, #8b5cf6) 60%, #fff) 50%, var(--accent, #8b5cf6) 78%, transparent); opacity: .85; }
.tl-bar .ttl { display: flex; align-items: center; gap: 8px; pointer-events: none; }
.tl-bar .ttl img { width: 18px; height: 18px; border-radius: 5px; }
.tl-bar .ttl b { color: var(--label, #fff); font-weight: 700; }
.tl-bar .ttl i { font-style: normal; opacity: .55; }
html.winctl-blur .tl-bar { color: var(--label-3, rgba(235,235,245,.32)); }
html.winctl-blur .tl-bar::after { opacity: .3; }`;
  const ICON = {
    c: '<svg viewBox="0 0 8 8"><path d="M1.5 1.5l5 5M6.5 1.5l-5 5"/></svg>',
    m: '<svg viewBox="0 0 8 8"><path d="M1.2 4h5.6"/></svg>',
    x: '<svg viewBox="0 0 8 8"><path d="M2 6l4-4M2.6 2H6v3.4" /></svg>',
  };

  window.WinCtl = {
    attach(opts = {}) {
      const go = () => {
        const api = window.pywebview && window.pywebview.api;
        if (!api || document.querySelector(".tl")) return;
        const s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s);
        document.documentElement.classList.add("winctl");
        let drag;
        if (opts.bar) {                             // 整条标题栏，本身就是拖动区域
          document.documentElement.classList.add("winctl-bar");
          drag = document.createElement("header");
          drag.className = "tl-bar pywebview-drag-region";
          drag.innerHTML = '<span class="ttl"><img src="/ui/icon.png" alt=""><b></b><i></i></span>';
          drag.querySelector("b").textContent = opts.title || document.title;
          if (window.WinCtl._sub) drag.querySelector("i").textContent = `· ${window.WinCtl._sub}`;
        } else {
          drag = document.createElement("div");
          drag.className = "tl-drag pywebview-drag-region";
          drag.style.width = opts.dragWidth || "100%";
          drag.style.height = opts.dragHeight || "44px";
        }
        drag.addEventListener("dblclick", () => api.toggle_maximize());
        const bar = document.createElement("div");
        bar.className = "tl"; bar.setAttribute("role", "group"); bar.setAttribute("aria-label", "窗口");
        bar.innerHTML = `<button class="c" type="button" title="关闭" aria-label="关闭">${ICON.c}</button>`
          + `<button class="m" type="button" title="最小化" aria-label="最小化">${ICON.m}</button>`
          + `<button class="x" type="button" title="最大化 / 还原" aria-label="最大化或还原">${ICON.x}</button>`;
        bar.querySelector(".c").addEventListener("click", () => api.close());
        bar.querySelector(".m").addEventListener("click", () => api.minimize());
        bar.querySelector(".x").addEventListener("click", () => api.toggle_maximize());
        document.body.append(drag, bar);
        // 窗口失去焦点时三点变灰（焦点只是移到页面里的 iframe 时不算）
        addEventListener("blur", () => setTimeout(() => {
          if (!document.hasFocus()) document.documentElement.classList.add("winctl-blur");
        }, 0));
        addEventListener("focus", () => document.documentElement.classList.remove("winctl-blur"));
      };
      if (window.pywebview && window.pywebview.api) go();
      else window.addEventListener("pywebviewready", go, { once: true });
    },
    /** 标题栏副标题（当前页面名） */
    setSub(text) {
      const i = document.querySelector(".tl-bar .ttl i");
      if (i) i.textContent = text ? `· ${text}` : "";
      this._sub = text;
    },
  };
})();
