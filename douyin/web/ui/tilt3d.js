/* 3D 悬停：卡片跟随鼠标倾斜，表面一道高光，文字（歌名）浮在卡片上方。
   用法：Tilt3D.attach(容器, "卡片选择器", { label: (卡片) => "文字", max: 最大倾角, top: "文字位置" })
   事件委托在容器上，卡片重新渲染后照样生效；拖拽中的卡片（.dragging）和「动画：关闭」时不倾斜。
   样式由本文件注入，不依赖页面自己的 CSS（拨片开头页面只加了引用这一处）。 */
(function () {
  const CSS = `
.t3d { transform-style: preserve-3d; transition: transform .5s cubic-bezier(.2,.8,.2,1), box-shadow .5s; }
.t3d.t3d-live { transition: transform .09s linear, box-shadow .3s; box-shadow: 0 30px 50px -24px rgba(0,0,0,.85); z-index: 3; }
.t3d-label { position: absolute; left: 50%; width: 84%; text-align: center; pointer-events: none; z-index: 6; color: #fff;
  font: 700 15px/1.35 "Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei UI", sans-serif; letter-spacing: .02em;
  text-shadow: 0 2px 4px rgba(0,0,0,.7), 0 10px 26px rgba(0,0,0,.75); overflow-wrap: anywhere;
  opacity: 0; transform: translate(-50%, -50%) translateZ(20px) scale(.92); transition: opacity .3s, transform .5s cubic-bezier(.2,.8,.2,1); }
.t3d-label small { display: block; margin-top: 3px; font-weight: 500; font-size: 12px; opacity: .8; }
.t3d.t3d-live .t3d-label { opacity: 1; transform: translate(-50%, -50%) translateZ(70px) scale(1); }
.t3d-glare { position: absolute; inset: 0; border-radius: inherit; pointer-events: none; z-index: 5; opacity: 0; transition: opacity .3s;
  background: radial-gradient(circle at var(--gx, 50%) var(--gy, 50%), rgba(255,255,255,.26), transparent 58%); }
.t3d.t3d-live .t3d-glare { opacity: 1; }`;
  let injected = false;
  const off = () => window.StudioSettings && window.StudioSettings.motionScale() === 0;

  function reset(el) {
    el.classList.remove("t3d-live");
    el.style.transform = "";
  }
  window.Tilt3D = {
    attach(root, sel, opts = {}) {
      if (!injected) { const s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s); injected = true; }
      const max = opts.max || 14;
      let cur = null;
      const prep = (el) => {
        if (el._t3d) return;
        el._t3d = true;
        el.classList.add("t3d");
        if (getComputedStyle(el).position === "static") el.style.position = "relative";
        const g = document.createElement("i"); g.className = "t3d-glare"; el.appendChild(g);
        if (opts.label) { const l = document.createElement("div"); l.className = "t3d-label"; l.style.top = opts.top || "50%"; el.appendChild(l); }
      };
      root.addEventListener("mousemove", (e) => {
        const el = e.target.closest(sel);
        if (cur && cur !== el) { reset(cur); cur = null; }
        if (!el || !root.contains(el) || el.classList.contains("dragging") || off()) return;
        prep(el);
        if (cur !== el) {
          cur = el;
          const l = el.querySelector(":scope > .t3d-label");
          if (l) { const v = opts.label(el); l.innerHTML = ""; const [a, b] = Array.isArray(v) ? v : [v];
            l.append(a || ""); if (b) { const s = document.createElement("small"); s.textContent = b; l.appendChild(s); } }
        }
        const r = el.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        el.classList.add("t3d-live");
        el.style.transform = `perspective(800px) rotateX(${((0.5 - y) * 2 * max).toFixed(2)}deg) rotateY(${((x - 0.5) * 2 * max).toFixed(2)}deg) translateZ(12px)`;
        el.style.setProperty("--gx", `${(x * 100).toFixed(1)}%`);
        el.style.setProperty("--gy", `${(y * 100).toFixed(1)}%`);
      });
      root.addEventListener("mouseleave", () => { if (cur) { reset(cur); cur = null; } });
      root.addEventListener("dragstart", () => { if (cur) { reset(cur); cur = null; } }, true);
    },
  };
})();
