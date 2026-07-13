# STEMViz 豆包大模型 API 替换方案

> 方案日期：2026年7月12日
> 目标：将项目中的 OpenRouter、Google AI、ElevenLabs 三个 API 统一替换为字节跳动豆包大模型 API

---

## 一、项目现状分析

### 1.1 当前 API 使用情况

| 功能模块 | 当前 API 提供商 | 当前模型 | 用途 | 主要代码位置 |
|---------|--------------|---------|------|------------|
| LLM推理 | OpenRouter | Claude Sonnet 4.5 | 概念解释、场景规划、Manim代码生成 | [agents/base.py](file:///d:/STEMViz-main/agents/base.py), [agents/concept_interpreter.py](file:///d:/STEMViz-main/agents/concept_interpreter.py), [agents/manim_agent.py](file:///d:/STEMViz-main/agents/manim_agent.py) |
| 多模态视频分析 | Google AI (Gemini) | Gemini 2.5 Flash / Pro | 分析无声动画视频，生成带时间戳解说脚本 | [generation/script_generator.py](file:///d:/STEMViz-main/generation/script_generator.py) |
| 语音合成 (TTS) | ElevenLabs | eleven_v3 / eleven_multilingual_v2 | 将解说脚本转换为语音 | [generation/tts/elevenlabs_provider.py](file:///d:/STEMViz-main/generation/tts/elevenlabs_provider.py) |

### 1.2 当前架构特点

- **LLM推理**：使用 OpenAI 兼容的 Chat Completions API，通过 `requests` 库直接调用
- **多模态**：使用 Google GenAI SDK，支持视频文件上传 + 内容生成
- **TTS**：使用 ElevenLabs Python SDK，逐段合成后拼接

---

## 二、豆包大模型 API 能力调研

### 2.1 总体概览

豆包大模型通过**火山引擎方舟（Volcano Engine Ark）**平台提供服务，已形成完整的产品矩阵：

| 产品系列 | 模型名称 | 核心能力 | 适用场景 |
|---------|---------|---------|---------|
| **Seed 2.1 系列** | Doubao-Seed-2.1-Pro | 旗舰级，Coding/Agent/多模态 | 高复杂度任务、生产级应用 |
| | Doubao-Seed-2.1-Turbo | 轻量高效，性价比高 | 规模化生产、批量调用 |
| | Doubao-Seed-Evolving | 持续迭代，月更2-4次 | 开发者探索、前沿能力 |
| **语音合成** | Seed-TTS 2.0 | 100+音色、多语种、时间戳 | 视频配音、有声书、客服 |
| **视频生成** | Seedance 2.5 | 高清视频生成（7月初发布） | 内容创作（本项目暂不需要） |

### 2.2 LLM 推理能力（对应 OpenRouter）

**API 接入点**：
- Chat Completions: `https://ark.cn-beijing.volces.com/api/v3/chat/completions`
- Responses API: `https://ark.cn-beijing.volces.com/api/v3/responses`

**核心特性**：
- ✅ **OpenAI 完全兼容**：可直接使用 OpenAI SDK 或现有 `requests` 调用方式
- ✅ **深度思考模式**：通过 `thinking` 参数控制，支持 `reasoning_effort`（minimal/low/medium/high）
- ✅ **256K 上下文窗口**：输入输出各 256K tokens
- ✅ **函数调用（Function Calling）**
- ✅ **批量推理、上下文缓存**
- ✅ **Coding & Agent 能力突出**：Terminal Bench 2.1 与 Claude Opus 4.7 持平

**模型选型建议**：
| 场景 | 推荐模型 | 理由 |
|-----|---------|------|
| 概念解释、场景规划 | doubao-seed-2.1-pro | 需要较强的推理和结构化输出能力 |
| Manim 代码生成 | doubao-seed-2.1-pro | Coding 能力是 Seed 2.1 的强项 |
| 成本敏感场景 | doubao-seed-2.1-turbo | 价格减半，多数场景能力接近 Pro |

**定价对比**（参考2026年6月官方公布）：
| 模型 | 输入价格（元/百万tokens） | 输出价格（元/百万tokens） |
|-----|------------------------|------------------------|
| Claude Sonnet 4.5 (OpenRouter) | ~15 | ~75 |
| Doubao-Seed-2.1-Pro | 6 | 30 |
| Doubao-Seed-2.1-Turbo | 3 | 15 |

> 💡 **成本优势**：替换为豆包后，LLM 推理成本预计可降低 **60%-80%**

### 2.3 多模态视频理解能力（对应 Google Gemini）

**支持模型**：Doubao-Seed-2.1-Pro / Turbo 系列均支持视频理解

**视频输入方式**：

| 方式 | 大小限制 | 适用场景 |
|-----|---------|---------|
| **Files API 上传（推荐）** | 512MB（默认存储）/ 2GB（TOS存储） | 大文件、多次复用 |
| Base64 编码 | 50MB（请求体≤64MB） | 小文件快速测试 |
| URL 传入 | 50MB | 文件已有公网地址 |

**核心能力**：
- ✅ **视频理解**：通过 `fps` 参数控制抽帧率（建议 0.3-1.0 fps）
- ✅ **时间戳分析**：可输出带开始/结束时间的事件描述
- ✅ **图片理解**：支持 low/high/xhigh 三种精细度模式
- ✅ **支持格式**：mp4、wmv、webm、mkv、m4v、flv、avi、mov

**调用流程**（Files API 方式）：
```
1. 上传视频文件 → 获取 File ID
2. 等待文件处理完成（processing → active）
3. 使用 Responses/Chat API 传入 file_id + 文本指令
4. 获取分析结果
```

> 💡 **与 Gemini 的对比**：Seed 2.1 在视频时序理解基准（TOMATO、LVBench）上大幅领先 Gemini 3.1 Pro，完全可以替代

### 2.4 语音合成（TTS）能力（对应 ElevenLabs）

**API 接入点**：
- 单向流式 HTTP: `POST https://openspeech.bytedance.com/api/v3/tts/unidirectional`
- 单向流式 WebSocket: `wss://openspeech.bytedance.com/api/v3/tts/unidirectional/stream`
- 异步长文本: `submit` + `query` 接口（最大10万字符）

**核心能力**：
- ✅ **100+ 精品音色**：普通话、方言（四川话/东北话/粤语/上海话）、英语、日语、西语等
- ✅ **声音复刻**：支持自定义音色克隆（seed-icl-2.0）
- ✅ **多情感支持**：happy/sad/angry 等情感调节
- ✅ **字级别时间戳**：开启 `enable_subtitle` 后返回字幕级时间戳
- ✅ **音频格式**：mp3 / pcm / ogg_opus / wav
- ✅ **语速调节**：-50 ~ +100（对应 0.5x ~ 2.0x）
- ✅ **音量调节**：-50 ~ +100
- ✅ **SSML 标记语言**：更精细的发音控制
- ✅ **LaTeX 文本朗读**：教育场景专用

**认证方式**：
- Header: `X-Api-Key`（API Key）
- Header: `X-Api-Resource-Id`（资源ID，如 `seed-tts-2.0`）
- Header: `X-Api-Request-Id`（UUID随机字符串）

> 💡 **与 ElevenLabs 的对比**：豆包 TTS 在中文音色数量和质量上更有优势，且价格更低廉；ElevenLabs 在英文音色和情感细腻度上仍有一定优势

---

## 三、替换方案详解

### 3.1 总体架构图

```
┌───────────────────────────────────────────────────────────┐
│                     STEMViz 项目                           │
├─────────────┬──────────────────┬──────────────────────────┤
│  LLM 推理    │  多模态视频分析   │     语音合成 (TTS)        │
├─────────────┼──────────────────┼──────────────────────────┤
│ 火山方舟     │   火山方舟        │   火山引擎语音服务         │
│ (Ark)       │   (Ark)          │   (OpenSpeech)           │
│             │                  │                          │
│ Seed 2.1    │   Seed 2.1       │   Seed-TTS 2.0           │
│ (Pro/Turbo) │   (视频理解)     │   (100+音色)            │
└─────────────┴──────────────────┴──────────────────────────┘
         统一使用火山引擎账号管理，一套 API Key 体系
```

### 3.2 LLM 推理替换方案

#### 3.2.1 修改点清单

| 文件 | 修改内容 | 影响程度 |
|-----|---------|---------|
| [config.py](file:///d:/STEMViz-main/config.py) | 新增豆包配置，修改默认模型名称和base_url | 中 |
| [agents/base.py](file:///d:/STEMViz-main/agents/base.py) | 基本不需要修改（已兼容OpenAI格式） | 小 |
| [.env.example](file:///d:/STEMViz-main/.env.example) | 新增 `ARK_API_KEY` 等环境变量 | 小 |
| [pipeline.py](file:///d:/STEMViz-main/pipeline.py) | 修改 agent 初始化参数 | 小 |

#### 3.2.2 具体实施方案

**方案**：由于项目已使用 OpenAI 兼容格式的 `requests` 调用，只需修改 base_url 和 API Key 即可。

1. **新增配置项**（config.py）：
   - `ark_api_key`: 火山方舟 API Key
   - `ark_base_url`: `https://ark.cn-beijing.volces.com/api/v3`
   - `reasoning_model`: `doubao-seed-2-1-pro-xxxxxx`（具体模型ID以控制台为准）

2. **调整 thinking 参数**：
   - 豆包 Seed 2.1 支持 `thinking` 参数和 `reasoning_effort`
   - 需适配请求体格式（与 Anthropic 的 reasoning 参数略有不同）

3. **保持向后兼容**：
   - 保留 OpenRouter 配置，可通过 `llm_provider` 配置项切换

### 3.3 多模态视频分析替换方案

#### 3.3.1 修改点清单

| 文件 | 修改内容 | 影响程度 |
|-----|---------|---------|
| [config.py](file:///d:/STEMViz-main/config.py) | 新增豆包多模态配置 | 中 |
| [generation/script_generator.py](file:///d:/STEMViz-main/generation/script_generator.py) | 重写 Gemini 相关逻辑，改用火山方舟 Files API + Responses API | 大 |
| [requirements.txt](file:///d:/STEMViz-main/requirements.txt) | 移除 google-genai，可选添加 volcenginesdkarkruntime | 小 |

#### 3.3.2 具体实施方案

**核心变化**：
- 移除 `google.genai` 依赖
- 改用火山方舟 Files API 上传视频
- 使用 Responses API（或 Chat API）进行视频理解

**调用流程对比**：

| 步骤 | Gemini（当前） | 豆包 Seed 2.1（替换后） |
|-----|---------------|----------------------|
| 1 | `client.files.upload(file=...)` | `client.files.create(file=..., purpose="user_data", preprocess_configs={"video": {"fps": 0.3}})` |
| 2 | 轮询文件状态 | 轮询文件状态（wait_for_processing） |
| 3 | `client.models.generate_content(model=..., contents=[file, prompt])` | `client.responses.create(model=..., input=[{"role": "user", "content": [{"type": "input_video", "file_id": file.id}, {"type": "input_text", "text": prompt}]}])` |

**SDK 选择**：
- 方案A：使用官方 SDK `volcenginesdkarkruntime`（推荐）
- 方案B：继续使用 `requests` 调用 REST API（与现有 LLM 风格一致）

> 建议选择方案A，官方 SDK 封装了文件上传、状态轮询等常用操作，开发效率更高

### 3.4 语音合成（TTS）替换方案

#### 3.4.1 修改点清单

| 文件 | 修改内容 | 影响程度 |
|-----|---------|---------|
| [config.py](file:///d:/STEMViz-main/config.py) | 新增豆包TTS配置 | 中 |
| [generation/tts/doubao_provider.py](file:///d:/STEMViz-main/generation/tts/doubao_provider.py) | 新增，实现豆包TTS Provider | 大（新增文件） |
| [generation/tts/__init__.py](file:///d:/STEMViz-main/generation/tts/__init__.py) | 导出新 Provider | 小 |
| [pipeline.py](file:///d:/STEMViz-main/pipeline.py) | 新增 TTS Provider 选择逻辑 | 小 |
| [requirements.txt](file:///d:/STEMViz-main/requirements.txt) | 移除 elevenlabs，新增 requests（已有） | 小 |

#### 3.4.2 具体实施方案

**新增 DoubaoTTSSynthesizer 类**，继承自 `BaseTTSSynthesizer`：

- 使用 HTTP 单向流式接口（`/api/v3/tts/unidirectional`）
- 请求格式：JSON body，包含 `req_params.text`, `req_params.speaker`, `req_params.audio_params`
- 响应：HTTP Chunked 流式返回音频数据
- 支持 MP3 格式直接输出，与现有流程兼容

**配置项新增**：
- `doubao_tts_api_key`: 语音服务 API Key
- `doubao_tts_resource_id`: `seed-tts-2.0`
- `doubao_tts_voice_id`: 音色ID（如 `zh_female_vv_jupiter_bigtts`）
- `doubao_tts_speech_rate`: 语速（默认0）
- `doubao_tts_loudness_rate`: 音量（默认0）

**音色选择建议**（教育场景）：

| 场景 | 推荐音色 | 特点 |
|-----|---------|------|
| 中文女声解说 | zh_female_vv_jupiter_bigtts（vv音色） | 活泼灵动，分享感强 |
| 中文男声解说 | zh_male_yunzhou_jupiter_bigtts（云舟音色） | 清爽沉稳 |
| 英文解说 | en_male_tim_uranus_bigtts / en_female_dacey_uranus_bigtts | 美式英语 |

---

## 四、实施步骤

### 阶段一：准备工作（0.5天）

1. **注册火山引擎账号**并完成实名认证
2. **开通服务**：
   - 火山方舟 → 开通 Doubao-Seed-2.1-Pro / Turbo
   - 语音合成 → 开通 Seed-TTS 2.0
3. **获取 API Key**：
   - 方舟 API Key（用于 LLM 和多模态）
   - 语音服务 API Key（用于 TTS）
4. **配置环境变量**：复制 `.env` 新增豆包相关配置

### 阶段二：LLM 推理替换（1天）

1. 修改 `config.py` 新增豆包配置
2. 测试 `BaseAgent._call_llm()` 兼容性（基本兼容，可能需微调 thinking 参数）
3. 测试 Concept Interpreter Agent
4. 测试 Manim Agent（场景规划 + 代码生成）
5. 验证生成质量和速度

### 阶段三：多模态视频分析替换（2天）

1. 新增 `DoubaoVideoAnalyzer` 类（或直接修改 `ScriptGenerator`）
2. 实现 Files API 视频上传
3. 实现视频理解调用
4. 适配 SRT 输出格式解析
5. 端到端测试：生成视频 → 分析 → 输出脚本

### 阶段四：TTS 语音合成替换（1.5天）

1. 新增 `DoubaoTTSSynthesizer` Provider
2. 实现 HTTP 流式 TTS 调用
3. 实现音频保存和拼接逻辑
4. 测试音色选择和语速调节
5. 验证中文、英文效果

### 阶段五：集成测试与优化（1天）

1. 全流程端到端测试
2. 性能对比测试（速度、质量、成本）
3. 文档更新（README、配置说明）
4. 清理旧 API 依赖（可选，建议保留以支持回退）

---

## 五、成本与收益分析

### 5.1 成本对比（估算）

| 服务 | 当前方案 | 豆包方案 | 成本降低 |
|-----|---------|---------|---------|
| LLM推理 | ~$2-5 / 视频（Claude Sonnet） | ~¥2-5 / 视频（Seed 2.1 Pro） | ~60-80% |
| 视频分析 | ~$0.5-1 / 视频（Gemini Flash） | ~¥0.5-1 / 视频（Seed 2.1） | ~40-60% |
| TTS合成 | ~$0.1-0.3 / 视频（ElevenLabs） | ~¥0.05-0.2 / 视频（Seed-TTS） | ~50-70% |
| **总计** | **~$2.6-6.3 / 视频** | **~¥2.55-6.2 / 视频** | **~50-70%** |

> 注：以上为粗略估算，实际成本取决于视频时长、复杂度、token用量等因素

### 5.2 收益总结

✅ **成本大幅降低**：整体 API 成本预计降低 50%-70%

✅ **单一供应商管理**：一个火山引擎账号搞定所有AI能力，简化计费和运维

✅ **中文能力更强**：TTS中文音色更自然，LLM中文理解更准确

✅ **服务稳定性**：国内访问速度更快，延迟更低，无海外网络波动问题

✅ **生态持续扩展**：Seedance视频生成、图片生成等能力可后续接入

⚠️ **潜在风险**：
- 英文TTS音色质量可能略逊于 ElevenLabs
- 需要重新适配和测试，有一定开发工作量
- 需熟悉火山引擎控制台和计费体系

---

## 六、风险与注意事项

### 6.1 技术风险

| 风险点 | 影响程度 | 应对措施 |
|-------|---------|---------|
| 视频理解输出格式与 Gemini 有差异 | 中 | 充分测试，调整 prompt 以保证 SRT 格式输出稳定 |
| TTS 英文音色质量不如 ElevenLabs | 低（若主要用中文） | 优先使用中文场景，英文可后续评估 |
| API 接口细节不完全兼容 | 低 | 封装适配层，隔离差异 |

### 6.2 运营风险

| 风险点 | 影响程度 | 应对措施 |
|-------|---------|---------|
| 额度/限流问题 | 中 | 提前了解限流策略，必要时申请提升配额 |
| 模型版本更新 | 低 | 使用 Evolving 版本或固定模型版本号 |
| 费用超支 | 低 | 设置预算告警，监控用量 |

### 6.3 迁移建议

1. **渐进式迁移**：先替换一个模块（如 LLM），验证稳定后再替换其他
2. **保留回退能力**：保留原有 API 配置，可随时切回
3. **充分测试**：用 3-5 个不同复杂度的 STEM 概念做对比测试
4. **监控对比**：记录迁移前后的质量、速度、成本数据

---

## 七、后续扩展方向

迁移完成后，可基于豆包生态进一步扩展：

1. **Seedance 视频生成**：探索直接用文字生成教学演示视频的可能性
2. **Seedream 图片生成**：为动画生成配套的示意图和素材
3. **语音克隆**：用特定教师的声音生成解说
4. **多语言支持优化**：利用豆包多语种能力，支持更多语言的解说

---

## 附录：参考资源

- [火山方舟控制台](https://console.volcengine.com/ark)
- [豆包大模型官方文档](https://www.volcengine.com/docs/82379)
- [Seed 2.1 模型介绍](https://www.volcengine.com/docs/82379/2549861)
- [视频理解开发指南](https://www.volcengine.com/docs/82379/1895586)
- [语音合成 API 文档](https://www.volcengine.com/docs/6561/2528925)
- [TTS 音色列表](https://www.volcengine.com/docs/6561/1257544)
