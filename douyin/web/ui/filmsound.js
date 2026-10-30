/* 作品集的胶片音效（WebAudio 实时合成，没有音频文件）：
   - 齿孔咔嗒：每经过一张作品响一声，滚得越快越亮、越响；两声之间至少 22ms
   - 摩擦声：滚动时才有，音量跟随速度，停下后约 0.3 秒淡出，1.5 秒后整个停止（不会一直循环）
   - 定位反馈：停在某张作品上时一声柔和的闷响
   音效走独立的增益节点，不影响视频本身的声音；设置里关掉后不再创建任何声音。
   浏览器要求先有一次点击/按键才能出声，之前的滚动静默。 */
(function () {
  let ctx = null, master = null, noise = null, fric = null, fricGain = null, fricFilter = null, stopTimer = 0, lastTick = 0;
  const S = () => window.StudioSettings.get();

  function ensure() {
    if (!S().sound) return null;
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
      master = ctx.createGain();
      master.connect(ctx.destination);
      const len = ctx.sampleRate * 2;
      noise = ctx.createBuffer(1, len, ctx.sampleRate);
      const d = noise.getChannelData(0);
      let b = 0;
      for (let i = 0; i < len; i++) { b = 0.97 * b + 0.03 * (Math.random() * 2 - 1); d[i] = (Math.random() * 2 - 1) * 0.55 + b * 2.2; }
    }
    master.gain.value = Math.pow(S().volume, 1.6) * 0.9;
    return ctx.state === "running" ? ctx : null;
  }
  // 浏览器的自动播放策略：第一次点击/按键后才能出声
  const unlock = () => { if (ctx && ctx.state !== "running") ctx.resume(); else if (!ctx && S().sound) { ensure(); ctx && ctx.resume(); } };
  window.addEventListener("pointerdown", unlock, { capture: true });
  window.addEventListener("keydown", unlock, { capture: true });

  function burst(t, dur, f0, q, gain) {
    const src = ctx.createBufferSource();
    src.buffer = noise;
    src.playbackRate.value = 0.9 + Math.random() * 0.2;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass"; bp.frequency.value = f0; bp.Q.value = q;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(gain, t + 0.0015);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(bp).connect(g).connect(master);
    src.start(t, Math.random() * 1.5, dur + 0.02);
  }

  window.FilmSound = {
    /** 经过一张作品：speed 0~1 */
    tick(speed) {
      if (!S().soundTick || !ensure()) return;
      const now = ctx.currentTime;
      if (now - lastTick < 0.022) return;
      lastTick = now;
      const s = Math.min(1, Math.max(0, speed));
      burst(now, 0.012 + 0.01 * (1 - s), 2600 + 2200 * s, 2.2, 0.22 + 0.38 * s);   // 齿孔
      burst(now + 0.004, 0.03, 900, 6, 0.05 + 0.06 * s);                              // 胶片片基的轻微共振
    },
    /** 滚动速度 0~1（每帧调用）；为 0 时摩擦声淡出 */
    friction(speed) {
      if (!S().soundFriction || !ensure()) return;
      const now = ctx.currentTime, s = Math.min(1, Math.max(0, speed));
      if (s > 0.02 && !fric) {
        fric = ctx.createBufferSource(); fric.buffer = noise; fric.loop = true;
        fricFilter = ctx.createBiquadFilter(); fricFilter.type = "bandpass"; fricFilter.Q.value = 0.9;
        fricGain = ctx.createGain(); fricGain.gain.value = 0;
        fric.connect(fricFilter).connect(fricGain).connect(master);
        fric.start();
      }
      if (!fric) return;
      fricFilter.frequency.setTargetAtTime(700 + 1500 * s, now, 0.05);
      fricGain.gain.setTargetAtTime(s > 0.02 ? 0.035 + 0.1 * s : 0, now, s > 0.02 ? 0.04 : 0.1);
      clearTimeout(stopTimer);
      if (s <= 0.02) stopTimer = setTimeout(() => { if (fric) { fric.stop(); fric.disconnect(); fric = null; } }, 1500);
    },
    /** 停在某张作品上 */
    settle() {
      if (!S().soundSettle || !ensure()) return;
      const now = ctx.currentTime;
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = "sine"; o.frequency.setValueAtTime(150, now); o.frequency.exponentialRampToValueAtTime(82, now + 0.12);
      g.gain.setValueAtTime(0, now); g.gain.linearRampToValueAtTime(0.16, now + 0.004); g.gain.exponentialRampToValueAtTime(0.0001, now + 0.18);
      o.connect(g).connect(master); o.start(now); o.stop(now + 0.2);
      burst(now, 0.02, 1800, 3, 0.12);
    },
    /** 设置中心的「试听」 */
    preview() {
      unlock();
      const run = () => {
        if (!ensure()) return;
        let k = 0;
        const iv = setInterval(() => { this.tick(0.3 + k * 0.08); this.friction(0.5); if (++k >= 6) { clearInterval(iv); this.friction(0); setTimeout(() => this.settle(), 140); } }, 90);
      };
      ctx && ctx.state !== "running" ? ctx.resume().then(run) : run();
    },
    /** 关闭音效：立即停掉正在响的摩擦声 */
    stop() { if (fric) { try { fric.stop(); } catch (e) { /* 已停止 */ } fric = null; } },
  };
  window.StudioSettings.on((s) => { if (!s.sound) window.FilmSound.stop(); else if (master) master.gain.value = Math.pow(s.volume, 1.6) * 0.9; });
})();
