
import { requireAuth } from "../core/auth.js";
await requireAuth();

import { mountShell, toast } from "../core/shell.js";
import { CONFIG } from "../core/config.js";
import { findRole } from "../core/data.js";
import { settings, reports, pid } from "../core/store.js";

import {
  createSession,
  createJob,
  getJob,
  evaluateSession
} from "../core/api.js";

import { esc } from "../core/utils.js";

// =====================================================
// DATA ROLE, LEVEL, DAN QUESTION BANK
// =====================================================

const params = new URLSearchParams(location.search);

const roleId = params.get("role");
const experienceLevel = params.get("level");

const validLevels = [
  "Beginner",
  "Intermediate",
  "Advanced"
];

const role = await findRole(roleId);

if (!role || !validLevels.includes(experienceLevel)) {
  location.replace("roles.html");
  await new Promise(() => {});
}

// =====================================================
// LOAD QUESTION BANK
// =====================================================

async function loadQuestionSet() {
  const roleName = role.nama || role.name || role.id;

  const queryParams = new URLSearchParams({
    role: roleName,
    experience_level: experienceLevel
  });

  const apiBase = (
    CONFIG.apiBase || "http://127.0.0.1:8000"
  ).replace(/\/+$/, "");

  const response = await fetch(
    `${apiBase}/api/question-set?${queryParams.toString()}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json"
      }
    }
  );

  const result = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      result.detail ||
      `Gagal mengambil pertanyaan (${response.status})`
    );
  }

  if (!result.success) {
    throw new Error(
      result.message || "Question Bank gagal dimuat."
    );
  }

  const questions = result.data ?? result.questions;

  if (!Array.isArray(questions)) {
    throw new Error(
      "Format respons Question Bank tidak valid."
    );
  }

  if (
    questions.length !== 7 ||
    Number(result.total) !== 7
  ) {
    throw new Error(
      `Question Bank harus mengembalikan 7 pertanyaan. Diterima: ${questions.length}.`
    );
  }

  return {
    ...result,
    data: questions
  };
}

let questionSet;

try {
  questionSet = await loadQuestionSet();

  console.log(
    "[QUESTION SET] Berhasil dimuat:",
    questionSet
  );

} catch (error) {
  console.error("[QUESTION SET ERROR]", error);

  alert("Gagal memuat pertanyaan: " + error.message);

  location.replace("roles.html");
  await new Promise(() => {});
}

// =====================================================
// NORMALISASI PERTANYAAN
// =====================================================

const rawQuestions = questionSet.data;

if (
  !Array.isArray(rawQuestions) ||
  rawQuestions.length !== 7
) {
  alert("Bank soal tidak mengembalikan 7 pertanyaan.");

  location.replace("roles.html");
  await new Promise(() => {});
}

const soal = rawQuestions.map((q) => ({
  id: q.id ?? q.external_id,
  teks: q.teks ?? q.question_text,
  kompetensi: q.kompetensi ?? q.competency ?? "Umum",
  kategori: q.kategori ?? q.category ?? "",
  jenis: q.jenis ?? q.question_type ?? "",
  experience_level: q.experience_level ?? experienceLevel,
  stage: q.stage ?? "",
  topic: q.topic ?? "",
  expected_elements: q.expected_elements ?? [],
  reference_context: q.reference_context ?? ""
}));

if (soal.some((q) => !q.id || !q.teks)) {
  alert("Format pertanyaan dari server tidak lengkap.");

  location.replace("roles.html");
  await new Promise(() => {});
}

const generalTotal = soal.filter(
  (q) => q.jenis === "general"
).length;

const technicalTotal = soal.filter(
  (q) => q.jenis === "technical"
).length;

if (generalTotal !== 2 || technicalTotal !== 5) {
  alert(
    `Komposisi pertanyaan tidak sesuai. Umum: ${generalTotal}, Teknis: ${technicalTotal}.`
  );

  location.replace("roles.html");
  await new Promise(() => {});
}

const attempt = reports.nextAttempt(role.id);

const Q = soal.map((s) => s.teks);

const participantId = pid();

// =====================================================
// SHELL DAN ELEMENT SELECTOR
// =====================================================

await mountShell({
  page: "roles",
  title: role.nama || role.name || role.id,
  subtitle: `${experienceLevel} · Percobaan ke-${attempt} · ${Q.length} pertanyaan`,
  compact: true,
  back: "roles.html"
});

const $ = (id) => document.getElementById(id);

// =====================================================
// STATE
// =====================================================

let stream = null;
let rec = null;
let chunks = [];
let clips = [];

let qi = 0;
let sec = 0;
let timer = null;

let running = false;
let busy = false;

let sessionData = null;

// =====================================================
// UTILITIES
// =====================================================

const two = (n) => String(n).padStart(2, "0");

const mmss = (s) =>
  `${two(Math.floor(s / 60))}:${two(s % 60)}`;

// =====================================================
// RENDER TOP ACTIONS
// =====================================================

function renderTop(label) {
  $("topActions").innerHTML = running
    ? `<button class="btn" id="endBtn">Akhiri sesi</button>
       <span class="pill live"><i></i>${stream ? "Merekam" : "Sesi berjalan"}</span>`
    : `<span class="pill idle">${label || "Belum merekam"}</span>`;

  if ($("endBtn")) {
    $("endBtn").onclick = endEarly;
  }
}

// =====================================================
// RENDER PERTANYAAN
// =====================================================

function renderSide() {
  const total = Q.length;

  $("qCount").textContent = running
    ? `${qi + 1}/${total}`
    : `${total} pertanyaan`;

  $("prog").style.width =
    (running ? (qi / total) * 100 : 0) + "%";

  $("nextBtn").textContent =
    qi >= total - 1
      ? "Selesaikan sesi"
      : "Pertanyaan berikutnya";

  if (!running) {
    $("qBody").innerHTML = `
      <div class="intro">
        <b>Siap berlatih?</b>
        <p class="muted">
          Anda akan menjawab 2 pertanyaan umum dan
          5 pertanyaan teknis untuk posisi
          ${esc(role.nama || role.name || role.id)}
          dengan tingkat pengalaman
          ${esc(experienceLevel)}.
          Jawab setiap pertanyaan dengan jelas dan natural.
          Tekan tombol "Pertanyaan berikutnya" setelah selesai menjawab.
        </p>
      </div>
    `;

    return;
  }

  const done = Q.slice(0, qi)
    .map((t, i) => `
      <div class="qcard done">
        <span class="qnum">${two(i + 1)}</span>
        <p>${esc(t)}</p>
        <span class="qdone">✓</span>
      </div>
    `)
    .join("");

  const cur = `
    <div class="qcard on">
      <span class="qnum">${two(qi + 1)}</span>
      <p>${esc(Q[qi])}</p>
    </div>
  `;

  const left = total - qi - 1;

  const lock = left > 0
    ? `<p class="muted small qlock">
         ${left} pertanyaan tersisa. Pertanyaan berikutnya
         akan ditampilkan setelah Anda menekan tombol lanjut.
       </p>`
    : "";

  $("qBody").innerHTML = done + cur + lock;
}

// =====================================================
// KAMERA
// =====================================================

async function openCam() {
  if (stream) return true;

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 960 },
        height: { ideal: 540 }
      },
      audio: true
    });

  } catch (error) {
    console.error("[CAMERA]", error);
    return false;
  }

  const cam = $("cam");

  cam.srcObject = stream;
  cam.style.display = "block";

  cam.style.transform = settings.get().mirror
    ? "scaleX(-1)"
    : "none";

  $("ph").hidden = true;

  return true;
}

// =====================================================
// VIDEO RECORDING
// =====================================================

function startRec() {
  chunks = [];

  if (!stream) return;

  try {
    const mimeType = MediaRecorder.isTypeSupported(
      "video/webm;codecs=vp9"
    )
      ? "video/webm;codecs=vp9"
      : "video/webm";

    rec = new MediaRecorder(stream, { mimeType });

    rec.ondataavailable = (e) => {
      if (e.data.size) {
        chunks.push(e.data);
      }
    };

    rec.start();

  } catch (error) {
    console.error("[RECORDING START ERROR]", error);

    throw new Error(
      "Tidak dapat memulai perekaman video."
    );
  }
}

function stopRec() {
  return new Promise((resolve, reject) => {
    if (!rec || rec.state === "inactive") {
      return resolve(
        new Blob([], {
          type: "video/webm"
        })
      );
    }

    rec.onstop = () => {
      resolve(
        new Blob(chunks, {
          type: rec.mimeType || "video/webm"
        })
      );
    };

    rec.onerror = (event) => {
      reject(
        event.error ||
        new Error("Gagal menghentikan rekaman.")
      );
    };

    rec.stop();
  });
}

// =====================================================
// VALIDASI SESSION QUESTIONS
// =====================================================

function validateSessionQuestions(questions) {
  if (
    !Array.isArray(questions) ||
    questions.length !== 7
  ) {
    throw new Error(
      "Sesi tidak memiliki tepat 7 pertanyaan."
    );
  }

  // ID pertanyaan Question Bank dan ID baris
  // session_questions tidak harus sama.
  // Yang harus sama adalah urutan dan teksnya.

  const invalidQuestion = questions.some((q, i) => {
    const sessionQuestionId = q.session_question_id;
    const questionOrder = Number(q.question_order);
    const questionText = q.question_text;

    return (
      !sessionQuestionId ||
      !questionText ||
      questionOrder !== i + 1
    );
  });

  if (invalidQuestion) {
    console.error(
      "[SESSION QUESTION VALIDATION]",
      questions
    );

    throw new Error(
      "ID atau urutan pertanyaan session tidak sesuai."
    );
  }

  const sessionQuestionIds = questions.map(
    (q) => String(q.session_question_id)
  );

  if (new Set(sessionQuestionIds).size !== 7) {
    throw new Error(
      "Terdapat ID pertanyaan sesi yang duplikat."
    );
  }

  // Pastikan teks pertanyaan dan urutannya
  // sama dengan Question Bank.
  for (let i = 0; i < questions.length; i++) {
    if (questions[i].question_text !== soal[i].teks) {
      console.error("[QUESTION TEXT MISMATCH]", {
        index: i,
        sessionQuestion: questions[i],
        questionBank: soal[i]
      });

      throw new Error(
        `Teks pertanyaan nomor ${i + 1} tidak sesuai dengan Question Bank.`
      );
    }
  }

  return true;
}

// =====================================================
// MULAI SESI
// =====================================================

async function start() {
  if (!$("consent").checked) {
    return toast(
      "Centang persetujuan terlebih dahulu."
    );
  }

  $("startBtn").disabled = true;

  if (!(await openCam())) {
    if (!CONFIG.mock) {
      $("startBtn").disabled = false;

      return toast(
        "Kamera atau mikrofon tidak dapat diakses."
      );
    }

    $("phText").textContent =
      "Mode demo (kamera tidak tersedia)";

    $("previewBtn").hidden = true;

    toast(
      "Kamera tidak tersedia. Melanjutkan dalam mode demo."
    );
  }

  if (!CONFIG.mock) {
    try {
      sessionData = await createSession({
        role: role.nama || role.name || role.id,
        pid: participantId,
        attempt,
        experienceLevel
      });

      if (!sessionData?.session_id) {
        throw new Error(
          "Backend tidak mengembalikan Session ID."
        );
      }

      validateSessionQuestions(sessionData.questions);

      console.log(
        "[SESSION] Berhasil membuat session:",
        sessionData
      );

    } catch (e) {
      console.error("[SESSION ERROR]", e);

      stream?.getTracks().forEach((t) => t.stop());
      stream = null;

      $("cam").style.display = "none";
      $("ph").hidden = false;
      $("startBtn").disabled = false;

      return toast(
        "Gagal memulai sesi: " + e.message
      );
    }
  }

  running = true;
  qi = 0;
  sec = 0;
  clips = [];

  $("guide").hidden = true;
  $("vtag").hidden = !stream;

  $("consentRow").hidden = true;
  $("startBtn").hidden = true;
  $("nextBtn").hidden = false;

  $("timer").textContent = "00:00";

  renderTop();
  renderSide();

  try {
    startRec();

  } catch (error) {
    console.error("[RECORDING ERROR]", error);

    running = false;

    stream?.getTracks().forEach((t) => t.stop());
    stream = null;

    $("startBtn").hidden = false;
    $("startBtn").disabled = false;
    $("nextBtn").hidden = true;

    return toast(error.message);
  }

  // Timer hanya menghitung durasi.
  // Tidak ada batas waktu atau perpindahan otomatis.
  timer = setInterval(tick, 1000);
}

// =====================================================
// TIMER BEBAS DURASI
// =====================================================

function tick() {
  if (!running) return;

  sec++;

  // Menampilkan durasi berjalan tanpa batas maksimal.
  $("timer").textContent = mmss(sec);
}

// =====================================================
// PERTANYAAN BERIKUTNYA
// =====================================================

async function next() {
  if (!running || busy) return;

  busy = true;

  try {
    clips[qi] = await stopRec();

    if (qi >= Q.length - 1) {
      await finish();
      return;
    }

    qi++;
    sec = 0;

    $("timer").textContent = "00:00";

    renderSide();

    startRec();

  } catch (e) {
    console.error("[RECORDING ERROR]", e);

    toast(
      "Terjadi kesalahan saat menyimpan rekaman."
    );

  } finally {
    busy = false;
  }
}

// =====================================================
// AKHIRI SESI LEBIH AWAL
// =====================================================

async function endEarly() {
  if (!running || busy) return;

  if (!confirm(
    "Akhiri sesi sekarang? Pertanyaan yang belum dijawab tidak ikut dianalisis."
  )) {
    return;
  }

  busy = true;

  try {
    clips[qi] = await stopRec();

    await finish();

  } catch (e) {
    console.error("[RECORDING ERROR]", e);

    toast(
      "Terjadi kesalahan saat menyimpan rekaman."
    );

  } finally {
    busy = false;
  }
}

// =====================================================
// SELESAIKAN SESI
// =====================================================

async function finish() {
  if (!running) return;

  running = false;

  clearInterval(timer);
  timer = null;

  stream?.getTracks().forEach((t) => t.stop());
  stream = null;

  $("cam").style.display = "none";
  $("vtag").hidden = true;

  $("nextBtn").hidden = true;
  $("proc").hidden = false;

  renderTop("Memproses…");

  try {
    const asked = soal.slice(0, clips.length);

    if (clips.length === 0) {
      throw new Error(
        "Tidak ada video yang berhasil direkam."
      );
    }

    if (!CONFIG.mock && !sessionData?.session_id) {
      throw new Error("Session ID tidak ditemukan.");
    }

    const sessionQuestions = CONFIG.mock
      ? []
      : sessionData.questions.slice(0, asked.length);

    const jobId = await createJob({
      role: role.nama || role.name || role.id,
      soal: asked,
      blobs: clips,
      bahasa: settings.get().bahasa,
      attempt,
      sessionId: sessionData?.session_id,
      sessionQuestions
    });

    console.log(
      "[JOB] Job berhasil dibuat:",
      jobId
    );

    const hasil = await poll(jobId);

    if (!hasil) {
      throw new Error(
        "Hasil analisis tidak ditemukan."
      );
    }

    // =================================================
    // EVALUASI GROQ
    // =================================================

    let evaluationResult = null;
    let evaluationError = null;

    if (!CONFIG.mock) {
      try {
        $("procMsg").textContent =
          "Transkrip selesai. Sedang mengevaluasi jawaban menggunakan AI...";

        $("procBar").style.width = "90%";

        evaluationResult = await evaluateSession(
          sessionData.session_id
        );

        if (evaluationResult.success) {
          console.log(
            "[GROQ EVALUATION] Semua jawaban berhasil dievaluasi:",
            evaluationResult
          );

        } else {
          const evaluatedCount =
            evaluationResult.evaluated;

          const failedCount =
            evaluationResult.failed_count;

          evaluationError =
            `Evaluasi belum lengkap. ${evaluatedCount} jawaban berhasil dievaluasi, ${failedCount} jawaban gagal.`;

          console.warn(
            "[GROQ PARTIAL EVALUATION]",
            evaluationResult
          );
        }

      } catch (error) {
        evaluationError = error.message;

        console.error(
          "[GROQ EVALUATION ERROR]",
          error
        );
      }
    }

    // =================================================
    // NORMALISASI HASIL PERTANYAAN
    // =================================================

    if (hasil.pertanyaan) {
      hasil.pertanyaan.forEach((q, i) => {
        q.id ??= asked[i]?.id;
        q.kompetensi ??= asked[i]?.kompetensi;
      });
    }

    // =================================================
    // SIMPAN HASIL LAPORAN
    // =================================================

    reports.add({
      id: jobId,
      job_id: jobId,
      session_id: sessionData?.session_id ?? null,
      role: role.id,
      roleNama: role.nama || role.name || role.id,
      experience_level: experienceLevel,
      attempt,
      pid: participantId,

      ...hasil,

      evaluation_result: evaluationResult,
      evaluation_error: evaluationError
    });

    // =================================================
    // NAVIGASI KE HALAMAN LAPORAN
    // =================================================

    const reportSessionId = sessionData?.session_id;

    if (!CONFIG.mock && !reportSessionId) {
      throw new Error(
        "Session ID untuk laporan tidak ditemukan."
      );
    }

    location.href = CONFIG.mock
      ? `report.html?id=${encodeURIComponent(jobId)}`
      : `report.html?id=${encodeURIComponent(reportSessionId)}&job=${encodeURIComponent(jobId)}`;

  } catch (e) {
    console.error("[JOB ERROR]", e);

    $("procMsg").textContent =
      "Terjadi kendala: " + e.message;

    $("retryBtn").hidden = false;
  }
}

// =====================================================
// POLLING JOB
// =====================================================

async function poll(id) {
  while (true) {
    const j = await getJob(id);

    $("procMsg").textContent =
      j.pesan || "Memproses…";

    $("procBar").style.width =
      Math.round((j.progres || 0) * 100) + "%";

    if (j.status === "selesai") {
      return j.hasil;
    }

    if (j.status === "gagal") {
      throw new Error(
        j.pesan || "Analisis gagal"
      );
    }

    await new Promise((resolve) =>
      setTimeout(resolve, 1200)
    );
  }
}

// =====================================================
// EVENT LISTENERS
// =====================================================

$("previewBtn").onclick = async () => {
  if (await openCam()) {
    $("guide").hidden = false;
  } else {
    toast(
      "Kamera atau mikrofon tidak dapat diakses."
    );
  }
};

$("startBtn").onclick = start;

$("nextBtn").onclick = next;

window.addEventListener("beforeunload", (e) => {
  if (running) {
    e.preventDefault();
    e.returnValue = "";
  }
});

// =====================================================
// INITIAL RENDER
// =====================================================

renderTop();
renderSide();
