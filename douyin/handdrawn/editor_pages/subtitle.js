// 手绘字幕片段（OpenFilm 网页片段协议：window.film.frame(t) 画 t 秒的样子，同一个 t 永远画得一样）。
// #line 是可编辑的歌词（剪辑器里改字 = 改它的文字，换行用 <br>）；data-times = 每个字开始唱的秒数（相对片段开头），
// 字数和改过的文字对不上时，在 data-dur 里平均分配。#hi 每帧照 #line 重建，唱过的字变暖黄；整句随 12fps 轻轻抖动，像手画的。
(function () {
  const line = document.getElementById('line'), hi = document.getElementById('hi'), wrap = document.getElementById('wrap');
  const times = JSON.parse(line.dataset.times || '[]'), dur = +(line.dataset.dur || 3), len = +(line.dataset.len || dur + .5);   // dur 唱的长度，len 片段长度
  const hash = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
  const esc = (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c] || c);

  function fit() {                                   // 长句缩字号，不出框
    let size = +(line.dataset.size || 64);
    line.style.setProperty('--size', size + 'px'); hi.style.setProperty('--size', size + 'px');
    const maxW = document.body.clientWidth - 48;
    while (size > 28 && line.scrollWidth > maxW) { size -= 2; line.style.setProperty('--size', size + 'px'); hi.style.setProperty('--size', size + 'px'); }
  }
  function frame(t) {
    const rows = line.innerHTML.split(/<br\s*\/?>/i).map((r) => r.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' '));
    const chars = rows.join('').replace(/\s/g, '').length;
    const at = times.length === chars ? times : Array.from({ length: chars }, (_, i) => i / Math.max(1, chars) * dur * .9);
    let k = 0;
    hi.innerHTML = rows.map((r) => [...r].map((c) => { if (/\s/.test(c)) return esc(c); const on = t + 1e-3 >= at[k++]; return `<span class="${on ? 'on' : ''}">${esc(c)}</span>`; }).join('')).join('<br>');
    fit();
    const step = Math.floor(t * 12);                 // 12fps 的手绘抖动
    wrap.style.transform = `rotate(${(hash(step) - .5) * 1.6}deg) translate(${(hash(step + 7) - .5) * 3}px, ${(hash(step + 13) - .5) * 3}px)`;
    const fade = Math.min(1, t / .15, Math.max(0, (len - t) / .15));
    wrap.style.opacity = String(Math.max(0, fade));
  }
  window.film = { frame, ready: () => document.fonts.load('64px "ZCOOL KuaiLe"') };
  if (!window.filmHost) {                            // 单独打开时自己播放
    const t0 = performance.now();
    window.film.ready().then(() => { const loop = () => { frame(((performance.now() - t0) / 1000) % len); requestAnimationFrame(loop); }; loop(); });
  }
})();
