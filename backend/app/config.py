
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Membaca .env lokal.
# Di Render, environment variables akan dibaca langsung dari server.
load_dotenv(BASE_DIR / ".env")

# ==========================================
# SUPABASE CONFIGURATION
# ==========================================

SUPABASE_URL = os.getenv("SUPABASE_URL")

SUPABASE_SECRET_KEY = (
    os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# ==========================================
# GROQ CONFIGURATION
# ==========================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

GROQ_STT_MODEL = os.getenv(
    "GROQ_STT_MODEL",
    "whisper-large-v3"
)

# ==========================================
# API CONFIGURATION
# ==========================================

API_HOST = os.getenv("API_HOST", "0.0.0.0")

try:
    API_PORT = int(
        os.getenv("PORT") or os.getenv("API_PORT", "8000")
    )
except (TypeError, ValueError):
    raise ValueError(
        "PORT atau API_PORT harus berupa angka."
    )

# ==========================================
# VALIDATION
# ==========================================

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise ValueError(
        "Konfigurasi Supabase belum lengkap. "
        "Periksa SUPABASE_URL dan SUPABASE_SECRET_KEY."
    )
