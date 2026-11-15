
from fastapi import APIRouter, HTTPException, Depends

from app.database import supabase
from app.auth import get_current_participant


router = APIRouter(
    prefix="/api",
    tags=["Master Data"]
)


# ==========================================
# KONFIGURASI ROLE DAN EXPERIENCE LEVEL
# ==========================================

ROLE_CONFIG = {
    "Data Analyst": {
        "id": "data-analyst",
        "bidang": "Data & Analytics",
        "deskripsi": (
            "Mengolah data menjadi insight "
            "untuk mendukung pengambilan keputusan."
        )
    },
    "Data Engineer": {
        "id": "data-engineer",
        "bidang": "Data Engineering",
        "deskripsi": (
            "Merancang dan mengelola pipeline "
            "serta infrastruktur data."
        )
    },
    "Data Scientist": {
        "id": "data-scientist",
        "bidang": "Data Science & AI",
        "deskripsi": (
            "Menggunakan statistik dan machine learning "
            "untuk menghasilkan prediksi dan insight."
        )
    }
}

ROLE_SLUG_MAP = {
    config["id"]: role_name
    for role_name, config in ROLE_CONFIG.items()
}

EXPERIENCE_LEVELS = [
    "Beginner",
    "Intermediate",
    "Advanced"
]

QUESTION_TYPES = [
    "general",
    "technical"
]


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def normalize_role(role):
    """
    Menerima nama role maupun slug dari frontend.
    Mengembalikan nama role standar atau None.
    """

    if not isinstance(role, str):
        return None

    role = role.strip()

    if not role:
        return None

    if role in ROLE_CONFIG:
        return role

    return ROLE_SLUG_MAP.get(role.lower())


def normalize_experience_level(level):
    if not isinstance(level, str):
        return None

    level = level.strip().lower()

    for valid_level in EXPERIENCE_LEVELS:
        if valid_level.lower() == level:
            return valid_level

    return None


def normalize_question_type(question_type):
    if not isinstance(question_type, str):
        return None

    question_type = question_type.strip().lower()

    if question_type not in QUESTION_TYPES:
        return None

    return question_type


def map_question(question):
    """
    Menyamakan format pertanyaan database
    dengan format yang digunakan frontend.
    """

    return {
        "id": question.get("external_id"),
        "teks": question.get("question_text"),
        "kompetensi": (
            question.get("competency")
            or question.get("topic")
            or question.get("category")
        ),
        "kategori": (
            question.get("category")
            or question.get("topic")
        ),
        "jenis": question.get("question_type"),
        "difficulty": question.get("difficulty"),
        "experience_level": question.get("experience_level"),
        "stage": question.get("stage"),
        "topic": question.get("topic"),
        "expected_elements": (
            question.get("expected_elements") or []
        ),
        "reference_context": question.get("reference_context"),
        "expected_evidence": question.get("expected_evidence"),
        "followup_focus": question.get("followup_focus"),
        "kriteria": []
    }


def get_active_questions():
    response = (
        supabase.table("question_bank")
        .select(
            "id, external_id, role, question_text, "
            "category, difficulty, is_active, "
            "competency_id, competency, question_type, "
            "expected_evidence, followup_focus, "
            "experience_level, stage, topic, "
            "expected_elements, reference_context"
        )
        .eq("is_active", True)
        .order("external_id")
        .execute()
    )

    return response.data or []


# ==========================================
# 1. GET PARTICIPANTS
# ==========================================

@router.get("/participants")
def get_participants(
    participant=Depends(get_current_participant)
):
    try:
        response = (
            supabase.table("participants")
            .select("id, external_id, name, email, created_at")
            .eq("id", participant["id"])
            .order("name")
            .execute()
        )

        data = response.data or []

        return {
            "success": True,
            "total": len(data),
            "data": data
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil data peserta: {str(error)}"
        )


# ==========================================
# 2. GET QUESTIONS
# ==========================================

@router.get("/questions")
def get_questions(
    role: str = None,
    experience_level: str = None,
    question_type: str = None
):
    try:
        query = (
            supabase.table("question_bank")
            .select("*")
            .eq("is_active", True)
        )

        if role is not None:
            normalized_role = normalize_role(role)

            if not normalized_role:
                raise HTTPException(
                    status_code=400,
                    detail="Role tidak valid."
                )

            query = query.eq("role", normalized_role)

        if experience_level is not None:
            normalized_level = normalize_experience_level(
                experience_level
            )

            if not normalized_level:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Experience level harus Beginner, "
                        "Intermediate, atau Advanced."
                    )
                )

            query = query.eq(
                "experience_level",
                normalized_level
            )

        if question_type is not None:
            normalized_type = normalize_question_type(
                question_type
            )

            if not normalized_type:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Question type harus general "
                        "atau technical."
                    )
                )

            query = query.eq(
                "question_type",
                normalized_type
            )

        response = (
            query
            .order("external_id")
            .execute()
        )

        data = response.data or []

        return {
            "success": True,
            "total": len(data),
            "data": data
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil Question Bank: {str(error)}"
        )


# ==========================================
# 3. GET QUESTION SET
# 2 GENERAL + 5 TECHNICAL
# ==========================================

@router.get("/question-set")
def get_question_set(
    role: str,
    experience_level: str
):
    try:
        normalized_role = normalize_role(role)

        if not normalized_role:
            raise HTTPException(
                status_code=400,
                detail="Role tidak valid."
            )

        normalized_level = normalize_experience_level(
            experience_level
        )

        if not normalized_level:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Experience level harus Beginner, "
                    "Intermediate, atau Advanced."
                )
            )

        all_questions = get_active_questions()

        # ----------------------------------
        # 2 PERTANYAAN GENERAL
        # ----------------------------------

        general_questions = [
            question
            for question in all_questions
            if (
                (question.get("question_type") or "").lower()
                == "general"
                and question.get("role") is None
            )
        ]

        # ----------------------------------
        # 5 PERTANYAAN TECHNICAL
        # ----------------------------------

        technical_questions = [
            question
            for question in all_questions
            if (
                (question.get("question_type") or "").lower()
                == "technical"
                and question.get("role") == normalized_role
                and question.get("experience_level")
                == normalized_level
            )
        ]

        # ----------------------------------
        # VALIDASI JUMLAH
        # ----------------------------------

        if len(general_questions) != 2:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Question Bank harus memiliki tepat "
                    "2 pertanyaan general yang aktif. "
                    f"Ditemukan: {len(general_questions)}."
                )
            )

        if len(technical_questions) != 5:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Question Bank harus memiliki tepat "
                    "5 pertanyaan technical untuk "
                    f"{normalized_role} - {normalized_level}. "
                    f"Ditemukan: {len(technical_questions)}."
                )
            )

        # ----------------------------------
        # VALIDASI DATA PERTANYAAN
        # ----------------------------------

        selected_questions = (
            general_questions + technical_questions
        )

        question_ids = [
            question.get("external_id")
            for question in selected_questions
        ]

        if any(not question_id for question_id in question_ids):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Terdapat pertanyaan aktif yang "
                    "belum memiliki external_id."
                )
            )

        if len(set(question_ids)) != len(question_ids):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Terdapat external_id pertanyaan "
                    "yang duplikat dalam Question Bank."
                )
            )

        if any(
            not (question.get("question_text") or "").strip()
            for question in selected_questions
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Terdapat pertanyaan aktif yang "
                    "teksnya kosong."
                )
            )

        # ----------------------------------
        # URUTKAN PERTANYAAN
        # ----------------------------------

        general_questions.sort(
            key=lambda question: (
                question.get("external_id") or ""
            )
        )

        technical_questions.sort(
            key=lambda question: (
                question.get("external_id") or ""
            )
        )

        # ----------------------------------
        # GANTI PLACEHOLDER ROLE
        # ----------------------------------

        for question in general_questions:
            question_text = question.get("question_text") or ""

            question["question_text"] = question_text.replace(
                "{role}",
                normalized_role
            )

        selected_questions = (
            general_questions + technical_questions
        )

        mapped_questions = [
            map_question(question)
            for question in selected_questions
        ]

        return {
            "success": True,
            "role": normalized_role,
            "experience_level": normalized_level,
            "total": len(mapped_questions),
            "general_total": len(general_questions),
            "technical_total": len(technical_questions),
            "data": mapped_questions
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menyiapkan pertanyaan: {str(error)}"
        )


# ==========================================
# 4. GET RUBRIC CRITERIA
# ==========================================

@router.get("/rubric-criteria")
def get_rubric_criteria():
    try:
        response = (
            supabase.table("rubric_criteria")
            .select("*")
            .execute()
        )

        data = response.data or []

        return {
            "success": True,
            "total": len(data),
            "data": data
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil kriteria rubrik: {str(error)}"
        )


# ==========================================
# 5. GET ROLES
# ==========================================

@router.get("/roles")
def get_roles():
    try:
        response = (
            supabase.table("question_bank")
            .select(
                "external_id, role, question_text, category, "
                "competency, question_type, difficulty, "
                "expected_evidence, followup_focus"
            )
            .eq("is_active", True)
            .order("external_id")
            .execute()
        )

        grouped_roles = {
            role_name: []
            for role_name in ROLE_CONFIG
        }

        for question in response.data or []:
            role_name = question.get("role")

            if role_name not in grouped_roles:
                continue

            grouped_roles[role_name].append({
                "id": question.get("external_id"),
                "teks": question.get("question_text"),
                "kompetensi": (
                    question.get("competency")
                    or question.get("category")
                ),
                "kategori": question.get("category"),
                "jenis": question.get("question_type"),
                "difficulty": question.get("difficulty"),
                "expected_evidence": (
                    question.get("expected_evidence")
                ),
                "followup_focus": (
                    question.get("followup_focus")
                ),
                "kriteria": []
            })

        roles = []

        for role_name, config in ROLE_CONFIG.items():
            roles.append({
                **config,
                "nama": role_name,
                "soal": grouped_roles[role_name],
                "experience_levels": EXPERIENCE_LEVELS
            })

        return {
            "success": True,
            "total": len(roles),
            "data": roles
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil daftar role: {str(error)}"
        )
