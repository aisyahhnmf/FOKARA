
import { CONFIG } from "./config.js";
import { getAuthHeaders } from "./auth.js";
import { mockReport } from "./mock.js";

const mockJobs = {};

const API_BASE = (
  CONFIG.apiBase || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

// =====================================================
// GET QUESTION SET
// =====================================================

export async function getQuestionSet({
  role,
  experienceLevel
}) {
  if (!role || !experienceLevel) {
    throw new Error(
      "Role dan experience level harus dipilih."
    );
  }

  const params = new URLSearchParams({
    role,
    experience_level: experienceLevel,
  });

  const res = await fetch(
    `${API_BASE}/api/question-set?${params.toString()}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    }
  );

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(
      data.detail ||
      `Gagal mengambil pertanyaan (${res.status})`
    );
  }

  // Backend mengembalikan daftar pertanyaan
  // melalui properti "data", bukan "questions".
  const questions = Array.isArray(data.data)
    ? data.data
    : data.questions;

  if (
    !data.success ||
    !Array.isArray(questions) ||
    Number(data.total) !== 7 ||
    questions.length !== 7
  ) {
    console.error(
      "[QUESTION BANK RESPONSE]",
      data
    );

    throw new Error(
      `Question Bank tidak mengembalikan 7 pertanyaan. Jumlah diterima: ${
        Array.isArray(questions)
          ? questions.length
          : 0
      }.`
    );
  }

  // Samakan format agar frontend bisa memakai
  // questionSet.questions maupun questionSet.data.
  return {
    ...data,
    data: questions,
    questions,
  };
}

// =====================================================
// CREATE SESSION
// =====================================================

export async function createSession({
  role,
  pid,
  attempt,
  experienceLevel,
}) {
  if (!role) {
    throw new Error("Role belum dipilih.");
  }

  if (!experienceLevel) {
    throw new Error(
      "Experience level belum dipilih."
    );
  }

  const res = await fetch(
    `${API_BASE}/api/sessions`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(await getAuthHeaders()),
      },
      body: JSON.stringify({
        role,
        pid,
        attempt,
        experience_level: experienceLevel,
      }),
    }
  );

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(
      data.detail ||
      `Gagal membuat sesi (${res.status})`
    );
  }

  if (
    !data.session_id ||
    !Array.isArray(data.questions)
  ) {
    throw new Error(
      "Respons pembuatan sesi tidak lengkap."
    );
  }

  if (data.questions.length !== 7) {
    throw new Error(
      "Sesi tidak memiliki tepat 7 pertanyaan."
    );
  }

  const invalidQuestion = data.questions.some(
    (question) =>
      !question.session_question_id ||
      !question.question_text ||
      !question.question_order
  );

  if (invalidQuestion) {
    throw new Error(
      "Data pertanyaan sesi dari backend tidak lengkap."
    );
  }

  return data;
}

// =====================================================
// CREATE JOB
// =====================================================

export async function createJob({
  role,
  soal,
  blobs,
  bahasa = "id",
  attempt = 1,
  sessionId = null,
  sessionQuestions = [],
}) {
  if (CONFIG.mock) {
    const id =
      "demo" + Date.now().toString(36);

    mockJobs[id] = {
      t0: Date.now(),
      soal,
      attempt,
    };

    return id;
  }

  if (!sessionId) {
    throw new Error("Session ID tidak ditemukan.");
  }

  if (
    !Array.isArray(soal) ||
    !Array.isArray(blobs) ||
    !Array.isArray(sessionQuestions)
  ) {
    throw new Error(
      "Data pertanyaan atau video tidak valid."
    );
  }

  if (
    soal.length === 0 ||
    soal.length !== blobs.length ||
    soal.length !== sessionQuestions.length
  ) {
    throw new Error(
      "Jumlah pertanyaan, video, dan data pertanyaan sesi tidak sesuai."
    );
  }

  const questions = soal.map((s, i) => ({
    question_text: s.teks,
    question_external_id: s.id,
    session_question_id:
      sessionQuestions[i]?.session_question_id,
    question_order:
      sessionQuestions[i]?.question_order,
  }));

  const invalidQuestion = questions.some(
    (question) =>
      !question.question_text ||
      !question.question_external_id ||
      !question.session_question_id ||
      !question.question_order
  );

  if (invalidQuestion) {
    throw new Error(
      "Data pertanyaan tidak lengkap. ID pertanyaan sesi mungkin tidak ditemukan."
    );
  }

  const fd = new FormData();

  fd.append(
    "meta",
    JSON.stringify({
      session_id: sessionId,
      role,
      bahasa,
      attempt,
      questions,
    })
  );

  blobs.forEach((blob, i) => {
    fd.append(
      "videos",
      blob,
      `q${i + 1}.webm`
    );
  });

  const res = await fetch(
    `${API_BASE}/api/jobs`,
    {
      method: "POST",
      headers: await getAuthHeaders(),
      body: fd,
    }
  );

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(
      data.detail ||
      `Gagal mengirim video (${res.status})`
    );
  }

  if (!data.id) {
    throw new Error(
      "Backend tidak mengembalikan ID job."
    );
  }

  return data.id;
}

// =====================================================
// GET JOB
// =====================================================

export async function getJob(id) {
  if (CONFIG.mock) {
    const m = mockJobs[id];

    if (!m) {
      throw new Error(
        "Sesi demo tidak ditemukan (halaman dimuat ulang?)"
      );
    }

    const p = Math.min(
      (Date.now() - m.t0) / 4000,
      1
    );

    const n = m.soal.length;

    return p < 1
      ? {
          status: "proses",
          progres: p,
          pesan: `Menganalisis pertanyaan ${Math.min(
            Math.floor(p * n) + 1,
            n
          )} dari ${n}`,
        }
      : {
          status: "selesai",
          progres: 1,
          hasil: mockReport(
            m.soal,
            m.attempt
          ),
        };
  }

  if (!id) {
    throw new Error("Job ID tidak ditemukan.");
  }

  const res = await fetch(
    `${API_BASE}/api/jobs/${encodeURIComponent(id)}`,
    {
      method: "GET",
      headers: await getAuthHeaders(),
    }
  );

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(
      data.detail ||
      `Gagal membaca status (${res.status})`
    );
  }

  return data;
}

// =====================================================
// EVALUASI GROQ
// =====================================================

export async function evaluateSession(sessionId) {
  if (CONFIG.mock) {
    return null;
  }

  if (!sessionId) {
    throw new Error(
      "Session ID tidak ditemukan untuk evaluasi."
    );
  }

  const res = await fetch(
    `${API_BASE}/api/sessions/${encodeURIComponent(sessionId)}/evaluate`,
    {
      method: "POST",
      headers: await getAuthHeaders(),
    }
  );

  const data = await res.json().catch(() => ({}));

  // Error HTTP berarti request benar-benar gagal.
  if (!res.ok) {
    throw new Error(
      data.detail ||
      data.message ||
      `Evaluasi Groq gagal (${res.status})`
    );
  }

  // Validasi respons backend.
  if (
    !data ||
    typeof data !== "object" ||
    Array.isArray(data)
  ) {
    throw new Error(
      "Respons evaluasi dari backend tidak valid."
    );
  }

  // Jangan langsung throw ketika success=false.
  // Backend mungkin berhasil mengevaluasi sebagian jawaban.
  const failed = Array.isArray(data.failed)
    ? data.failed
    : [];

  const skipped = Array.isArray(data.skipped)
    ? data.skipped
    : [];

  const evaluated = Number(data.evaluated || 0);

  const failedCount = Number(
    data.failed_count ?? failed.length
  );

  return {
    ...data,

    success: data.success === true,

    evaluated,

    failed_count: failedCount,

    failed,

    skipped,

    data: Array.isArray(data.data)
      ? data.data
      : [],
  };
}
