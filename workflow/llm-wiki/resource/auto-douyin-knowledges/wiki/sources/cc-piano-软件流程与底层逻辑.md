---
type: source
title: "cc-piano：软件流程、代码结构与底层逻辑"
created: 2026-10-24
updated: 2026-10-24
tags: [cc-piano, 钢琴视频, 渲染管线, 抖音短视频, 源码分析]
related: [cc-piano, midi到下落音符视频渲染管线, 逐帧绘制坐标与特效模型, 任务队列与子进程进度协议, 剪映草稿生成, 半自动多平台发布, fluidsynth, demucs, faster-whisper, pyjianyingdraft, cc-piano-5秒预览试跑, cc-piano-网页接口冒烟测试, cc-piano未试跑模块是否可用]
sources: ["cc-piano-软件流程与底层逻辑.md"]
authors: []
year: 2026
url: ""
venue: ""
---

# cc-piano：软件流程、代码结构与底层逻辑

## 概述

本文档整理于 2026-10-24，针对 cc-piano（中文名「琴房 Studio」）版本 2.4.0（`douyin/app/VERSION`），项目位置 `D:\cc-engine\douyin\`。内容基于源码阅读与当日实际试跑，系统描述了这款本地运行的抖音短视频制作软件的架构、渲染管线、逐帧绘制算法、目录结构、性能数据与试跑记录。

主线功能是 **MIDI → Synthesia 风格的钢琴下落音符视频**（下落音符 + 琴键高亮 + FluidSynth 合成的钢琴声），同时输出封面、发布文案，并在剪映里生成可继续编辑的草稿。围绕主线还有音轨剪辑、拨片开头、发布台、作品集与设置等模块。

## 整体架构

```
cc-piano.exe（app/launcher.py，PyInstaller）
  └─ 用内置 Python 后台启动 web/server.py（标准库 ThreadingHTTPServer，仅监听 127.0.0.1:8765）
       ├─ 前端：web/app.html 外壳 + 各页面（单文件 HTML，无前端构建）
       ├─ 任务队列 job_queue（渲染/转写/音轨/拨片开头，串行执行，一次一个）
       │    └─ 每个任务 = 一个子进程：piano/render.py、tracks/build.py、tracks/flick_render.py、piano/transcribe.py
       └─ 发布队列 publish_queue（一次一个 Edge 发布窗口）→ publish/publisher.py
  └─ 窗口：app/window.py（pywebview / WebView2 无边框窗口），失败时退回 Edge 应用模式窗口
```

- 源码版入口：双击 `douyin\启动琴房.bat`（即 `.venv\Scripts\python.exe web\server.py`），浏览器打开 http://127.0.0.1:8765/ 。
- 端口可用环境变量 `QINFANG_PORT` 修改；端口已被占用时，server 认为琴房已在运行，直接打开页面。
- 安装版 = 启动器 exe + `runtime\`（官方嵌入版 Python 3.13 + 全部依赖）+ `douyin\` 项目文件。启动器轮询 `/api/health` 等待服务就绪，端口被占用会自动换端口，窗口关掉后服务一起退出。打包脚本 `app/build_app.py`（Inno Setup 6），超过 2GB 分卷；绝不打包 `publish/profile`（平台登录信息）。

### 页面结构

外壳左侧导航，Ctrl+1~6 切换，页面首次打开后常驻、切走时暂停动画。

| 页面 | 地址 | 作用 | 样式 |
|---|---|---|---|
| 琴房 | `/studio` | MIDI → 钢琴视频 | `web/glass.css`（受保护，不改 UI 和逻辑） |
| 音轨剪辑 | `/tracks` | 多轨 DAW 风格视频 + 歌词 | `glass.css`（受保护） |
| 拨片开头 | `/flick` | 图库 + 拨片下滑片头 | `glass.css`（受保护） |
| 发布台 | `/tour` | 一键发布 | `web/ui/` |
| 作品集 | `/works` | 半弧形胶片浏览成片 | `web/ui/` |
| 设置 | `/settings` | 外观、存储位置、音效等 | `web/ui/` |

## 主流程：琴房（MIDI → 成片）

用户操作：把 MIDI 拖进舞台 → 立即试听（空格播放）→ 填标题/水印、选背景图或视频、背景音、横竖屏 → 「试渲染 15 秒」看效果 → 「生成视频」。没有 MIDI 时可拖 mp3/wav，用字节跳动开源的钢琴转写模型转成 MIDI；有五线谱 PDF 时可用 `piano/score2midi.py`（Audiveris + music21）。

后台调用链：网页 `POST /api/render` → 任务进队列 → 参数写成 `uploads/jobs/<id>.json` → 子进程 `piano/render.py --job <json> --json-progress` → 子进程每行输出 `@@{json}` 进度，server 解析后供网页轮询 `/api/jobs/<id>`。

`render.py` 的 `render()` 按顺序执行 10 步：

1. **读配置和元数据**：`piano/config.yaml`（画面、布局、音符颜色、特效、音频、剪映默认值）+ 曲子同名 `.yaml`（标题、副标题、水印、背景、发布标题/话题等），命令行和网页参数优先。
2. **解析 MIDI**（`piano/midi_notes.py`）：建立速度变化表把 tick 换算成秒；多轨时平均音高最高的轨算右手，单轨按中央 C（60）分左右手；每个音符最短 0.05 秒。
3. **合成钢琴音频**（`piano/audio.py`）：FluidSynth 2.6.1 + GeneralUser GS 音色库渲染 wav，再用 ffmpeg loudnorm **两遍**归一化到 -14 LUFS（短曲单遍不准），48kHz。
4. **（可选）爆款开头**（`piano/intro.py`）：头像唱片 × 曲子封面唱片，配全曲 12%~80% 里音符最密最响的 4 秒。目前在 `config.yaml` 里 `intro.enabled: false` 关闭，代码保留。
5. **多进程渲染画面**：按 10 秒一段切片，`multiprocessing.Pool`（默认 4 进程）并行；每段同时输出两个图层视频：`notes`（黑底下落音符）和 `keys`（琴键条），每层通过 imageio-ffmpeg 管道送进 libx264。失败的片段自动重试一次（多为内存紧张）。片段用 ffmpeg concat 无损拼接成 `notes.mp4`、`keys.mp4`。
6. **背景与文字**：没指定背景时生成深色渐变；文字层 `text.png`（标题小型大写字母风格 + 中文微软雅黑）和蒙版 `scrim.png`。
7. **ffmpeg 一次合成成片**（`audio.compose`）：背景（缩放裁切、按 `bg_dim` 压暗）→ 音符层用 **screen（滤色）混合** → 叠琴键条 → 叠文字 → 首 0.8 秒淡入、尾 1.5 秒淡出；音频：钢琴声延后 `lead_in` 3 秒，有背景音时循环铺满、淡入淡出后混音再限幅。有开头时开头和正片在同一次编码里拼接。
8. **封面**：取全曲约 1/3 处的一帧（有开头时用开头画面）。
9. **剪映草稿**（`piano/jianying.py`，pyJianYingDraft）：轨道从下到上：背景、音符（滤色）、琴键、蒙版、片头、标题、副标题、水印、钢琴、背景音。先写到 `output/<曲名>/draft/`，再用 robocopy 镜像进剪映草稿目录（商店版 Python 不能直接写 AppData）。草稿引用 `output/<曲名>/<时间戳>/` 里的素材，**导出前不能删**。
10. **交付**：`待上传/<日期时间>_<标题>/` 下 `video.mp4`、`cover.jpg`、`publish.md`（标题+文案+话题）和 `job.json`（生成参数，发布时据此补渲染竖屏版）。预览模式只写 `output/<曲名>/preview.mp4`，不进待上传、不生成草稿。

成片保存位置由 `piano/storage.py` 统一决定（设置 → 存储）：默认 `D:\cc-engine\douyin\待上传`，也可跟随浏览器下载文件夹下的「琴房Studio」或自定义，设置存在 `douyin/app_settings.json`。

## 逐帧绘制的底层逻辑（`piano/frames.py` 的 `Renderer`）

- **坐标**：琴键顶边 `kb_y` 以上是下落区；音符速度 = `kb_y / lookahead`（默认 2.6 秒从顶部落到琴键）。t 时刻某音符底边 y = `kb_y - (start - t) × speed`，顶边按 end 计算，画成圆角矩形。
- **按下判定**：`start <= t < end` 的音符对应琴键高亮（白键/黑键用预先算好的标签蒙版 `kb.labels` 一次性替换颜色）。
- **琴键尺寸**：高度不超过真实比例（白键长约为宽的 6.4 倍）；`key_range: auto` 时按曲子音域裁剪琴键，竖屏默认用 auto。
- **发光**：音符先画成灰度蒙版，缩到 1/4 分辨率做高斯模糊、着色后放大叠加（为速度全部用 Pillow uint8 运算，numpy 只算蒙版）。
- **特效**：击键闪光（琴键顶部的椭圆高斯光斑，随时间衰减）、击键溅起的光点（带重力的粒子）、刚按下的琴键上一道亮带从上往下扫过、琴键顶部亮线流光。
- **标题保护**：音符在标题区内渐隐（`note_visibility` 蒙版），保证标题不被遮挡。
- 竖屏（1080×1920）时琴键底边上移到 0.82，避开抖音底部文案区。

## 其他流程

- **音轨剪辑**（`tracks/`）：Demucs `htdemucs_6s` 分离 6 轨 → 波形从右往左滚动（播放头固定），钢琴轨显示转写音符，配色取自封面；主题 sunset / tech / classical（`tracks/themes.py`），可选封面虚化背景、胶片颗粒、副歌烟花、逐词高亮歌词 + 唱歌的像素小人、首尾循环。歌词用 faster-whisper（`tools/models/whisper-medium`，CPU int8）识别分离出的人声，再以 LRC 文本为准纠错。`tracks/prepare.py` 一步准备（分离/歌词/选片段/分析，结果缓存），网页调用 `tracks/build.py <song.json> --prepare`。
- **拨片开头**（`/flick`，`tracks/flick_render.py`）：图库 `douyin/flick/library/`（`library.json` 记顺序和名称），播放器截图自动裁出专辑封面（`tracks/cover_crop.py`）；生成 `待上传/开头_<日期>_<标题>/intro.mp4` + 单独的音效轨 + 剪映草稿。带运动模糊，4 秒开头约 5–7 分钟。
- **发布台**（`publish/publisher.py`、`publish/platforms.py`）：抖音、小红书、B 站、视频号、快手。专用 Edge 窗口每平台一个标签页，上传视频、填标题文案话题，**停在「发布」按钮前**由人确认；首次需扫码登录，登录状态在 `publish/profile/`（只在本机）。B 站用横屏，其余用竖屏（没有就按 `job.json` 自动补渲染）。平台改版导致填不上时显示「需要手动填写」，选择器集中在 `platforms.py`。

## 目录速查

| 路径 | 内容 |
|---|---|
| `piano/` | 钢琴视频核心：render、midi_notes、frames、keyboard、overlay、audio、jianying、intro、transcribe、score2midi、storage、config.yaml |
| `web/` | server.py（793 行，全部 HTTP 接口和任务队列）+ 各页面 HTML，`web/ui/` 新样式 |
| `tracks/` | 音轨剪辑与拨片开头 |
| `publish/` | 发布自动化 |
| `app/` | 启动器、窗口、打包、图标、VERSION |
| `songs/` | MIDI 曲库 + 同名 yaml（`example.yaml` 是模板） |
| `tools/` | FluidSynth、音色库、Audiveris、模型（钢琴转写、whisper） |
| `output/` | 中间素材（剪映草稿引用，勿删） |
| `待上传/` | 成片 |
| `uploads/` | 网页上传的素材和任务 json，可清空 |
| `analytics/report.py` | 创作者中心导出数据 → HTML 报表 |

## 性能与注意事项

- 1080p60 约 35–40 帧/秒（4 进程），5 分钟曲子约 8 分钟；每进程连同 x264 编码约占 400–600MB 内存，内存紧时 `--workers 2`。
- `--fps 30` 渲染时间减半。
- 改编他人作品涉及音乐版权，发布前确认 MIDI 来源与平台规则。

## 试跑记录（2026-10-24）

1. 命令行渲染 5 秒预览：`.venv\Scripts\python piano\render.py songs\TRASH_Patience.mid --preview 5 --no-draft --workers 2`
   - 535 个音符，加前后留白共 11 秒、660 帧；钢琴音频 9 秒完成，画面 36 秒完成，总耗时 52 秒（2 进程）。
   - 产物 `output/TRASH_Patience/preview.mp4`：1920×1080、60fps、H.264 + AAC 48kHz 立体声，11.00 秒，约 1.1MB；中间素材 notes.mp4、keys.mp4、piano.wav、text.png、scrim.png、background_default.jpg。
   - 抽帧检查：标题「Patience / TRA$H」、下落音符发光、琴键高亮、击键光点、右下角水印「@谬紫克！」均正常。详见 [[cc-piano-5秒预览试跑]]。
2. 网页服务：在测试端口 8799 临时启动 `web/server.py --no-browser`
   - `/api/health` 返回 ok；`/api/version` 返回 2.4.0；`/api/songs` 列出 Mitsuha_Theme 和 TRASH_Patience 两首；
   - `/`、`/studio`、`/tracks`、`/flick`、`/tour`、`/works`、`/settings` 均返回 200。详见 [[cc-piano-网页接口冒烟测试]]。
3. 未试跑的部分：完整成片 + 剪映草稿、音轨剪辑、拨片开头、录音转写、发布台（会真实打开平台页面或耗时较长）。跟踪见 [[cc-piano未试跑模块是否可用]]。

## 证据等级与内部张力

- 第 3–5 节的流程描述主要来自源码阅读，第 8 节为实际试跑，二者证据等级不同，不应混为一谈。
- 文档称 `intro.enabled: false` 关闭爆款开头，但渲染流程第 4 步与剪映轨道仍保留片头逻辑，属「代码保留、功能关闭」状态。
- 性能数据（35–40 帧/秒）未说明硬件配置与曲目，跨环境复用需谨慎。

## 与其他页面的关系

- 核心主体见 [[cc-piano]]；渲染链路见 [[midi到下落音符视频渲染管线]]；逐帧算法见 [[逐帧绘制坐标与特效模型]]；调度机制见 [[任务队列与子进程进度协议]]；剪映输出见 [[剪映草稿生成]]；发布见 [[半自动多平台发布]]。
- 关键外部依赖：[[fluidsynth]]、[[demucs]]、[[faster-whisper]]、[[pyjianyingdraft]]。
- 试跑方法（命令行预览 + 网页接口冒烟测试）与 [[环境与依赖审查方法]] 在方法论上同源。