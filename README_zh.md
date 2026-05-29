<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/MCP-Server-green?style=flat-square" alt="MCP">
  <img src="https://img.shields.io/badge/Qwen3.6--Plus-Vision-orange?style=flat-square" alt="Qwen">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Smithery-Deploy-purple?style=flat-square" alt="Smithery">
</p>

<p align="center">
  <a href="README.md">English</a>
</p>

# vision-bridge

**让纯文本 AI（DeepSeek、Claude、Codex）也能看图** — 通过 MCP 桥接到千问/OpenAI 多模态模型。

```
纯文本 AI  ──MCP──>  vision-bridge  ──API──>  qwen3.6-plus
                        (339行)                "法兰，外径120，6个M8通孔..."
```

## 快速开始

### 1. 安装

```bash
pip install mcp
git clone https://github.com/qniequn-boop/vision-bridge.git
```

### 2. 配置 API Key

```bash
# 阿里云 DashScope（默认）
setx DASHSCOPE_API_KEY "sk-你的Key"

# 或 OpenAI
setx OPENAI_API_KEY "sk-你的Key"
setx VISION_PROVIDER "openai"
```

### 3. 配置 AI 客户端

**Codex** (`~\.codex\config.toml`):
```toml
[mcp_servers.vision]
type = "stdio"
command = "python"
args = ["-m", "vision_bridge.server"]
env = { DASHSCOPE_API_KEY = "sk-你的Key" }
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "vision": {
      "command": "python",
      "args": ["-m", "vision_bridge.server"],
      "env": { "DASHSCOPE_API_KEY": "sk-你的Key" }
    }
  }
}
```

### 4. 重启使用

```
用户："帮我看看这个法兰图纸，外径多少？"

AI: analyze_image("flange.png", "读出外径尺寸和螺栓孔规格")
  → qwen3.6-plus: "外径 O120mm，6个M8通孔，均布在 O90mm 螺栓圆上"
```

## 工具

| 工具 | 说明 |
|------|------|
| `analyze_image` | 多模态视觉分析（默认 qwen3.6-plus） |
| `qwen_chat` | 文本对话，别名: `smart` / `fast` / `cheap` |
| `qwen_embed` | 文本向量嵌入 |
| `list_models` | 列出可用模型、别名、能力 |
| `audit_log` | 查看 API 调用历史、费用、延迟 |

## 架构

```
┌──────────┐  MCP/JSON-RPC  ┌──────────────────┐  OpenAI兼容接口   ┌──────────────┐
│ AI Agent │◄──────────────►│ vision-bridge     │◄────────────────►│ DashScope /  │
│ (Codex,  │   (stdio)      │ - 6模块提示词      │ /chat/completions │ OpenAI       │
│  Claude) │                │ - 安全提取         │                   │ qwen3.6-plus │
└──────────┘                │ - 审计日志         │                   └──────────────┘
                            │ - 重试+缓存        │
                            └──────────────────┘
```

## SYSTEM_PROMPT 六大模块

专家提示词经过精心设计，覆盖了罕见和极端场景：

| 模块 | 作用 |
|------|------|
| **关键规则** | 读每一个数字、孔类型、公差、标题栏 |
| **防混淆** | 刻度尺≠尺寸、网格≠几何、透视变形感知 |
| **图纸类型** | 自动检测 14 种类型（PCB、P&ID、建筑、GOST/JIS...）|
| **多国标准** | GOST(俄)、JIS(日)、DIN/ISO(欧)、ANSI/ASME(美)、旧图纸 |
| **歧义标注** | `[LOW CONFIDENCE]` 标记、公制/英制双报 |
| **输出格式** | 四段式：场景 → 特征 → 尺寸 → 警告 |

## 模型支持

### 千问（默认）

| 别名 | 模型 |
|------|------|
| `vision` | `qwen3.6-plus` |
| `vision-max` | `qwen3-vl-235b-a22b-instruct` |
| `fast` / `smart` | `qwen3.6-plus` |
| `cheap` | `qwen-turbo` |
| `embed` | `text-embedding-v3` |

### OpenAI

设置 `VISION_PROVIDER=openai` 切换。

| 别名 | 模型 |
|------|------|
| `vision` | `gpt-4o-mini` |
| `vision-max` | `gpt-4o` |

## 特性

- **智能提示词** — 6 模块、14 种图纸类型、5 国标准、防混淆规则
- **动态上下文** — 将对话意图传递给视觉模型，定向检索
- **安全提取** — 优雅处理 API 返回空/缺失/异常
- **截断检测** — `max_tokens` 截断时自动警告
- **图片大小守卫** — >15MB 拒绝上传
- **11 种类型化错误** — 每种附修复建议
- **审计日志** — JSONL 格式 `~/.vision-bridge/log.jsonl`
- **响应缓存** — SHA-256，24 小时 TTL
- **指数退避重试** — 3 次，429/5xx 自动重试
- **费用预估** — 可配置上限 (`VISION_MAX_COST_USD`)
- **双 Provider** — 千问/OpenAI 环境变量切换
- **自动 MIME 检测** — PNG/JPEG/WebP/BMP

## 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `DASHSCOPE_API_KEY` | — | 千问 API Key（DashScope） |
| `OPENAI_API_KEY` | — | OpenAI API Key |
| `VISION_PROVIDER` | `qwen` | 切换：`qwen` 或 `openai` |
| `VISION_MAX_COST_USD` | `0.50` | 单次调用最高费用 |

## CLI

```bash
python -m vision_bridge.cli image.png "这是什么零件？"
```

## 许可证

MIT


## 故障排查

### MCP 服务未加载

**症状：** 重启后找不到 `analyze_image` 工具。

**原因：** TOML 配置中反斜杠被当作转义符。比如 `ision_bridge` 中的 `` 被解析为垂直制表符，导致整个配置文件解析失败，Codex 无法启动。

**修复：** 在 TOML 配置中始终使用正斜杠：

```toml
[mcp_servers.vision]
type = "stdio"
command = "python"
args = ["C:/Users/you/project/src/vision_bridge/server.py"]
env = { DASHSCOPE_API_KEY = "sk-your-key" }
```

**其他常见问题：**
- 文件路径中不要包含中文或非 ASCII 字符 — TOML 解析器可能乱码
- Python 不在 PATH 中 — 用 `python --version` 验证
- API Key 未设置 — 用 `echo %DASHSCOPE_API_KEY%` (Windows) 验证
