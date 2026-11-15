
import traceback

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends

from app.database import supabase
from app.auth import get_current_participant


router = APIRouter(
    prefix="/api",
    tags=["Interview History"]
)


# =====================================================
# HELPER
# =====================================================

def safe_float(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def parse_datetime(value):
    if not value:
        return None

    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed

    except (TypeError, ValueError):
        return None


def get_session_timestamp(session):
    """
    Mengambil timestamp sesi dengan fallback.
    """
    for column in [
        "started_at",
        "created_at",
        "ended_at",
        "completed_at",
        "finished_at",
        "end_time"
    ]:
        value = session.get(column)

        if value and parse_datetime(value):
            return value

    return None


# =====================================================
# VALIDASI KRITERIA EVALUASI
# =====================================================

EXPECTED_CRITERIA_COUNT = 5


def get_criterion(criteria_map, criterion_id):
    """
    Mengambil kriteria dengan aman, baik ID berupa string
    maupun tipe lain.
    """
    criterion = criteria_map.get(criterion_id)

    if criterion:
        return criterion

    return criteria_map.get(str(criterion_id), {})


def get_criterion_max_score(criterion, score_item=None):
    max_score = safe_float(
        (criterion or {}).get("max_score"),
        safe_float(
            (score_item or {}).get("max_score"),
            4.0
        )
    )

    return max_score if max_score > 0 else 4.0


def get_complete_rubric_scores(scores, criteria_map):
    """
    Hanya menerima evaluasi yang memiliki tepat lima kriteria
    dengan nilai lengkap dan valid.
    """

    if not isinstance(scores, list):
        return []

    if len(criteria_map) != EXPECTED_CRITERIA_COUNT:
        return []

    if len(scores) != EXPECTED_CRITERIA_COUNT:
        return []

    expected_ids = {
        str(criterion_id)
        for criterion_id in criteria_map.keys()
    }

    scores_by_criterion = {}

    for item in scores:
        criterion_id = item.get("criterion_id")

        if criterion_id is None:
            return []

        criterion_key = str(criterion_id)

        if criterion_key not in expected_ids:
            return []

        if criterion_key in scores_by_criterion:
            return []

        criterion = get_criterion(
            criteria_map,
            criterion_id
        )

        if not criterion:
            return []

        raw_score = item.get("score")

        if raw_score is None:
            return []

        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            return []

        if score < 0:
            return []

        max_score = get_criterion_max_score(
            criterion,
            item
        )

        if score > max_score:
            return []

        weight = safe_float(
            criterion.get("weight"),
            0
        )

        if weight <= 0:
            return []

        scores_by_criterion[criterion_key] = item

    if set(scores_by_criterion.keys()) != expected_ids:
        return []

    complete_scores = []

    for criterion_id in criteria_map.keys():
        item = scores_by_criterion.get(
            str(criterion_id)
        )

        if not item:
            return []

        complete_scores.append(item)

    return complete_scores


def get_active_scores(
    evaluation,
    llm_scores,
    legacy_scores,
    criteria_map
):
    """
    Menentukan sumber skor yang boleh digunakan.

    Jika evaluasi LLM sudah ada:
    - Gunakan skor LLM hanya jika lengkap.
    - Jika tidak lengkap, jangan gunakan skor parsial.
    - Jangan fallback ke rubric_scores lama.

    Jika evaluasi LLM belum ada:
    - Boleh menggunakan rubric_scores lama,
      tetapi tetap harus lengkap.
    """

    if evaluation:
        complete_scores = get_complete_rubric_scores(
            llm_scores,
            criteria_map
        )

        if complete_scores:
            return complete_scores, "llm"

        return [], None

    complete_scores = get_complete_rubric_scores(
        legacy_scores,
        criteria_map
    )

    if complete_scores:
        return complete_scores, "rubric"

    return [], None


def enrich_scores(scores, criteria_map):
    """
    Menambahkan bobot kriteria ke setiap skor.
    """

    enriched = []

    for item in scores:
        criterion = get_criterion(
            criteria_map,
            item.get("criterion_id")
        )

        enriched.append({
            **item,
            "weight_percent": (
                safe_float(criterion.get("weight")) * 100
            )
        })

    return enriched


# =====================================================
# PERHITUNGAN DURASI
# =====================================================

def calculate_duration_seconds(session, fallback_end=None):
    stored_duration = session.get("duration_seconds")

    if stored_duration is not None:
        try:
            return max(0, int(float(stored_duration)))
        except (TypeError, ValueError):
            pass

    start_time = parse_datetime(
        session.get("started_at")
        or session.get("created_at")
    )

    if not start_time:
        return None

    end_time = None

    for column in [
        "ended_at",
        "completed_at",
        "finished_at",
        "end_time"
    ]:
        end_time = parse_datetime(session.get(column))

        if end_time:
            break

    if not end_time:
        end_time = parse_datetime(fallback_end)

    if not end_time:
        return None

    return max(
        0,
        int((end_time - start_time).total_seconds())
    )


# =====================================================
# COMPUTER VISION DATA FETCHING
# =====================================================

def fetch_cv_observations(
    session_ids=None,
    session_id=None,
    select_columns="*",
    page_size=500
):
    """
    Mengambil seluruh observasi CV menggunakan pagination.

    Bisa digunakan untuk:
    - Banyak sesi sekaligus melalui session_ids.
    - Satu sesi tertentu melalui session_id.

    Data diambil per halaman agar tidak terpotong
    oleh batas jumlah baris Supabase.
    """

    if not session_id and not session_ids:
        return []

    if page_size < 1:
        raise ValueError("page_size harus lebih besar dari 0.")

    all_observations = []
    offset = 0

    while True:
        query = (
            supabase.table("cv_observations")
            .select(select_columns)
        )

        if session_id:
            query = query.eq(
                "session_id",
                session_id
            )
        else:
            query = query.in_(
                "session_id",
                session_ids
            )

        query = (
            query
            .order("timestamp_seconds")
            .order("id")
            .range(
                offset,
                offset + page_size - 1
            )
        )

        response = query.execute()
        page_data = response.data or []

        all_observations.extend(page_data)

        print(
            f"[CV PAGINATION] "
            f"Offset: {offset}, "
            f"Data diterima: {len(page_data)}, "
            f"Total sementara: {len(all_observations)}"
        )

        if len(page_data) < page_size:
            break

        offset += page_size

    return all_observations


def log_cv_summary(session_id, summary):
    """
    Menampilkan jumlah observasi CV per indikator
    pada terminal backend.
    """

    print(
        f"\n[CV SUMMARY] Session: {session_id}"
    )

    for indicator, data in summary.items():
        label_count = sum(
            data["labels"].values()
        )

        print(
            f"  {indicator}: "
            f"total={data['total']}, "
            f"valid={data['valid']}, "
            f"invalid={data['invalid']}, "
            f"labels={label_count}, "
            f"status={data['status']}"
        )


# =====================================================
# COMPUTER VISION SUMMARY
# =====================================================

def build_cv_summary(observations):
    indicators = [
        "head_motion",
        "gaze",
        "expression"
    ]

    summary = {}

    for indicator in indicators:
        rows = [
            item for item in observations
            if item.get("indicator_type") == indicator
        ]

        valid_rows = [
            item for item in rows
            if item.get("is_valid") is True
        ]

        confidences = [
            safe_float(item.get("confidence"))
            for item in valid_rows
            if item.get("confidence") is not None
        ]

        labels = {}

        for item in valid_rows:
            label = item.get("predicted_label")

            if label:
                labels[label] = labels.get(label, 0) + 1

        summary[indicator] = {
            "total": len(rows),
            "valid": len(valid_rows),
            "invalid": len(rows) - len(valid_rows),
            "labels": labels,
            "average_confidence": (
                round(
                    sum(confidences) / len(confidences),
                    4
                )
                if confidences else None
            ),
            "status": (
                "available" if valid_rows
                else "unavailable"
            )
        }

    return summary


def build_session_cv_metrics(observations):
    summary = build_cv_summary(observations)

    gaze_data = summary["gaze"]

    gaze_percentage = None

    if gaze_data["total"] > 0:
        gaze_percentage = round(
            gaze_data["valid"] / gaze_data["total"] * 100,
            2
        )

    neutral_labels = {
        "normal",
        "neutral",
        "center",
        "centre",
        "forward",
        "straight",
        "front",
        "none",
        "no_movement",
        "no movement"
    }

    head_motion_events = 0

    for item in observations:
        if (
            item.get("indicator_type") != "head_motion"
            or item.get("is_valid") is not True
        ):
            continue

        label = str(
            item.get("predicted_label") or ""
        ).strip().lower()

        if label and label not in neutral_labels:
            head_motion_events += 1

    return {
        "gaze_percentage": gaze_percentage,
        "head_motion_count": head_motion_events,
        "cv_summary": summary,
        "total_cv_observations": len(observations)
    }


# =====================================================
# PERHITUNGAN PERFORMA
# =====================================================

def calculate_performance(scores, criteria_map):
    total_weight = 0
    weighted_percentage = 0

    for item in scores:
        criterion = get_criterion(
            criteria_map,
            item.get("criterion_id")
        )

        weight = safe_float(
            item.get("weight_percent"),
            safe_float(criterion.get("weight")) * 100
        )

        score = safe_float(item.get("score"))

        max_score = get_criterion_max_score(
            criterion,
            item
        )

        if weight <= 0 or max_score <= 0:
            continue

        normalized_score = (
            score / max_score
        ) * 100

        total_weight += weight
        weighted_percentage += normalized_score * weight

    if total_weight <= 0:
        return None

    return round(
        weighted_percentage / total_weight,
        2
    )


# =====================================================
# BATCH HELPER
# =====================================================

def group_by(items, key):
    grouped = {}

    for item in items:
        value = item.get(key)

        if value is not None:
            grouped.setdefault(value, []).append(item)

    return grouped


def get_last_answer_at(answers):
    timestamps = [
        parse_datetime(item.get("created_at"))
        for item in answers
        if item.get("created_at")
    ]

    timestamps = [
        item for item in timestamps
        if item is not None
    ]

    if not timestamps:
        return None

    return max(timestamps).isoformat()


def get_batch_session_performance(
    session,
    questions_by_session,
    answers_by_question,
    rubric_by_answer,
    evaluations_by_answer,
    scores_by_evaluation,
    criteria_map
):
    session_id = session["id"]

    questions = questions_by_session.get(
        session_id,
        []
    )

    question_ids = [
        item["id"] for item in questions
    ]

    answers = []

    for question_id in question_ids:
        answers.extend(
            answers_by_question.get(
                question_id,
                []
            )
        )

    result = {
        "session_id": session_id,
        "attempt_number": session.get("attempt_number") or 1,
        "started_at": get_session_timestamp(session),
        "last_answer_at": get_last_answer_at(answers),
        "score": None,
        "total_questions": len(question_ids),
        "total_answers": len(answers),
        "evaluated_questions": 0
    }

    if not answers:
        return result

    all_scores = []
    evaluated_question_ids = set()

    for answer in answers:
        answer_id = answer["id"]
        question_id = answer.get("session_question_id")

        evaluation = evaluations_by_answer.get(
            answer_id
        )

        llm_scores = []

        if evaluation:
            llm_scores = scores_by_evaluation.get(
                evaluation["id"],
                []
            )

        legacy_scores = rubric_by_answer.get(
            answer_id,
            []
        )

        current_scores, source = get_active_scores(
            evaluation,
            llm_scores,
            legacy_scores,
            criteria_map
        )

        if not current_scores:
            continue

        if question_id:
            evaluated_question_ids.add(question_id)

        all_scores.extend(
            enrich_scores(
                current_scores,
                criteria_map
            )
        )

    result["evaluated_questions"] = len(
        evaluated_question_ids
    )

    result["score"] = calculate_performance(
        all_scores,
        criteria_map
    )

    return result


# =====================================================
# GET /api/sessions
# OPTIMIZED: BATCH QUERY
# =====================================================

@router.get("/sessions")
def get_sessions(
    participant=Depends(get_current_participant)
):
    try:
        participant_id = participant["id"]

        print(
            f"\n[HISTORY] Mengambil sesi participant: "
            f"{participant_id}"
        )

        # 1. AMBIL SEMUA SESI

        sessions_response = (
            supabase.table("interview_sessions")
            .select("*")
            .eq("participant_id", participant_id)
            .order("started_at", desc=True)
            .execute()
        )

        sessions = sessions_response.data or []

        if not sessions:
            return {
                "success": True,
                "total": 0,
                "data": []
            }

        session_ids = [
            item["id"] for item in sessions
        ]

        # 2. DATA PESERTA

        participants_response = (
            supabase.table("participants")
            .select("id, name, external_id")
            .eq("id", participant_id)
            .execute()
        )

        participant_map = {
            item["id"]: item
            for item in (participants_response.data or [])
        }

        # 3. KRITERIA RUBRIK

        criteria_response = (
            supabase.table("rubric_criteria")
            .select("*")
            .execute()
        )

        criteria_map = {
            item["id"]: item
            for item in (criteria_response.data or [])
        }

        # 4. SEMUA PERTANYAAN SESI

        questions_response = (
            supabase.table("session_questions")
            .select("id, session_id")
            .in_("session_id", session_ids)
            .execute()
        )

        questions = questions_response.data or []

        questions_by_session = group_by(
            questions,
            "session_id"
        )

        question_ids = [
            item["id"] for item in questions
        ]

        # 5. SEMUA JAWABAN

        answers = []

        if question_ids:
            answers_response = (
                supabase.table("answers")
                .select(
                    "id, session_question_id, created_at"
                )
                .in_(
                    "session_question_id",
                    question_ids
                )
                .execute()
            )

            answers = answers_response.data or []

        answers_by_question = group_by(
            answers,
            "session_question_id"
        )

        answer_ids = [
            item["id"] for item in answers
        ]

        # 6. SEMUA SKOR RUBRIK LAMA

        rubric_scores = []

        if answer_ids:
            rubric_response = (
                supabase.table("rubric_scores")
                .select("*")
                .in_("answer_id", answer_ids)
                .execute()
            )

            rubric_scores = rubric_response.data or []

        rubric_by_answer = group_by(
            rubric_scores,
            "answer_id"
        )

        # 7. SEMUA EVALUASI LLM

        llm_evaluations = []

        if answer_ids:
            llm_response = (
                supabase.table("llm_evaluations")
                .select("*")
                .in_("answer_id", answer_ids)
                .execute()
            )

            llm_evaluations = llm_response.data or []

        evaluations_by_answer = {
            item["answer_id"]: item
            for item in llm_evaluations
        }

        evaluation_ids = [
            item["id"] for item in llm_evaluations
        ]

        # 8. SEMUA SKOR EVALUASI LLM

        llm_scores = []

        if evaluation_ids:
            llm_scores_response = (
                supabase.table("llm_evaluation_scores")
                .select("*")
                .in_("evaluation_id", evaluation_ids)
                .execute()
            )

            llm_scores = llm_scores_response.data or []

        scores_by_evaluation = group_by(
            llm_scores,
            "evaluation_id"
        )

        # 9. SEMUA OBSERVASI COMPUTER VISION
        # Menggunakan pagination agar tidak terpotong.

        cv_observations = []

        if session_ids:
            cv_observations = fetch_cv_observations(
                session_ids=session_ids,
                select_columns=(
                    "id, session_id, timestamp_seconds, "
                    "indicator_type, is_valid, confidence, "
                    "predicted_label"
                )
            )

        cv_by_session = group_by(
            cv_observations,
            "session_id"
        )

        print(
            f"\n[HISTORY CV] "
            f"Total observasi CV terbaca: "
            f"{len(cv_observations)}"
        )

        # 10. SUSUN HASIL
        # Sesi tanpa jawaban tidak ditampilkan.

        results = []

        for session in sessions:
            session_id = session["id"]

            session_questions = questions_by_session.get(
                session_id,
                []
            )

            has_answers = any(
                answers_by_question.get(question["id"])
                for question in session_questions
            )

            if not has_answers:
                continue

            try:
                performance = get_batch_session_performance(
                    session,
                    questions_by_session,
                    answers_by_question,
                    rubric_by_answer,
                    evaluations_by_answer,
                    scores_by_evaluation,
                    criteria_map
                )

                session_observations = cv_by_session.get(
                    session_id,
                    []
                )

                cv_metrics = build_session_cv_metrics(
                    session_observations
                )

                log_cv_summary(
                    session_id,
                    cv_metrics["cv_summary"]
                )

                participant_data = participant_map.get(
                    session.get("participant_id")
                )

                duration_seconds = calculate_duration_seconds(
                    session,
                    performance.get("last_answer_at")
                )

                results.append({
                    **session,

                    "started_at": get_session_timestamp(session),

                    "participant": participant_data,

                    "duration_seconds": duration_seconds,

                    "rubric_score": performance.get("score"),

                    "gaze_percentage": (
                        cv_metrics["gaze_percentage"]
                    ),

                    "head_motion_count": (
                        cv_metrics["head_motion_count"]
                    ),

                    "performance": performance,

                    "cv_summary": cv_metrics["cv_summary"],

                    "total_cv_observations": (
                        cv_metrics["total_cv_observations"]
                    )
                })

            except Exception as error:
                print(
                    f"[HISTORY SESSION ERROR] "
                    f"{session_id}: {error}"
                )
                traceback.print_exc()

                results.append({
                    **session,

                    "participant": participant_map.get(
                        session.get("participant_id")
                    ),

                    "duration_seconds": calculate_duration_seconds(
                        session
                    ),

                    "rubric_score": None,
                    "gaze_percentage": None,
                    "head_motion_count": None,
                    "performance": None,
                    "cv_summary": None,
                    "total_cv_observations": 0
                })

        print(
            f"[HISTORY] Selesai. Total sesi: {len(results)}"
        )

        return {
            "success": True,
            "total": len(results),
            "data": results
        }

    except Exception as error:
        print("[GET SESSIONS ERROR]")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal mengambil daftar sesi: "
                f"{str(error)}"
            )
        )


# =====================================================
# RIWAYAT PERFORMA UNTUK DETAIL LAPORAN
# =====================================================

def get_session_performance(session, criteria_map):
    session_id = session["id"]

    result = {
        "session_id": session_id,
        "attempt_number": session.get("attempt_number") or 1,
        "started_at": get_session_timestamp(session),
        "last_answer_at": None,
        "score": None,
        "total_questions": 0,
        "total_answers": 0,
        "evaluated_questions": 0
    }

    # 1. PERTANYAAN SESI

    questions_response = (
        supabase.table("session_questions")
        .select("id")
        .eq("session_id", session_id)
        .execute()
    )

    questions = questions_response.data or []

    question_ids = [
        item["id"] for item in questions
    ]

    result["total_questions"] = len(question_ids)

    if not question_ids:
        return result

    # 2. JAWABAN

    answers_response = (
        supabase.table("answers")
        .select("*")
        .in_("session_question_id", question_ids)
        .execute()
    )

    answers = answers_response.data or []

    result["total_answers"] = len(answers)

    result["last_answer_at"] = get_last_answer_at(
        answers
    )

    answer_ids = [
        item["id"] for item in answers
    ]

    if not answer_ids:
        return result

    # 3. RUBRIC SCORES LAMA

    rubric_response = (
        supabase.table("rubric_scores")
        .select("*")
        .in_("answer_id", answer_ids)
        .execute()
    )

    rubric_scores = rubric_response.data or []

    # 4. EVALUASI LLM

    llm_response = (
        supabase.table("llm_evaluations")
        .select("*")
        .in_("answer_id", answer_ids)
        .execute()
    )

    llm_evaluations = llm_response.data or []

    evaluation_ids = [
        item["id"] for item in llm_evaluations
    ]

    # 5. DETAIL SKOR LLM

    llm_scores = []

    if evaluation_ids:
        llm_scores_response = (
            supabase.table("llm_evaluation_scores")
            .select("*")
            .in_("evaluation_id", evaluation_ids)
            .execute()
        )

        llm_scores = llm_scores_response.data or []

    # 6. KELOMPOKKAN DATA

    evaluation_by_answer = {
        item["answer_id"]: item
        for item in llm_evaluations
    }

    scores_by_evaluation = group_by(
        llm_scores,
        "evaluation_id"
    )

    rubric_by_answer = group_by(
        rubric_scores,
        "answer_id"
    )

    # 7. HITUNG NILAI DAN JUMLAH PERTANYAAN DIEVALUASI

    all_scores = []
    evaluated_question_ids = set()

    for answer in answers:
        answer_id = answer["id"]
        question_id = answer.get("session_question_id")

        evaluation = evaluation_by_answer.get(
            answer_id
        )

        current_llm_scores = []

        if evaluation:
            current_llm_scores = scores_by_evaluation.get(
                evaluation["id"],
                []
            )

        legacy_scores = rubric_by_answer.get(
            answer_id,
            []
        )

        current_scores, source = get_active_scores(
            evaluation,
            current_llm_scores,
            legacy_scores,
            criteria_map
        )

        if not current_scores:
            continue

        if question_id:
            evaluated_question_ids.add(question_id)

        all_scores.extend(
            enrich_scores(
                current_scores,
                criteria_map
            )
        )

    result["evaluated_questions"] = len(
        evaluated_question_ids
    )

    result["score"] = calculate_performance(
        all_scores,
        criteria_map
    )

    return result


# =====================================================
# GET PERFORMANCE HISTORY
# =====================================================

def get_performance_history(session, criteria_map):
    participant_id = session.get("participant_id")
    role = session.get("role")
    experience_level = session.get("experience_level")

    if not participant_id:
        return []

    # Ambil semua sesi milik peserta yang sama.

    query = (
        supabase.table("interview_sessions")
        .select("*")
        .eq("participant_id", participant_id)
    )

    # Riwayat hanya untuk role yang sama.

    if role:
        query = query.eq("role", role)

    history_response = query.execute()

    all_history_sessions = history_response.data or []

    # Sesi dengan level yang sama tetap masuk.
    # Sesi lama dengan level NULL juga disertakan.

    history_sessions = [
        item for item in all_history_sessions
        if (
            item.get("experience_level") == experience_level
            or item.get("experience_level") is None
        )
    ]

    performance_history = []

    # Hitung performa setiap sesi.

    for history_session in history_sessions:
        try:
            performance = get_session_performance(
                history_session,
                criteria_map
            )

            # Sesi tanpa jawaban bukan percobaan.

            if performance.get("total_answers", 0) <= 0:
                continue

            performance["duration_seconds"] = (
                calculate_duration_seconds(
                    history_session,
                    performance.get("last_answer_at")
                )
            )

            performance_history.append(performance)

        except Exception as error:
            print(
                "[PERFORMANCE HISTORY ERROR] "
                f"Sesi {history_session.get('id')}: {error}"
            )
            traceback.print_exc()

    # Pastikan sesi yang sedang dibuka ikut masuk.

    current_session_id = session["id"]

    existing_ids = {
        item["session_id"]
        for item in performance_history
    }

    if current_session_id not in existing_ids:
        try:
            current_performance = get_session_performance(
                session,
                criteria_map
            )

            if current_performance.get("total_answers", 0) > 0:
                current_performance["duration_seconds"] = (
                    calculate_duration_seconds(
                        session,
                        current_performance.get("last_answer_at")
                    )
                )

                performance_history.append(
                    current_performance
                )

        except Exception as error:
            print(
                "[PERFORMANCE HISTORY ERROR] "
                f"Sesi aktif {current_session_id}: {error}"
            )
            traceback.print_exc()

    # Urutkan berdasarkan waktu sesi.

    def history_sort_key(item):
        timestamp = parse_datetime(
            item.get("started_at")
        )

        if timestamp is None:
            timestamp = datetime.min.replace(
                tzinfo=timezone.utc
            )

        return (
            timestamp,
            str(item.get("session_id") or "")
        )

    performance_history.sort(
        key=history_sort_key
    )

    # Nomor percobaan berdasarkan sesi yang memiliki jawaban.

    for index, item in enumerate(
        performance_history,
        start=1
    ):
        item["attempt_number"] = index

    return performance_history


# =====================================================
# GET /api/sessions/{session_id}
# DETAIL LAPORAN
# =====================================================

@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: str,
    participant=Depends(get_current_participant),
):
    try:
        print(
            f"\n[REPORT] Mengambil detail sesi: {session_id}"
        )

        # 1. DATA SESI

        session_response = (
            supabase.table("interview_sessions")
            .select("*")
            .eq("id", session_id)
            .eq("participant_id", participant["id"])
            .maybe_single()
            .execute()
        )

        session_data = session_response.data

        if not session_data:
            raise HTTPException(
                status_code=404,
                detail="Sesi wawancara tidak ditemukan."
            )

        participant_id = session_data.get(
            "participant_id"
        )

        # 2. PERTANYAAN

        questions_response = (
            supabase.table("session_questions")
            .select("*")
            .eq("session_id", session_id)
            .order("question_order")
            .execute()
        )

        question_data = questions_response.data or []

        question_ids = [
            question["id"]
            for question in question_data
        ]

        # 3. PESERTA

        participant_data = None

        if participant_id:
            participant_response = (
                supabase.table("participants")
                .select("*")
                .eq("id", participant_id)
                .maybe_single()
                .execute()
            )

            participant_data = participant_response.data

        # 4. JAWABAN

        answers_data = []

        if question_ids:
            answers_response = (
                supabase.table("answers")
                .select("*")
                .in_(
                    "session_question_id",
                    question_ids
                )
                .execute()
            )

            answers_data = answers_response.data or []

        answer_ids = [
            answer["id"]
            for answer in answers_data
        ]

        # 5. RUBRIC SCORES LAMA

        rubric_data = []

        if answer_ids:
            rubric_response = (
                supabase.table("rubric_scores")
                .select("*")
                .in_("answer_id", answer_ids)
                .execute()
            )

            rubric_data = rubric_response.data or []

        # 6. EVALUASI LLM

        llm_evaluations_data = []

        if answer_ids:
            llm_response = (
                supabase.table("llm_evaluations")
                .select("*")
                .in_("answer_id", answer_ids)
                .execute()
            )

            llm_evaluations_data = llm_response.data or []

        evaluation_ids = [
            item["id"]
            for item in llm_evaluations_data
        ]

        # 7. DETAIL SKOR LLM

        llm_scores_data = []

        if evaluation_ids:
            llm_scores_response = (
                supabase.table("llm_evaluation_scores")
                .select("*")
                .in_("evaluation_id", evaluation_ids)
                .execute()
            )

            llm_scores_data = (
                llm_scores_response.data or []
            )

        # 8. KRITERIA

        criteria_response = (
            supabase.table("rubric_criteria")
            .select("*")
            .execute()
        )

        criteria_map = {
            item["id"]: item
            for item in (criteria_response.data or [])
        }

        # 9. COMPUTER VISION
        # Ambil semua observasi berdasarkan session_id.
        # Jangan membatasi berdasarkan session_question_id
        # agar ringkasan tingkat sesi konsisten dengan
        # endpoint GET /api/sessions.

        cv_observations_data = fetch_cv_observations(
            session_id=session_id,
            select_columns="*"
        )

        print(
            f"\n[REPORT CV] "
            f"Session: {session_id}, "
            f"Total observasi: "
            f"{len(cv_observations_data)}"
        )

        # 10. MAP JAWABAN

        answer_map = {
            item["session_question_id"]: item
            for item in answers_data
        }

        # 11. MAP RUBRIK

        rubric_map = {}

        for item in rubric_data:
            answer_id = item["answer_id"]

            criterion = get_criterion(
                criteria_map,
                item.get("criterion_id")
            )

            weight = safe_float(
                (criterion or {}).get("weight")
            )

            rubric_map.setdefault(
                answer_id,
                []
            ).append({
                **item,
                "weight_percent": weight * 100,
                "criterion": criterion
            })

        # 12. MAP SKOR LLM

        llm_score_map = {}

        for item in llm_scores_data:
            evaluation_id = item["evaluation_id"]

            criterion = get_criterion(
                criteria_map,
                item.get("criterion_id")
            )

            weight = safe_float(
                (criterion or {}).get("weight")
            )

            llm_score_map.setdefault(
                evaluation_id,
                []
            ).append({
                **item,
                "weight_percent": weight * 100,
                "criterion": criterion
            })

        # 13. MAP EVALUASI LLM

        llm_evaluation_map = {}

        for evaluation in llm_evaluations_data:
            evaluation_id = evaluation["id"]

            llm_evaluation_map[
                evaluation["answer_id"]
            ] = {
                **evaluation,
                "scores": llm_score_map.get(
                    evaluation_id,
                    []
                )
            }

        # 14. MAP OBSERVASI CV PER PERTANYAAN

        cv_observation_map = {}

        for item in cv_observations_data:
            question_id = item.get(
                "session_question_id"
            )

            # Observasi tanpa session_question_id
            # tetap masuk ringkasan sesi, tetapi tidak
            # dimasukkan ke ringkasan pertanyaan.

            if question_id is None:
                continue

            cv_observation_map.setdefault(
                question_id,
                []
            ).append(item)

        # 15. GABUNGKAN DATA PERTANYAAN

        detailed_questions = []

        for question in question_data:
            question_id = question["id"]

            answer = answer_map.get(question_id)

            answer_id = (
                answer["id"]
                if answer else None
            )

            old_scores = (
                rubric_map.get(answer_id, [])
                if answer_id else []
            )

            llm_evaluation = (
                llm_evaluation_map.get(answer_id)
                if answer_id else None
            )

            llm_scores = (
                llm_evaluation.get("scores", [])
                if llm_evaluation else []
            )

            # Hanya skor lengkap dan valid yang boleh digunakan.

            active_scores, evaluation_source = get_active_scores(
                llm_evaluation,
                llm_scores,
                old_scores,
                criteria_map
            )

            total_weight = 0
            weighted_score = 0
            weighted_percentage = 0

            for item in active_scores:
                criterion = get_criterion(
                    criteria_map,
                    item.get("criterion_id")
                )

                weight = safe_float(
                    item.get("weight_percent"),
                    safe_float(
                        criterion.get("weight")
                    ) * 100
                )

                score = safe_float(
                    item.get("score")
                )

                max_score = get_criterion_max_score(
                    criterion,
                    item
                )

                if weight <= 0 or max_score <= 0:
                    continue

                total_weight += weight

                weighted_score += (
                    score * (weight / 100)
                )

                weighted_percentage += (
                    (score / max_score) * 100
                ) * weight

            if evaluation_source == "llm":
                all_synthetic = llm_evaluation.get(
                    "is_synthetic"
                )

            elif evaluation_source == "rubric":
                all_synthetic = all(
                    item.get("is_synthetic") is True
                    for item in active_scores
                )

            else:
                all_synthetic = None

            review_status = list({
                item["review_status"]
                for item in old_scores
                if item.get("review_status")
            })

            cv_observations = cv_observation_map.get(
                question_id,
                []
            )

            cv_summary = build_cv_summary(
                cv_observations
            )

            cv_by_indicator = {
                "head_motion": [],
                "gaze": [],
                "expression": []
            }

            for observation in cv_observations:
                indicator = observation.get(
                    "indicator_type"
                )

                if indicator in cv_by_indicator:
                    cv_by_indicator[indicator].append(
                        observation
                    )

            detailed_questions.append({
                **question,

                "answer": answer,

                "rubric_scores": old_scores,

                "llm_evaluation": llm_evaluation,

                "active_rubric_scores": active_scores,

                "rubric_summary": {
                    "total_criteria": len(active_scores),

                    "total_weight": round(
                        total_weight / 100,
                        4
                    ),

                    "weighted_score": round(
                        weighted_score,
                        2
                    ),

                    "weighted_percentage": (
                        round(
                            weighted_percentage / total_weight,
                            2
                        )
                        if total_weight > 0 else None
                    ),

                    "all_synthetic": all_synthetic,

                    "review_status": review_status,

                    "evaluation_source": evaluation_source
                },

                "cv_observations": cv_observations,

                "cv_summary": cv_summary,

                "cv_by_indicator": cv_by_indicator,

                "cv_status": (
                    "completed" if cv_observations
                    else "unavailable"
                ),

                "cv_observation_count": len(
                    cv_observations
                )
            })

        # 16. RINGKASAN CV SESI

        total_cv_observations = len(
            cv_observations_data
        )

        session_cv_summary = build_cv_summary(
            cv_observations_data
        )

        log_cv_summary(
            session_id,
            session_cv_summary
        )

        # 17. DURASI SESI

        last_answer_at = get_last_answer_at(
            answers_data
        )

        duration_seconds = calculate_duration_seconds(
            session_data,
            last_answer_at
        )

        # 18. RIWAYAT PERFORMA

        performance_history = []

        try:
            performance_history = get_performance_history(
                session_data,
                criteria_map
            )

            # Samakan nomor percobaan pada laporan utama
            # dengan nomor urut pada riwayat performa.

            current_history = next(
                (
                    item
                    for item in performance_history
                    if item.get("session_id") == session_id
                ),
                None
            )

            if current_history:
                session_data["attempt_number"] = (
                    current_history["attempt_number"]
                )

        except Exception as history_error:
            print(
                "[PERFORMANCE HISTORY ERROR] "
                f"{history_error}"
            )
            traceback.print_exc()

        # 19. RESPONSE

        return {
            "success": True,

            "data": {
                "session": {
                    **session_data,

                    "started_at": get_session_timestamp(
                        session_data
                    ),

                    "duration_seconds": duration_seconds
                },

                "participant": participant_data,

                "questions": detailed_questions,

                "computer_vision": {
                    "status": session_data.get(
                        "cv_feature_status",
                        "unknown"
                    ),

                    "total_observations": (
                        total_cv_observations
                    ),

                    "summary": session_cv_summary
                },

                "performance_history": performance_history
            }
        }

    except HTTPException:
        raise

    except Exception as error:
        print(
            f"\n[ERROR DETAIL SESSION] {session_id}"
        )

        print(
            f"Jenis error: {type(error).__name__}"
        )

        print(
            f"Pesan error: {str(error)}"
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal mengambil detail sesi: "
                f"{str(error)}"
            )
        )
