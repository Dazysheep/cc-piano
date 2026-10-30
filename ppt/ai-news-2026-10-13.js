const pptxgen = require('pptxgenjs');
const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9'; // 10 x 5.625
pres.title = '今日AI大事 2026-10-13';

const C = {
  navy: '0B1426', navy2: '16213A', cyan: '22D3EE', cyanDk: '0E7490',
  coral: 'F97362', ink: '1E293B', muted: '64748B', tint: 'EEF6FA', white: 'FFFFFF', line: 'CBD5E1',
};
const F = 'Microsoft YaHei';

// 视觉母题：圆形徽章 + 单字
function badge(slide, x, y, d, ch, fill = C.cyan, color = C.navy) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill } });
  slide.addText(ch, { x, y, w: d, h: d, align: 'center', valign: 'middle', fontFace: F, fontSize: d * 22, bold: true, color, margin: 0 });
}
function title(slide, text, sub) {
  slide.addText(text, { x: 0.5, y: 0.32, w: 9, h: 0.6, fontFace: F, fontSize: 28, bold: true, color: C.ink, margin: 0 });
  if (sub) slide.addText(sub, { x: 0.5, y: 0.92, w: 9, h: 0.3, fontFace: F, fontSize: 12, color: C.muted, margin: 0 });
}
function source(slide, text) {
  slide.addText('来源：' + text, { x: 0.5, y: 5.2, w: 9, h: 0.25, fontFace: F, fontSize: 9, color: C.muted, margin: 0 });
}
function card(slide, x, y, w, h, fill = C.tint) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill } });
}
function bullets(items, size = 13, color = C.ink) {
  return items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6, fontSize: size, color, fontFace: F } }));
}
function unconfirmed(slide, x, y) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 0.85, h: 0.26, rectRadius: 0.05, fill: { color: 'FDE8E4' }, line: { color: C.coral, width: 0.75 } });
  slide.addText('未经证实', { x, y, w: 0.85, h: 0.26, align: 'center', valign: 'middle', fontFace: F, fontSize: 9, bold: true, color: 'B4432F', margin: 0 });
}

// 1 封面
{
  const s = pres.addSlide(); s.background = { color: C.navy };
  s.addShape(pres.shapes.OVAL, { x: 6.6, y: -1.2, w: 5, h: 5, fill: { color: C.navy2 }, line: { color: C.navy2 } });
  s.addShape(pres.shapes.OVAL, { x: 7.9, y: 0.6, w: 1.5, h: 1.5, fill: { color: C.cyan }, line: { color: C.cyan } });
  s.addText('AI', { x: 7.9, y: 0.6, w: 1.5, h: 1.5, align: 'center', valign: 'middle', fontFace: 'Arial', fontSize: 40, bold: true, color: C.navy, margin: 0 });
  s.addText('今日AI大事', { x: 0.6, y: 1.7, w: 6.5, h: 0.9, fontFace: F, fontSize: 44, bold: true, color: C.white, margin: 0 });
  s.addText('2026年10月13日 · 全球与中国要闻速览', { x: 0.6, y: 2.65, w: 6.5, h: 0.45, fontFace: F, fontSize: 18, color: C.cyan, margin: 0 });
  s.addText('模型 · 算力 · 资本 · 政策 · 产业 · 社会', { x: 0.6, y: 3.3, w: 6.5, h: 0.35, fontFace: F, fontSize: 13, color: 'A5B4CC', margin: 0 });
  s.addText('资料截至 2026-10-13，综合公开报道整理；标注"未经证实"的条目尚无官方确认', { x: 0.6, y: 4.85, w: 8.8, h: 0.3, fontFace: F, fontSize: 10, color: '7C8BA6', margin: 0 });
  s.addNotes('本简报汇总2026年10月13日前后的AI要闻，信息来自公开媒体报道。');
}

// 2 今日看点：四个大数字
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, '今日看点', '四个数字读懂今天的AI');
  const stats = [
    ['2×', 'Meta Muse Wonder API 定价', '约为主流竞品的两倍'],
    ['$1亿', 'Anthropic 前沿部署工程师计划', '目标2027年底培养1万人'],
    ['2–3年', '英特尔CEO：AI硬件短缺', '将持续的时间'],
    ['17天', '英国AISI前沿模型测试中断', '已于10月11日恢复'],
  ];
  stats.forEach(([n, l, d], i) => {
    const x = 0.5 + i * 2.3, y = 1.6, w = 2.05, h = 2.9;
    card(s, x, y, w, h);
    s.addText(n, { x: x + 0.15, y: y + 0.35, w: w - 0.3, h: 1.0, fontFace: F, fontSize: 38, bold: true, color: C.cyanDk, margin: 0 });
    s.addText(l, { x: x + 0.15, y: y + 1.5, w: w - 0.3, h: 0.8, fontFace: F, fontSize: 13, bold: true, color: C.ink, margin: 0, valign: 'top' });
    s.addText(d, { x: x + 0.15, y: y + 2.2, w: w - 0.3, h: 0.6, fontFace: F, fontSize: 11, color: C.muted, margin: 0, valign: 'top' });
  });
}

// 3 Meta Muse Wonder
{
  const s = pres.addSlide(); s.background = { color: C.white };
  badge(s, 0.5, 0.35, 0.55, '模');
  s.addText('Meta 发布 Muse Wonder：高价冲击前沿', { x: 1.2, y: 0.35, w: 8.3, h: 0.55, fontFace: F, fontSize: 24, bold: true, color: C.ink, margin: 0, valign: 'middle' });
  s.addText(bullets([
    '10月12日由 Meta 超级智能实验室发布 Muse Wonder 与 Muse Wonder Full 两款模型',
    'Meta 称其推理、写作、代码得分接近 Anthropic 顶尖模型；未公布参数量、上下文长度与具体分数',
    '先向付费订阅用户开放，接入个人智能体 Muse；Full 版仅限 Muse Code 订阅',
    'Alexandr Wang："真正的前沿模型，可与世界最佳模型竞争"',
  ], 13), { x: 0.5, y: 1.2, w: 4.6, h: 3.8, valign: 'top', margin: 0 });
  s.addChart(pres.charts.BAR, [
    { name: '输入', labels: ['Muse Wonder', '主流竞品*'], values: [4, 2] },
    { name: '输出', labels: ['Muse Wonder', '主流竞品*'], values: [20, 10] },
  ], {
    x: 5.4, y: 1.15, w: 4.1, h: 3.7, barDir: 'col', barGrouping: 'clustered',
    chartColors: [C.cyan, C.navy], showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 11, dataLabelFormatCode: '$0',
    showTitle: true, title: 'API 价格（美元 / 百万 tokens）', titleFontSize: 12, titleColor: C.ink, titleFontFace: F,
    showLegend: true, legendPos: 'b', legendFontSize: 10, legendFontFace: F,
    catAxisLabelColor: C.muted, catAxisLabelFontFace: F, catAxisLabelFontSize: 11, valAxisHidden: true,
    valGridLine: { style: 'none' }, catGridLine: { style: 'none' },
  });
  source(s, 'IT之家、Dataconomy、AIToolsRecap（10/12–13）。*竞品指 GPT-6.1 Sol 与 Claude Sonnet 5.5，价格据第三方报道');
}

// 4 算力与芯片
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, '算力与芯片：短缺仍是主旋律');
  const items = [
    ['芯', '英特尔：AI硬件短缺还将持续2–3年', 'CEO陈立武在新加坡表示；英特尔Q2数据中心与AI业务营收同比 +59%', false],
    ['微', '微软 Maia 300 自研加速器', '据报道：288GB HBM4、18TB/s，每兆瓦token产出比主流GPU高40%，2027年起规模部署', true],
    ['材', '应用材料：营收翻倍，人员不翻倍', 'CEO Gary Dickerson称借助AI工具提效；硅谷EPIC中心投资50亿美元', false],
    ['光', '联讯仪器：前三季度净利预增约19–21倍', '预计19–21亿元，AI拉动光通信测试需求', false],
  ];
  items.forEach(([ch, h, d, flag], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.5 + col * 4.6, y = 1.3 + row * 1.85, w = 4.4, hh = 1.65;
    card(s, x, y, w, hh);
    badge(s, x + 0.2, y + 0.25, 0.5, ch);
    s.addText(h, { x: x + 0.85, y: y + 0.2, w: w - 1.0, h: 0.55, fontFace: F, fontSize: 13, bold: true, color: C.ink, margin: 0, valign: 'middle' });
    s.addText(d, { x: x + 0.85, y: y + 0.8, w: w - 1.0, h: 0.75, fontFace: F, fontSize: 11, color: C.muted, margin: 0, valign: 'top' });
    if (flag) unconfirmed(s, x + w - 1.0, y + hh - 0.36);
  });
  source(s, 'IT之家、新浪财经、AIToolsRecap（10/12–13）；Maia 300 规格未见微软官方公告');
}

// 5 前沿实验室
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, '前沿实验室：人才、资本与产品取舍');
  // 左：Anthropic 大卡片
  card(s, 0.5, 1.3, 5.2, 2.75);
  badge(s, 0.75, 1.5, 0.55, 'A');
  s.addText('Anthropic', { x: 1.45, y: 1.5, w: 4, h: 0.55, fontFace: F, fontSize: 18, bold: true, color: C.ink, margin: 0, valign: 'middle' });
  s.addText(bullets([
    '投入1亿美元培养"前沿部署工程师"：4天线下培训 + 12周驻场实践，2027年底前目标1万人',
    '与 HCLTech 结成全球顶级合作伙伴，覆盖 Claude、Cowork、Claude Code',
    '本周投资者日引发IPO传闻，报道估值最高约2万亿美元；公司未确认',
  ], 12), { x: 0.75, y: 2.15, w: 4.75, h: 1.75, valign: 'top', margin: 0 });
  unconfirmed(s, 4.65, 3.68);
  // 右：OpenAI
  card(s, 5.95, 1.3, 3.55, 2.75);
  badge(s, 6.2, 1.5, 0.55, 'O');
  s.addText('OpenAI', { x: 6.9, y: 1.5, w: 2.5, h: 0.55, fontFace: F, fontSize: 18, bold: true, color: C.ink, margin: 0, valign: 'middle' });
  s.addText(bullets([
    '据 The Information，正与一家成立数月的初创公司谈判，拟转交已搁置的视频模型 Sora',
    '是否包含模型权重尚不清楚',
  ], 12), { x: 6.2, y: 2.15, w: 3.1, h: 1.75, valign: 'top', margin: 0 });
  card(s, 0.5, 4.25, 9, 0.8, C.navy);
  badge(s, 0.7, 4.4, 0.5, '购');
  s.addText([{ text: '并购动向  ', options: { bold: true, color: C.cyan } }, { text: 'IonQ 拟以至多13亿美元全股票收购 Elisity；亚马逊与 AI 视频公司 Decart 洽谈收购（均据 WSJ）', options: { color: C.white } }], { x: 1.4, y: 4.25, w: 7.9, h: 0.8, fontFace: F, fontSize: 12, margin: 0, valign: 'middle' });
  source(s, 'IT之家、新浪科技、The Information、WSJ、AIToolsRecap（10/11–13）');
}

// 6 政策与安全
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, '政策与安全', '监管恢复与新型攻击并行');
  const rows = [
    ['英', '英国AISI恢复前沿模型测前访问', '9/24起中断17天，10/11解冻；Gemini 4 Argon 已进入评估', C.cyan],
    ['美', '"超级智能"更名行政令余波', '9/29签署，要求联邦机构以 SI 取代 AI；NSF称将调整资助文本用语', C.cyan],
    ['韩', '韩国：AI被用于攻击7家银行', '约6.8万人信息受影响（总统公开警告）', C.coral],
    ['网', 'PoeLLM 挖矿僵尸网络盯上AI服务器', '扫描暴露的 LiteLLM / Ollama，疑利用 CVE-2026-42271（Black Lotus Labs）', C.coral],
  ];
  rows.forEach(([ch, h, d, col], i) => {
    const y = 1.4 + i * 0.92;
    badge(s, 0.5, y, 0.6, ch, col, col === C.coral ? C.white : C.navy);
    s.addText(h, { x: 1.35, y: y - 0.02, w: 8.1, h: 0.34, fontFace: F, fontSize: 14, bold: true, color: C.ink, margin: 0 });
    s.addText(d, { x: 1.35, y: y + 0.33, w: 8.1, h: 0.3, fontFace: F, fontSize: 11, color: C.muted, margin: 0 });
  });
  source(s, 'AISI公告、Startup Fortune、TechRepublic、Quartz、Lumen Black Lotus Labs（10/8–13）');
}

// 7 中国动态
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, '中国：工业AI与具身智能加速落地');
  // 左侧两个大数字
  [['600台', '上海目标：每万名工人机器人数'], ['500家', '上海目标：先进级智能工厂']].forEach(([n, l], i) => {
    const y = 1.3 + i * 1.85;
    card(s, 0.5, y, 3.2, 1.65, C.navy);
    s.addText(n, { x: 0.75, y: y + 0.2, w: 2.8, h: 0.8, fontFace: F, fontSize: 36, bold: true, color: C.cyan, margin: 0 });
    s.addText(l, { x: 0.75, y: y + 1.05, w: 2.8, h: 0.4, fontFace: F, fontSize: 12, color: C.white, margin: 0 });
  });
  card(s, 4.0, 1.3, 5.5, 3.5);
  s.addText(bullets([
    '上海发布新一代智能制造行动方案：4大工程、19项重点任务',
    '第26届工博会10月12日开幕：24个国家和地区、3200+家展商；63所高校带来527个项目',
    '宇树科技王兴兴：具身智能机器人1–2年内可进入工厂',
    '卡奥斯发布工业世界模型与全栈智能体矩阵；2026人工智能产业大会10月14–16日在济南举行',
  ], 13).map((b) => (b.options.paraSpaceAfter = 14, b)), { x: 4.25, y: 1.3, w: 5.05, h: 3.5, valign: 'middle', margin: 0 });
  source(s, '上观新闻、澎湃新闻、经济观察报（10/12–13）');
}

// 8 内容与社会
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, '社会影响：就业暴露与内容可信度');
  s.addChart(pres.charts.BAR, [{ name: '受AI影响岗位比例', labels: ['全球', '发达经济体', '低收入国家'], values: [40, 60, 26] }], {
    x: 0.5, y: 1.25, w: 4.6, h: 3.75, barDir: 'bar', chartColors: [C.cyanDk],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0"%"', dataLabelFontSize: 12,
    showTitle: true, title: 'IMF：AI 影响（暴露）的岗位占比', titleFontSize: 12, titleColor: C.ink, titleFontFace: F,
    showLegend: false, valAxisHidden: true, valAxisMaxVal: 75, valAxisMinVal: 0,
    catAxisLabelColor: C.ink, catAxisLabelFontFace: F, catAxisLabelFontSize: 11, catAxisOrientation: 'maxMin',
    valGridLine: { style: 'none' }, catGridLine: { style: 'none' },
  });
  card(s, 5.4, 1.3, 4.1, 3.7);
  badge(s, 5.65, 1.5, 0.55, '书', C.coral, C.white);
  s.addText('出版业的AI信任危机', { x: 6.35, y: 1.5, w: 3.0, h: 0.55, fontFace: F, fontSize: 15, bold: true, color: C.ink, margin: 0, valign: 'middle' });
  s.addText(bullets([
    'WIRED调查：美国五大出版集团中有3家被指未披露地使用AI',
    '国内一出版社发现书中含AI生成文字，宣布召回销毁并修订',
    '注意：IMF数据衡量的是"暴露度"，并非预测的失业数',
  ], 12), { x: 5.65, y: 2.25, w: 3.65, h: 2.6, valign: 'top', margin: 0 });
  source(s, 'IMF（Georgieva讲话）、WIRED、人民日报客户端（10/13）');
}

// 9 趋势总结
{
  const s = pres.addSlide(); s.background = { color: C.navy };
  s.addText('今天的三个信号', { x: 0.5, y: 0.4, w: 9, h: 0.7, fontFace: F, fontSize: 32, bold: true, color: C.white, margin: 0 });
  const t = [
    ['1', '前沿模型开始"按价值定价"', 'Meta 以竞品两倍价格入场，竞争焦点从价格战转向能力与生态'],
    ['2', '算力瓶颈推动垂直整合', '硬件短缺预期延续，云厂商加码自研芯片，供应链公司业绩高增'],
    ['3', '落地与治理同步加速', '部署人才、工业场景快速扩张；测评、安全与内容披露问题同时升温'],
  ];
  t.forEach(([n, h, d], i) => {
    const x = 0.5 + i * 3.05, y = 1.55, w = 2.85, hh = 3.0;
    card(s, x, y, w, hh, C.navy2);
    badge(s, x + 0.25, y + 0.3, 0.7, n);
    s.addText(h, { x: x + 0.25, y: y + 1.2, w: w - 0.5, h: 0.8, fontFace: F, fontSize: 15, bold: true, color: C.white, margin: 0, valign: 'top' });
    s.addText(d, { x: x + 0.25, y: y + 1.95, w: w - 0.5, h: 0.95, fontFace: F, fontSize: 12, color: 'A5B4CC', margin: 0, valign: 'top' });
  });
}

// 10 来源
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, '来源与说明');
  s.addText(bullets([
    '新浪AI热点小时报（2026-10-13 09时、10时），转引 IT之家、The Information、澎湃新闻、WIRED 等',
    'AIToolsRecap《AI News Today, 13 Oct 2026》，转引 Meta、微软、AISI、WSJ 等',
    'Dataconomy 中文版：Meta 推出 Muse Wonder 和 Muse Wonder Full（10/13）',
    'Startup Fortune：英国AISI恢复前沿模型测试；TechRepublic：Super Intelligence 行政令',
    'Innovation in the News《Tech Tuesday - October 13, 2026》',
  ], 13), { x: 0.5, y: 1.25, w: 9, h: 2.2, valign: 'top', margin: 0 });
  card(s, 0.5, 3.65, 9, 1.05, 'FDF1EE');
  s.addText('可信度说明：多数条目来自二手报道与聚合站。Anthropic IPO 估值、微软 Maia 300 规格尚无官方确认；竞品价格引自第三方。正式引用前请核对原始公告。', {
    x: 0.7, y: 3.75, w: 8.6, h: 0.85, fontFace: F, fontSize: 11, color: '8A3A2B', margin: 0, valign: 'middle' });
}

const out = process.argv[2] || require('path').join(__dirname, 'output', 'AI大事_2026-10-13.pptx');
pres.writeFile({ fileName: out }).then((f) => console.log('wrote', f));
