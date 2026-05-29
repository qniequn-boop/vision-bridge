"""vision CLI v3.0 — auto-compress + connection pooling"""
import base64, sys, os, json, io, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


PROVIDER = os.getenv("VISION_PROVIDER", "qwen")
CFG = {
    "qwen":  {"base":"https://dashscope.aliyuncs.com","key_env":"DASHSCOPE_API_KEY","vision":"qwen3.6-plus"},
    "openai": {"base":"https://api.openai.com","key_env":"OPENAI_API_KEY","vision":"gpt-4o-mini"}
}
def analyze(p, up=None):
    """Analyze image with vision model."""
    cfg = CFG.get(PROVIDER, CFG["qwen"])
    k = os.getenv(cfg["key_env"])
    if not k: return "ERROR: set " + cfg["key_env"]
    try:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return "ERROR: " + p + " not found"
    ext = os.path.splitext(p)[1].lower()
    mime = {"png":"image/png","jpg":"image/jpeg","jpeg":"image/jpeg","webp":"image/webp","gif":"image/gif","bmp":"image/bmp"}.get(ext,"image/jpeg")
    body = {"model":cfg["vision"],"messages":[{"role":"user","content":[
        {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}},
        {"type":"text","text": up or "Analyze this image meticulously. If engineering drawing: read every dimension, hole spec, tolerance. If screenshot: read all text. If photo: identify object and material. Do NOT miss small details or peripheral elements."}
    ]}],"max_tokens":2000}
    req = Request(f"{cfg['base']}/compatible-mode/v1/chat/completions", data=json.dumps(body).encode(),
                  headers={"Content-Type":"application/json","Authorization":"Bearer "+k,"Connection":"keep-alive"})
    try:
        r = json.loads(urlopen(req, timeout=120).read())
        return r["choices"][0]["message"]["content"]
    except HTTPError as e:
        eb = {}
        try: eb = json.loads(e.read())
        except: pass
        return f"API ERROR [{e.code}]: {eb.get('error',{}).get('message',str(e))}"
def main():
    """CLI entry point for vision-bridge."""
    if len(sys.argv)<2: print("usage: vision-cli <image> [prompt]")
    else: print(analyze(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else None))

if __name__ == "__main__":
    main()
