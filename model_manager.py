import threading, gc, httpx
from config import MODEL_DIR, CTX, GPU_LAYERS

# Real GGUF releases on Hugging Face. Sizes are unknown until the server reports them.
CATALOG = [
    {"id": "qwen2.5-1.5b", "name": "Qwen2.5 1.5B Instruct", "kind": "General", "quant": "Q4_K_M",
     "repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF", "file": "qwen2.5-1.5b-instruct-q4_k_m.gguf"},
    {"id": "llava-1.5-7b", "name": "LLaVA 1.5 7B (vision)", "kind": "Vision", "quant": "Q4_K",
     "repo": "mys/ggml_llava-v1.5-7b", "file": "ggml-model-q4_k.gguf", "mmproj": "mmproj-model-f16.gguf"},
    {"id": "qwen2.5-coder-1.5b", "name": "Qwen2.5 Coder 1.5B Instruct", "kind": "Code", "quant": "Q4_K_M",
     "repo": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF", "file": "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"},
]

class Manager:
    def __init__(self):
        self.cloud = None; self.llm = self.vlm = None; self.active = self.vactive = None; self.loading = None; self.errors = {}
        self.dl = {}; self.cancel = threading.Event()
        self.infer = threading.Lock(); self.lock = threading.Lock()

    def path(self, name):
        p = (MODEL_DIR / name).resolve()
        if p.parent != MODEL_DIR: raise ValueError("Path model tidak valid")
        return p

    def list(self):
        local = {p.name: p.stat().st_size for p in MODEL_DIR.glob("*.gguf")}
        items = [dict(m) for m in CATALOG]
        known = {m["file"] for m in CATALOG}
        items += [{"id": f, "name": f, "kind": "Local", "file": f} for f in local if f not in known]
        for it in items:
            f = it["file"]; it["size"] = local.get(f)
            have = f in local and (not it.get("mmproj") or it["mmproj"] in local)
            if self.loading == f: it["status"] = "Loading"
            elif f in (self.active, self.vactive): it["status"] = "Loaded"
            elif have: it["status"] = "Downloaded"
            else: it["status"] = "Not Installed"
            if f in self.errors: it["status"], it["error"] = "Error", self.errors[f]
            if it["id"] in self.dl: it["download"] = self.dl[it["id"]]
        return items

    def download(self, mid):
        m = next((x for x in CATALOG if x["id"] == mid), None)
        if not m: raise KeyError("Model tidak ada di katalog")
        if self.dl.get(mid, {}).get("state") == "downloading": return
        self.dl[mid] = {"state": "downloading", "done": 0, "total": 0}
        threading.Thread(target=self._dl, args=(m,), daemon=True).start()

    def _dl(self, m):
        st = self.dl[m["id"]]
        try:
            for fn in [m["file"]] + ([m["mmproj"]] if m.get("mmproj") else []):
                if not self.path(fn).exists(): self._dl_file(st, m["repo"], fn)
            st["state"] = "done"
        except Exception as e:
            st.update(state="error", error=str(e))

    def _dl_file(self, st, repo, fn):
        part = self.path(fn + ".part"); url = f"https://huggingface.co/{repo}/resolve/main/{fn}"
        d0, t0 = st["done"], st["total"]
        if True:
            have = part.stat().st_size if part.exists() else 0  # resume from partial file
            with httpx.stream("GET", url, follow_redirects=True, timeout=30,
                              headers={"Range": f"bytes={have}-"} if have else {}) as r:
                r.raise_for_status()
                if r.status_code == 200: have = 0  # server ignored Range
                st.update(total=t0 + have + int(r.headers.get("content-length", 0)), done=d0 + have)
                with open(part, "ab" if have else "wb") as f:
                    for ch in r.iter_bytes(1 << 20):
                        f.write(ch); st["done"] += len(ch)
            part.rename(self.path(fn))

    def load(self, fname):
        p = self.path(fname)
        if not p.exists() or p.suffix != ".gguf": raise FileNotFoundError("Model belum terpasang.")
        with self.lock:
            self.loading = fname; self.errors.pop(fname, None)
            try:
                from llama_cpp import Llama
                m = next((x for x in CATALOG if x["file"] == fname), {})
                if m.get("mmproj"):
                    from llama_cpp.llama_chat_format import Llava15ChatHandler
                    h = Llava15ChatHandler(clip_model_path=str(self.path(m["mmproj"])))
                    self.vlm = None; gc.collect()
                    self.vlm = Llama(model_path=str(p), chat_handler=h, n_ctx=CTX, n_gpu_layers=GPU_LAYERS, verbose=False)
                    self.vactive = fname
                else:
                    self.llm = None; gc.collect()
                    self.llm = Llama(model_path=str(p), n_ctx=CTX, n_gpu_layers=GPU_LAYERS, verbose=False)
                    self.active = fname
            except Exception as e:
                self.errors[fname] = str(e); raise
            finally:
                self.loading = None

    def unload(self, keep_lock=False):
        self.cloud = None; self.llm = self.vlm = None; self.active = self.vactive = None; gc.collect()

    def stream(self, llm, msgs, temp, mx):
        with self.infer:  # llama.cpp contexts are not thread-safe
            for c in llm.create_chat_completion(messages=msgs, temperature=temp, max_tokens=mx, stream=True):
                if self.cancel.is_set(): break
                t = c["choices"][0]["delta"].get("content")
                if t: yield t

mm = Manager()
