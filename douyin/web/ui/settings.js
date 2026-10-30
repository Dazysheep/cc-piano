/* cc-piano 统一设置：外观 / 作品集 / 胶片音效 / 视频展示。
   存在 localStorage（项目原有的设置也都存在这里；安装版的 Edge 窗口配置目录会保留它，重启后仍然有效）。
   只有外壳导航、发布台、作品集、设置中心加载本文件；拨片开头、琴房钢琴、音轨剪辑不受影响。
   页面之间通过 BroadcastChannel 实时同步：在设置中心改动，其他已打开的页面立即生效。 */
(function () {
  const KEY = "studio.ui.v1";
  const DEFAULTS = {
    // A. 外观
    appearance: "dark",          // dark | light | auto（跟随系统）
    accent: "violet",            // 见 ACCENTS
    background: "aurora",        // aurora（柔光渐变）| plain（纯色）
    glass: true,                 // 毛玻璃材质
    motion: "full",              // full | reduced | off
    textSize: "standard",        // standard | large
    landing: true,               // 启动时先显示黑白开端页（landing.html）
    landingLang: "en",           // 开端页文字：en（英文）| zh（中文）
    landingSound: true,          // 开端页钢琴声（音符落键、点击琴键）
    model3d: false,              // 3D 建模（Blender）是否启用：启用后左侧功能栏出现「3D 建模」（服务端 model3d.json 为准，设置页会同步）
    perfMode: false,             // 流畅模式：毛玻璃换成半透明实底、开端页动画简化、不预加载其他页面
    // 侧边栏
    navLabels: true,             // 显示功能名称（关掉后只显示图标）
    navGroups: true,             // 显示「创作 / 分发」分组标题
    navKeys: true,               // 悬停时显示快捷键 Ctrl 1~9、Ctrl 0
    navHidden: [],               // 左侧功能栏里隐藏的功能（记隐藏的，不记显示的：以后新加的功能默认显示）
    // B. 作品集
    worksView: "arc",            // arc（半弧形胶片）| grid（网格）
    arcCurve: 0.55,              // 弧度 0（接近直线）~ 1（很弯）
    wheelSensitivity: 1.0,       // 0.4 ~ 2
    switchAnim: "smooth",        // smooth（平滑）| spring（轻微回弹）
    animSpeed: 1.0,              // 0.5 ~ 2（越大越快）
    // C. 胶片音效
    sound: true,
    volume: 0.5,                 // 0 ~ 1
    soundTick: true,             // 齿孔咔嗒
    soundFriction: true,         // 滚动摩擦
    soundSettle: true,           // 定位反馈
    // D. 视频展示
    autoplay: true,              // 选中作品后自动播放
    autoplayMuted: true,         // 自动播放时静音
    loadDelay: 350,              // 停稳后多久开始加载视频（毫秒）
    loop: true,
    bgFollow: true,              // 背景跟随当前作品封面
    bgBlur: 60,                  // 背景模糊（像素）
  };
  // 强调色：[颜色, 按钮上的文字颜色, 名称]；浅色系（黄、青柠、淡紫）上面用深色文字
  const ACCENTS = {
    rose: ["#e11d48", "#ffffff", "玫红"], pink: ["#f472b6", "#ffffff", "粉色"], orange: ["#fb923c", "#ffffff", "橙色"],
    yellow: ["#facc15", "#1a1a1a", "明黄"], lime: ["#84cc16", "#1a1a1a", "青柠"], emerald: ["#10b981", "#ffffff", "翠绿"],
    sky: ["#0ea5e9", "#ffffff", "天蓝"], blue: ["#3b82f6", "#ffffff", "蓝色"], violet: ["#8b5cf6", "#ffffff", "紫罗兰"],
    lavender: ["#a78bfa", "#1a1a1a", "淡紫"],
  };
  const chan = "BroadcastChannel" in window ? new BroadcastChannel("studio-ui") : null;
  const subs = [];

  // ---- 服务端备份（/api/ui-state，存在 app_settings.json）：localStorage 按「地址:端口」分开存，
  //      软件换了端口启动就像全新安装；所以启动时先从服务端恢复，改动后再同步回去。
  //      除了这里的设置，也一起备份发布平台勾选、上次的页面、拨片开头和音轨剪辑页记住的内容。
  const MIRROR = ["studio.ui.v1", "qinfang.tour", "studio.tab", "flick.settings", "tracks.song"];
  const TS = "studio.persist.ts";
  let pushT = 0;
  function push(mode) {
    clearTimeout(pushT);
    const go = () => {
      try {
        const ts = Date.now(), keys = {};
        MIRROR.forEach((k) => { const v = localStorage.getItem(k); if (v != null) keys[k] = v; });
        localStorage.setItem(TS, String(ts));
        const body = JSON.stringify({ ts, keys });
        if (mode === "beacon" && navigator.sendBeacon) navigator.sendBeacon("/api/ui-state", body);
        else fetch("/api/ui-state", { method: "POST", headers: { "Content-Type": "application/json" }, body }).catch(() => {});
      } catch (e) { /* 服务没开：下次再同步 */ }
    };
    if (mode) go(); else pushT = setTimeout(go, 400);
  }
  function merge(text) {                             // 服务端的更新就写进本机；本机的更新就传上去。返回是否改了本机
    const s = JSON.parse(text), local = +(localStorage.getItem(TS) || 0);
    if (s.ts > local) {
      Object.entries(s.keys || {}).forEach(([k, v]) => localStorage.setItem(k, v));
      localStorage.setItem(TS, String(s.ts));
      return true;
    }
    if (local > s.ts || !s.ts) push("now");
    return false;
  }
  (function restore() {
    if (window.parent !== window) return;           // 只在顶层页面（外壳、开端页）恢复，iframe 里的页面直接用
    try {
      if (localStorage.getItem(TS)) {               // 本机已经有设置（平时都是这样）：后台对一下，不卡住页面解析
        fetch("/api/ui-state").then((r) => r.ok ? r.text() : null).then((t) => {
          if (t && merge(t)) { cur = load(); notify(); }
        }).catch(() => {});
        return;
      }
      const x = new XMLHttpRequest();                // 本机是空的（换了端口 / 清了数据）：同步取回，画出来之前设置就位
      x.open("GET", "/api/ui-state", false); x.send();
      if (x.status === 200) merge(x.responseText);
    } catch (e) { /* 服务没开或隐私模式：照常用本机的 */ }
  })();
  if (window.parent === window) {
    window.addEventListener("storage", (e) => { if (MIRROR.includes(e.key)) push(); });   // iframe 里的页面改了
    window.addEventListener("pagehide", () => push("beacon"));
  }
  let cur = load();

  function load() {
    try { return { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(KEY)) || {}) }; }
    catch (e) { return { ...DEFAULTS }; }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(cur)); } catch (e) { /* 隐私模式等：只在本页生效 */ }
    push();
  }
  function notify(from) {
    apply();
    subs.forEach((f) => f(cur));
    if (from !== "remote" && chan) chan.postMessage(cur);
  }
  function resolvedTheme() {
    if (cur.appearance !== "auto") return cur.appearance;
    return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  function apply(doc = document) {
    const el = doc.documentElement, theme = resolvedTheme();
    const reduce = cur.motion === "off" || matchMedia("(prefers-reduced-motion: reduce)").matches && cur.motion !== "full";
    el.dataset.theme = theme;
    el.dataset.motion = reduce ? "off" : cur.motion;
    el.dataset.glass = cur.glass && !cur.perfMode ? "on" : "off";
    el.dataset.perf = cur.perfMode ? "on" : "off";
    el.dataset.bg = cur.background;
    el.dataset.text = cur.textSize;
    const a = ACCENTS[cur.accent] || ACCENTS[DEFAULTS.accent];   // 旧版本存的颜色名不在列表里时用默认
    el.style.setProperty("--accent", a[0]);
    el.style.setProperty("--on-accent", a[1]);
  }

  window.StudioSettings = {
    DEFAULTS, ACCENTS,
    get: () => cur,
    set(patch) { cur = { ...cur, ...patch }; save(); notify(); },
    reset() { cur = { ...DEFAULTS }; save(); notify(); },
    on(f) { subs.push(f); },
    apply,
    /** 动画时长倍数：关闭动画时为 0 */
    motionScale: () => (document.documentElement.dataset.motion === "off" ? 0
      : document.documentElement.dataset.motion === "reduced" ? 0.5 : 1),
  };
  if (chan) chan.onmessage = (e) => { cur = { ...DEFAULTS, ...e.data }; notify("remote"); };
  window.addEventListener("storage", (e) => { if (e.key === KEY) { cur = load(); notify("remote"); } });
  matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => { if (cur.appearance === "auto") notify("remote"); });
  apply();
})();
