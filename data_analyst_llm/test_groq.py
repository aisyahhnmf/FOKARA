
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import os

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("API key tidak ditemukan")
    raise SystemExit

client = Groq(api_key=api_key)

try:
    print("Menguji koneksi ke Groq...")

    models = client.models.list()

    print("Koneksi Groq berhasil!")
    print("Daftar model yang tersedia:")

    for model in models.data[:10]:
        print("-", model.id)

except Exception as e:
    print("Koneksi Groq gagal.")
    print(type(e).__name__, e)
