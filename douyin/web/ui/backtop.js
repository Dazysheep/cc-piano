/* 「回到顶部」悬浮按钮：被观察的元素（预览区）滚出视野时出现。
   出现动画：三个音符从按钮左侧依次跳到右侧，按钮随之从左到右逐渐显现，文字最后浮现；点击平滑滚回顶部。
   样式由本文件注入。用法：BackTop.attach(要观察的元素, { label: "回到顶部" }) */
(function () {
  const CSS = `
.bt-wrap { position: fixed; right: 28px; bottom: 28px; z-index: 40; pointer-events: none; }
.bt { position: relative; display: inline-flex; align-items: center; gap: 9px; height: 46px; padding: 0 20px 0 16px; border-radius: 999px; border: 0;
  cursor: pointer; color: #111; background: #fff; font: 600 14px "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif; letter-spacing: .06em;
  box-shadow: 0 14px 34px -12px rgba(0,0,0,.65); clip-path: inset(0 100% 0 0 round 999px); opacity: 0; transform: translateY(6px);
  transition: clip-path .7s cubic-bezier(.65,0,.35,1) .25s, opacity .3s .2s, transform .5s .2s; pointer-events: none; }
.bt svg { width: 18px; height: 18px; flex: none; }
.bt span { opacity: 0; transform: translateY(8px); display: inline-block; transition: opacity .4s .75s, transform .5s cubic-bezier(.2,.8,.2,1) .75s; }
.bt-wrap.on .bt { clip-path: inset(0 0 0 0 round 999px); opacity: 1; transform: none; pointer-events: auto; }
.bt-wrap.on .bt span { opacity: 1; transform: none; }
.bt-wrap.on .bt:hover { transform: translateY(-2px); box-shadow: 0 18px 40px -12px rgba(0,0,0,.75); }
.bt-wrap.off .bt { transition: clip-path .35s ease, opacity .25s, transform .3s; }
.bt-wrap.off .bt span { transition: opacity .15s, transform .2s; }
.bt-note { position: absolute; left: -6px; top: 8px; width: 18px; height: 22px; opacity: 0; color: #fff; z-index: 1;
  filter: drop-shadow(0 2px 6px rgba(0,0,0,.6)); }
.bt-note svg { width: 100%; height: 100%; }
.bt-wrap.on .bt-note { animation: bt-hop 1.05s cubic-bezier(.45,0,.55,1) forwards; }
.bt-wrap.on .bt-note:nth-of-type(2) { animation-delay: .14s; }
.bt-wrap.on .bt-note:nth-of-type(3) { animation-delay: .28s; }
@keyframes bt-hop {
  0%   { opacity: 0; transform: translate(0, 10px) rotate(-12deg) scale(.7); }
  12%  { opacity: 1; transform: translate(14px, -24px) rotate(-6deg) scale(1); }
  30%  { transform: translate(38px, 2px) rotate(4deg); }
  48%  { transform: translate(64px, -20px) rotate(-4deg); }
  66%  { transform: translate(90px, 2px) rotate(6deg); }
  84%  { opacity: 1; transform: translate(116px, -16px) rotate(-2deg); }
  100% { opacity: 0; transform: translate(140px, -30px) rotate(10deg) scale(.6); } }
@media (prefers-reduced-motion: reduce) { .bt, .bt span { transition-duration: .01ms !important; transition-delay: 0s !important; } .bt-note { display: none; } }`;
  const NOTE = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M9 18.5a3 3 0 1 1-2-2.83V5.5l11-2.5v12.5a3 3 0 1 1-2-2.83V6.6l-7 1.6z"/></svg>';
  window.BackTop = {
    attach(target, opts = {}) {
      if (!target) return;
      const label = opts.label || "回到顶部";
      const s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s);
      const wrap = document.createElement("div");
      wrap.className = "bt-wrap";
      wrap.innerHTML = `<i class="bt-note">${NOTE}</i><i class="bt-note">${NOTE}</i><i class="bt-note">${NOTE}</i>
        <button class="bt" type="button" aria-label="${label}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
          <span>${label}</span></button>`;
      document.body.appendChild(wrap);
      wrap.querySelector(".bt").addEventListener("click", () => {
        window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      });
      new IntersectionObserver(([e]) => {
        const show = !e.isIntersecting && window.scrollY > 40;
        if (show === wrap.classList.contains("on")) return;
        wrap.classList.toggle("on", show);
        wrap.classList.toggle("off", !show);
        if (show) wrap.querySelectorAll(".bt-note").forEach((n) => { n.style.animation = "none"; void n.offsetWidth; n.style.animation = ""; });
      }, { threshold: 0 }).observe(target);
    },
  };
})();
