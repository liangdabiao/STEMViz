# STEMViz - STEM 概念动画生成器

> **基于豆包大模型的 AI 教学动画生成工具** — 只需输入一个 STEM 概念，自动生成带旁白和字幕的教学动画视频。

STEMViz 利用字节跳动火山方舟（豆包）大模型的全套 AI 能力（LLM 推理、多模态视频理解、TTS 语音合成），配合 Manim 数学动画引擎，将复杂的 STEM 概念转化为生动的、带同步旁白的教学动画视频。

---

## ✨ 功能特性

- 🎬 **全自动动画生成**：输入概念 → 输出带旁白的完整教学视频
- 🧠 **多智能体架构**：概念解析 Agent + Manim 代码生成 Agent + 视频理解 Agent
- 🎙️ **AI 旁白生成**：多模态大模型观看动画后生成情境化旁白
- 🔊 **豆包 TTS 语音合成**：高质量中文语音，支持多种音色
- ⚡ **并行处理**：多场景代码并发生成，提升效率
- 🎨 **Gradio Web 界面**：简洁易用的浏览器界面
- 🧹 **自动清理**：生成成功后自动清理临时文件

---

## 🏗️ 工作流程与原理

### 整体架构

```
用户输入（STEM 概念）
    │
    ▼
┌─────────────────────────┐
│  步骤 1: 概念解析        │  豆包 LLM (Seed 2.1 Pro)
│  Concept Interpreter    │  → 拆解子概念、确定依赖关系
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  步骤 2: 动画生成        │  豆包 LLM + Manim
│  Manim Agent            │  场景规划 → 代码生成 → 渲染 → 拼接
└─────────────────────────┘
    │ 输出: 无声动画 MP4
    ▼
┌─────────────────────────┐
│  步骤 3: 脚本生成        │  豆包多模态 (Video Understanding)
│  Script Generator       │  → 分析视频画面 → 生成时间轴旁白 (SRT)
└─────────────────────────┘
    │ 输出: SRT 字幕脚本
    ▼
┌─────────────────────────┐
│  步骤 4: 语音合成        │  豆包 TTS (Seed TTS 1.0/2.0)
│  Audio Synthesizer      │  → 按字幕时间轴对齐生成语音
└─────────────────────────┘
    │ 输出: MP3 音频
    ▼
┌─────────────────────────┐
│  步骤 5: 视频合成        │  FFmpeg
│  Video Compositor       │  → 合并视频+音频，烧录字幕
└─────────────────────────┘
    │
    ▼
  最终视频（带旁白+字幕）
```

### 各步骤详细原理

#### 步骤 1：概念解析（Concept Interpreter）

**使用模型**：豆包 Seed 2.1 Pro

**原理**：
- 将用户输入的概念（如"勾股定理"）送入大模型
- 大模型将其拆解为 4-6 个子概念（如"直角三角形定义"、"面积法证明"等）
- 确定子概念之间的依赖关系（哪些是前置知识）
- 为每个子概念生成教学目标和关键要点

**输出**：结构化的 JSON，包含子概念列表、依赖关系、难度等

---

#### 步骤 2：动画生成（Manim Agent）

**使用模型**：豆包 Seed 2.1 Pro（场景规划） + Seed 2.1 Turbo（代码生成）

**原理**：
1. **场景规划**：根据概念分析结果，规划 4-6 个动画场景，每个场景对应一个子概念
2. **并行代码生成**：为每个场景调用豆包 Turbo 模型生成 Manim Python 代码
   - 使用 OpenAI 兼容的 API 格式
   - 提示词包含 Manim 最佳实践和代码规范
3. **代码修复**：如果渲染失败，自动将错误信息反馈给 LLM，让其修复（最多重试 2 次）
4. **场景渲染**：调用 Manim 命令行渲染每个场景为 MP4
5. **视频拼接**：用 FFmpeg 将多个场景拼接成完整的无声动画

**技术细节**：
- 代码生成采用并行处理（`concurrent.futures`），提升速度
- 渲染失败时自动简化代码（移除复杂数学公式等），确保至少有基础动画输出
- LaTeX 数学公式通过 MiKTeX 渲染（Windows）

---

#### 步骤 3：脚本生成（Script Generator）

**使用模型**：豆包 Seed 2.1 Pro（多模态视频理解）

**原理**：
1. **视频上传**：将无声动画通过豆包 File API 上传到云端
2. **视频处理**：等待豆包服务端抽帧处理（约 2-5 秒）
3. **画面分析**：调用豆包 Responses API，让模型"观看"视频
   - 模型理解每个时间点画面上的内容
   - 生成与画面对齐的旁白文字
   - 输出 SRT 格式字幕（带精确时间戳）
4. **时长校准**：确保字幕总时长与视频匹配

**技术细节**：
- 使用豆包 File API 上传视频（支持最大 2GB）
- 支持多语言旁白生成（中文、英文等）
- SRT 格式确保精确的时间同步

---

#### 步骤 4：语音合成（Audio Synthesizer）

**使用服务**：豆包语音合成（Seed TTS 1.0/2.0）

**原理**：
1. 逐条读取 SRT 字幕文件中的每一条旁白
2. 对每条文字调用豆包 TTS API 生成对应的语音片段
3. 根据字幕的时间戳，在各片段之间插入静音，确保精确对齐
4. 将所有片段拼接成完整的音频文件（MP3 格式）

**技术细节**：
- 支持新版控制台（X-Api-Key）和旧版控制台（APP ID + Access Token）两种鉴权方式
- 支持调整语速、音量
- 自动对齐视频时长（音频短于视频时自动补静音）

---

#### 步骤 5：视频合成（Video Compositor）

**使用工具**：FFmpeg

**原理**：
1. 将无声动画视频与 TTS 语音合并
2. 将 SRT 字幕"烧录"到视频画面上（可选）
3. 输出最终的 MP4 文件（H.264 视频 + AAC 音频）

**技术细节**：
- 支持字幕样式自定义（字体大小、颜色、背景、位置）
- 使用 CRF 控制视频质量
- 自动添加 faststart 元数据，便于网络流媒体播放

---

## 🛠️ 技术栈

| 模块 | 技术 |
|------|------|
| **Web 界面** | Gradio |
| **动画引擎** | Manim Community Edition |
| **LLM 推理** | 豆包 Seed 2.1 Pro / Turbo（火山方舟） |
| **多模态理解** | 豆包多模态 + File API（火山方舟） |
| **语音合成** | 豆包 TTS 1.0 / 2.0（火山引擎） |
| **视频处理** | FFmpeg |
| **配置管理** | Pydantic Settings + .env |

---

## 📦 安装

### 前置要求

**系统要求：**
- Python 3.10+
- FFmpeg（视频处理）
- LaTeX（Manim 数学公式渲染，可选但推荐）

**API 密钥：**
- 豆包火山方舟 API Key（用于 LLM 推理和多模态视频理解）
- 豆包语音合成 API Key（用于 TTS 语音合成）

---

### 步骤 1：安装系统依赖

#### Windows

**FFmpeg**：
```powershell
# 方式一：使用 Chocolatey
choco install ffmpeg

# 方式二：从官网下载并手动添加到 PATH
# https://ffmpeg.org/download.html
```

**LaTeX (MiKTeX)**：
```powershell
# 下载安装包（阿里云镜像，约 140MB）
# https://mirrors.aliyun.com/CTAN/systems/win32/miktex/setup/windows-x64/basic-miktex-25.12-x64.exe

# 运行安装程序，选择"为当前用户安装"
# 安装后确保 latex 和 dvisvgm 命令可用
```

#### macOS
```bash
# 安装 FFmpeg
brew install ffmpeg

# 安装 LaTeX（用于数学公式渲染）
brew install --cask mactex
```

#### Linux (Ubuntu/Debian)
```bash
# 安装 FFmpeg
sudo apt install ffmpeg

# 安装 LaTeX
sudo apt install texlive texlive-latex-extra texlive-fonts-extra texlive-science
```

**验证安装：**
```bash
ffmpeg -version
latex --version
```

---

### 步骤 2：克隆项目

```bash
git clone https://github.com/qnguyen3/STEMViz.git
cd STEMViz
```

---

### 步骤 3：安装 Python 依赖

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

---

### 步骤 4：配置 API 密钥

1. 复制环境变量模板：
   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env` 文件，填入你的豆包 API 密钥：

```env
# ========== 豆包大模型配置（火山方舟）==========
# LLM 推理 + 多模态视频理解
DOUBAO_API_KEY=你的豆包方舟APIKey
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# ========== 豆包 TTS 配置（语音合成）==========
# 新版控制台 API Key 方式
DOUBAO_TTS_API_KEY=你的豆包TTS_APIKey
DOUBAO_TTS_RESOURCE_ID=seed-tts-1.0
DOUBAO_TTS_AUTH_MODE=new

# 音色：双笙（活泼女声）
DOUBAO_TTS_VOICE_ID=zh_female_shuangkuaisisi_moon_bigtts
DOUBAO_TTS_SPEED_RATIO=0.0
DOUBAO_TTS_VOLUME_RATIO=0.0

# ========== 模型选择 ==========
REASONING_MODEL=doubao-seed-2-1-pro-260628
MULTIMODAL_MODEL=doubao-seed-2-1-pro-260628
```

**获取 API Key：**
- **豆包方舟（LLM + 多模态）**：登录 [火山引擎方舟平台](https://www.volcengine.com/product/ark) → 创建接入点 → 获取 API Key
- **豆包 TTS**：登录 [火山引擎语音合成](https://www.volcengine.com/product/tts) → 创建应用 → 获取 API Key

---

### 步骤 5：验证安装

```bash
# 验证 Manim
manim --version

# 验证 FFmpeg
ffmpeg -version
```

---

## 🚀 使用方法

### 方式一：Web 界面（推荐）

```bash
python app.py
```

浏览器会自动打开 `http://127.0.0.1:7860`

**使用步骤：**
1. 在输入框中输入要讲解的 STEM 概念（如"讲解勾股定理"）
2. 选择旁白语言（中文/英文等）
3. 点击「生成动画」按钮
4. 等待生成（约 10-30 分钟，取决于概念复杂度）
5. 生成的视频会显示在页面上

---

### 方式二：命令行使用

```bash
# 基本用法
python app-cli.py "讲解勾股定理"

# 指定中文
python app-cli.py "美国总统加菲尔德的勾股定理证明" --lang 中文

# 指定英文
python app-cli.py "Explain bubble sort" --lang English
```

### 方式三：Python 脚本调用

```python
from pipeline import Pipeline

pipeline = Pipeline()
result = pipeline.run("讲解勾股定理", target_language="中文")

if result["status"] == "success":
    print("✅ 生成成功！")
    print("视频路径:", result["video_result"]["output_path"])
else:
    print("❌ 失败:", result.get("error"))
```

---

### 示例 Prompt

```
- 讲解勾股定理
- 解释冒泡排序算法
- 什么是导数
- 演示梯度下降优化
- 用医疗诊断例子讲解贝叶斯定理
- 可视化傅里叶变换
- 解释神经网络中的反向传播
```

---

## ⚙️ 配置说明

主要配置在 `config.py` 中，常用配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `manim_quality` | 动画质量 (`480p15`/`720p30`/`1080p60`/`1440p60`) | `1080p60` |
| `manim_max_scene_duration` | 单场景最大时长（秒） | `30` |
| `reasoning_model` | LLM 推理模型 | `doubao-seed-2-1-pro-260628` |
| `multimodal_model` | 多模态视频理解模型 | `doubao-seed-2-1-pro-260628` |
| `doubao_tts_voice_id` | TTS 音色 | `zh_female_shuangkuaisisi_moon_bigtts` |
| `subtitle_burn_in` | 是否烧录字幕到视频 | `True` |
| `subtitle_font_size` | 字幕字体大小 | `24` |

---

## 📂 输出目录结构

```
output/
├── analyses/          # 概念分析结果（JSON）
├── scene_plans/       # 场景规划（JSON）
├── scene_codes/       # 生成的 Manim 代码
├── scenes/            # 单个场景视频
├── animations/        # 拼接后的无声动画
├── scripts/           # SRT 旁白脚本
├── audio/             # TTS 生成的语音
│   └── segments/      # 单个语音片段
└── final/             # 最终视频（带旁白+字幕）⭐
```

> **注意**：临时文件会在生成成功后自动清理，只保留最终视频和脚本。

---

## 🔧 常见问题

### 1. "LaTeX not found" 错误

确保 MiKTeX 已安装并添加到 PATH：
```powershell
# 验证
latex --version
dvisvgm --version

# Windows 默认安装路径
# C:\Users\<用户名>\AppData\Local\Programs\MiKTeX\miktex\bin\x64
```

### 2. "FFmpeg not found" 错误

```bash
# 验证
ffmpeg -version

# 如果没安装，下载并添加到 PATH
# https://ffmpeg.org/download.html
```

### 3. Manim 命令找不到

确保虚拟环境已激活：
```bash
# Windows
.venv\Scripts\activate

# 重新安装
pip install --force-reinstall manim
```

### 4. API 密钥错误

- 检查 `.env` 文件中的密钥是否正确
- 确认火山方舟和 TTS 服务是否已开通
- 检查 API 额度是否充足
- 注意不要在密钥前后加空格或引号

### 5. 内存不足

- 降低动画质量：`manim_quality = "720p30"`
- 减少单场景时长：`manim_max_scene_duration = 20`

### 6. 生成很慢

- 首次运行较慢，因为 LaTeX 包需要下载
- 后续运行会缓存包，速度会提升
- 复杂概念自然需要更长时间（平均 10-30 分钟）

---

## 📁 项目结构

```
STEMViz/
├── agents/                 # AI 智能体
│   ├── base.py                # 基础 Agent 类（API 调用、JSON 解析）
│   ├── concept_interpreter.py # 概念解析 Agent
│   ├── manim_agent.py         # Manim 动画生成 Agent
│   └── manim_models.py        # 数据模型
├── generation/             # 内容生成
│   ├── script_generator.py    # 多模态脚本生成
│   ├── video_compositor.py    # 视频合成
│   └── tts/                   # TTS 语音合成
│       ├── base.py
│       └── doubao_provider.py # 豆包 TTS 实现
├── rendering/              # 动画渲染
│   └── manim_renderer.py      # Manim 代码执行器
├── config.py                # 配置管理
├── pipeline.py              # 主流程编排
├── app.py                   # Gradio Web 界面
└── requirements.txt         # Python 依赖
```

---

## 🤝 贡献

欢迎贡献！请：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交改动 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目使用非商业许可证 - 详见 LICENSE 文件。

---

## 🙏 致谢

- **Manim Community**：优秀的数学动画引擎
- **3Blue1Brown**：激励了教育数学可视化的方向
- **火山引擎 / 豆包**：强大的 AI 能力（LLM、多模态、TTS）

---

## 📮 联系方式

原项目：[https://github.com/qnguyen3/STEMViz](https://github.com/qnguyen3/STEMViz)

---

**⭐ 如果觉得有用，请给个 Star！**
