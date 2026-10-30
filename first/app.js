const app = document.getElementById("app");
const sortedPosts = [...POSTS].sort((a, b) => b.date.localeCompare(a.date));
let state = { query: "", tag: null };

// ---------- 工具函数 ----------
const escapeHtml = (s) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const inline = (s) =>
  escapeHtml(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2">')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

// 极简 Markdown 渲染：标题、段落、列表、引用、代码块
function markdown(src) {
  const lines = src.trim().split("\n");
  let html = "", i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const code = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i++;
      html += `<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`;
    } else if (/^#{1,3} /.test(line)) {
      const level = line.match(/^#+/)[0].length;
      html += `<h${level}>${inline(line.slice(level + 1))}</h${level}>`;
      i++;
    } else if (/^(- |\d+\. )/.test(line)) {
      const ordered = /^\d+\. /.test(line);
      const items = [];
      while (i < lines.length && /^(- |\d+\. )/.test(lines[i])) items.push(lines[i++].replace(/^(- |\d+\. )/, ""));
      const tag = ordered ? "ol" : "ul";
      html += `<${tag}>${items.map((t) => `<li>${inline(t)}</li>`).join("")}</${tag}>`;
    } else if (line.startsWith("> ")) {
      const quote = [];
      while (i < lines.length && lines[i].startsWith("> ")) quote.push(lines[i++].slice(2));
      html += `<blockquote><p>${inline(quote.join(" "))}</p></blockquote>`;
    } else if (line.trim() === "") {
      i++;
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() !== "" && !/^(#|- |\d+\. |> |```)/.test(lines[i])) para.push(lines[i++]);
      html += `<p>${inline(para.join(" "))}</p>`;
    }
  }
  return html;
}

const excerpt = (post) =>
  post.content.replace(/```[\s\S]*?```/g, "").replace(/[#>*`\-]/g, "").replace(/\s+/g, " ").trim().slice(0, 80) + "…";

const readTime = (post) => Math.max(1, Math.round(post.content.length / 400));

const metaHtml = (post) => `
  <div class="meta">
    <span>📅 ${post.date}</span>
    <span>⏱ ${readTime(post)} 分钟阅读</span>
    ${post.tags.map((t) => `<a class="tag" href="#/" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</a>`).join("")}
  </div>`;

// ---------- 页面 ----------
function renderHome() {
  const allTags = [...new Set(POSTS.flatMap((p) => p.tags))];
  app.innerHTML = `
    <div class="toolbar">
      <input class="search" type="search" placeholder="搜索文章…" value="${escapeHtml(state.query)}">
      <div class="tags">
        <button class="tag ${state.tag ? "" : "active"}" data-tag="">全部</button>
        ${allTags.map((t) => `<button class="tag ${state.tag === t ? "active" : ""}" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</button>`).join("")}
      </div>
    </div>
    <div id="list"></div>`;
  app.querySelector(".search").addEventListener("input", (e) => {
    state.query = e.target.value;
    renderList();
  });
  renderList();
}

function renderList() {
  const q = state.query.trim().toLowerCase();
  const posts = sortedPosts.filter(
    (p) =>
      (!state.tag || p.tags.includes(state.tag)) &&
      (!q || p.title.toLowerCase().includes(q) || p.content.toLowerCase().includes(q))
  );
  document.getElementById("list").innerHTML = posts.length
    ? posts
        .map(
          (p) => `
      <article class="post-card">
        <h2><a href="#/post/${p.id}">${escapeHtml(p.title)}</a></h2>
        ${metaHtml(p)}
        <p class="excerpt">${escapeHtml(excerpt(p))}</p>
      </article>`
        )
        .join("")
    : `<p class="empty">没有找到相关文章 🤔</p>`;
}

function renderPost(id) {
  const idx = sortedPosts.findIndex((p) => p.id === id);
  if (idx === -1) return renderNotFound();
  const post = sortedPosts[idx];
  const newer = sortedPosts[idx - 1], older = sortedPosts[idx + 1];
  document.title = `${post.title} - 我的博客`;
  app.innerHTML = `
    <article class="post">
      <h1>${escapeHtml(post.title)}</h1>
      ${metaHtml(post)}
      <div class="post-body">${markdown(post.content)}</div>
      <nav class="post-nav">
        <span>${newer ? `← <a href="#/post/${newer.id}">${escapeHtml(newer.title)}</a>` : ""}</span>
        <span>${older ? `<a href="#/post/${older.id}">${escapeHtml(older.title)}</a> →` : ""}</span>
      </nav>
    </article>`;
}

function renderAbout() {
  document.title = "关于 - 我的博客";
  app.innerHTML = `
    <article class="post">
      <h1>关于我</h1>
      <div class="post-body">${markdown(`
你好！我是这个博客的作者，一名热爱编程与阅读的人。

这里记录我的学习笔记、读书心得和生活感悟。

- 📧 邮箱：your@email.com
- 🐙 GitHub：[github.com/yourname](https://github.com)
`)}</div>
    </article>`;
}

function renderNotFound() {
  app.innerHTML = `<p class="empty">页面不存在，<a href="#/">返回首页</a></p>`;
}

// ---------- 路由 ----------
function router() {
  const hash = location.hash.slice(1) || "/";
  window.scrollTo(0, 0);
  if (hash === "/") {
    document.title = "我的博客";
    renderHome();
  } else if (hash.startsWith("/post/")) renderPost(decodeURIComponent(hash.slice(6)));
  else if (hash === "/about") renderAbout();
  else renderNotFound();
}

// 点击标签筛选（列表页和文章页的标签都可用）
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-tag]");
  if (!el) return;
  e.preventDefault();
  state.tag = el.dataset.tag || null;
  if (location.hash === "#/" || location.hash === "") renderHome();
  else location.hash = "#/";
});

// ---------- 深色模式 ----------
const toggle = document.getElementById("theme-toggle");
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  toggle.textContent = theme === "dark" ? "☀️" : "🌙";
  try { localStorage.setItem("theme", theme); } catch {}
}
let saved = null;
try { saved = localStorage.getItem("theme"); } catch {}
setTheme(saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
toggle.addEventListener("click", () =>
  setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark")
);

document.getElementById("year").textContent = new Date().getFullYear();
window.addEventListener("hashchange", router);
router();
