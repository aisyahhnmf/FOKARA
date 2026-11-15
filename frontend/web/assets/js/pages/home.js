
import { requireAuth, getCurrentUser, getAuthHeaders } from "../core/auth.js";
import { mountShell } from "../core/shell.js";
import { CONFIG } from "../core/config.js";

// =====================================================
// CONFIGURATION
// =====================================================

const API_URL = (CONFIG.apiBase || "http://127.0.0.1:8000")
  .replace(/\/+$/, "");

const $ = (id) => document.getElementById(id);

// =====================================================
// AUTHENTICATION
// =====================================================

const session = await requireAuth();

if (!session) {
  throw new Error("Sesi login tidak ditemukan.");
}

// =====================================================
// SHELL
// =====================================================

await mountShell({
  page: "home",
  title: "Beranda",
  subtitle: "Latihan wawancara dengan umpan balik berbasis kamera"
});

// =====================================================
// USER GREETING
// =====================================================

function getDisplayName(user) {
  const metadata = user?.user_metadata || {};

  const fullName =
    metadata.full_name ||
    metadata.name ||
    metadata.fullName ||
    user?.email?.split("@")[0];

  if (fullName && String(fullName).trim()) {
    return String(fullName).trim();
  }

  return "Pengguna";
}

async function renderGreeting() {
  try {
    const user = await getCurrentUser();
    const displayName = getDisplayName(user);
    const firstName = displayName.split(/\s+/)[0];

    const greeting = $("greetingName");

    if (greeting) {
      greeting.textContent = firstName;
    }
  } catch (error) {
    console.error("[HOME] Gagal mengambil profil pengguna:", error);
  }
}

// =====================================================
// GENERAL HELPERS
// =====================================================

function getValue(object, keys, fallback = null) {
  for (const key of keys) {
    const value = object?.[key];

    if (
      value !== undefined &&
      value !== null &&
      value !== ""
    ) {
      return value;
    }
  }

  return fallback;
}

function toNumber(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const number = Number(value);

  return Number.isFinite(number) ? number : null;
}

function getSessionId(item) {
  return String(
    item?.id ||
    item?.session_id ||
    item?.external_id ||
    ""
  );
}

function getRole(item) {
  return getValue(
    item,
    [
      "role",
      "job_role",
      "position",
      "job_title"
    ],
    "Latihan wawancara"
  );
}

function getSessionDate(item) {
  return getValue(
    item,
    [
      "started_at",
      "created_at",
      "session_date",
      "date"
    ],
    getValue(
      item?.performance,
      [
        "started_at",
        "created_at"
      ]
    )
  );
}

function formatDate(value) {
  if (!value) {
    return "Tanggal tidak tersedia";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Tanggal tidak tersedia";
  }

  return date.toLocaleString("id-ID", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function getRubricScore(item) {
  const performance = item?.performance || {};

  return toNumber(
    getValue(
      item,
      [
        "rubric_score",
        "rubric_percentage",
        "performance_score",
        "overall_score"
      ],
      getValue(
        performance,
        [
          "weighted_percentage",
          "percentage",
          "rubric_score"
        ]
      )
    )
  );
}

function getEvaluationProgress(item) {
  const performance = item?.performance || {};

  const evaluated = toNumber(
    getValue(
      performance,
      [
        "evaluated_questions",
        "evaluated_count"
      ],
      getValue(
        item,
        [
          "evaluated_questions",
          "evaluated_count"
        ]
      )
    )
  );

  const total = toNumber(
    getValue(
      performance,
      [
        "total_questions",
        "question_count"
      ],
      getValue(
        item,
        [
          "total_questions",
          "question_count"
        ]
      )
    )
  );

  return {
    evaluated: evaluated ?? 0,
    total: total ?? 0
  };
}

function formatScore(score) {
  if (score === null || score === undefined) {
    return "–";
  }

  return `${score.toFixed(1).replace(".", ",")}%`;
}

function getChronologicalSessions(data) {
  return [...data].sort((a, b) => {
    const dateA = new Date(getSessionDate(a) || 0).getTime();
    const dateB = new Date(getSessionDate(b) || 0).getTime();

    return dateB - dateA;
  });
}

// =====================================================
// LOAD SESSIONS FROM API
// =====================================================

async function loadSessions() {
  const authHeaders = await getAuthHeaders();

  const response = await fetch(`${API_URL}/api/sessions`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      ...authHeaders
    }
  });

  if (response.status === 401 || response.status === 403) {
    throw new Error(
      "Sesi login berakhir. Silakan login kembali."
    );
  }

  const result = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      result.detail ||
      result.message ||
      "Gagal mengambil data latihan."
    );
  }

  if (result.success === false) {
    throw new Error(
      result.message ||
      result.detail ||
      "Gagal mengambil data latihan."
    );
  }

  const data = Array.isArray(result)
    ? result
    : Array.isArray(result.data)
      ? result.data
      : Array.isArray(result.sessions)
        ? result.sessions
        : [];

  return {
    total: toNumber(result.total) ?? data.length,
    sessions: getChronologicalSessions(data)
  };
}

// =====================================================
// STATISTICS
// =====================================================

function renderStatistics(data, total) {
  const totalElement = $("totalPractice");
  const scoreElement = $("latestScore");
  const evaluatedElement = $("evaluatedQuestions");

  if (totalElement) {
    totalElement.textContent = total;
  }

  if (!data.length) {
    if (scoreElement) {
      scoreElement.textContent = "–";
    }

    if (evaluatedElement) {
      evaluatedElement.textContent = "–";
    }

    return;
  }

  // Nilai terakhir yang memang sudah tersedia.
  const latestScoredSession = data.find(
    (item) => getRubricScore(item) !== null
  );

  if (scoreElement) {
    scoreElement.textContent = latestScoredSession
      ? formatScore(getRubricScore(latestScoredSession))
      : "–";
  }

  // Progres evaluasi dari sesi terbaru.
  const latest = data[0];
  const progress = getEvaluationProgress(latest);

  if (evaluatedElement) {
    evaluatedElement.textContent =
      `${progress.evaluated}/${progress.total}`;
  }
}

// =====================================================
// LAST REPORT
// =====================================================

function renderLastReport(data) {
  const card = $("lastCard");

  if (!card) return;

  if (!data.length) {
    card.hidden = true;
    return;
  }

  const latest = data[0];

  const roleElement = $("lastRole");
  const dateElement = $("lastDate");
  const scoreElement = $("lastScore");
  const linkElement = $("lastLink");

  if (roleElement) {
    roleElement.textContent = getRole(latest);
  }

  if (dateElement) {
    dateElement.textContent = formatDate(
      getSessionDate(latest)
    );
  }

  if (scoreElement) {
    scoreElement.textContent = formatScore(
      getRubricScore(latest)
    );
  }

  const sessionId = getSessionId(latest);

  if (linkElement) {
    if (sessionId) {
      linkElement.href =
        `pages/report.html?id=${encodeURIComponent(sessionId)}`;

      linkElement.hidden = false;
    } else {
      linkElement.hidden = true;
    }
  }

  card.hidden = false;
}

// =====================================================
// EMPTY / ERROR STATE
// =====================================================

function renderError(message) {
  console.error("[HOME]", message);

  const totalElement = $("totalPractice");
  const scoreElement = $("latestScore");
  const evaluatedElement = $("evaluatedQuestions");

  if (totalElement) {
    totalElement.textContent = "–";
  }

  if (scoreElement) {
    scoreElement.textContent = "–";
  }

  if (evaluatedElement) {
    evaluatedElement.textContent = "–";
  }

  const card = $("lastCard");

  if (card) {
    card.hidden = true;
  }

  const content = $("content");

  if (content) {
    let errorElement = $("homeError");

    if (!errorElement) {
      errorElement = document.createElement("p");
      errorElement.id = "homeError";
      errorElement.className = "banner";
      errorElement.setAttribute("role", "alert");

      content.prepend(errorElement);
    }

    errorElement.textContent = message;
  }
}

// =====================================================
// INITIALIZATION
// =====================================================

async function initHome() {
  await renderGreeting();

  try {
    const result = await loadSessions();

    renderStatistics(
      result.sessions,
      result.total
    );

    renderLastReport(result.sessions);

    console.log("[HOME] Data berhasil dimuat:", {
      total: result.total,
      sessions: result.sessions.length,
      latestSession: result.sessions[0] || null
    });

  } catch (error) {
    renderError(
      error.message ||
      "Terjadi kesalahan saat memuat data Beranda."
    );
  }
}

await initHome();
