/* cc-piano 左侧功能栏的唯一清单：外壳（app.html）照它画侧边栏，设置里的「调整左侧功能栏」照它列出可增减的功能。
   以后加新功能，只要在这里加一项（再在 web/server.py 的 PAGES 里加页面路由），侧边栏和设置弹窗都会自动出现。
   字段：key（页面名）、title、src（页面地址）、group（"创作" | "分发" | "系统"：系统放在侧边栏底部）、
         kbd（Ctrl 快捷键，可省略）、fixed（不能隐藏，比如设置）、requires（要先启用的功能，比如 3D 建模）、icon（SVG）。 */
(function () {
  const S = (inner, extra = "") =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ${extra}>${inner}</svg>`;
  window.CC_GROUPS = ["创作", "分发"];
  window.CC_TABS = [
    { key: "studio", title: "琴房", src: "/studio?view=studio", group: "创作", kbd: "1",
      icon: S('<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M8 5v8M12 5v8M16 5v8"/>') },
    { key: "tracks", title: "音轨剪辑", src: "/tracks", group: "创作", kbd: "2",
      icon: S('<path d="M4 9v6M8 6v12M12 9v6M16 4v16M20 8v8"/>', 'stroke-linecap="round"') },
    { key: "flick", title: "拨片开头", src: "/flick", group: "创作", kbd: "3",
      icon: S('<rect x="6" y="7" width="12" height="12" rx="2.5"/><path d="M8 4h8M10 1.8h4" stroke-linecap="round"/>') },
    { key: "edit", title: "剪辑", src: "/edit", group: "创作", kbd: "7",
      icon: S('<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="M8 7.5 20 16M8 16.5 20 8"/>', 'stroke-linecap="round"') },
    { key: "anim", title: "动画库", src: "/anim", group: "创作", kbd: "8",
      icon: S('<rect x="4" y="7" width="13" height="11" rx="2"/><path d="M7 7V5.5h7V7M8 11.5h1M12 11.5h1M9 14.5h3"/><path d="M19 4l.6 1.4L21 6l-1.4.6L19 8l-.6-1.4L17 6l1.4-.6z" fill="currentColor" stroke="none"/>', 'stroke-linejoin="round"') },
    { key: "sections", title: "分段修改", src: "/sections", group: "创作", kbd: "9",
      icon: S('<rect x="3" y="5" width="18" height="10" rx="2"/><path d="M9 5v10M15 5v10"/><path d="M7 19h6l2 2v-2h2"/>', 'stroke-linecap="round" stroke-linejoin="round"') },
    { key: "writer", title: "编剧", src: "/writer", group: "创作", kbd: "0",
      icon: S('<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/><path d="M14 20h6"/>', 'stroke-linecap="round" stroke-linejoin="round"') },
    { key: "model3d", title: "3D 建模", src: "/model3d", group: "创作", requires: "model3d",
      icon: S('<path d="M12 2.8 20.5 7.5v9L12 21.2 3.5 16.5v-9z"/><path d="M12 12 20.5 7.5M12 12 3.5 7.5M12 12v9.2"/>', 'stroke-linejoin="round"') },
    { key: "tour", title: "发布台", src: "/tour", group: "分发", kbd: "4",
      icon: S('<path d="M21 3 10 14M21 3l-7 18-4-7-7-4z"/>', 'stroke-linejoin="round"') },
    { key: "works", title: "作品集", src: "/works", group: "分发", kbd: "5",
      icon: S('<rect x="3" y="3" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="2"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2"/>') },
    { key: "settings", title: "设置", src: "/settings", group: "系统", kbd: "6", fixed: true,
      icon: S('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>') },
  ];
  /** 当前设置下这个功能是否显示：没被隐藏，且要求的功能已启用（fixed 的永远显示）。 */
  window.CC_TAB_VISIBLE = (t, s) => !!t.fixed || (!(s.navHidden || []).includes(t.key) && (!t.requires || !!s[t.requires]));
})();
