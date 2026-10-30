// 抖音周报 PPT：node weekly.js <数据.json> <输出.pptx>
// 数据由 workflow/daily/weekly.py 从创作者中心快照生成（数字都是真实数据，这里只负责排版）。
const fs = require('fs');
const pptxgen = require('pptxgenjs');

const [, , dataPath, outPath] = process.argv;
const D = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9'; // 10 x 5.625
pres.title = D.title;

// 配色取自音轨界面：深色面板 + 象牙白文字 + 各条音轨的颜色，网易云红做强调
const C = {
  bg: '121218', panel: '1E1E28', panel2: '262633', ivory: 'F2EDE4', muted: '9A97A6',
  red: 'E5484D', gold: 'E8C77A', pink: 'E89AB0', lav: 'B9A3E8', teal: '6CC5B0',
};
const LANES = [C.gold, C.pink, C.lav, C.teal, C.red];
const F = 'Microsoft YaHei';
const pct = (x, d = 1) => (x * 100).toFixed(d) + '%';

function bg(slide) { slide.background = { color: C.bg }; }
// 视觉母题：音轨上的「片段」——圆角色块 + 左侧小色点
function clip(slide, x, y, w, h, fill = C.panel) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: fill }, line: { color: fill } });
}
function dot(slide, x, y, color, d = 0.16) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color } });
}
function title(slide, text, sub) {
  slide.addText(text, { x: 0.5, y: 0.3, w: 9, h: 0.6, fontFace: F, fontSize: 26, bold: true, color: C.ivory, margin: 0 });
  if (sub) slide.addText(sub, { x: 0.5, y: 0.88, w: 9, h: 0.3, fontFace: F, fontSize: 11, color: C.muted, margin: 0 });
}
function foot(slide) {
  slide.addText(`数据来源：抖音创作者中心 · ${D.data_time}`, { x: 0.5, y: 5.25, w: 9, h: 0.22, fontFace: F, fontSize: 8, color: C.muted, margin: 0 });
}
function stat(slide, x, y, w, value, label, color) {
  clip(slide, x, y, w, 1.25);
  dot(slide, x + 0.2, y + 0.24, color);
  slide.addText(label, { x: x + 0.45, y: y + 0.15, w: w - 0.6, h: 0.32, fontFace: F, fontSize: 11, color: C.muted, margin: 0 });
  slide.addText(value, { x: x + 0.2, y: y + 0.5, w: w - 0.4, h: 0.6, fontFace: F, fontSize: 28, bold: true, color: C.ivory, margin: 0 });
}
const chartBase = (t) => ({
  showTitle: true, title: t, titleColor: C.ivory, titleFontFace: F, titleFontSize: 12,
  catAxisLabelColor: C.muted, valAxisLabelColor: C.muted, catAxisLabelFontFace: F, catAxisLabelFontSize: 9,
  valAxisLabelFontSize: 9, valGridLine: { color: '33333F', size: 0.5 }, catGridLine: { style: 'none' },
  showValue: true, dataLabelColor: C.ivory, dataLabelFontSize: 9, showLegend: false,
});
const names = D.rows.map((r) => `${r.date} ${r.title.slice(0, 8)}`);

// 1. 封面
{
  const s = pres.addSlide(); bg(s);
  LANES.forEach((c, i) => clip(s, 0.5 + i * 0.5, 0.6, 0.38, 0.12 + (i % 3) * 0.06, c));
  s.addText(D.title, { x: 0.5, y: 1.2, w: 9, h: 0.9, fontFace: F, fontSize: 40, bold: true, color: C.ivory, margin: 0 });
  s.addText(`${D.account} · 音轨拆解`, { x: 0.5, y: 2.1, w: 9, h: 0.4, fontFace: F, fontSize: 16, color: C.muted, margin: 0 });
  stat(s, 0.5, 3.3, 2.8, String(D.total_play), '全部作品总播放', C.gold);
  stat(s, 3.6, 3.3, 2.8, pct(D.completion), '条均完播率', C.red);
  stat(s, 6.7, 3.3, 2.8, String(D.fans), '作品带来的涨粉', C.teal);
  foot(s);
}

// 2. 总览
{
  const s = pres.addSlide(); bg(s);
  title(s, '这一周的数据', `共 ${D.rows.length} 条作品，本周发布 ${D.week_count} 条` + (D.has_prev ? `，比上次统计播放 +${D.d_total}` : '（第一次统计，下周起有周环比）'));
  const tiles = [
    [pct(D.bounce), '条均 2 秒跳出率', C.red], [pct(D.five), '条均 5 秒完播率', C.gold],
    [pct(D.completion), '条均完播率', C.pink], [pct(D.share, 0), '平均看完全片的比例', C.lav],
  ];
  tiles.forEach(([v, l, c], i) => stat(s, 0.5 + (i % 2) * 4.6, 1.45 + Math.floor(i / 2) * 1.55, 4.4, v, l, c));
  s.addText('一句话：大部分人在开头几秒就划走了，完播率低主要是「留不住开头」。', {
    x: 0.5, y: 4.6, w: 9, h: 0.4, fontFace: F, fontSize: 13, italic: true, color: C.gold, margin: 0,
  });
  foot(s);
}

// 3. 每条作品：播放 + 完播
{
  const s = pres.addSlide(); bg(s);
  title(s, '每条作品', '左：播放量；右：完播率（看完整条的人占比）');
  clip(s, 0.5, 1.35, 4.4, 3.75); clip(s, 5.1, 1.35, 4.4, 3.75);
  s.addChart(pres.charts.BAR, [{ name: '播放', labels: names, values: D.rows.map((r) => r.play) }], {
    x: 0.6, y: 1.45, w: 4.2, h: 3.55, barDir: 'bar', chartColors: [C.gold], dataLabelPosition: 'outEnd',
    ...chartBase('播放量'),
  });
  s.addChart(pres.charts.BAR, [{ name: '完播率', labels: names, values: D.rows.map((r) => +(r.completion * 100).toFixed(2)) }], {
    x: 5.2, y: 1.45, w: 4.2, h: 3.55, barDir: 'bar', chartColors: [C.red], dataLabelPosition: 'outEnd',
    dataLabelFormatCode: '0.0"%"', valAxisLabelFormatCode: '0.0"%"', valAxisMajorUnit: 0.5, ...chartBase('完播率 %'),
  });
  foot(s);
}

// 4. 人在哪里走掉
{
  const s = pres.addSlide(); bg(s);
  const avgView = D.rows.reduce((a, r) => a + r.view_sec, 0) / Math.max(1, D.rows.length);
  title(s, '人在哪里走掉', `平均每人只看 ${avgView.toFixed(1)} 秒；2 秒内就划走的人占 ${pct(D.bounce, 0)}`);
  clip(s, 0.5, 1.35, 5.6, 3.75);
  s.addChart(pres.charts.BAR, [
    { name: '2 秒跳出', labels: names, values: D.rows.map((r) => +(r.bounce * 100).toFixed(1)) },
    { name: '5 秒完播', labels: names, values: D.rows.map((r) => +(r.five * 100).toFixed(1)) },
  ], {
    x: 0.6, y: 1.45, w: 5.4, h: 3.55, barDir: 'col', barGrouping: 'clustered', chartColors: [C.red, C.gold],
    dataLabelPosition: 'outEnd', dataLabelFormatCode: '0"%"', valAxisLabelFormatCode: '0"%"',
    ...chartBase('2 秒跳出 vs 5 秒完播（%）'), showLegend: true, legendPos: 'b', legendColor: C.muted, legendFontFace: F, legendFontSize: 9,
  });
  clip(s, 6.3, 1.35, 3.2, 3.75, C.panel2);
  const lines = D.rows.map((r) => ({ text: `${r.title.slice(0, 9)}：看 ${r.view_sec.toFixed(1)}s / ${Math.round(r.duration)}s`, options: { breakLine: true, fontSize: 10.5, color: C.ivory, fontFace: F, paraSpaceAfter: 6 } }));
  s.addText([{ text: '平均观看 / 全片时长', options: { breakLine: true, bold: true, fontSize: 12, color: C.gold, fontFace: F, paraSpaceAfter: 8 } }, ...lines],
    { x: 6.5, y: 1.5, w: 2.9, h: 3.5, valign: 'top', margin: 0 });
  foot(s);
}

// 5. 问题与建议
{
  const s = pres.addSlide(); bg(s);
  title(s, '看出来的问题，和怎么改', '规则写在 workflow/daily/report.py 里；建议都是「待验证」，下周用实验检验');
  const col = (x, head, items, color) => {
    clip(s, x, 1.35, 4.4, 3.75);
    dot(s, x + 0.25, 1.58, color);
    s.addText(head, { x: x + 0.5, y: 1.48, w: 3.7, h: 0.35, fontFace: F, fontSize: 14, bold: true, color: C.ivory, margin: 0 });
    s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 8, fontSize: 11.5, color: C.ivory, fontFace: F } })),
      { x: x + 0.2, y: 1.95, w: 4.0, h: 3.05, valign: 'top', margin: 0 });
  };
  col(0.5, '问题', D.problems, C.red);
  col(5.1, '建议', D.tips, C.teal);
  foot(s);
}

// 6. 下周实验
{
  const s = pres.addSlide(); bg(s);
  title(s, '下周第一轮实验', '在现有模板上每次只改一处，A/B 隔天发，比数据；主题始终是音轨拆解');
  D.experiments.forEach((e, i) => {
    const x = 0.5 + i * 3.05;
    clip(s, x, 1.4, 2.85, 3.0);
    s.addText(String(i + 1), { x: x + 0.25, y: 1.6, w: 0.7, h: 0.7, fontFace: F, fontSize: 30, bold: true, color: LANES[i], margin: 0 });
    s.addText(e.name, { x: x + 0.25, y: 2.35, w: 2.4, h: 0.4, fontFace: F, fontSize: 16, bold: true, color: C.ivory, margin: 0 });
    s.addText(e.change, { x: x + 0.25, y: 2.8, w: 2.4, h: 0.95, fontFace: F, fontSize: 12, color: C.ivory, valign: 'top', margin: 0 });
    s.addText('看：' + e.metric, { x: x + 0.25, y: 3.8, w: 2.4, h: 0.5, fontFace: F, fontSize: 10, color: C.muted, valign: 'top', margin: 0 });
  });
  foot(s);
}

// 7. 本周做了什么
{
  const s = pres.addSlide(); bg(s);
  title(s, '这周 cc-piano 新增的能力', '都已保存进 cc-piano，可以随时调用');
  D.done.forEach((t, i) => {
    const y = 1.4 + i * 0.72;
    clip(s, 0.5, y, 9, 0.58);
    dot(s, 0.75, y + 0.21, LANES[i % LANES.length]);
    s.addText(t, { x: 1.1, y, w: 8.2, h: 0.58, fontFace: F, fontSize: 12.5, color: C.ivory, valign: 'middle', margin: 0 });
  });
  foot(s);
}

// 8. 结尾
{
  const s = pres.addSlide(); bg(s);
  LANES.forEach((c, i) => clip(s, 0.5 + i * 0.5, 0.6, 0.38, 0.12 + ((i + 1) % 3) * 0.06, c));
  s.addText('下周盯这三个数', { x: 0.5, y: 1.2, w: 9, h: 0.7, fontFace: F, fontSize: 32, bold: true, color: C.ivory, margin: 0 });
  stat(s, 0.5, 2.4, 2.8, pct(D.bounce, 0), '2 秒跳出（越低越好）', C.red);
  stat(s, 3.6, 2.4, 2.8, pct(D.five, 0), '5 秒完播（越高越好）', C.gold);
  stat(s, 6.7, 2.4, 2.8, pct(D.completion), '完播率（越高越好）', C.pink);
  s.addText('以上是本周的起点数值。每天 12:00 的日报会跟踪变化，下周六再出对比。', {
    x: 0.5, y: 4.0, w: 9, h: 0.4, fontFace: F, fontSize: 12, color: C.muted, margin: 0,
  });
  foot(s);
}

pres.writeFile({ fileName: outPath }).then(() => console.log(outPath));
