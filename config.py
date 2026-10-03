import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
MODEL_DIR = Path(os.getenv("MODEL_DIRECTORY", ROOT / "models")).resolve()
DB_PATH = Path(os.getenv("DB_PATH", ROOT / "farxzz.db"))
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
CTX = int(os.getenv("CONTEXT_LENGTH", "4096"))
GPU_LAYERS = int(os.getenv("N_GPU_LAYERS", "-1"))  # ignored by CPU-only builds
DEFAULT_TEXT_MODEL = os.getenv("DEFAULT_TEXT_MODEL", "")  # filename inside MODEL_DIRECTORY
CORS = [o for o in os.getenv("CORS_ORIGINS", "").split(",") if o]
MODEL_DIR.mkdir(parents=True, exist_ok=True)
