
import logging
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.database import supabase
from app.auth import get_current_participant


router = APIRouter(
    prefix="/api",
    tags=["Interview Sessions"]
)

logger = logging.getLogger(__name__)


# ==========================================
# ROLE CONFIGURATION
# ==========================================

ROLE_MAP = {
    "data-analyst": "Data Analyst",
    "data-engineer": "Data Engineer",
    "data-scientist": "Data Scientist",
}

EXPERIENCE_LEVELS = [
    "Beginner",
    "Intermediate",
    "Advanced"
]


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def normalize_role(value):
    """
    Menormalisasi role dari slug maupun nama lengkap.
    """

    if not isinstance(value, str):
        return None

    value = value.strip()

    if value in ROLE_MAP.values():
        return value

    return ROLE_MAP.get(value.lower())


def normalize_experience_level(value):
    """
    Menormalisasi experience level.
    """

    if not isinstance(value, str):
        return None

    value = value.strip().lower()

    for level in EXPERIENCE_LEVELS:
        if level.lower() == value:
            return level

    return None


def get_next_attempt_number(participant_id, role, experience_level):
    """
    Menghitung nomor percobaan berdasarkan:
    - participant_id
    - role
    - experience_level

    Setiap kombinasi peserta, role, dan level
    mempunyai urutan percobaan masing-masing.
    """

    response = (
        supabase.table("interview_sessions")
        .select("id")
        .eq("participant_id", participant_id)
        .eq("role", role)
        .eq("experience_level", experience_level)
        .execute()
    )

    existing_sessions = response.data or []

    return len(existing_sessions) + 1


def get_selected_questions(role, experience_level):
    """
    Mengambil tepat:
    - 2 pertanyaan general
    - 5 pertanyaan technical sesuai role dan level

    Total: 7 pertanyaan.
    """

    response = (
        supabase.table("question_bank")
        .select(
            "id, external_id, role, question_text, "
            "competency_id, competency, question_type, "
            "experience_level, difficulty"
        )
        .eq("is_active", True)
        .order("external_id")
        .execute()
    )

    all_questions = response.data or []

    # --------------------------------------
    # GENERAL QUESTIONS
    # --------------------------------------

    general_questions = [
        question
        for question in all_questions
        if (
            (question.get("question_type") or "").lower()
            == "general"
            and question.get("role") is None
        )
    ]

    # --------------------------------------
    # TECHNICAL QUESTIONS
    # --------------------------------------

    technical_questions = [
        question
        for question in all_questions
        if (
            (question.get("question_type") or "").lower()
            == "technical"
            and question.get("role") == role
            and question.get("experience_level")
            == experience_level
        )
    ]

    # --------------------------------------
    # VALIDASI JUMLAH PERTANYAAN
    # --------------------------------------

    if len(general_questions) != 2:
        raise HTTPException(
            status_code=409,
            detail=(
                "Question Bank harus memiliki tepat "
                "2 pertanyaan general aktif. "
                f"Ditemukan: {len(general_questions)}."
            )
        )

    if len(technical_questions) != 5:
        raise HTTPException(
            status_code=409,
            detail=(
                "Question Bank harus memiliki tepat "
                "5 pertanyaan technical untuk "
                f"{role} - {experience_level}. "
                f"Ditemukan: {len(technical_questions)}."
            )
        )

    # --------------------------------------
    # URUTKAN PERTANYAAN
    # --------------------------------------

    general_questions.sort(
        key=lambda question: question.get("external_id") or ""
    )

    technical_questions.sort(
        key=lambda question: question.get("external_id") or ""
    )

    selected_questions = (
        general_questions + technical_questions
    )

    # --------------------------------------
    # VALIDASI DATA PERTANYAAN
    # --------------------------------------

    question_ids = [
        question.get("id")
        for question in selected_questions
    ]

    if any(not question_id for question_id in question_ids):
        raise HTTPException(
            status_code=409,
            detail="Terdapat pertanyaan tanpa ID yang valid."
        )

    if len(set(question_ids)) != 7:
        raise HTTPException(
            status_code=409,
            detail="Terdapat ID pertanyaan yang duplikat."
        )

    for question in selected_questions:

        question_text = (
            question.get("question_text") or ""
        ).strip()

        if not question_text:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Terdapat pertanyaan kosong "
                    "di dalam Question Bank."
                )
            )

        question["question_text"] = (
            question_text.replace("{role}", role)
        )

    return selected_questions


# ==========================================
# REQUEST MODEL
# ==========================================

class CreateSessionRequest(BaseModel):
    role: str
    experience_level: str
    pid: str | None = None

    # Opsional untuk kompatibilitas dengan frontend lama.
    # Nomor percobaan tetap dihitung oleh backend.
    attempt: int | None = Field(default=None, ge=1)


# ==========================================
# CREATE INTERVIEW SESSION
# ==========================================

@router.post("/sessions")
def create_session(
    payload: CreateSessionRequest,
    participant=Depends(get_current_participant),
):

    # --------------------------------------
    # 1. VALIDASI ROLE
    # --------------------------------------

    role = normalize_role(payload.role)

    if not role:
        raise HTTPException(
            status_code=400,
            detail="Role tidak valid."
        )

    # --------------------------------------
    # 2. VALIDASI EXPERIENCE LEVEL
    # --------------------------------------

    experience_level = normalize_experience_level(
        payload.experience_level
    )

    if not experience_level:
        raise HTTPException(
            status_code=400,
            detail=(
                "Experience level harus Beginner, "
                "Intermediate, atau Advanced."
            )
        )

    # --------------------------------------
    # 3. AMBIL PERTANYAAN
    # --------------------------------------

    try:
        selected_questions = get_selected_questions(
            role,
            experience_level
        )

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Gagal mengambil Question Bank untuk %s - %s",
            role,
            experience_level
        )

        raise HTTPException(
            status_code=500,
            detail="Terjadi kesalahan saat mengambil Question Bank."
        )

    # --------------------------------------
    # 4. BUAT IDENTITAS SESSION
    # --------------------------------------

    session_external_id = (
        f"{participant.get('external_id') or participant['id']}"
        f"-{uuid4().hex}"
    )

    session_id = None

    try:

        # Hitung nomor percobaan dari database.
        # Tidak menggunakan nomor dari frontend.

        attempt_number = get_next_attempt_number(
            participant_id=participant["id"],
            role=role,
            experience_level=experience_level
        )

        # ----------------------------------
        # 5. SIMPAN INTERVIEW SESSION
        # ----------------------------------

        session_data = {
            "external_id": session_external_id,
            "participant_id": participant["id"],
            "role": role,
            "experience_level": experience_level,
            "session_name": (
                f"{role} - {experience_level} "
                f"- Percobaan {attempt_number}"
            ),
            "status": "pending",
            "started_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "attempt_number": attempt_number,
            "is_synthetic": False,
        }

        session_result = (
            supabase.table("interview_sessions")
            .insert(session_data)
            .execute()
        )

        if not session_result.data:
            raise RuntimeError(
                "Gagal membuat interview session."
            )

        session = session_result.data[0]
        session_id = session["id"]

        # ----------------------------------
        # 6. SIAPKAN SESSION QUESTIONS
        # ----------------------------------

        session_questions = []

        for index, question in enumerate(
            selected_questions,
            start=1
        ):

            session_questions.append({
                "external_id": f"SQ-{uuid4().hex}",
                "session_id": session_id,
                "question_id": question["id"],
                "question_order": index,
                "question_text": question["question_text"],
                "competency_id": question.get("competency_id"),
                "competency": question.get("competency"),
                "question_type": question.get("question_type"),
                "difficulty": question.get("difficulty"),
                "is_synthetic": False,
            })

        # ----------------------------------
        # 7. SIMPAN SESSION QUESTIONS
        # ----------------------------------

        question_result = (
            supabase.table("session_questions")
            .insert(session_questions)
            .execute()
        )

        saved_questions = question_result.data or []

        if len(saved_questions) != 7:
            raise RuntimeError(
                "Jumlah pertanyaan tersimpan tidak sesuai. "
                f"Diharapkan 7, ditemukan {len(saved_questions)}."
            )

        # ----------------------------------
        # 8. URUTKAN HASIL
        # ----------------------------------

        saved_questions.sort(
            key=lambda question: question["question_order"]
        )

        # ----------------------------------
        # 9. RESPONSE
        # ----------------------------------

        return {
            "success": True,
            "session_id": session_id,
            "participant_id": participant["id"],
            "role": role,
            "experience_level": experience_level,
            "attempt": attempt_number,
            "attempt_number": attempt_number,
            "total_questions": len(saved_questions),
            "general_total": 2,
            "technical_total": 5,
            "questions": [
                {
                    "external_id": row["external_id"],
                    "session_question_id": row["id"],
                    "question_id": row["question_id"],
                    "question_order": row["question_order"],
                    "question_text": row["question_text"],
                    "question_type": row.get("question_type"),
                    "difficulty": row.get("difficulty"),
                }
                for row in saved_questions
            ],
        }

    except Exception:

        # ----------------------------------
        # 10. ROLLBACK
        # ----------------------------------

        if session_id:
            try:
                (
                    supabase.table("session_questions")
                    .delete()
                    .eq("session_id", session_id)
                    .execute()
                )

                (
                    supabase.table("interview_sessions")
                    .delete()
                    .eq("id", session_id)
                    .execute()
                )

            except Exception:
                logger.exception(
                    "Gagal melakukan rollback session %s",
                    session_id
                )

        logger.exception(
            "Gagal membuat interview session untuk %s - %s",
            role,
            experience_level
        )

        raise HTTPException(
            status_code=500,
            detail="Gagal membuat sesi interview. Periksa log backend."
        )
