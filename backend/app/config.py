"""
Pair-03 configuration.

Derived values per the lab spec:
  PAIR        = 03
  PORT_BASE   = 9000 + (PAIR * 10) = 9030
  DB/Kafka prefix = p03
  SEED        = 3  (used by the seed generator and any random_state)
  CITY_SET    = San Jose, Santa Clara, Fremont

Backend runs on PORT_BASE (9030). Frontend dev server conventionally runs on
PORT_BASE + 1 (9031) — agree this with your teammate so the two of you don't
collide on ports when running both halves locally.
"""
import os

PAIR = 3
PAIR_STR = f"{PAIR:02d}"  # "03"
PORT_BASE = 9000 + (PAIR * 10)  # 9030
DB_PREFIX = f"p{PAIR_STR}"  # "p03"
SEED = PAIR  # 3
CITY_SET = ["San Jose", "Santa Clara", "Fremont"]

# --- Database ---
# Override any of these with environment variables in a real run; defaults
# assume a local MySQL instance with a database named p03_handshake.
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", f"{DB_PREFIX}_handshake")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# --- Auth ---
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-before-submission-p03")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 24h token lifetime

# --- File uploads ---
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
RESUME_DIR = os.path.join(UPLOAD_DIR, "resumes")
PROFILE_PIC_DIR = os.path.join(UPLOAD_DIR, "profile_pics")
MAX_PROFILE_PIC_BYTES = 5 * 1024 * 1024  # 5 MB

# --- AI assistant ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
AGENT_MAX_ITERATIONS = 6  # hard iteration ceiling for the tool-use loop
