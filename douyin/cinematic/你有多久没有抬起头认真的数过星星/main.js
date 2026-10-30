// 《你有多久没有抬起头认真的数过星星》MV · 3D 电影风格部分（剧本 mv_v2）。
// 每个镜头一个场景组（同一时间只显示一个），CC 是 3D 的方块小人；评论按剧本在画面里浮现（2D 叠层，跟着 3D 锚点走）。
// 帧是时间 t 的纯函数（渲染器会乱序取帧）。手绘段（16–30、74–84.5 秒）在 douyin/handdrawn 里画，这里留黑。
import * as THREE from 'three';
import { makePost } from '/core/three/post.js';

const W = 1920, H = 1080, DUR = 84.5;
const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(W, H);
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
document.getElementById('stage').appendChild(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(32, W / H, .1, 600);
const post = makePost(renderer, scene, camera, W, H, { ssaa: 1, ao: false });
post.bloom.strength = .55; post.bloom.threshold = .72; post.bloom.radius = .55;
post.vig.uniforms.amt.value = .45; post.vig.uniforms.contrast.value = .1; post.vig.uniforms.sat.value = 1.0;
const ov = document.getElementById('ov').getContext('2d');
// 跟着镜头的柔和补光：让 CC 的正面在暗场景里也读得出来（每个场景另有自己的主光 / 轮廓光）
const fill = new THREE.PointLight('#ffe6c8', 3.2, 9, 1.1); fill.position.set(.6, .5, 0); camera.add(fill); scene.add(camera);

// ---------- 小工具 ----------
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const ease = x => { x = clamp(x); return x * x * (3 - 2 * x); };
const lerp = (a, b, k) => a + (b - a) * k;
const hash = i => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
const mat = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: .7, metalness: 0, ...o });
const box = (w, h, d, m) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);

// 窗户贴图：一栋楼一张，亮灯的格子暖黄
function windowTex(cols, rows, seed, lit = .35, warm = '#FFC870') {
  const c = document.createElement('canvas'); c.width = cols * 16; c.height = rows * 20; const g = c.getContext('2d');
  g.fillStyle = '#0d0f1c'; g.fillRect(0, 0, c.width, c.height);
  for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
    const on = hash(seed * 97 + i * 13 + j * 7) < lit;
    g.fillStyle = on ? (hash(i + j * 3 + seed) < .25 ? '#9FD0FF' : warm) : '#1a1d30'; g.fillRect(i * 16 + 4, j * 20 + 5, 8, 10);
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.magFilter = THREE.NearestFilter; return t;
}
function building(w, h, d, seed, lit, base = '#1b1d2c') {
  const tex = windowTex(Math.max(2, Math.round(w * 2)), Math.max(3, Math.round(h * 1.6)), seed, lit);
  const side = new THREE.MeshStandardMaterial({ color: base, roughness: .8, emissive: '#ffffff', emissiveMap: tex, emissiveIntensity: 1.4, map: tex });
  const m = box(w, h, d, [side, side, mat(base), mat(base), side, side]); m.position.y = h / 2; return m;
}
// CC 小人：身体 10×6（单位 0.1），四条腿，两只竖条眼睛，两只手（可转）
function makeCC(o = {}) {
  const g = new THREE.Group(), s = o.s || 1;
  const body = mat(o.col || '#D97757', { roughness: .55 }), dark = mat(o.dk || '#A84D33'), ink = mat('#1c1620', { roughness: .4 });
  const torso = box(1 * s, .6 * s, .55 * s, body); torso.position.y = .5 * s; g.add(torso);
  [-.4, -.2, .1, .3].forEach(x => { const l = box(.1 * s, .24 * s, .12 * s, dark); l.position.set((x + .05) * s, .1 * s, 0); g.add(l); });
  const eyes = [];
  for (const x of [-.25, .25]) { const e = box(.1 * s, .2 * s, .04 * s, ink); e.position.set(x * s, .6 * s, .28 * s); g.add(e); eyes.push(e); }
  const arms = [];
  for (const side of [-1, 1]) {
    const piv = new THREE.Group(); piv.position.set(side * .5 * s, .52 * s, 0);
    const a = box(.24 * s, .1 * s, .12 * s, body); a.position.x = side * .12 * s; piv.add(a); g.add(piv); arms.push(piv);
  }
  g.userData = { torso, eyes, arms, s };
  return g;
}
function poseCC(cc, p = {}) {
  const { eyes, arms, torso, s } = cc.userData;
  arms[0].rotation.z = -(p.aL ?? .2); arms[1].rotation.z = p.aR ?? .2;
  for (const e of eyes) { e.scale.y = p.blink ? .15 : 1; e.position.y = (.6 + (p.look || 0) * .04) * s; }
  torso.rotation.x = -(p.tilt || 0); cc.rotation.x = 0;
  eyes.forEach(e => { e.position.z = .28 * s + (p.look > .5 ? .0 : 0); });
}
// 星空：位置固定（hash），亮度按时间一颗颗亮起
function starField(n, r, seed, yMin = .05) {
  const pos = new Float32Array(n * 3), born = new Float32Array(n), sz = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const u = hash(seed + i * 3), v = yMin + (1 - yMin) * hash(seed + i * 7 + 1), th = u * Math.PI * 2, ph = Math.acos(v);
    pos.set([r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph), r * Math.sin(ph) * Math.sin(th)], i * 3);
    born[i] = hash(seed + i * 11); sz[i] = .6 + 2.4 * Math.pow(hash(seed + i * 13), 3);
  }
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('born', new THREE.BufferAttribute(born, 1)); geo.setAttribute('sz', new THREE.BufferAttribute(sz, 1));
  const m = new THREE.ShaderMaterial({
    uniforms: { k: { value: 1 }, t: { value: 0 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `attribute float born; attribute float sz; uniform float k, t; varying float a;
      void main(){ a = clamp((k - born) * 6.0, 0., 1.) * (.75 + .25 * sin(t * 3. + born * 40.));
        vec4 mv = modelViewMatrix * vec4(position, 1.); gl_Position = projectionMatrix * mv; gl_PointSize = sz * 5.5 * a + 0.5; }`,
    fragmentShader: `varying float a; void main(){ vec2 p = gl_PointCoord - .5; float d = length(p);
      float core = smoothstep(.5, .0, d); float cross = max(smoothstep(.06,.0,abs(p.x))*smoothstep(.5,.0,abs(p.y)), smoothstep(.06,.0,abs(p.y))*smoothstep(.5,.0,abs(p.x)));
      gl_FragColor = vec4(vec3(1., .93, .78) * 1.6, (core * core + cross * .6) * a); }`
  });
  return new THREE.Points(geo, m);
}
function skyDome(top, bottom) {
  const m = new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false, uniforms: { top: { value: new THREE.Color(top) }, bot: { value: new THREE.Color(bottom) } },
    vertexShader: 'varying vec3 p; void main(){ p = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }',
    fragmentShader: 'varying vec3 p; uniform vec3 top, bot; void main(){ gl_FragColor = vec4(mix(bot, top, smoothstep(-.05, .6, p.y)), 1.); }' });
  return new THREE.Mesh(new THREE.SphereGeometry(400, 32, 16), m);
}
function lampPost(h = 4.2, col = '#FFC46B', power = 30) {
  const g = new THREE.Group(), pole = box(.08, h, .08, mat('#22232c', { metalness: .6, roughness: .4 })); pole.position.y = h / 2; g.add(pole);
  const arm = box(.7, .06, .06, pole.material); arm.position.set(.3, h, 0); g.add(arm);
  const head = new THREE.Mesh(new THREE.SphereGeometry(.12, 12, 8), new THREE.MeshBasicMaterial({ color: new THREE.Color(col).multiplyScalar(3) })); head.position.set(.62, h - .08, 0); g.add(head);
  const light = new THREE.PointLight(col, power, 9, 1.6); light.position.copy(head.position); g.add(light);
  const cone = new THREE.Mesh(new THREE.ConeGeometry(1.5, h - .1, 24, 1, true), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: .035, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false }));
  cone.position.set(.62, (h - .1) / 2, 0); cone.visible = false;   // 光锥在后期里会糊成实心三角，不用
  g.userData = { light, head, cone }; return g;
}

// ---------- 场景（每个镜头一组） ----------
const ENV = {};
const add = (name, g) => { g.visible = false; scene.add(g); ENV[name] = g; return g; };

// A. 城市夜：霓虹、湿地面、看不到星星（0–16 秒）
{
  const g = add('city', new THREE.Group());
  g.add(skyDome('#0b1024', '#2a3150'));
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), mat('#0e1018', { roughness: .18, metalness: .55 })); ground.rotation.x = -Math.PI / 2; g.add(ground);
  for (let i = 0; i < 26; i++) {
    const side = i % 2 ? 1 : -1, z = -6 - Math.floor(i / 2) * 5.5, w = 3 + hash(i) * 3, h = 10 + hash(i + 5) * 26;
    const b = building(w, h, 4, i + 1, .32); b.position.set(side * (6 + hash(i + 9) * 4), 0, z); g.add(b);
  }
  const neonCols = ['#FF3D7F', '#36E2FF', '#FFB13D', '#9D6BFF'];
  for (let i = 0; i < 9; i++) {
    const n = new THREE.Mesh(new THREE.PlaneGeometry(1.6 + hash(i) * 2, .5), new THREE.MeshBasicMaterial({ color: new THREE.Color(neonCols[i % 4]).multiplyScalar(2.2) }));
    const side = i % 2 ? 1 : -1; n.position.set(side * (4.2 + hash(i + 2)), 2.5 + hash(i + 3) * 6, -4 - i * 4); n.rotation.y = -side * Math.PI / 2; g.add(n);
    const l = new THREE.PointLight(neonCols[i % 4], 14, 10, 1.6); l.position.copy(n.position); g.add(l);
  }
  g.add(new THREE.HemisphereLight('#4a5a9a', '#05060a', .35));
  const cc = makeCC(); cc.position.set(0, 0, 2); g.add(cc); g.userData.cc = cc;
  const fog = new THREE.FogExp2('#1b2140', .028); g.userData.fog = fog;
  const sc = document.createElement('canvas'); sc.width = sc.height = 256; const sg = sc.getContext('2d');
  const rg = sg.createRadialGradient(128, 128, 0, 128, 128, 128); rg.addColorStop(0, 'rgba(255,248,225,1)'); rg.addColorStop(.12, 'rgba(255,226,160,.9)'); rg.addColorStop(.4, 'rgba(255,200,120,.18)'); rg.addColorStop(1, 'rgba(255,200,120,0)');
  sg.fillStyle = rg; sg.fillRect(0, 0, 256, 256); sg.globalCompositeOperation = 'lighter';
  for (const [w, h] of [[256, 6], [6, 256]]) { const lg = sg.createRadialGradient(128, 128, 0, 128, 128, 128); lg.addColorStop(0, 'rgba(255,240,200,.9)'); lg.addColorStop(1, 'rgba(255,240,200,0)'); sg.fillStyle = lg; sg.fillRect(128 - w / 2, 128 - h / 2, w, h); }
  const stex = new THREE.CanvasTexture(sc); stex.colorSpace = THREE.SRGBColorSpace;
  const star = new THREE.Sprite(new THREE.SpriteMaterial({ map: stex, color: new THREE.Color('#ffffff').multiplyScalar(2.2), blending: THREE.AdditiveBlending, depthWrite: false, fog: false })); star.scale.setScalar(6);
  star.position.set(1.5, 30, -60); g.add(star); g.userData.star = star;
}
// B. 醒来长大（24–30 秒，手绘 → 3D 的落点）：白光里站起来的大人 CC
{
  const g = add('wake', new THREE.Group());
  g.add(skyDome('#F6E9D2', '#E9D6B8'));
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), mat('#e9dcc6', { roughness: .9 })); floor.rotation.x = -Math.PI / 2; g.add(floor);
  const sun = new THREE.DirectionalLight('#FFF1D6', 2.4); sun.position.set(-4, 8, 6); g.add(sun); g.add(new THREE.AmbientLight('#FFE7C4', .6));
  const cc = makeCC(); g.add(cc); g.userData.cc = cc;
}
// C. 地铁车窗：倒影里更亮的小 CC 渐渐远去（30–36 秒）
{
  const g = add('subway', new THREE.Group());
  g.add(skyDome('#05060b', '#0a0c14'));
  const wm = mat('#2a2f3c', { roughness: .5, metalness: .3 });
  for (const [w, h, x, y] of [[13, 6, -8.6, 3], [13, 6, 8.6, 3], [4.2, .8, 0, .4], [4.2, 3.0, 0, 4.5]]) { const p = box(w, h, .2, wm); p.position.set(x, y, -1.6); g.add(p); }   // 墙，中间留窗
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(4.2, 2.2), new THREE.MeshPhysicalMaterial({ color: '#10131d', roughness: .05, metalness: .2, transparent: true, opacity: .55, clearcoat: 1 }));
  glass.position.set(0, 1.9, -1.45); g.add(glass);
  const fm = mat('#9aa3b5', { metalness: .8, roughness: .3 });
  for (const [w, h, x, y] of [[4.4, .1, 0, .8], [4.4, .1, 0, 3.0], [.1, 2.3, -2.15, 1.9], [.1, 2.3, 2.15, 1.9]]) { const f = box(w, h, .12, fm); f.position.set(x, y, -1.5); g.add(f); }
  const tunnel = new THREE.Group(); g.add(tunnel); g.userData.tunnel = tunnel;
  for (let i = 0; i < 12; i++) { const s = new THREE.Mesh(new THREE.PlaneGeometry(1.2, .05), new THREE.MeshBasicMaterial({ color: new THREE.Color('#9FD0FF').multiplyScalar(3) })); s.position.set(i * 3 - 18, 1.2 + hash(i) * 1.4, -3); tunnel.add(s); }
  const lamp = new THREE.PointLight('#cfe0ff', 6, 8, 1.5); lamp.position.set(0, 4, 1.5); g.add(lamp); g.add(new THREE.AmbientLight('#8090b0', .25));
  const cc = makeCC(); cc.position.set(-.2, .55, .8); g.add(cc); g.userData.cc = cc;
  const ghost = makeCC({ col: '#5a5470', dk: '#3e3a52' }); ghost.position.set(-.2, .95, -1.75); ghost.scale.setScalar(.9); g.add(ghost); g.userData.ghost = ghost;   // 没表情的倒影
  const bright = makeCC({ s: .75 }); bright.position.set(.6, 1.5, -2.2); g.add(bright); g.userData.bright = bright;
  bright.traverse(m => { if (m.material && m.material.color) { m.material = m.material.clone(); m.material.emissive = new THREE.Color('#FFB46B'); m.material.emissiveIntensity = 1.6; } });
  const glow = new THREE.PointLight('#FFC27A', 4, 3, 2); bright.add(glow); glow.position.y = .5;
}
// D. 天没亮出门、天黑才回：路灯一盏盏（36–42 秒）
{
  const g = add('street', new THREE.Group());
  g.add(skyDome('#070a1a', '#141a36'));
  const road = new THREE.Mesh(new THREE.PlaneGeometry(80, 12), mat('#14151c', { roughness: .35, metalness: .3 })); road.rotation.x = -Math.PI / 2; g.add(road);
  for (let i = 0; i < 10; i++) { const d = box(.9, .01, .12, mat('#d8cfb8', { emissive: '#3a352a' })); d.position.set(i * 4 - 18, .01, 1.6); g.add(d); }
  const lamps = []; for (let i = 0; i < 6; i++) { const l = lampPost(); l.position.set(i * 6 - 12, 0, -2.2); g.add(l); lamps.push(l); } g.userData.lamps = lamps;
  for (let i = 0; i < 8; i++) { const b = building(4, 8 + hash(i) * 10, 3, i + 40, .12); b.position.set(i * 6 - 20, 0, -7); g.add(b); }
  g.add(new THREE.HemisphereLight('#26305a', '#020205', .25));
  const cc = makeCC(); g.add(cc); g.userData.cc = cc;
  const pack = box(.5, .45, .28, mat('#B23B3B')); pack.position.set(0, .5, -.38); cc.add(pack);
}
// E. 台灯下拆录取信 → 阳台举向夜空（42–55 秒）
{
  const g = add('desk', new THREE.Group());
  g.add(skyDome('#0b0d1d', '#1c1d36'));
  const roomFloor = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), mat('#2b2420')); roomFloor.rotation.x = -Math.PI / 2; g.add(roomFloor);
  const desk = box(1.9, .07, .8, mat('#7a5236', { roughness: .5 })); desk.position.set(0, .5, -.45); g.add(desk);
  for (const x of [-.85, .85]) { const leg = box(.06, .5, .06, desk.material); leg.position.set(x, .25, -.45); g.add(leg); }
  const lampL = new THREE.SpotLight('#FFB867', 11, 5, .8, .7, 1.3); lampL.position.set(-.6, 1.25, -.35); lampL.target.position.set(0, .8, .5); g.add(lampL, lampL.target);
  const bulb = new THREE.Mesh(new THREE.SphereGeometry(.09, 12, 8), new THREE.MeshBasicMaterial({ color: new THREE.Color('#FFD08A').multiplyScalar(5) })); bulb.position.copy(lampL.position); g.add(bulb);
  const lampArm = box(.03, .75, .03, mat('#2c2c33', { metalness: .7 })); lampArm.position.set(-.72, .88, -.5); lampArm.rotation.z = -.3; g.add(lampArm);
  g.add(new THREE.AmbientLight('#3a3150', .25));
  const cc = makeCC(); cc.position.set(0, 0, .35); g.add(cc); g.userData.cc = cc;
  const letter = new THREE.Mesh(new THREE.PlaneGeometry(.5, .34), new THREE.MeshStandardMaterial({ color: '#f4ecdc', roughness: .8, side: THREE.DoubleSide, emissive: '#3a2a10', emissiveIntensity: .3 }));
  letter.position.set(0, 1.25, .9); g.add(letter); g.userData.letter = letter;
  const seal = new THREE.Mesh(new THREE.PlaneGeometry(.52, .12), mat('#B3202C', { side: THREE.DoubleSide })); seal.position.set(0, -.17, .001); letter.add(seal);
  const tears = []; for (let i = 0; i < 2; i++) { const d = new THREE.Mesh(new THREE.SphereGeometry(.03, 10, 8), new THREE.MeshPhysicalMaterial({ color: '#bfe4ff', transmission: .6, roughness: .05, emissive: '#6fb6ff', emissiveIntensity: .8 })); cc.add(d); tears.push(d); } g.userData.tears = tears;
  const city = new THREE.Group(); city.position.set(0, 0, -30); g.add(city); g.userData.city = city;
  for (let i = 0; i < 18; i++) { const b = building(3 + hash(i) * 3, 6 + hash(i + 3) * 18, 3, i + 70, .45); b.position.set(i * 4.5 - 40, -6, -hash(i + 8) * 20); city.add(b); }
}
// F. 老居民楼之间：猛然抬头，满天星星（55–74 秒）
{
  const g = add('alley', new THREE.Group());
  g.add(skyDome('#0a0e26', '#1d2346'));
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(40, 60), mat('#1a1a22', { roughness: .6 })); ground.rotation.x = -Math.PI / 2; g.add(ground);
  for (let i = 0; i < 10; i++) {
    const side = i % 2 ? 1 : -1, b = building(5, 5 + hash(i) * 4, 6, i + 90, .38, '#2a2632'); b.position.set(side * 6.6, 0, -i * 3.2 + 4); b.rotation.y = side * .03; g.add(b);
    for (let k = 0; k < 3; k++) { const bal = box(.2, .9, 1.4, mat('#3b3542')); bal.position.set(side * 4.02, 1.6 + k * 2.2, -i * 3.2 + 4); g.add(bal); }
  }
  for (let i = 0; i < 6; i++) { const w = new THREE.Mesh(new THREE.CylinderGeometry(.008, .008, 13.2, 4), mat('#0c0c10')); w.rotation.z = Math.PI / 2; w.position.set(0, 4.6 + i * .5, -2 - i * 3); g.add(w); }   // 电线
  const lp = lampPost(3.4, '#FFB866', 16); lp.position.set(-2.8, 0, -2.6); g.add(lp);
  g.add(new THREE.HemisphereLight('#3a4680', '#06060a', .45));
  const stars = starField(3200, 300, 5, .1); g.add(stars); g.userData.stars = stars;
  const milky = new THREE.Mesh(new THREE.PlaneGeometry(600, 70), new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { k: { value: 0 } },
    vertexShader: 'varying vec2 v; void main(){ v = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }',
    fragmentShader: 'varying vec2 v; uniform float k; void main(){ float d = abs(v.y-.5)*2.; float n = fract(sin(dot(floor(v*vec2(300.,40.)), vec2(12.9,78.2)))*43758.5); gl_FragColor = vec4(vec3(.55,.5,.95), k*.28*smoothstep(1.,.0,d)*(.7+.3*n)); }' }));
  milky.position.set(0, 160, -200); milky.rotation.set(-.6, 0, -.35); g.add(milky); g.userData.milky = milky;
  const cc = makeCC(); g.add(cc); g.userData.cc = cc;
  const phone = box(.16, .26, .02, new THREE.MeshStandardMaterial({ color: '#111', emissive: '#9fd0ff', emissiveIntensity: 1.2 })); cc.userData.arms[1].add(phone); phone.position.set(.26, .05, .1); g.userData.phone = phone;
}

// ---------- 镜头表（时间 → 场景、相机、动作、评论） ----------
const C = (pos, look, fov = 32) => ({ pos, look, fov });
function cam(a, b, k) { camera.position.lerpVectors(a.pos, b.pos, k); const l = new THREE.Vector3().lerpVectors(a.look, b.look, k); camera.fov = lerp(a.fov, b.fov, k); camera.updateProjectionMatrix(); camera.lookAt(l); return l; }
let TEXT = [];   // 本帧要画的评论 / 屏幕字：{text, user, anchor(Vector3|null), x, y, k, size, color, glow}
const COM = {
  song: '不知道从什么时候开始抬头看星星也成为了一种奢侈当你被生活压的喘不过气的时候或许也该找个时间卸下身上所有的担子，远离城市',
  shine: '我好像……追不上以前那个闪闪发光的自己了', dark: '但是现在上学天是黑的，放学天也是黑的。我好像没有一秒钟多余的时间去看风景',
  happy: '我考上研啦，这次哭，是因为幸福。', stars: '回家的路上一直在低头玩手机，猛然间抬头发现今晚有好多星星啊！',
};
// 注：画面里的评论截取的是原文中连续的一段（不改字），完整原文在剧本和字幕卡里。

const SHOTS = [
  [0, 10, 'city', t => {
    const g = ENV.city, cc = g.userData.cc; scene.fog = g.userData.fog;
    const k = seg(t, 0, 10), walk = seg(t, 5, 10);
    cc.position.set(0, 0, lerp(2, 0, walk)); cc.rotation.y = lerp(.35, -.6, walk);
    const ph = t * 6 * (walk > 0 ? 1 : 0); poseCC(cc, { aL: -.25 + .25 * Math.sin(ph), aR: -.25 - .25 * Math.sin(ph), look: 1 - walk * 2 });
    cc.userData.torso.rotation.x = -.3 * (1 - walk);
    cam(C(V3(1.5, .45, 5.4), V3(-.3, 1.4, -2), 36), C(V3(2.6, .9, 5.2), V3(-.6, 1.6, -3), 32), ease(k));
    post.dof.focus = camera.position.distanceTo(cc.position); post.dof.aper = 2.4;
    TEXT.push({ text: COM.song, user: '宋艾星SIX · 6288 赞', x: W * .5, y: H * .2, k: seg(t, .3, 3.2) * (1 - seg(t, 8.6, 9.6)), size: 34, color: '#d8e4ff', wrap: 26 });
  }],
  [10, 16, 'city', t => {
    const g = ENV.city, cc = g.userData.cc; scene.fog = g.userData.fog;
    cc.position.set(0, 0, -3); poseCC(cc, { aL: -.2, aR: -.2, look: 1 }); cc.userData.torso.rotation.x = -.35;
    const k = ease(seg(t, 10, 16)); g.userData.star.scale.setScalar(lerp(4, 60, Math.pow(k, 2.2)));
    cam(C(V3(0, .4, 2.4), V3(1.5, 30, -60), 38), C(V3(.4, 3, -2), V3(1.5, 30, -60), 18), k);
    post.dof.focus = 60; post.dof.aper = 1.5;
  }],
  [27, 30, 'wake', t => {
    const cc = ENV.wake.userData.cc; scene.fog = new THREE.Fog('#f1e2c8', 6, 30);
    const k = ease(seg(t, 27, 29.6)); cc.position.set(0, 0, 0); cc.scale.setScalar(lerp(.45, 1, k));
    poseCC(cc, { aL: lerp(-.3, 1.1, seg(t, 28.4, 29.6)), aR: lerp(-.3, 1.1, seg(t, 28.4, 29.6)), blink: t < 28.2 });
    cam(C(V3(0, .5, 2.2), V3(0, .5, 0), 30), C(V3(0, 1, 4.8), V3(0, .7, 0), 34), k);
    post.dof.focus = camera.position.distanceTo(cc.position); post.dof.aper = 3;
  }],
  [30, 36, 'subway', t => {
    const g = ENV.subway, cc = g.userData.cc; scene.fog = null;
    g.userData.tunnel.position.x = ((t * 14) % 36) - 18;
    const away = ease(seg(t, 31.5, 36)); g.userData.bright.position.set(lerp(.6, 1.9, away), lerp(1.5, 1.9, away), lerp(-2.2, -7, away));
    cc.position.set(-1.35, .8, -.2); cc.rotation.y = Math.PI * .5 + .5; cc.scale.setScalar(.8);
    poseCC(cc, { aL: -.3, aR: .1 }); poseCC(g.userData.ghost, { aL: -.4, aR: -.4 });
    cam(C(V3(-3.6, 1.6, 2.9), V3(.2, 1.75, -1.8), 32), C(V3(-3.1, 1.6, 2.5), V3(.5, 1.8, -1.8), 30), ease(seg(t, 30, 36)));
    post.dof.focus = camera.position.distanceTo(V3(0, 1.6, -1.5)); post.dof.aper = 3.4;
    TEXT.push({ text: COM.shine, user: '13号女听客 · 2326 赞', anchor: V3(.2, 2.55, -1.4), k: seg(t, 30.6, 32) * (1 - seg(t, 35.4, 36)), size: 36, color: '#fff2dc' });
  }],
  [36, 42, 'street', t => {
    const g = ENV.street, cc = g.userData.cc; scene.fog = new THREE.FogExp2('#0e1230', .045);
    const k = seg(t, 36, 42); cc.position.set(lerp(-9, 5, k), 0, 0); cc.rotation.y = Math.PI / 2;
    const ph = t * 6; poseCC(cc, { aL: .2 + .3 * Math.sin(ph), aR: .2 - .3 * Math.sin(ph), look: -1 }); cc.position.y = Math.abs(Math.sin(ph)) * .04;
    cc.userData.torso.rotation.x = .15;
    g.userData.lamps.forEach((l, i) => { const on = seg(t, 36.2 + i * .9, 36.5 + i * .9); l.userData.light.intensity = 30 * on; l.userData.cone.material.opacity = .06 * on; l.userData.head.material.color.setScalar(on > .5 ? 1 : .15).multiply(new THREE.Color('#FFC46B')).multiplyScalar(on > .5 ? 3 : 1); });
    cam(C(V3(cc.position.x - 2.4, .55, 5.6), V3(cc.position.x + .6, 1.3, -.5), 34), C(V3(cc.position.x - 2, .6, 5.4), V3(cc.position.x + .8, 1.4, -.5), 34), k);
    post.dof.focus = camera.position.distanceTo(cc.position); post.dof.aper = 2.6;
    const lit = Math.min(5, Math.floor((t - 36.2) / .9)), lamp = g.userData.lamps[clamp(lit, 0, 5)];
    TEXT.push({ text: COM.dark, user: 'kgieusuis · 5934 赞', anchor: V3(lamp.position.x + .62, 4.9, -2.2), k: seg(t, 36.8, 38) * (1 - seg(t, 41.4, 42)), size: 32, color: '#ffe3b0', wrap: 18 });
  }],
  [42, 55, 'desk', t => {
    const g = ENV.desk, cc = g.userData.cc, letter = g.userData.letter; scene.fog = null;
    const open = ease(seg(t, 44.5, 46.5)), cry = seg(t, 47, 47.6), out = ease(seg(t, 50, 52.5));
    letter.position.set(0, lerp(.36, .46, open) + out * .62, lerp(.82, .8, open)); letter.rotation.x = lerp(-1.1, -.8, open) + out * .7;
    poseCC(cc, { aL: lerp(.6, 1.0, open) + out * .8, aR: lerp(.6, 1.0, open) + out * .8, look: out > .5 ? 1 : -1 });
    cc.userData.torso.rotation.x = lerp(.1, -.3, out);
    g.userData.tears.forEach((d, i) => { const p = ((t * .9 + i * .5) % 1); d.visible = cry > 0; d.position.set(i ? .25 : -.25, .52 - p * .35, .3); });
    g.userData.city.visible = out > .02; g.userData.city.position.y = lerp(-8, 0, out);
    const a = C(V3(2.5, 1.9, 4.4), V3(0, .45, .2), 30), b = C(V3(2.0, 1.65, 3.8), V3(0, .5, .3), 30), c = C(V3(-2.0, .55, 3.6), V3(0, 1.3, -10), 36);
    if (t < 50) cam(a, b, ease(seg(t, 42, 50))); else cam(b, c, out);
    post.dof.focus = camera.position.distanceTo(letter.position); post.dof.aper = 3.2;
    TEXT.push({ text: COM.happy, user: 'Romance · 2789 赞', x: W * .5, y: H * .17, k: seg(t, 46.6, 47.6) * (1 - seg(t, 50.5, 51.2)), size: 40, color: '#fff4e0' });
    TEXT.push({ text: '永远年轻，永远热泪盈眶', x: W * .5, y: H * .82, k: seg(t, 52, 53) * (1 - seg(t, 54.6, 55)), size: 46, color: '#ffe7b8', serif: true });
  }],
  [55, 74, 'alley', t => {
    const g = ENV.alley, cc = g.userData.cc; scene.fog = new THREE.FogExp2('#141838', .03);
    const up = ease(seg(t, 56.4, 57.2)), count = seg(t, 62, 68), orbit = ease(seg(t, 68, 74));
    cc.position.set(0, 0, lerp(1, -.2, seg(t, 55, 56.5))); cc.rotation.y = 0;
    poseCC(cc, { aL: count > 0 ? 1.2 + .25 * Math.sin(t * 6) : lerp(-.2, .3, up), aR: lerp(.9, -.4, up), look: lerp(-1, 1, up) });
    cc.userData.torso.rotation.x = lerp(.2, -.42, up);
    g.userData.phone.material.emissiveIntensity = 1.2 * (1 - up);
    g.userData.stars.material.uniforms.k.value = lerp(0, 1.02, ease(seg(t, 56.5, 66))); g.userData.stars.material.uniforms.t.value = t;
    g.userData.milky.material.uniforms.k.value = ease(seg(t, 58, 66));
    if (t < 56.5) cam(C(V3(.4, 1.4, 4.0), V3(0, .4, 0), 32), C(V3(.3, 1.2, 3.6), V3(0, .45, 0), 32), seg(t, 55, 56.5));
    else if (t < 62) cam(C(V3(.3, .7, 2.6), V3(0, .6, 0), 36), C(V3(1.1, .18, 2.9), V3(-.2, 6.5, -12), 58), ease(seg(t, 56.5, 58.5)));
    else if (t < 68) cam(C(V3(-1.1, .42, 1.5), V3(.7, 5, -10), 52), C(V3(-1.0, .45, 1.35), V3(.7, 5.6, -10), 50), seg(t, 62, 68));
    else { const a = lerp(-.9, .9, orbit), r = lerp(2.6, 6, orbit); camera.position.set(Math.sin(a) * r, lerp(.6, 2.2, orbit), Math.cos(a) * r); camera.fov = 38; camera.updateProjectionMatrix(); camera.lookAt(0, lerp(1, 3.5, orbit), 0); }
    post.dof.focus = camera.position.distanceTo(cc.position) + (t > 57 && t < 68 ? 8 : 0); post.dof.aper = 2.2;
    TEXT.push({ text: COM.stars, user: '不吃饭的人会饿 · 169 赞', x: W * .5, y: H * .2, k: seg(t, 58, 59.6) * (1 - seg(t, 66.5, 67.5)), size: 38, color: '#fff3d0', glow: 1 });
    if (count > 0 && count < 1) { const n = 1 + Math.floor(count * 9); TEXT.push({ text: String(n), x: W * (.56 + .03 * Math.sin(n * 2.1)), y: H * (.3 + .05 * Math.cos(n * 1.7)), k: 1 - (count * 9 % 1) * .5, size: 64, color: '#FFE9A8' }); }
  }],
];

// ---------- 2D 叠层：评论字（带柔光）+ 胶片颗粒 ----------
function wrapLines(s, n) { const out = []; for (let i = 0; i < s.length; i += n) out.push(s.slice(i, i + n)); return out; }
function drawText(T) {
  for (const x of T) {
    if (x.k <= .01) continue;
    let px = x.x, py = x.y;
    if (x.anchor) { const p = x.anchor.clone().project(camera); px = (p.x * .5 + .5) * W; py = (-p.y * .5 + .5) * H; }
    const lines = wrapLines(x.text, x.wrap || 22), lh = x.size * 1.45;
    ov.save(); ov.globalAlpha = ease(x.k); ov.textAlign = 'center'; ov.textBaseline = 'middle';
    ov.font = `${x.serif ? '' : '600 '}${x.size}px ${x.serif ? '"KaiTi","STKaiti",serif' : '"Microsoft YaHei","PingFang SC",sans-serif'}`;
    const bw = Math.max(...lines.map(l => ov.measureText(l).width)) + x.size * 1.6, bh = lines.length * lh + (x.user ? lh * .9 : 0) + x.size * .6;
    const grd = ov.createRadialGradient(px, py + (x.user ? lh * .3 : 0), 0, px, py, Math.max(bw, bh) * .62);
    grd.addColorStop(0, 'rgba(6,8,18,.55)'); grd.addColorStop(1, 'rgba(6,8,18,0)'); ov.fillStyle = grd;
    ov.fillRect(px - bw * .7, py - bh * .8, bw * 1.4, bh * 1.6);
    lines.forEach((ln, i) => {
      const y = py + (i - (lines.length - 1) / 2) * lh + (1 - ease(x.k)) * 12;
      ov.shadowColor = 'rgba(255,214,150,.75)'; ov.shadowBlur = 18 * (x.glow ? 1.6 : 1); ov.fillStyle = x.color; ov.fillText(ln, px, y);
    });
    if (x.user) { ov.shadowBlur = 8; ov.font = `${Math.round(x.size * .62)}px "Microsoft YaHei",sans-serif`; ov.fillStyle = 'rgba(230,230,240,.85)'; ov.fillText('—— ' + x.user, px, py + (lines.length / 2 + .5) * lh); }
    ov.restore();
  }
}
const grainC = document.createElement('canvas'); grainC.width = 480; grainC.height = 270;
function grain(t) {
  const g = grainC.getContext('2d'), id = g.createImageData(480, 270), d = id.data, f = Math.floor(t * 24);
  for (let i = 0; i < d.length; i += 4) { const v = (hash(i * .25 + f * 7.13) - .5) * 38; d[i] = d[i + 1] = d[i + 2] = 128 + v; d[i + 3] = 255; }
  g.putImageData(id, 0, 0);
  ov.save(); ov.globalCompositeOperation = 'overlay'; ov.globalAlpha = .22; ov.imageSmoothingEnabled = true; ov.drawImage(grainC, 0, 0, W, H); ov.restore();
}

window.render = t => {
  TEXT = []; ov.clearRect(0, 0, W, H);
  const s = SHOTS.find(([a, b]) => t >= a && t < b);
  for (const k in ENV) ENV[k].visible = false;
  if (!s) { renderer.setClearColor('#000'); renderer.clear(); return; }     // 手绘段：在 douyin/handdrawn 里画
  ENV[s[2]].visible = true;
  s[3](t);
  scene.updateMatrixWorld(); camera.updateMatrixWorld();
  post.composer.render();
  drawText(TEXT);
  grain(t);
};
window.DUR = DUR;
window.READY = true;
