"""vision-bridge MCP — multimodal bridge for text-only AI agents

Give single-modal AI (DeepSeek, Claude, Codex) vision via Qwen/OpenAI.

"""

import base64, sys, os, json, hashlib, time, pathlib

from urllib.request import Request, urlopen

from urllib.error import HTTPError, URLError

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vision-bridge")

# ═══════════════════════════════════════════════════════

DATA_DIR = pathlib.Path.home() / ".vision-bridge"

AUDIT_LOG = DATA_DIR / "log.jsonl"

CACHE_DIR = DATA_DIR / "cache"

MAX_RETRIES = 1

CACHE_TTL_S = 86400

DATA_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR.mkdir(exist_ok=True)

PROVIDER = os.getenv("VISION_PROVIDER", "qwen")

PROVIDERS = {

    "qwen": {

        "base": "https://dashscope.aliyuncs.com",

        "key_env": "DASHSCOPE_API_KEY",

        "models": {

            "qwen3.6-plus": {"caps":["chat","vision"],"ctx":131072,"in_m":1.5,"out_m":4.5},

            "qwen-vl-max-latest": {"caps":["chat","vision"],"ctx":131072,"in_m":1.5,"out_m":4.5},

            "qwen3-vl-235b-a22b-instruct": {"caps":["chat","vision"],"ctx":131072,"in_m":3.0,"out_m":9.0},

            "qwen-turbo": {"caps":["chat"],"ctx":131072,"in_m":0.3,"out_m":0.6},

            "qwen-plus": {"caps":["chat"],"ctx":131072,"in_m":0.8,"out_m":2.0},

            "text-embedding-v3": {"caps":["embed"],"ctx":8192,"in_m":0.0007,"dims":1024},

        },

        "aliases": {

            "smart":"qwen-vl-max-latest","fast":"qwen-plus","cheap":"qwen-turbo",

            "vision":"qwen-vl-max-latest","vision-max":"qwen3-vl-235b-a22b-instruct",

            "embed":"text-embedding-v3"

        }

    },

    "openai": {

        "base": "https://api.openai.com",

        "key_env": "OPENAI_API_KEY",

        "models": {

            "gpt-4o": {"caps":["chat","vision"],"ctx":128000,"in_m":2.5,"out_m":10.0},

            "gpt-4o-mini": {"caps":["chat","vision"],"ctx":128000,"in_m":0.15,"out_m":0.6},

            "text-embedding-3-small": {"caps":["embed"],"ctx":8191,"in_m":0.02,"dims":1536},

        },

        "aliases": {

            "smart":"gpt-4o","fast":"gpt-4o-mini","cheap":"gpt-4o-mini",

            "vision":"gpt-4o-mini","vision-max":"gpt-4o",

            "embed":"text-embedding-3-small"

        }

    }

}

CFG = PROVIDERS.get(PROVIDER, PROVIDERS["qwen"])

# ═══════════════════════════════════════════════════════

def _key():

    k = os.getenv(CFG["key_env"])

    if not k: raise RuntimeError(f"[MISSING_KEY] Set {CFG['key_env']}")

    return k

def _resolve(name):

    return CFG["aliases"].get(name, name)

def _spec(name):

    mid = _resolve(name)

    return CFG["models"].get(mid, {"caps":["chat","vision"],"ctx":32000,"in_m":0,"out_m":0})

def _estimate_cost(mid, itok, otok):

    s = _spec(mid)

    return (itok * s.get("in_m",0) + otok * s.get("out_m",0)) / 1e6

def _cache_key(*args):

    return hashlib.sha256(json.dumps(args,sort_keys=True).encode()).hexdigest()[:16]

def _cache_rw(key, val=None):

    cf = CACHE_DIR / key

    if val is None:

        if cf.exists() and time.time() - cf.stat().st_mtime < CACHE_TTL_S:

            try: return json.loads(cf.read_text())

            except: pass

        return None

    cf.write_text(json.dumps(val))

def _audit(**e):

    e.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    try:

        with open(AUDIT_LOG, "a", encoding="utf-8") as f:

            f.write(json.dumps(e) + "\n")

    except: pass

def _mime_type(path):

    ext = os.path.splitext(path)[1].lower()

    return {"png":"image/png","jpg":"image/jpeg","jpeg":"image/jpeg",

            "webp":"image/webp","gif":"image/gif","bmp":"image/bmp"}.get(ext,"image/jpeg")

def _api(path, body, timeout=90):

    url = f"{CFG['base']}{path}"

    data = json.dumps(body).encode()

    for attempt in range(MAX_RETRIES):

        try:

            req = Request(url, data=data,

                          headers={"Content-Type":"application/json",

                                   "Authorization":f"Bearer {_key()}",

                                   "Connection":"keep-alive"})

            with urlopen(req, timeout=timeout) as resp:

                return json.loads(resp.read())

        except HTTPError as e:

            eb = {}

            try: eb = json.loads(e.read())

            except: pass

            msg = eb.get("error",{}).get("message", str(e))

            if e.code == 401: raise RuntimeError(f"[INVALID_KEY] {msg}")

            if e.code == 404: raise RuntimeError(f"[MODEL_NOT_FOUND] {msg}")

            if e.code in (429, 502, 503):

                if attempt < MAX_RETRIES - 1:

                    time.sleep(2 ** attempt)

                    continue

                raise RuntimeError(f"[{'RATE_LIMIT' if e.code==429 else 'SERVER_ERROR'}] {msg}")

            raise RuntimeError(f"[HTTP {e.code}] {msg}")

        except URLError as e:

            if attempt < MAX_RETRIES - 1:

                time.sleep(2 ** attempt)

                continue

            raise RuntimeError(f"[NETWORK] {e.reason}")

    raise RuntimeError("[TIMEOUT] All retries exhausted")

def _safe_content(r):

    """Safely extract content from API response. Never crashes."""

    try:

        choices = r.get("choices", [])

        if not choices:

            return "[ERROR: API returned empty choices]"

        msg = choices[0].get("message", {})

        content = msg.get("content")

        if content is None:

            return "[WARNING: model returned no content (possible content filter)]"

        return content

    except Exception as e:

        return f"[ERROR extracting response: {e}]"

# ═══════════════════════════════════════════════════════

# ============================================================
#  TOOLS

# ═══════════════════════════════════════════════════════

SYSTEM_PROMPT = (

    "You are a meticulous engineering and visual analysis expert.\n"

    "\n"

    "=== CRITICAL RULES (apply to EVERY image) ===\n"

    "1. Read ALL numbers, labels, annotations \u2014 even if small, blurry, or in tables.\n"

    "2. For holes: specify type (through/blind/tapped/countersunk/counterbore) + thread if marked.\n"

    "3. For dimensions: include units, diameters(O), radii(R), PCD/BCD, angles.\n"

    "4. Note tolerances, surface finish, material callouts, revision numbers, title blocks.\n"

    "5. Identify view types: front/top/side/section/detail/auxiliary, 1st vs 3rd angle projection.\n"

    "6. For multi-content images: clearly separate each region before describing.\n"

    "\n"

    "=== ANTI-CONFUSION RULES ===\n"

    "- If a ruler, caliper, or coin appears in a photo: do NOT read its markings as part dimensions.\n"

    "- If grid lines, graph paper, or dot grid is visible: state it\'s a background, not geometry.\n"

    "- If the image is taken at an angle (perspective distortion): note that dimensions may be skewed.\n"

    "- If there are reflections, shadows, or transparent surfaces: describe the object \u2014 not the artifacts.\n"

    "- If the drawing uses dashed/hidden lines, centerlines, or phantom lines: identify their line type.\n"

    "- If the drawing uses simplified/symbolic representation (thread, spring, gear tooth): decode the convention.\n"

    "\n"

    "=== DRAWING TYPE AUTO-DETECTION ===\n"

    "Before analyzing, classify the drawing type from this list:\n"

    "- Mechanical part drawing (orthographic views, sections, dimensions)\n"

    "- Assembly/exploded view (balloons, parts list, BOM table)\n"

    "- PCB / electronics (silkscreen, copper traces, vias, pads)\n"

    "- Piping & Instrumentation (P&ID: equipment symbols, instrument bubbles, line types)\n"

    "- Architectural / floor plan (walls, doors, windows, room labels)\n"

    "- Electrical schematic (wire connections, component symbols, ladder logic)\n"

    "- Hydraulic / pneumatic circuit (valve symbols, flow arrows, manifold blocks)\n"

    "- Welding drawing (weld symbols, joint preparation, groove angles)\n"

    "- Casting / forging drawing (parting lines, draft angles, machining allowances)\n"

    "- Sheet metal flat pattern (bend lines, K-factor, relief cuts)\n"

    "- Isometric / pictorial (3D-looking drawing, often piping or layout)\n"

    "- Hand sketch (freehand lines, may lack scale, check for erasures/multiple tries)\n"

    "- Scanned/fax copy (noise, stains, low contrast, folded creases visible)\n"

    "- Photo of a physical part (NOT a drawing \u2014 note reference objects for scale)\n"

    "\n"

    "=== NON-STANDARD STANDARDS ===\n"

    "Recognize these drawing conventions:\n"

    "- GOST (Russian): Cyrillic text, unique surface finish triangles, different section hatching\n"

    "- JIS (Japanese): kanji notes, triangular surface marks, specific tolerance tables\n"

    "- DIN/ISO (German/European): specific dimension placement, ISO tolerance codes (H7, g6, etc.)\n"

    "- ANSI/ASME (American): inch dimensions, bilateral tolerances, different thread callouts\n"

    "- Old/vintage drawings: may use pre-ISO symbols, obsolete standards, hand-lettering\n"

    "\n"

    "=== AMBIGUITY & UNCERTAINTY ===\n"

    "- If a number is partially obscured: report it as \'approximately X (partially visible)\'.\n"

    "- If you cannot determine whether a feature is metric or imperial: state both possibilities.\n"

    "- If the image resolution prevents reading small text: note it and give best estimate.\n"

    "- Flag anything you are less than 80% confident about with [LOW CONFIDENCE] prefix.\n"

    "\n"

    "=== OUTPUT FORMAT ===\n"

    "- Answer concisely but exhaustively \u2014 no fluff, every fact.\n"

    "- Structure response: 1)Scene/Type 2)Content/Features 3)Dimensions/Numbers 4)Warnings/Ambiguities\n"

    "- Do NOT miss peripheral elements, watermarks, or fine print.\n"

    "- If a user question was provided, answer it specifically after the general analysis."

)

def _make_prompt(user_question=""):

    """Combine expert system prompt with user's specific question.

    output_format: "auto" (AI decides), "json" (force JSON), "text" (plain text)"""

    base = SYSTEM_PROMPT

    if output_format == "json":

        base += STRUCTURED_PROMPT

    elif output_format == "auto":

        base += (

            "\n\n=== OUTPUT FORMAT DECISION ===\n"

            "If this image is an engineering drawing, technical diagram, blueprint, "

            "mechanical part drawing, PCB layout, architectural plan, P&ID, or any "

            "technical document with dimensions/measurements: output PURE JSON "

            "(no markdown fences, no extra text)\n"

            + STRUCTURED_PROMPT +

            "\nOtherwise (casual photo, screenshot, artwork): "

            "describe naturally in plain text following the OUTPUT FORMAT rules above."

        )

    if user_question:

        return base + "\n\nUSER QUESTION:\n" + user_question + "\n\nAnswer the user question with expert precision."

    return base + "\n\nDescribe this image completely."

@mcp.tool()

def analyze_image(image_path: str, question: str = "", model: str = "vision") -> str:

    """Analyze image with vision AI. Supports engineering drawings, screenshots, photos.

    Args: image_path (absolute path), question (optional), model (alias or ID),

          format ("auto"=AI decides JSON/text, "json"=force structured JSON, "text"=plain text)"""

    t0 = time.time()

    model_id = _resolve(model)

    spec = _spec(model)

    if "vision" not in spec.get("caps", []):

        return f"[CAPABILITY] {model_id} lacks vision capability"

    # cache

    ck = _cache_key("analyze", image_path, question, model_id)

    cached = _cache_rw(ck)

    if cached:

        _audit(tool="analyze_image", model=model_id, inputTokens=0, outputTokens=0,

               costUsd=0, latencyMs=int((time.time()-t0)*1000), cached=True)

        return cached["content"]

    # read

    try:

        fsize = os.path.getsize(image_path)

        if fsize > 15 * 1024 * 1024:

            return f"[INVALID_INPUT] Image too large ({fsize/1024/1024:.1f}MB). Max: 15MB. Please resize."

        with open(image_path, "rb") as f:

            b64 = base64.b64encode(f.read()).decode()

        mime = _mime_type(image_path)

    except FileNotFoundError:

        return f"[INVALID_INPUT] File not found: {image_path}"

    except Exception as e:

        return f"[READ_ERROR] {e}"

    # cost cap check

    max_cost = float(os.getenv("VISION_MAX_COST_USD", "0.50"))

    est_cost = _estimate_cost(model_id, 3000, 2000)

    if est_cost > max_cost:

        return f"[COST_CAP] Estimated ${est_cost:.4f} exceeds limit ${max_cost:.2f}. Set VISION_MAX_COST_USD higher."

    # api call

    prompt = _make_prompt(question)

    body = {

        "model": model_id,

        "messages": [{"role":"user","content":[

            {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}},

            {"type":"text","text":prompt}

        ]}],

        "max_tokens": 2000 if format == "text" else 4000

    }

    try:

        r = _api("/compatible-mode/v1/chat/completions", body, timeout=90)

        content = _safe_content(r)

    except RuntimeError as e:

        _audit(tool="analyze_image", model=model_id, inputTokens=0, outputTokens=0,

               costUsd=0, latencyMs=int((time.time()-t0)*1000), cached=False, error=str(e))

        return str(e)

    # Try structured JSON parsing for json/auto modes

    parsed_json = None

    if format in ("json", "auto"):

        parsed_json = _parse_json_response(content)

    in_tok = r.get("usage",{}).get("prompt_tokens", 500)

    out_tok = r.get("usage",{}).get("completion_tokens", len(content)//4 if content else 0)

    # warn if truncated

    trunc_warn = ""

    if r.get("choices",[{}])[0].get("finish_reason","") == "length":

        trunc_warn = " [WARNING: response truncated, increase max_tokens]"

    cost = _estimate_cost(model_id, in_tok, out_tok)

    total_ms = int((time.time()-t0)*1000)

    if content.startswith("[ERROR:") or content.startswith("[WARNING:"):

        pass  # never cache error/warning responses

    else:

        _cache_rw(ck, {"content": content})

    _audit(tool="analyze_image", model=model_id, inputTokens=in_tok, outputTokens=out_tok,

           costUsd=round(cost,6), latencyMs=total_ms, cached=False)

    # Build output

    footer = f"\n\n---\n_{model_id} · {in_tok}↑{out_tok}↓ · ${cost:.4f} · {total_ms}ms_"

    if parsed_json:

        result = json.dumps(parsed_json, ensure_ascii=False, indent=2)

        return result + footer

    if format == "json":

        return f"[JSON_PARSE_FAILED] Model did not return valid JSON. Raw response:\n\n{content}{trunc_warn}{footer}"

    return f"{content}{trunc_warn}{footer}"

@mcp.tool()

def qwen_chat(prompt: str, model: str = "fast", system: str = "") -> str:

    """Chat with text model. Aliases: smart/fast/cheap."""

    model_id = _resolve(model)

    messages = []

    if system: messages.append({"role":"system","content":system})

    messages.append({"role":"user","content":prompt})

    try:

        r = _api("/compatible-mode/v1/chat/completions",

                 {"model":model_id,"messages":messages,"max_tokens":2000})

        content = _safe_content(r)

        _audit(tool="qwen_chat", model=model_id,

               inputTokens=r.get("usage",{}).get("prompt_tokens",0),

               outputTokens=r.get("usage",{}).get("completion_tokens",0),

               costUsd=round(_estimate_cost(model_id,

                   r.get("usage",{}).get("prompt_tokens",0),

                   r.get("usage",{}).get("completion_tokens",0)),6),

               cached=False)

        return content

    except RuntimeError as e:

        return str(e)

@mcp.tool()

def qwen_embed(text: str, model: str = "embed") -> str:

    """Get text embeddings."""

    model_id = _resolve(model)

    try:

        r = _api("/compatible-mode/v1/embeddings", {"model":model_id,"input":text})

        emb = r["data"][0]["embedding"]

        return f"Dim: {len(emb)}  [{', '.join(f'{x:.4f}' for x in emb[:8])} ...]"

    except RuntimeError as e:

        return str(e)

@mcp.tool()

def list_models() -> str:

    """List available models, aliases, and capabilities."""

    lines = [f"Provider: {PROVIDER}", "", "=== Aliases ==="]

    for a, m in sorted(CFG["aliases"].items()):

        lines.append(f"  {a:14s} -> {m}")

    lines += ["", "=== Models ==="]

    for m, s in sorted(CFG["models"].items()):

        caps = ",".join(s.get("caps",[]))

        ctx = f"{s.get('ctx',0)//1024}k"

        lines.append(f"  {m:30s} [{caps:15s}] ctx:{ctx}")

    return "\n".join(lines)

@mcp.tool()

def audit_log(lines: int = 20) -> str:

    """Show recent API call history with costs and latency."""

    if not AUDIT_LOG.exists(): return "No audit log yet."

    entries = []

    for l in open(AUDIT_LOG):

        if l.strip():

            try: entries.append(json.loads(l.strip()))

            except: pass

    entries = entries[-lines:]

    out = [f"Last {len(entries)} calls:", ""]

    total = 0

    for e in entries:

        ts = e.get("ts","")[:19]; tool = e.get("tool","?")

        m = e.get("model","?"); cost = e.get("costUsd",0)

        lat = e.get("latencyMs",0); c = " [CACHED]" if e.get("cached") else ""

        err = f" ERR:{e.get('error','')}" if e.get("error") else ""

        out.append(f"  {ts} | {tool:14s} | {m:20s} | ${cost:.4f} | {lat}ms{c}{err}")

        total += cost

    out += ["", f"Total: ${total:.4f}"]

    return "\n".join(out)

def main():

    """Entry point for vision-bridge MCP server."""

    mcp.run()

if __name__ == "__main__":

    main()

