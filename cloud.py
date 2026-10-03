import os, json, httpx

# Optional cloud models. Requests go to Anthropic, so the UI marks them clearly.
MODELS = [
    {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5", "api": "claude-haiku-4-5-20251001", "note": "Cloud · paling hemat"},
    {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5", "api": "claude-sonnet-5-5", "note": "Cloud · seimbang"},
    {"id": "claude-opus-5-5", "name": "Claude Opus 5.5", "api": "claude-opus-5-5", "note": "Cloud · terbaik, paling mahal"},
]

def key(): return os.getenv("ANTHROPIC_API_KEY", "")

def _content(c):
    if isinstance(c, str): return c
    out = []
    for p in c:
        if p["type"] == "text": out.append(p)
        else:
            out.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": p["image_url"]["url"].split(",", 1)[1]}})
    return out

def stream(mid, msgs, max_tokens, cancel):
    api = next(m["api"] for m in MODELS if m["id"] == mid)
    body = {"model": api, "max_tokens": max_tokens, "stream": True, "system": msgs[0]["content"],
            "messages": [{"role": m["role"], "content": _content(m["content"])} for m in msgs[1:]]}
    h = {"x-api-key": key(), "anthropic-version": "2023-06-01", "content-type": "application/json"}
    with httpx.stream("POST", "https://api.anthropic.com/v1/messages", json=body, headers=h,
                      timeout=httpx.Timeout(60, read=120)) as r:
        if r.status_code != 200:
            r.read()
            try: detail = r.json()["error"]["message"]
            except Exception: detail = r.text[:200]
            raise RuntimeError(f"Anthropic API {r.status_code}: {detail}")
        for line in r.iter_lines():
            if cancel.is_set(): break
            if line.startswith("data: "):
                d = json.loads(line[6:])
                if d.get("type") == "content_block_delta" and d["delta"].get("type") == "text_delta":
                    yield d["delta"]["text"]
