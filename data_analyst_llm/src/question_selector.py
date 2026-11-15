import csv, json, random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "data" / "question_bank.csv"

def load_bank():
    with open(BANK_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def get_session_questions(role: str, level: str, seed: int = None):
    rows = load_bank()
    general = [r for r in rows if r["question_type"] == "general"]
    technical = [r for r in rows if r["question_type"] == "technical"
                 and r["role"] == role and r["experience_level"] == level]
    if len(general) != 2 or len(technical) < 5:
        raise ValueError("Question bank belum memenuhi komposisi 2 umum + 5 teknis.")
    # Urutan umum tetap; teknis dapat diacak dengan seed agar dapat direproduksi.
    rng = random.Random(seed)
    rng.shuffle(technical)
    selected = general + technical[:5]
    return selected

if __name__ == "__main__":
    for q in get_session_questions("Data Analyst", "Beginner", seed=42):
        print(q["question_id"], q["question"])
