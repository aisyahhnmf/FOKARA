
import csv
import json
import os
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv
from supabase import create_client


# =====================================================
# CONFIGURATION
# =====================================================

ROOT = Path(__file__).resolve().parent

CSV_PATH = ROOT / "data_analyst_llm" / "data" / "question_bank.csv"
ENV_PATH = ROOT / "backend" / ".env"

load_dotenv(ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_URL atau SUPABASE_SECRET_KEY "
        "tidak ditemukan di backend/.env"
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# =====================================================
# READ AND VALIDATE CSV
# =====================================================

def load_questions():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CSV tidak ditemukan: {CSV_PATH}"
        )

    with CSV_PATH.open(
        encoding="utf-8-sig",
        newline=""
    ) as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if len(rows) != 47:
        raise ValueError(
            f"Jumlah pertanyaan harus 47, ditemukan {len(rows)}"
        )

    required_columns = {
        "question_id",
        "question_type",
        "role",
        "experience_level",
        "stage",
        "topic",
        "difficulty",
        "question",
        "expected_elements",
        "reference_context",
    }

    if not required_columns.issubset(reader.fieldnames or []):
        raise ValueError("Kolom CSV tidak lengkap.")

    ids = [row["question_id"].strip() for row in rows]

    if len(set(ids)) != 47:
        raise ValueError("Terdapat ID pertanyaan duplikat.")

    if any(not question_id for question_id in ids):
        raise ValueError("Ada question_id kosong.")

    allowed_roles = {
        "Data Analyst",
        "Data Scientist",
        "Data Engineer",
    }

    level_counts = Counter()
    general_count = 0
    technical_count = 0

    payload = []

    for row in rows:
        question_id = row["question_id"].strip()
        question_type = row["question_type"].strip().lower()
        role = row["role"].strip() or None
        level = row["experience_level"].strip() or None
        topic = row["topic"].strip() or None
        stage = row["stage"].strip() or None
        difficulty = row["difficulty"].strip() or None
        question_text = row["question"].strip()

        if not question_text:
            raise ValueError(
                f"Pertanyaan kosong: {question_id}"
            )

        try:
            elements = json.loads(row["expected_elements"])
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Expected elements tidak valid: {question_id}"
            ) from error

        if (
            not isinstance(elements, list)
            or not elements
            or not all(isinstance(item, str) for item in elements)
        ):
            raise ValueError(
                f"Expected elements harus berupa array string: {question_id}"
            )

        if question_type == "general":
            general_count += 1

            if role is not None or level is not None:
                raise ValueError(
                    f"Pertanyaan general harus tanpa role dan level: {question_id}"
                )

        elif question_type == "technical":
            technical_count += 1

            if role not in allowed_roles:
                raise ValueError(
                    f"Role tidak valid: {question_id} - {role}"
                )

            if level not in {
                "Beginner",
                "Intermediate",
                "Advanced",
            }:
                raise ValueError(
                    f"Level tidak valid: {question_id} - {level}"
                )

            level_counts[(role, level)] += 1

        else:
            raise ValueError(
                f"Question type tidak dikenal: {question_id}"
            )

        # Pemetaan ke tabel question_bank.
        payload.append({
            "external_id": question_id,
            "role": role,
            "question_text": question_text,
            "category": topic,
            "difficulty": difficulty,
            "is_active": True,
            "question_type": question_type,
            "experience_level": level,
            "stage": stage,
            "topic": topic,
            "expected_elements": elements,
            "reference_context": (
                row["reference_context"].strip() or None
            ),
            # Kompatibilitas dengan struktur lama.
            "competency": topic,
            "expected_evidence": "; ".join(elements),
        })

    if general_count != 2 or technical_count != 45:
        raise ValueError(
            "Komposisi pertanyaan tidak sesuai: "
            f"general={general_count}, technical={technical_count}"
        )

    for role in allowed_roles:
        for level in ("Beginner", "Intermediate", "Advanced"):
            count = level_counts[(role, level)]

            if count != 5:
                raise ValueError(
                    f"{role} - {level}: seharusnya 5, ditemukan {count}"
                )

    return payload


# =====================================================
# IMPORT TO SUPABASE
# =====================================================

def import_questions(payload):
    question_ids = [
        item["external_id"]
        for item in payload
    ]

    print("\nMemulai import ke Supabase...")

    # Batch 10 data agar proses lebih mudah dikontrol.
    for start in range(0, len(payload), 10):
        batch = payload[start:start + 10]

        response = (
            supabase.table("question_bank")
            .upsert(
                batch,
                on_conflict="external_id"
            )
            .execute()
        )

        print(
            f"Batch {start // 10 + 1}: "
            f"{len(batch)} data berhasil dikirim."
        )

    # Verifikasi semua ID sudah tersedia.
    result = (
        supabase.table("question_bank")
        .select("external_id")
        .in_("external_id", question_ids)
        .execute()
    )

    found_ids = {
        item["external_id"]
        for item in (result.data or [])
    }

    missing_ids = set(question_ids) - found_ids

    if missing_ids:
        raise RuntimeError(
            "Verifikasi gagal. ID belum ditemukan: "
            + ", ".join(sorted(missing_ids))
        )

    print("\nIMPORT BERHASIL!")
    print("Total pertanyaan terverifikasi:", len(found_ids))
    print("General:", 2)
    print("Technical:", 45)


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    questions = load_questions()

    print("======================================")
    print(" FOKARA - QUESTION BANK IMPORT")
    print("======================================")
    print("CSV:", CSV_PATH)
    print("Total pertanyaan:", len(questions))
    print("General:", sum(
        q["question_type"] == "general"
        for q in questions
    ))
    print("Technical:", sum(
        q["question_type"] == "technical"
        for q in questions
    ))
    print("Metode: UPSERT berdasarkan external_id")
    print("Pertanyaan lama tidak dihapus.")
    print("======================================")

    confirmation = input(
        "\nKetik IMPORT untuk melanjutkan: "
    ).strip()

    if confirmation != "IMPORT":
        print("\nImport dibatalkan. Database tidak diubah.")
    else:
        import_questions(questions)
