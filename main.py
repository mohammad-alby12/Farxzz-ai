import json, re, time, subprocess, shutil, base64, io, os
from pathlib import Path
import psutil
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import config, database as db
from ai.model_manager import mm
from ai import cloud

db.init()
app = FastAPI(title="Farxzz AI", docs_url=None, redoc_url=None)
if config.CORS:
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS, allow_methods=["*"], allow_headers=["*"])
hits = {}

@app.middleware("http")
async def rate_limit(req: Request, call):
    ip = req.client.host if req.client else "?"; t = time.time()
    h = [x for x in hits.get(ip, []) if t - x < 60] + [t]; hits[ip] = h
    if len(h) > 300 and req.url.path.startswith("/api"):
        return JSONResponse({"detail": "Terlalu banyak request"}, 429)
    return await call(req)

SYSTEM = "Kamu adalah Farxzz AI, asisten yang berjalan lokal. Jawab dalam bahasa yang dipakai pengguna. Jika tidak tahu atau teks tidak terbaca, katakan terus terang."
IMAGES = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED = {".txt", ".md", ".docx", ".csv", ".json", ".py", ".js", ".ts", ".html", ".css", ".pdf"}

def parse(name, data):
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        import fitz
        with fitz.open(stream=data, filetype="pdf") as d: return "\n".join(p.get_text() for p in d)
    if ext == ".docx":
        import io, docx
        return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="replace")

def retrieve(text, query, n=3, size=1500):
    chunks = [text[i:i + size] for i in range(0, len(text), size)]
    if len(chunks) <= n: return text
    qw = set(re.findall(r"\w+", query.lower()))
    best = sorted(chunks, key=lambda c: -len(qw & set(re.findall(r"\w+", c.lower()))))[:n]
    return "\n...\n".join(best)

class Chat(BaseModel):
    conversation_id: str
    message: str = Field(max_length=20000)
    files: list[str] = []
    images: list[str] = []
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(1024, ge=16, le=4096)

@app.post("/api/chat/stream")
def chat(b: Chat):
    imgs = [r[0]["data"] for i in b.images if (r := db.q("select data from images where id=?", (i,)))]
    if imgs and not (mm.vlm or mm.cloud):
        raise HTTPException(409, "Vision model belum tersedia. Pilih atau pasang model multimodal terlebih dahulu.")
    use_cloud = bool(mm.cloud)
    llm = mm.vlm if imgs else (mm.llm or mm.vlm)
    if not (use_cloud or llm): raise HTTPException(409, "Model belum terpasang. Buka Model Hub untuk memasang model.")
    c = db.q("select * from conversations where id=?", (b.conversation_id,))
    if not c: raise HTTPException(404, "Percakapan tidak ditemukan")
    ctx = ""
    for fid in b.files:
        r = db.q("select name,text from files where id=?", (fid,))
        if r: ctx += f"\n[File: {r[0]['name']}]\n{retrieve(r[0]['text'], b.message)}\n"
    db.q("insert into messages values(?,?,?,?,?)", (db.uid(), b.conversation_id, "user", b.message, db.now()))
    if c[0]["title"] == "Chat baru":
        db.q("update conversations set title=? where id=?", (b.message[:40], b.conversation_id))
    hist = db.q("select role,content from messages where conv_id=? order by ts,rowid", (b.conversation_id,))[-20:]
    if ctx: hist[-1]["content"] = f"{ctx}\n{b.message}"
    if imgs:
        hist[-1]["content"] = [{"type": "text", "text": hist[-1]["content"]}] + [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + d}} for d in imgs]
    msgs = [{"role": "system", "content": SYSTEM}] + hist
    mm.cancel.clear()

    def gen():
        out = []
        try:
            for t in (cloud.stream(mm.cloud, msgs, b.max_tokens, mm.cancel) if use_cloud else mm.stream(llm, msgs, b.temperature, b.max_tokens)):
                out.append(t); yield "data: " + json.dumps({"t": t}) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"
        finally:
            if out: db.q("insert into messages values(?,?,?,?,?)", (db.uid(), b.conversation_id, "assistant", "".join(out), db.now()))
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")

@app.post("/api/chat/stop")
def stop(): mm.cancel.set(); return {"ok": True}

@app.get("/api/conversations")
def convs(): return db.q("select * from conversations order by favorite desc, created desc")

@app.post("/api/conversations")
def new_conv():
    i = db.uid(); db.q("insert into conversations values(?,?,?,?)", (i, "Chat baru", 0, db.now())); return {"id": i}

@app.get("/api/conversations/{cid}")
def get_conv(cid: str):
    c = db.q("select * from conversations where id=?", (cid,))
    if not c: raise HTTPException(404, "Tidak ditemukan")
    return {**c[0], "messages": db.q("select id,role,content from messages where conv_id=? order by ts,rowid", (cid,))}

class Patch(BaseModel):
    title: str | None = Field(None, max_length=120); favorite: bool | None = None

@app.patch("/api/conversations/{cid}")
def patch_conv(cid: str, p: Patch):
    if p.title is not None: db.q("update conversations set title=? where id=?", (p.title, cid))
    if p.favorite is not None: db.q("update conversations set favorite=? where id=?", (int(p.favorite), cid))
    return {"ok": True}

@app.delete("/api/conversations/{cid}")
def del_conv(cid: str):
    db.q("delete from messages where conv_id=?", (cid,)); db.q("delete from conversations where id=?", (cid,)); return {"ok": True}

@app.get("/api/models")
def models():
    ready = bool(cloud.key())
    extra = [{"id": m["id"], "name": m["name"], "kind": "Cloud", "note": m["note"],
              "status": "Loaded" if mm.cloud == m["id"] else ("Ready" if ready else "No API key")} for m in cloud.MODELS]
    return mm.list() + extra

class ModelReq(BaseModel): id: str

@app.post("/api/models/download")
def m_dl(r: ModelReq):
    try: mm.download(r.id)
    except KeyError as e: raise HTTPException(404, str(e))
    return {"ok": True}

@app.post("/api/models/load")
def m_load(r: ModelReq):
    if any(m["id"] == r.id for m in cloud.MODELS):
        if not cloud.key(): raise HTTPException(409, "API key Anthropic belum diatur. Isi ANTHROPIC_API_KEY di .env.")
        mm.cloud = r.id; return {"ok": True}
    f = next((m["file"] for m in mm.list() if m["id"] == r.id), None)
    if not f: raise HTTPException(404, "Model tidak dikenal")
    try: mm.load(f)
    except FileNotFoundError as e: raise HTTPException(409, str(e))
    except Exception as e: raise HTTPException(500, f"Gagal memuat model: {e}")
    return {"ok": True}

@app.post("/api/models/unload")
def m_unload(): mm.unload(); return {"ok": True}

@app.post("/api/files/upload")
async def upload(file: UploadFile = File(...)):
    name = Path(file.filename or "file").name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED | IMAGES: raise HTTPException(415, "Tipe file tidak didukung")
    data = await file.read(config.MAX_UPLOAD + 1)
    if len(data) > config.MAX_UPLOAD: raise HTTPException(413, "File terlalu besar")
    if ext in IMAGES:
        from PIL import Image
        try:
            im = Image.open(io.BytesIO(data)); im.load(); im = im.convert("RGB"); im.thumbnail((1600, 1600))
        except Exception: raise HTTPException(422, "Gambar tidak dapat dibaca")
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=90)
        i = db.uid(); db.q("insert into images values(?,?,?,?)", (i, name, base64.b64encode(buf.getvalue()).decode(), db.now()))
        return {"id": i, "name": name, "kind": "image", "size": list(im.size)}
    try: text = parse(name, data)
    except Exception as e: raise HTTPException(422, f"File tidak dapat dibaca: {e}")
    if not text.strip(): raise HTTPException(422, "Tidak ada teks yang dapat diambil dari file")
    i = db.uid(); db.q("insert into files values(?,?,?,?)", (i, name, text, db.now()))
    return {"id": i, "name": name, "kind": "file", "chars": len(text)}

@app.post("/api/images/ocr")
def ocr(r: ModelReq):
    if not shutil.which("tesseract"):
        raise HTTPException(409, "OCR belum tersedia: Tesseract belum terpasang di server (lihat README).")
    row = db.q("select data from images where id=?", (r.id,))
    if not row: raise HTTPException(404, "Gambar tidak ditemukan")
    import pytesseract
    from PIL import Image
    im = Image.open(io.BytesIO(base64.b64decode(row[0]["data"])))
    d = pytesseract.image_to_data(im, lang=os.getenv("OCR_LANG", "eng"), output_type=pytesseract.Output.DICT)
    lines = {}
    for k, w in enumerate(d["text"]):
        if not w.strip(): continue
        key = (d["block_num"][k], d["par_num"][k], d["line_num"][k])
        lines.setdefault(key, []).append(w if float(d["conf"][k]) >= 60 else "[tidak terbaca]")
    text = "\n".join(" ".join(v) for v in lines.values())
    note = "Tesseract hanya andal untuk teks cetak. Untuk tulisan tangan, pakai model vision."
    return {"text": text, "note": note}

def gpu():
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=3).stdout.strip().splitlines()[0].split(", ")
        return {"name": o[0], "vram_used_mb": int(o[1]), "vram_total_mb": int(o[2])}
    except Exception: return None

@app.get("/api/system")
def system():
    m = psutil.virtual_memory()
    return {"cpu": psutil.cpu_percent(interval=0.2), "ram_used": m.used, "ram_total": m.total, "gpu": gpu(),
            "disk_free": shutil.disk_usage(config.MODEL_DIR).free, "active_model": mm.active}

@app.get("/api/health")
def health(): return {"ok": True}

if config.DEFAULT_TEXT_MODEL:
    try: mm.load(config.DEFAULT_TEXT_MODEL)
    except Exception as e: print("Default model gagal dimuat:", e)

app.mount("/", StaticFiles(directory=config.ROOT / "frontend", html=True), name="ui")
