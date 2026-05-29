<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/MCP-Server-green?style=flat-square" alt="MCP">
  <img src="https://img.shields.io/badge/Qwen3.6--Plus-Vision-orange?style=flat-square" alt="Qwen">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Smithery-Deploy-purple?style=flat-square" alt="Smithery">
</p>

<p align="center">
  <a href="README_zh.md">中文</a>
</p>

# vision-bridge

**Give text-only AI (DeepSeek, Claude, Codex) the ability to see images** — MCP bridge to Qwen/OpenAI multimodal models.

```
Text-only AI  ──MCP──>  vision-bridge  ──API──>  qwen3.6-plus
                          (339 lines)              "Flange, OD120mm, 6xM8..."
```

## Quick Start

### 1. Install

```bash
pip install mcp
git clone https://github.com/qniequn-boop/vision-bridge.git
```

### 2. Set API Key

```bash
# Alibaba DashScope (default)
setx DASHSCOPE_API_KEY "sk-your-key"

# or OpenAI
setx OPENAI_API_KEY "sk-your-key"
setx VISION_PROVIDER "openai"
```

### 3. Configure AI Client

Add to your MCP client config:

**Codex** (`~\.codex\config.toml`):
```toml
[mcp_servers.vision]
type = "stdio"
command = "python"
args = ["-m", "vision_bridge.server"]
env = { DASHSCOPE_API_KEY = "sk-your-key" }
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "vision": {
      "command": "python",
      "args": ["-m", "vision_bridge.server"],
      "env": { "DASHSCOPE_API_KEY": "sk-your-key" }
    }
  }
}
```

### 4. Restart & Use

```
User: "Analyze this flange drawing, what's the OD?"

AI: analyze_image("flange.png", "Read OD and bolt hole specs")
  → qwen3.6-plus: "OD O120mm, 6xM8 thru holes, PCD O90mm"
```

## Tools

| Tool | Description |
|------|-------------|
| `analyze_image` | Multimodal vision analysis (qwen3.6-plus) |
| `qwen_chat` | Text chat with aliases: `smart` / `fast` / `cheap` |
| `qwen_embed` | Text embeddings |
| `list_models` | List models, aliases, capabilities |
| `audit_log` | API call history, costs, latency |

## Architecture

```
┌──────────┐  MCP/JSON-RPC  ┌──────────────────┐  OpenAI-Compatible  ┌──────────────┐
│ AI Agent │◄──────────────►│ vision-bridge     │◄──────────────────►│ DashScope /  │
│ (Codex,  │   (stdio)      │ - 6-module prompt │ /chat/completions  │ OpenAI       │
│  Claude) │                │ - Safe extraction │                    │ qwen3.6-plus │
└──────────┘                │ - Audit log       │                    └──────────────┘
                            │ - Retry + cache   │
                            └──────────────────┘
```

## SYSTEM_PROMPT Modules

The expert prompt is designed to handle rare and edge-case scenarios:

| Module | Purpose |
|--------|---------|
| **Critical Rules** | Read every number, hole type, tolerance, title block |
| **Anti-Confusion** | Ruler ≠ dimension, grid ≠ geometry, perspective awareness |
| **Drawing Types** | Auto-detect 14 types (PCB, P&ID, architectural, GOST/JIS...) |
| **Standards** | GOST, JIS, DIN/ISO, ANSI/ASME, vintage drawings |
| **Ambiguity** | `[LOW CONFIDENCE]` flagging, metric/imperial dual reports |
| **Output Format** | Structured 4-part: Scene → Features → Dimensions → Warnings |

## Supported Models

### Qwen (Default)

| Alias | Model |
|-------|-------|
| `vision` | `qwen3.6-plus` |
| `vision-max` | `qwen3-vl-235b-a22b-instruct` |
| `fast` / `smart` | `qwen3.6-plus` |
| `cheap` | `qwen-turbo` |
| `embed` | `text-embedding-v3` |

### OpenAI

Set `VISION_PROVIDER=openai`.

| Alias | Model |
|-------|-------|
| `vision` | `gpt-4o-mini` |
| `vision-max` | `gpt-4o` |

## Features

- **Intelligent prompt** — 6 modules, 14 drawing types, 5 standards, anti-confusion rules
- **Dynamic context** — conversation intent passed to vision model for targeted answers
- **Safe extraction** — handles null/empty/missing API responses gracefully
- **Truncation detection** — warns when `max_tokens` cuts response
- **Image size guard** — >15MB rejected before upload
- **11 typed errors** — each with remediation hints
- **Audit log** — JSONL at `~/.vision-bridge/log.jsonl`
- **Response cache** — SHA-256, 24h TTL
- **Exponential backoff** — 3 retries for 429/5xx
- **Cost estimation** — configurable cap (`VISION_MAX_COST_USD`)
- **Dual provider** — Qwen or OpenAI, switch via env var
- **Auto MIME** — PNG/JPEG/WebP/BMP detection

## Configuration

| Env Var | Default | Description |
|----------|---------|-------------|
| `DASHSCOPE_API_KEY` | — | Qwen API key (DashScope) |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `VISION_PROVIDER` | `qwen` | Switch: `qwen` or `openai` |
| `VISION_MAX_COST_USD` | `0.50` | Max cost per call |

## CLI

```bash
python -m vision_bridge.cli image.png "What is this part?"
```

## License

MIT


## Troubleshooting

### MCP server not loading (Codex / Claude)

**Symptom:** `analyze_image` tool not available after restart.

**Cause:** TOML config backslash escaping. Paths like `C:\pathision_bridge\server.py` are parsed as escape sequences (e.g., `` = vertical tab). This breaks the entire config, causing Codex to fail on startup.

**Fix:** Always use forward slashes in TOML args:

```toml
[mcp_servers.vision]
type = "stdio"
command = "python"
args = ["C:/Users/you/project/src/vision_bridge/server.py"]
env = { DASHSCOPE_API_KEY = "sk-your-key" }
```

**Other common issues:**
- Non-ASCII/Chinese characters in file paths — TOML parsers may mangle encoding
- Python not on PATH — verify with `python --version`
- API key not set — verify with `echo %DASHSCOPE_API_KEY%` (Windows) or `echo $DASHSCOPE_API_KEY` (macOS/Linux)
