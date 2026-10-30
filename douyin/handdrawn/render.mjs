// render.mjs：在无头 Edge 里驱动 studio.html，把手绘场景画成图。
//   node render.mjs --list [--song=<歌>]                                     列出登记的场景
//   node render.mjs --scene=<名> [--song=<歌>] --sheet=0,1.5,3 [--cols=3] --out=x.jpg   拼图自查
//   node render.mjs --scene=<名> [--song=<歌>] --frames [--fps=12] --out=<目录> [--scale=0.5]   逐帧 PNG（透明场景保留透明）
// 场景尺寸 / 时长 / 透明从场景登记里读。先 `. /d/cc-engine/filmlab/env.sh`（$EDGE）。
import puppeteer from 'puppeteer-core';
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).map(a => { const [k, ...v] = a.replace(/^--/, '').split('='); return [k, v.length ? v.join('=') : true]; }));
const EXE = args.chrome || process.env.EDGE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const browser = await puppeteer.launch({
  executablePath: EXE, headless: true, protocolTimeout: 0,
  args: ['--allow-file-access-from-files', '--ignore-gpu-blocklist', '--use-angle=d3d11', '--enable-gpu-rasterization',
         '--disable-renderer-backgrounding', '--disable-background-timer-throttling', '--no-first-run', '--disable-extensions']
});
const base = pathToFileURL(resolve('studio.html')).href;
async function open(params) {
  const page = await browser.newPage();
  page.on('console', m => { if (['error', 'warn'].includes(m.type())) console.log('[page]', m.text()); });
  page.on('pageerror', e => console.log('[page error]', e.message));
  await page.goto(base + '?' + new URLSearchParams({ render: 1, ...params }), { waitUntil: 'load' });
  await page.waitForFunction('window.ready === true', { timeout: 60000 });
  return page;
}
const song = { ...(args.song ? { song: args.song } : {}), ...(args.layer ? { layer: args.layer } : {}), ...(args.matte ? { matte: args.matte } : {}) };   // --layer=bg|male|others|props|subs|trans --matte=black|white：分层渲染
const probe = await open(song);
const list = await probe.evaluate(() => window.sceneList());
await probe.close();
if (args.list) { for (const [k, v] of Object.entries(list)) console.log(`${k}\t${v.w}x${v.h}\t${v.dur}s\t${v.alpha ? '透明' : '带底'}\t${v.zh}`); await browser.close(); process.exit(0); }

const names = String(args.scene || '').split(',').filter(Boolean);
for (const name of names) {
  const s = list[name]; if (!s) { console.log('没有这个场景：' + name); continue; }
  const page = await open({ ...song, scene: name, w: s.w, h: s.h, dur: s.dur, ...(s.alpha ? { alpha: 1 } : {}), ...(s.bpm ? { bpm: s.bpm, off: s.off || 0 } : {}) });
  const grab = async (t, type) => { const url = await page.evaluate((t, type) => window.renderAt(t, type, .9), t, type); return Buffer.from(url.slice(url.indexOf(',') + 1), 'base64'); };
  if (args.sheet) {
    const out = args.out || `out/${name}_sheet.jpg`; mkdirSync(dirname(out), { recursive: true });
    const { url, ms } = await page.evaluate(async (ts, cols, w) => {
      const h = Math.round(w * H / W), rows = Math.ceil(ts.length / cols), sc = document.createElement('canvas'), ms = [];
      sc.width = cols * w; sc.height = rows * h; const c = sc.getContext('2d');
      c.fillStyle = ALPHA ? '#cfc8bd' : '#000'; c.fillRect(0, 0, sc.width, sc.height);
      for (let i = 0; i < ts.length; i++) {
        const t0 = performance.now(); await window.renderAt(ts[i]); ms.push(Math.round(performance.now() - t0));
        const x = (i % cols) * w, y = Math.floor(i / cols) * h; c.drawImage(document.getElementById('out'), x, y, w, h);
        c.fillStyle = 'rgba(0,0,0,.6)'; c.fillRect(x, y, 70, 22); c.fillStyle = '#fff'; c.font = '15px sans-serif'; c.fillText(ts[i].toFixed(2) + 's', x + 5, y + 16);
      }
      return { url: sc.toDataURL('image/jpeg', .88), ms };
    }, String(args.sheet).split(',').map(Number), +(args.cols || 3), +(args.w || 480));
    writeFileSync(out, Buffer.from(url.slice(url.indexOf(',') + 1), 'base64'));
    console.log(`${out}  ms/帧：${ms.join(' ')}`);
  } else if (args.frames) {
    const fps = +(args.fps || 12), out = args.out || `out/${name}`, n = Math.round(s.dur * fps); mkdirSync(out, { recursive: true });
    // --from / --to（秒）：只渲染这一段（帧号仍按整片算，几个进程可以分段并行）；--jpg：存 JPEG（整片用，省空间）；已有的帧跳过（可续跑）
    const i0 = Math.floor(+(args.from || 0) * fps), i1 = Math.min(n, Math.ceil(+(args.to || s.dur) * fps)), ext = args.jpg ? 'jpg' : 'png';
    const t0 = Date.now(); let done = 0;
    for (let i = i0; i < i1; i++) { const f = `${out}/f${String(i).padStart(4, '0')}.${ext}`; if (existsSync(f)) continue;
      writeFileSync(f, await grab(i / fps, args.jpg ? 'image/jpeg' : 'image/png')); done++;
      if (done % 60 === 0) console.log(`${name}: ${i - i0 + 1}/${i1 - i0} 帧`); }
    console.log(`${name}: ${done} 帧 → ${out}（${(done ? (Date.now() - t0) / done : 0).toFixed(0)} ms/帧）`);
  }
  await page.close();
}
await browser.close();
