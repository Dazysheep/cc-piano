/* 把页面里的文字操作按钮换成简化图标：圆形按钮 + 线条图标，原来的文字变成悬停提示和读屏名称。
   按钮本身不换（原有的点击事件、id 都保留）；按钮里的数字角标（.count）保留在右上角。
   用法：Iconize.apply([{ sel: "#openDeliver", icon: "folder", label: "打开视频文件夹" }, ...])
         nav: "flick"  嵌在软件里时点它切到外壳的对应页面（不在 iframe 里跳转）。样式由本文件注入。 */
(function () {
  const P = 'fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"';
  const ICONS = {
    folder: `<svg viewBox="0 0 24 24" ${P}><path d="M3 7.5a2 2 0 0 1 2-2h4.2l2 2H19a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>`,
    jianying: `<svg viewBox="0 0 24 24" ${P}><rect x="3" y="5" width="18" height="14" rx="3"/><path d="m10 9.2 5 2.8-5 2.8z" fill="currentColor"/></svg>`,
    flick: `<svg viewBox="0 0 24 24" ${P}><rect x="6" y="8" width="12" height="12" rx="2.5"/><path d="M8 5h8M10 2.5h4"/></svg>`,
    home: `<svg viewBox="0 0 24 24" ${P}><path d="M4 11 12 4l8 7"/><path d="M6 9.5V20h12V9.5"/></svg>`,
    shelf: `<svg viewBox="0 0 24 24" ${P}><rect x="3.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.8"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.8"/></svg>`,
    send: `<svg viewBox="0 0 24 24" ${P}><path d="M21 3 10 14M21 3l-7 18-4-7-7-4z"/></svg>`,
    refresh: `<svg viewBox="0 0 24 24" ${P}><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg>`,
    plus: `<svg viewBox="0 0 24 24" ${P}><path d="M12 5v14M5 12h14"/></svg>`,
    copy: `<svg viewBox="0 0 24 24" ${P}><rect x="8" y="8" width="12" height="13" rx="2.5"/><path d="M16 8V5.5A2.5 2.5 0 0 0 13.5 3h-7A2.5 2.5 0 0 0 4 5.5v9A2.5 2.5 0 0 0 6.5 17H8"/></svg>`,
    replay: `<svg viewBox="0 0 24 24" ${P}><path d="M4 12a8 8 0 1 0 2.3-5.7"/><path d="M4 4v6h6"/><path d="m10.5 9.5 4 2.5-4 2.5z" fill="currentColor"/></svg>`,
  };
  const CSS = `
.ic-btn { position: relative; display: inline-grid !important; place-items: center; width: 40px; height: 40px; min-height: 0 !important;
  padding: 0 !important; border-radius: 50% !important; gap: 0 !important; flex: none !important; }
.ic-btn svg { width: 19px; height: 19px; }
.ic-btn .count { position: absolute; top: -4px; right: -4px; min-width: 17px; height: 17px; padding: 0 4px !important; border-radius: 999px;
  font-size: 10.5px !important; line-height: 17px !important; text-align: center; }
.ic-btn::after { content: attr(data-tip); position: absolute; left: 50%; top: calc(100% + 8px); transform: translate(-50%, -4px); z-index: 30;
  white-space: nowrap; pointer-events: none; padding: 4px 9px; border-radius: 8px; font-size: 12px; font-weight: 500; line-height: 1.4;
  background: rgba(20, 22, 30, .96); color: #fff; box-shadow: 0 8px 24px -8px rgba(0,0,0,.7), 0 0 0 .5px rgba(255,255,255,.1);
  opacity: 0; transition: opacity .18s, transform .22s cubic-bezier(.2,.8,.2,1); }
.ic-btn:hover::after, .ic-btn:focus-visible::after { opacity: 1; transform: translate(-50%, 0); }`;
  let injected = false;
  window.Iconize = {
    ICONS,
    apply(list) {
      if (!injected) { const s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s); injected = true; }
      for (const o of list) {
        const el = document.querySelector(o.sel);
        if (!el || el.classList.contains("ic-btn")) continue;
        const count = el.querySelector(".count");
        const label = o.label || el.textContent.replace(count ? count.textContent : "", "").trim();
        el.innerHTML = ICONS[o.icon] || "";
        if (count) el.appendChild(count);
        el.classList.add("ic-btn");
        el.dataset.tip = label; el.setAttribute("aria-label", label); el.removeAttribute("title");
        if (o.nav) {
          el.addEventListener("click", (e) => {
            if (window.parent === window) return;            // 单独打开时照常跳转
            e.preventDefault(); window.parent.postMessage({ nav: o.nav }, location.origin);
          });
        }
      }
    },
  };
})();
