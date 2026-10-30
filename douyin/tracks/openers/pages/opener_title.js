// 开头的歌名 / 歌手（OpenFilm 网页片段协议：window.film.frame(t) 画 t 秒的样子）。和拨片开头一样：0.7 秒内淡入，同时上浮 12 像素。
(function () {
  const wrap = document.getElementById('wrap');
  function frame(t) {
    const a = Math.max(0, Math.min(1, t / 0.7));
    wrap.style.opacity = String(a);
    wrap.style.transform = `translateY(${(1 - a) * 12}px)`;
  }
  window.film = { frame, ready: () => document.fonts.ready };
  if (!window.filmHost) {                            // 单独打开时自己播放
    const t0 = performance.now();
    const loop = () => { frame(((performance.now() - t0) / 1000) % 3); requestAnimationFrame(loop); };
    loop();
  }
})();
