# cc-piano

抖音「**cc的音乐引擎**」像素小人钢琴视频全套工具链。

从一段钢琴录屏出发，自动完成：AI 编剧 → 动画渲染 → 分层剪辑 → 定时发布 → 数据复盘，每天一条视频。

## 功能一览

| 模块 | 说明 |
|------|------|
| **琴房 Web UI** | 本地 Web 应用，集成编剧、剪辑、动画库、发布台等所有功能 |
| **音轨剪辑** | MIDI 解析 → 模板化视频生成，支持竖屏/横屏、节拍吸附、歌词同步 |
| **AI 编剧** | DeepSeek/Claude 根据歌词+旋律+网易云评论自动编写故事脚本 |
| **手绘动画** | p5.brush 水彩风格像素小人动画引擎，每首歌独立手绘场景 |
| **歌词动画** | 手绘风全曲歌词 MV，分层渲染+OpenFilm 可编辑交付 |
| **3D 建模** | Blender 集成（本地浮雕 / 云端 Hyper3D），MCP 驱动 |
| **拨片开头** | 一键生成吉他拨片风格的视频开场动画 |
| **运营自动化** | 每日制作 → 数据报表 → 飞书通知 → 定时发布，全链路自动化 |
| **知识库** | LLM Wiki 集成，自动维护歌曲档案、故事线台账、动画使用台账 |

## 项目结构

```
cc-piano/
├── douyin/                     # 核心项目
│   ├── web/                    # 琴房 Web UI（13 个页面）
│   ├── tracks/                 # 音轨剪辑引擎（31 个脚本）
│   ├── piano/                  # MIDI 解析与钢琴渲染
│   ├── handdrawn/              # 手绘动画引擎（p5.brush）
│   ├── cinematic/              # Story-MV 3D 场景（three.js）
│   ├── flick/                  # 拨片开头工具
│   ├── blender3d/              # Blender 3D 建模集成
│   ├── publish/                # 抖音自动发布
│   ├── data/                   # SQLite 数据库（db.py）
│   └── app/                    # 桌面应用打包（Inno Setup）
├── workflow/                   # 运营自动化
│   ├── daily/                  # 每日任务（制作/报表/发布）
│   ├── kb/                     # 知识库整理（DeepSeek）
│   └── llm-wiki/               # LLM Wiki 集成
├── feishu/                     # 飞书集成（lark-cli）
├── ppt/                        # 周报 PPT 生成
└── .claude/                    # Claude Code 技能和钩子
```

## 琴房 Web UI

本地启动后通过浏览器访问 `http://127.0.0.1:8765`，左侧导航栏包含：

| 页面 | 快捷键 | 功能 |
|------|--------|------|
| 琴房 `/studio` | — | 钢琴视频预览和渲染 |
| 音轨剪辑 `/tracks` | — | 模板化视频生成 |
| 拨片开头 `/flick` | — | 吉他拨片开场动画 |
| 编剧 `/writer` | Ctrl+0 | AI 编写故事脚本 |
| 分段编辑 `/sections` | Ctrl+9 | 逐段预览和 AI 修改 |
| 动画库 `/anim` | Ctrl+8 | 浏览/编辑像素小人动画 |
| 剪辑 `/edit` | — | OpenFilm Studio 嵌入 |
| 发布台 `/tour` | — | 抖音发布管理 |
| 作品集 `/works` | — | 已发布作品管理 |
| 3D 建模 `/model3d` | — | Blender 3D 模型库 |
| 设置 `/settings` | — | 侧边栏/外观/流畅模式 |

## 环境要求

- **Python 3.13+**（推荐使用 [uv](https://github.com/astral-sh/uv) 管理）
- **Node.js 18+**
- **Windows 10/11**（依赖 Windows UI Automation）
- **FFmpeg**（放在 `douyin/tools/ffmpeg/` 或系统 PATH）
- **Edge 浏览器**（用于无头渲染和抖音发布）

可选：
- **Blender 4.5 LTS**（3D 建模功能，放在 `douyin/tools/blender/`）
- **faster-whisper medium 模型**（歌词识别，放在 `douyin/tools/models/whisper-medium/`）

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/Dazysheep/cc-piano.git
cd cc-piano

# 2. 创建 Python 虚拟环境并安装依赖
cd douyin
uv venv .venv
.venv\Scripts\activate
uv pip install -r requirements.txt    # 如果有的话
cd ..

# 3. 复制配置模板
copy .mcp.example.json .mcp.json
copy workflow\config.example.json workflow\config.json
# 编辑这两个文件，填入你的飞书 App ID 等信息

# 4. 设置环境变量（API 密钥不存在代码里）
set CC_PIANO_LLM_KEY=<你的 OpenAI 兼容 API 密钥>
set CC_PIANO_WRITER_KEY_DEEPSEEK=<你的 DeepSeek API 密钥>

# 5. 启动琴房
douyin\启动琴房.bat
# 或者手动：
# douyin\.venv\Scripts\python douyin\web\server.py
```

浏览器会自动打开 `http://127.0.0.1:8765`。

## 每日运营流程

```
14:00  daily_make.py     收件箱新录屏 → Claude 编剧 → 自动渲染
12:00  report.py         拉取创作者中心数据 → 生成日报 → 发飞书群
21:58  publish_at.py     22:00~22:29 随机时间打开抖音发布页
周六   weekly.py         生成周报 PPT
```

这些任务通过 Windows 任务计划程序自动运行（`workflow/tasks/`）。

## 模板系统

视频渲染基于版本化模板（`douyin/tracks/templates/`），模板定义了：

- 时长、竖屏/横屏、节拍吸附
- 开头/结尾小剧场
- 背景主题、粒子效果
- 歌词显示方式
- 淡入淡出节拍数

歌曲 JSON 通过 `"template": "daw@v6"` 引用模板，歌曲级字段覆盖模板默认值。

## 数据库

项目使用 SQLite（`douyin/data/studio.db`）存储运营数据、内容版本和知识库索引，支持 FTS5 全文搜索。当前处于双写过渡期（DB + JSON 同时写入），删除 `studio.db` 即可回退到纯 JSON。

## 配置说明

| 文件 | 说明 | 是否包含密钥 |
|------|------|------------|
| `.mcp.json` | MCP 服务器配置（本地路径） | 否，但含本地路径 |
| `workflow/config.json` | 飞书 App ID 和群 ID | 是（需保密） |
| `web/writer_profiles.json` | LLM 模型端点配置 | 否（密钥在环境变量） |
| `web/llm.json` | 动画库聊天 LLM 配置 | 否（密钥在环境变量） |

**所有 API 密钥都通过环境变量传入**，不存在于代码或配置文件中：
- `CC_PIANO_LLM_KEY` — 动画库聊天 API 密钥
- `CC_PIANO_WRITER_KEY_<ID>` — 编剧页各模型的 API 密钥
- `BLENDERMCP_HYPER3D_API_KEY` — Hyper3D 云端 3D 生成（可选）
- `LLM_WIKI_API_TOKEN` — LLM Wiki API 令牌

## 技术栈

- **后端**：Python 3.13 + SQLite（WAL 模式）
- **前端**：原生 HTML/CSS/JS（glass.css 毛玻璃风格）
- **动画**：p5.brush（手绘水彩）、three.js（3D 场景）
- **音频**：faster-whisper（歌词识别）、FFmpeg（音视频处理）
- **AI**：DeepSeek（编剧/知识库）、Claude（编剧/代码修改）
- **自动化**：Windows Task Scheduler + 飞书机器人
- **3D**：Blender 4.5 LTS + blender-mcp
- **发布**：Selenium + Edge（抖音自动填写发布页）

## 许可证

本项目源码供学习参考。如需商用请联系作者。
