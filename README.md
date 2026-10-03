# Farxzz AI

Chat + analisis dokumen yang berjalan lokal (FastAPI + llama.cpp). Secara default tidak ada API key AI eksternal: internet hanya dipakai untuk mengunduh file model dari Hugging Face, dan chat/file tidak dikirim ke mana pun. Satu pengecualian opsional: model Claude (cloud), di bawah.

## Jalankan
1. Python 3.10+
2. `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
3. `pip install -r requirements.txt` (llama-cpp-python dikompilasi; untuk GPU NVIDIA lihat dokumentasinya, mis. `CMAKE_ARGS="-DGGML_CUDA=on"`)
4. `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
5. Buka http://localhost:8000 → **Model & sistem** → Unduh → Muat.

Model manual: taruh file `.gguf` di `models/`, lalu muat dari panel. Opsional env: `MODEL_DIRECTORY`, `DEFAULT_TEXT_MODEL` (nama file .gguf, dimuat saat start), `CONTEXT_LENGTH`, `N_GPU_LAYERS`, `MAX_UPLOAD_MB`, `CORS_ORIGINS`.

## Upload dokumen
Klik 📎 (PDF, TXT, MD, DOCX, CSV, JSON, PY, JS, TS, HTML, CSS). Teks diekstrak di server, dipotong per chunk, dan potongan paling relevan dikirim ke model lokal.

## Rekomendasi model (perkiraan, sesuaikan dengan hardware Anda)
RAM rendah: model 1–2B Q4. RAM sedang: 3–8B Q4. GPU: pilih ukuran yang muat di VRAM. Cek ukuran file dan RAM kosong di panel sebelum memuat.

## Gambar, vision, dan OCR
- **Vision:** unduh *LLaVA 1.5 7B (vision)* di panel model (±4,7 GB: model + proyektor gambar), lalu Muat. Lampirkan JPG/PNG/WEBP dan tanyakan apa saja. Model vision dan model teks bisa dimuat bersamaan; jika hanya vision yang dimuat, chat teks memakainya juga. Butuh RAM cukup untuk model 7B.
- **OCR:** pasang Tesseract di sistem (`apt install tesseract-ocr`, Windows: installer UB-Mannheim), opsional `OCR_LANG=eng+ind` bila paket bahasanya terpasang. Kata dengan keyakinan rendah ditulis `[tidak terbaca]`. Tesseract hanya andal untuk teks cetak.
- **Tulisan tangan:** tombol *Baca tulisan tangan* meminta model vision mentranskripsi dan menandai bagian yang tidak terbaca. LLaVA 1.5 kurang akurat untuk tulisan tangan; hasilnya perlu dicek manual.

## Model Claude (opsional, berbayar, cloud)
Buat `.env` di folder utama: `ANTHROPIC_API_KEY=sk-ant-...` lalu restart. Di panel model muncul Claude Haiku 4.5 (paling hemat), Sonnet 5.5, dan Opus 5.5 (terbaik, paling mahal). **Chat dan gambar dikirim ke Anthropic** saat model ini aktif dan ditagih sesuai harga API mereka (cek halaman pricing Anthropic). Key hanya dipakai di server, tidak pernah dikirim ke browser. Tanpa key, entri ini tidak bisa dipilih.

## Belum ada
Akun/kredit/pembayaran untuk pengguna lain, memori persisten, mode kode dengan syntax highlighting, command palette, halaman pengaturan, regenerate/edit pesan, dan pencarian chat.
