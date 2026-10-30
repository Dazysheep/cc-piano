# 抖音钢琴下落音符视频

MIDI → 下落音符 + 琴键高亮的钢琴视频（Synthesia 风格），配 FluidSynth 合成的钢琴音频，并输出封面和发布文案。

## cc-piano（软件版）

双击 `启动琴房.bat`（或安装版的「cc-piano」），打开 http://127.0.0.1:8765/ 。左侧导航：

| 页面 | 地址 | 内容 |
|---|---|---|
| 琴房 | `/studio?view=studio` | MIDI → 钢琴下落音符视频（原 `index.html`） |
| 音轨剪辑 | `/tracks` | 音轨模板：选歌（剪映缓存/上传）+ LRC + 封面 + 主题（日落/科技/古典）+ 效果开关 → 成片 + 剪映草稿 |
| 拨片开头 | `/flick` | 拨片开头图库与生成 |
| 发布台 | `/tour` | 一键发布到各平台（停在发布按钮前），独立页面 `web/tour.html`，接口与琴房原发布台相同 |
| 作品集 | `/works` | 半弧形胶片浏览（滚轮/方向键，胶片音效）+ 中央视频与背景联动；也可切到网格（悬停预览、全屏查看） |
| 设置 | `/settings` | 统一设置：外观（深色/浅色/自动、强调色、背景、毛玻璃、动画、文字大小）、作品集、胶片音效、视频展示 |

成片保存位置（设置 → 存储）：默认 `D:\cc-engine\douyin\待上传`（源码版和安装版都存这里）；也可以跟随浏览器的下载文件夹（Edge / Chrome 的下载设置，没有就用 Windows「下载」）下的「琴房Studio」，
也可以自定义；设置存在 `app_settings.json`，由 `piano/storage.py` 统一提供给钢琴、音轨、拨片开头和服务端。原来项目里的「待上传」仍会被读到。

外壳是 `web/app.html`：各页面第一次打开时加载、之后常驻，切换只是显示/隐藏（Ctrl+1~6），切走的页面会暂停动画。
琴房、音轨剪辑、拨片开头用 `web/glass.css`；发布台、作品集、设置和外壳用 `web/ui/`（`ui.css` 类 iOS 样式，
`settings.js` 设置存储与同步，`filmsound.js` WebAudio 合成的胶片音效）。设置存在 localStorage（键 `studio.ui.v1`），
只影响外壳、发布台、作品集和设置页，不改琴房钢琴设置、音轨剪辑和拨片开头。

**打包成安装程序**：`.venv\Scripts\python app\build_app.py`（需要 Inno Setup 6 和 `D:\cc-engine\.tmp\pkg\python-embed.zip`
官方嵌入版 Python 3.13）。产出 `dist\QinfangStudio\`（可直接运行 `cc-piano.exe`）和 `dist\installer\`（安装程序，超过 2GB 分卷）。
安装版 = 启动器 exe（`app/launcher.py`，PyInstaller）+ `runtime\`（嵌入版 Python + venv 全部依赖）+ `douyin\`（项目文件，
不含成片、上传和 `publish/profile` 登录信息）。窗口是 `app/window.py`（pywebview，WebView2 内核）的无边框窗口，左上角红黄绿三点
（`web/ui/winctl.js`）：关闭 / 最小化 / 铺满屏幕可用区域（不盖任务栏）再点还原，按住侧栏顶部拖动；网页设置存在 `uploads/webview`。
pywebview 启动不了时退回 Edge 应用窗口。版本号写在 `app/VERSION`（现在是 2.4.0），打包时进安装包名 `cc-piano_v<版本>_安装程序.exe`
（超过 2GB 分卷，`.exe` 和 `-1.bin`、`-2.bin` 放在同一个文件夹里运行），设置页底部也会显示。

## 琴房（钢琴页面）

双击 `启动琴房.bat`，浏览器会打开 http://127.0.0.1:8765/ ：

1. 把 MIDI 拖进舞台：立即生成试听，空格键播放，下落音符与成片排版一致
2. 填标题、水印，选背景图/视频、背景音和音量，横屏或竖屏
3. 「试渲染 15 秒」先看效果，「生成视频」出完整成片
4. 成片存进 `待上传/<日期>_<标题>/`（video.mp4、cover.jpg、publish.md），同时在剪映里生成可编辑草稿

关闭黑色命令行窗口即停止服务。上传的素材存在 `uploads/`，可随时清空。

### 爆款开头（V 开头）

4 秒开头：左边你的头像唱片（`assets/intro/avatar.jpg`，可在页面里点击更换）× 右边曲子封面唱片，
飞入旋转、音符环绕、中间 × 联动，配曲子里最抓耳的 4 秒（自动在全曲 12%~80% 里找音符最密、最响的一段）。
特效：节拍脉冲 + 波形环、星尘粒子 + 光带、故障风闪烁、胶片漏光 + 颗粒、「嗖 + 咚」转场音效。
有开头时封面自动用开头画面；剪映草稿里开头是最上层「片头」轨道的一段，其余轨道整体后移。
开关与参数在 `piano/config.yaml` 的 `intro` 段；「预览开头」只渲染开头，约半分钟。

### 没有 MIDI：钢琴录音转写

把 mp3/wav 拖到舞台上，会用字节跳动开源的钢琴转写模型转成 MIDI 并直接导入（首次下载约 170MB 模型到 `tools/models/`）。
纯钢琴录音效果最好；带鼓和贝斯的完整编曲会多出杂音符。也可以命令行：`.venv\Scripts\python piano\transcribe.py 录音.mp3`

### 音轨剪辑（tracks/，不走琴房）

编曲软件风格的多轨画面：拨片下滑开头 + 原曲/人声/钢琴/吉他/贝斯/其他 6 轨从右往左滚动（播放头固定），
波形来自 Demucs 6 轨分离（htdemucs_6s），钢琴轨显示转写出的音符，配色取自封面。

```powershell
# 1. 准备工作目录：source.wav（整首）、stems\*.wav（6 轨分离结果）、song.json（start/duration）
.venv\Scripts\python tracks\analyze.py <工作目录>
# 2. 渲染开头 + 正片 + 成片 + 两份剪映草稿（开头单独一份；作品一份，开头/正片/音乐/音效分轨）
.venv\Scripts\python tracks\build.py tracks\songs\one_more_light.json --work <工作目录>
```

新歌推荐用 `prepare.py` 一步准备好工作目录（6 轨分离、歌词、选片段、分析，结果缓存，换音频会重做），
或直接 `build.py --prepare`；网页「音轨剪辑」页就是这样调用的：

```powershell
.venv\Scripts\python tracks\build.py tracks\songs\sacred_play.json --prepare [--preview 10]
```

歌曲 json 的可选效果（`tracks/songs/sacred_play.json` 是完整示例）：

| 键 | 作用 |
|---|---|
| `theme` | `sunset`（One More Light 原版）/ `tech` / `classical`，配色字体在 `tracks/themes.py` |
| `backdrop` | 封面虚化做背景，轨道面板变毛玻璃 |
| `grain` | 胶片颗粒强度（0.05~0.1） |
| `fireworks` | 副歌放烟花，每小节一束、每束换一个色系（`stage.Fireworks`） |
| `lyrics` + `lrc` | 底部歌词（逐词高亮）+ 左下角唱歌的像素 Claude Code 小人：歌词越长小人越靠左，换句时跳舞步换位置（`stage.Singer`）；`lyrics_zh` 是每句的中文翻译 |
| `start: "auto"` | 自动选片段：副歌最多、开头几秒就进副歌、不在句子中间截断（需要 `lrc`） |
| `loop` | 首尾循环：开头第一张卡片就是主图，结尾主图从标题栏飞回中央，最后一帧 = 第一帧 |

歌词：faster-whisper（`tools/models/whisper-medium`，CPU int8）识别分离出的人声，逐词时间；文字以 LRC 为准修正听错的词，
LRC 和音频的整体时间差自动估计（`tracks/lyrics.py`）。副歌 = LRC 里重复次数最多的那几句。主题预览图：`tracks/theme_previews.py`。

开头与音轨之间是水墨转场：旧画面虚化压暗，墨从主图背后和四周洇开，墨里透出由虚到实的编曲界面，主图同时飞进标题栏小图（`daw.py` 的 `ENTRY`、`_build_ink`）。
滑动音效由 `tracks/sfx.py` 合成（卡片拨动声 + 风声 + 落定闷响 + 转场「呼」声），单独保存为 `intro_sfx.wav`，草稿里是独立的「音效」轨，可以自己剪；音量在 `build.py` 的 `SFX_GAIN`。

歌曲 json 里 `"intro_from_library": true` 时，开头直接用下面「拨片开头」图库的图片和顺序；
否则用 `final_image`（最后停留的图）+ `images`（依次滑过的其他图，路径相对 json）。

### 模板库、评论故事、CC 小人读评论、剪辑页

- **模板库**（`tracks/templates/<名称>/v<N>.json`，`tracks/template_lib.py`）：模板只存「怎么做」，歌曲 json 写 `"template": "daw@v4"`
  引用（歌曲字段优先）；改进时另存新版本，旧版本不覆盖。v1 原版效果；v2 竖屏实验；v3 横屏 + 约 60 秒卡点截取（起止吸附重拍，
  `tracks/clip.py`）+ 开头直接进高潮 + 重拍推近；v4 = v3 + 开头不写任何文字（`intro_text: false`）。没有 template 字段的旧歌出片不变。
- **拨片开头指定主图**：`intro_from_library: true` + `intro_final: "027.jpg"`（图库里的文件名）。每日制作会按「歌名 - 歌手」自动匹配图库。
- **竖屏**：模板 `vertical: true`（`daw.set_canvas`），上半屏大封面，下半屏多轨。
- **评论故事**：歌曲 json 的 `story`（幕 → 卡片 `{text, track, solo, mood}` + `finale`），评论卡片从对应音轨浮现，卡点在重拍上
  （`stage.CommentStory`、`build.schedule_story`）。有 story 时画面底部是舞台（`tracks/comment_scene.py`）：「网易云评论」文件夹
  + CC 小人走过去、打开、抽出评论、读、抛起（纸变成卡片飞出），再按 `mood` 表达情绪；尾声卡片飞回文件夹。
- **CC 小人动画库**（`tracks/clawd_anim.py`）：带立体感的像素小人（顶面/侧面厚度、挤压拉伸、景深、软阴影），17 段动画
  （idle/walk/turn_around/approach/open_folder/pull_card/read/toss + 9 种情绪 sad/lonely/happy/love/hope/laugh/nostalgic/angry/shy）。
  每段单独导出在 `assets/clawd/animations/`（透明 .webm、.gif、.png、manifest.json、预览页 index.html）：
  `.venv\Scripts\python tracks\clawd_anim.py --export [片段名…]`。
- **剪辑页**（左侧导航「剪辑」，Ctrl 7）：嵌入 OpenFilm Studio（`editor/`，`npm i openfilm`，MIT）。音轨成片出片时自动在成片文件夹里
  生成 `film/film.html` 工程（`tracks/openfilm_export.py`，素材硬链接）。所有剪辑步骤自动记录在 `film/.cc-history/`
  （`editor/journal.py`，每秒检查，右侧列表可回到任何一步，恢复本身也记一步）。OpenFilm 的数据、工程、浏览器都放在 `editor/` 下，
  ffmpeg/ffprobe 用 `tools/ffmpeg/`（`editor/studio.py` 设置环境变量），不写 C 盘。
  - 有评论故事的歌，出片时同一帧同时输出三份：成片用的 `main.mp4`（带评论，和以前完全一样）、不带评论的 `main_clean.mp4`、
    只有评论卡片和读评论小人的透明层 `comments.webm`（VP9 透明通道；`build.matte` 把叠加层分别画在黑底和白底上，
    两张的差就是透明度，误差不超过 2/255）。剪辑工程用后两个，评论层在最上面一条轨，可以单独挪动、裁剪、隐藏。
    不需要时 `build.py --no-layers`。
  - 首页（开端页）有「剪辑」卡片，点了直接进剪辑页。外壳会在后台提前加载各页面，作品集隐藏时不会自动播放（以前会在点「剪辑」时突然冒出声音，再加上剪辑器的声音就成了两路）。
  - 两侧栏可以收起（打开工程后左栏自动收窄）；切到别的页面时剪辑器会先卸载（它在另一个端口，没法从外面暂停），回来再载入，
    避免剪辑器和别的页面同时出声。
  - 右侧「发布用哪个版本」：在剪辑器里导出后（文件在 `editor/exports/`，以工程标题开头），点「发布用它」会复制成
    成片文件夹里的 `video_edited.mp4`，发布台预览和发布（`publish/publisher.py`）都优先用它；「改回」删掉它，用回原成片。
- **两人模式（模板 daw@v5，`cast: "duo"`）**：两个 Claude 小人，比原来小（像素格 4，舞台带 170）。
  - 女生（`clawd_anim.FEMALE`：粉色蝴蝶结、睫毛、蓝眼睛、腮红）在左下角唱歌（`tracks/duo_scene.py` 的 `SingerGirl`）：
    不转身，原地随人声张嘴、按拍摇头、唱到后半句闭眼享受、副歌重拍踮脚、唱得响举手，音符一直飘；歌词（逐词点亮 + 中文翻译）
    跟在她右边，最右到画面中线附近。
  - 男生（原来的样子）在右边读网易云评论；评论卡片写了 `vision` 时，读完头顶冒三个小圆点，展开成想象云朵（只有白色描边，
    里面透明），云里浮现 `tracks/visions.py` 的画面（14 个，预览 `assets/clawd/visions/overview.jpg`），一直飘到下一条评论
    抛出来之前；卡片会让开云朵的位置。
  - 结尾两人蹦跳着走到画面中间，一起鞠躬。开头拨片动画恢复歌名和歌手（`intro_text: true`）。
  - 动画库分角色存放：`assets/clawd/animations/male/`、`female/`（各自 manifest.json，总预览页 `animations/index.html`）。
- **开头 / 结尾小剧场（模板 daw@v6）**：
  - 开头「加班的夜」（`tracks/opening.py`，脚本 `tracks/templates/opening/office/v<N>.json`）：夜空半月 + 最戳人的评论浮现、歌名在左上角
    → 镜头下摇进高楼办公室，男生读评论（读到那条时评论浮起 + 想象云朵）→ 老板来电（来电卡片里是老板，乱码气泡，他扭头把手机拿远）
    → 女朋友来电（红烧肉）→ 他哭着拉下老虎扭蛋机的摇杆（v2；v1 是从右边拉镜头），掉出一颗扭蛋 → 拨片动画浮现在左边（半透明深色底、不用图片虚化背景，不挡画面）→ 停在封面后封面移到画面中间，歌名从封面后面移到下面；他收拾东西走出去、关灯。音效：铃声、电话里的乱码声、挂断音。
    开头长度按模板的 intro 秒数（从第一个重拍起取整小节），脚本里的 beats 是各段占的比例。
  - 结尾「回家」（`tracks/ending.py`，脚本 `tracks/templates/ending/home/v<N>.json`）：画面中间浮现小窗——回家、餐桌聊天、
    女生用网易云放这首歌（手机上方浮现封面小窗）、两人鞠躬、镜头推近直到消失。舞台上的两个小人在小窗出现前走出画面。
  - 共用道具在 `tracks/scenes.py`（半月、高楼、办公桌、老虎扭蛋机、来电卡片、对话气泡、红烧肉、网易云小窗……）。
  - v6 只显示 4 条音轨（`tracks_keep`），约 84 秒。
- **动画库页（左侧导航「动画库」，Ctrl 8，`web/anim.html` + `tracks/anim_lib.py`）**：
  - 男生表情、女生表情、想象画面：每个都有沿人物边缘裁好的透明动图（.webp），可以下载；开头 / 结尾动画有预览视频（`assets/scenes/`）。
  - 每个表情、开头、结尾都有一个聊天框：用一句话说想怎么改，发给你在「API 设置」里配的大模型（OpenAI 兼容接口，密钥只存在用户环境变量
    `CC_PIANO_LLM_KEY`），模型给出新的 JSON 方案，页面检查过字段后由你决定「采用」——存成新版本（旧版本保留）并生成预览。
  - 表情变体存在 `assets/clawd/variants/<角色>/<片段>/v<N>.json`（在原片段上调速度、幅度、表情、手势、特效）。
- **贴纯文本歌词**：歌曲 json 的 `lyrics_text`（`tracks/songs/<歌>.lyrics.txt`，原文一行、翻译一行），Whisper 听时间、文字以贴的为准
  （`lyrics.parse_plain` / `align_text` / `run_text`）。音轨剪辑页「歌曲」卡片可以直接粘贴；每日制作时，录屏之后在飞书群里
  发的文字（至少 4 行英文）会自动当成这首歌的歌词。
- **音轨剪辑页的模板**（「效果」卡片顶部）：下拉选模板的任一版本，效果开关显示「模板 + 这首歌改过的」实际值，改过的开关标「已改」；
  保存时和模板一样的效果不写进歌曲（模板说了算）。「当前效果另存为新版本」生成下一版（旧版本不覆盖，会问这一版改了什么）；
  「用这个模板批量生成…」勾选几首歌，改用这个模板、片段按模板时长重选、依次排队出片。

### 拨片开头（一键生成，双击 `启动拨片开头.bat`，或琴房顶部「拨片开头」）

网页地址 http://127.0.0.1:8765/flick 。
- 把图片拖进页面。音乐播放器截图会自动裁出专辑封面，普通图片会裁成正方形，重复的图片自动跳过。
- 拖动卡片调整顺序，可以改名、删除，点 ★ 设为最后停留的图（默认是最后一张）。
- 页面上方的预览会实时播放滑动效果。
- 填好标题和歌手（可留空），选横屏或竖屏，点「生成开头」，结果保存在 `待上传/开头_<日期>_<标题>/intro.mp4`，并另外生成剪映草稿「拨片开头_<标题>_<时间>」。

图库存放在 `flick/library/`（`library.json` 记录顺序和名称）。命令行用法：
`.venv\Scripts\python tracks\flick_render.py --title 歌名 --artist 歌手 [--seconds 4] [--vertical] [--no-draft]`。
生成的 intro.mp4 已带滑动音效，音效另存为 intro_sfx.wav，剪映草稿里开头和音效分两条轨道。渲染带运动模糊，4 秒开头大约需要 5–7 分钟。

### 五线谱 PDF/图片 → MIDI

```powershell
.venv\Scripts\python piano\score2midi.py 乐谱.pdf --out songs\曲名.mid --bpm 92
```

用 Audiveris（解压在 `tools/audiveris`，不装进系统）识别，music21 导出 MIDI。识别做不到 100%：
脚本会列出拍数不对的小节，请对照原谱检查；谱号切换处、长音符/连音、升降号是最常见的错误。
`songs/Mitsuha_Theme.mid` 就是这样生成后逐小节人工修正的（修正脚本 `songs/sources/fix_mitsuha.py`，原始识别结果在同目录）。

开头功能目前关闭（`piano/config.yaml` 里 `intro.enabled: false`，代码保留，改回 true 即可恢复）。

### 发布台（一键发布到抖音、小红书、B 站、视频号、快手）

页面底部的「发布台」：选一条成片，勾选平台，按需修改每个平台的标题/文案/话题（有字数提示），点「开始发布」：

- 抖音、小红书、视频号、快手用竖屏版，没有时先自动生成 `video_vertical.mp4`（依据成片文件夹里的 `job.json`）；B 站用横屏版
- 打开一个专用 Edge 窗口，每个平台一个标签页：上传视频、填好内容，**停在「发布」按钮前**，由你检查后手动点发布
- 第一次每个平台需要扫码登录，登录状态保存在 `publish/profile/`（只在本机）
- 封面、B 站分区等没法可靠自动选择的项目，会在发布台里标出来请你手动处理
- 平台改版导致某项没填上时会显示「需要手动填写」；选择器集中在 `publish/platforms.py`，改版后在那里补

## 快速开始

```powershell
cd D:\cc-engine\douyin
# 1. 把 MIDI 放进 songs/，可选同名 .yaml 写标题等（见 songs/example.yaml）
# 2. 先渲染 15 秒预览看效果
.venv\Scripts\python piano\render.py songs\lawrence.mid --preview 15
# 3. 渲染完整版
.venv\Scripts\python piano\render.py songs\lawrence.mid
# 竖屏版 / 批量
.venv\Scripts\python piano\render.py songs\lawrence.mid --vertical
.venv\Scripts\python piano\render.py songs\*.mid
```

输出在 `output/<曲名>/`：`video.mp4`（或 `preview.mp4`）、`cover.jpg`、`publish.md`。

## 剪映草稿模式

```powershell
.venv\Scripts\python piano\render.py songs\lawrence.mid --jianying
```

直接在剪映草稿列表里生成一个工程（重启剪映或回到首页刷新即可看到），轨道从下到上：

| 轨道 | 内容 | 在剪映里可以 |
|---|---|---|
| 背景 | 图片/视频（yaml 的 `background`），默认深色渐变 | 替换素材、加滤镜 |
| 音符 | 黑底音符动画，混合模式「滤色」 | 调透明度、加特效 |
| 琴键 | 琴键条，已放到画面底部 | 移动、缩放 |
| 标题 / 副标题 / 水印 | 剪映文字（Cinzel / 思源宋体） | 直接改字、字体、位置 |
| 钢琴 / 背景音 | 合成钢琴声；背景音循环铺满、首尾淡入淡出 | 调音量 |

素材文件保存在 `output/<曲名>/jianying/`，草稿引用的就是这里的文件，**导出成片前不要删除或移动**。
同名草稿会被覆盖。默认值（水印、背景音、音量、字体、字号）在 `piano/config.yaml` 的 `jianying` 段。

常用参数：`--title` / `--subtitle` / `--corner-text` 覆盖 yaml；`--fps 30` 渲染时间减半；`--workers N` 并行进程数（默认 4）。

## 速度与内存

- 1080p60 约 35–40 帧/秒（4 进程），5 分钟的曲子大约 8 分钟。
- 每个进程连同 x264 编码约占 400–500MB 内存。内存紧张时用 `--workers 2`；偶发失败的片段会自动重试。

## 调整外观

`piano/config.yaml`：音符颜色/发光（`notes`）、下落速度（`lookahead`）、左右手分色（`color_by_hand`）、琴键位置、背景色或背景图、字体、音频响度（默认 -14 LUFS）。

## 目录

| 路径 | 说明 |
|---|---|
| `web/server.py` / `web/index.html` | 琴房网页工作台（标准库 HTTP 服务 + 单文件前端，渲染任务串行排队） |
| `piano/render.py` | 入口：解析 MIDI → 合成音频 → 多进程渲染音符层/琴键层 → ffmpeg 合成成片 → 剪映草稿 → 封面/文案 |
| `piano/midi_notes.py` | MIDI 解析（速度变化、多轨识别左右手） |
| `piano/keyboard.py` / `frames.py` / `overlay.py` | 琴键、逐帧绘制、背景与文字 |
| `piano/audio.py` | FluidSynth 渲染 + 两遍响度归一化 + ffmpeg 合成 |
| `piano/jianying.py` | 生成剪映草稿（pyJianYingDraft），先写到 `output/<曲名>/draft/` 再用 robocopy 复制进剪映目录（商店版 Python 不能直接写 AppData） |
| `tools/` | FluidSynth 2.6.1、GeneralUser GS 音色库（换更好的钢琴 sf2 改 `audio.soundfont`） |
| `analytics/report.py` | 创作者中心导出数据 → HTML 报表 |

## 注意

- 他人作品（如坂本龙一的曲子）的改编演奏涉及音乐版权，发布前确认 MIDI 来源与平台规则。

