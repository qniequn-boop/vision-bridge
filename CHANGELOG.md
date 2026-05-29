# Changelog

## [1.0.1] - 2026-05-29

### Fixed
- **Truncation detection**: `len(finish_reason)` → `finish_reason` (bug made it always False)
- **Error caching**: `[ERROR:*]` and `[WARNING:*]` responses no longer cached for 24h
- **VISION_MAX_COST_USD**: now actually enforced before API calls (was documented but not implemented)
- **smart/fast aliases**: `fast` now uses `qwen-plus` instead of duplicating `qwen3.6-plus`
- **qwen_chat audit**: text chat calls now logged to audit trail (was only analyze_image)
- **pyproject.toml**: fixed `build-backend` from invalid `setuptools.backends._legacy:_Backend` to `setuptools.build_meta`
- **pyproject.toml**: replaced `your-username` placeholder with `qniequn-boop`


## [1.0.0] - 2026-05-29

### Added
- Initial release
- `analyze_image` — multimodal vision analysis via qwen3.6-plus or OpenAI
- `qwen_chat` — text chat with model aliases (smart/fast/cheap)
- `qwen_embed` — text embeddings
- `list_models` — show available models and capabilities
- `audit_log` — API call history with costs and latency
- Dynamic prompting: SYSTEM_PROMPT + conversation context
- 6-module expert SYSTEM_PROMPT:
  - Critical reading rules
  - Anti-confusion (ruler dimensions, grid geometry, perspective)
  - 14 drawing types auto-detection (PCB, P&ID, architectural, GOST/JIS/DIN...)
  - Non-standard standards awareness
  - Ambiguity flagging with [LOW CONFIDENCE]
  - Structured 4-part output format
- Safe content extraction (handles null/empty/missing API responses)
- Truncation detection when max_tokens cuts response
- Image size guard (>15MB rejection)
- Audit log with JSONL persistence
- Response cache (SHA-256, 24h TTL)
- Exponential backoff retry (3 attempts)
- Cost estimation with configurable cap
- Dual provider: Qwen DashScope (default) + OpenAI
- Auto MIME type detection (PNG/JPEG/WebP/BMP)
- CLI tool (`vision.py`) for direct terminal use
