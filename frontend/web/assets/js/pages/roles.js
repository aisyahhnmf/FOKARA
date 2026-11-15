
import { requireAuth, getAuthHeaders } from "../core/auth.js";
import { CONFIG } from "../core/config.js";

import { mountShell } from "../core/shell.js";
import { loadRoles } from "../core/data.js";
import { esc } from "../core/utils.js";

await requireAuth();

mountShell({
  page: "roles",
  title: "Pilih Posisi",
  subtitle:
    "Pilih posisi pekerjaan dan tingkat pengalaman untuk memulai simulasi wawancara."
});

const grid = document.getElementById("roleGrid");

const EXPERIENCE_LEVELS = [
  "Beginner",
  "Intermediate",
  "Advanced"
];

const INITIAL_COMPETENCIES = 5;

// =====================================================
// AMBIL JUMLAH SESI DARI BACKEND
// =====================================================

async function loadSessionCounts() {
  const headers = await getAuthHeaders();

  const response = await fetch(
    `${CONFIG.apiBase}/api/sessions`,
    {
      method: "GET",
      headers
    }
  );

  if (!response.ok) {
    throw new Error(
      `Gagal mengambil riwayat sesi (${response.status})`
    );
  }

  const payload = await response.json();

  if (
    !payload.success ||
    !Array.isArray(payload.data)
  ) {
    throw new Error(
      "Format data riwayat sesi dari server tidak sesuai."
    );
  }

  // Hitung jumlah sesi berdasarkan posisi.
  const counts = {};

  for (const session of payload.data) {
    const roleId = session.role;

    if (!roleId) continue;

    counts[roleId] = (counts[roleId] || 0) + 1;
  }

  return counts;
}

// =====================================================
// RENDER POSISI
// =====================================================

try {
  const [roles, sessionCounts] = await Promise.all([
    loadRoles(),
    loadSessionCounts()
  ]);

  grid.innerHTML = roles.map((r, index) => {
    const kompetensi = [
      ...new Set(
        (r.soal || [])
          .map((s) => s.kompetensi)
          .filter(Boolean)
      )
    ];

    const visibleCompetencies = kompetensi.slice(
      0,
      INITIAL_COMPETENCIES
    );

    const hiddenCompetencies = kompetensi.slice(
      INITIAL_COMPETENCIES
    );

    // Jumlah sesi milik akun yang sedang login.
    const totalSessions = sessionCounts[r.nama] || 0;

    const levelOptions = EXPERIENCE_LEVELS.map((level) => `
      <option value="${level}">${level}</option>
    `).join("");

    const competencyTags = (items) => items.map((item) => `
      <span class="tag">${esc(item)}</span>
    `).join("");

    return `
      <article class="card role">

        <div class="role-heading">
          <span class="chip">
            ${esc(r.bidang || "Posisi pekerjaan")}
          </span>

          <h3>${esc(r.nama)}</h3>

          <p class="role-description muted">
            ${esc(r.deskripsi || "")}
          </p>
        </div>

        <div class="role-competencies">

          <div class="competency-title">
            Kompetensi yang dilatih
            <span>${kompetensi.length}</span>
          </div>

          <div class="chips">
            ${competencyTags(visibleCompetencies)}
          </div>

          ${
            hiddenCompetencies.length
              ? `
                <details class="competency-details">
                  <summary>
                    Lihat ${hiddenCompetencies.length} kompetensi lainnya
                  </summary>

                  <div class="chips extra-chips">
                    ${competencyTags(hiddenCompetencies)}
                  </div>
                </details>
              `
              : ""
          }

        </div>

        <div class="role-footer">

          <p class="role-session muted small">
            <span>7 pertanyaan per sesi</span>
            <span class="session-separator">·</span>
            <span>
              ${
                totalSessions
                  ? `${totalSessions} sesi tersimpan`
                  : "Belum ada sesi latihan"
              }
            </span>
          </p>

          <div class="role-level">

            <label for="level-${index}">
              Tingkat pengalaman
            </label>

            <select
              id="level-${index}"
              class="level-select"
            >
              <option value="">Pilih tingkat pengalaman</option>
              ${levelOptions}
            </select>

          </div>

          <button
            class="btn primary role-start"
            data-role="${esc(r.id)}"
            data-level-select="level-${index}"
            disabled
          >
            Mulai latihan
          </button>

        </div>

      </article>
    `;
  }).join("");

  // ===================================================
  // EVENT LISTENER
  // ===================================================

  grid.querySelectorAll(".role-start").forEach((button) => {
    const select = document.getElementById(
      button.dataset.levelSelect
    );

    select.addEventListener("change", () => {
      button.disabled = !select.value;
    });

    button.addEventListener("click", () => {
      const level = select.value;

      if (!level) return;

      const params = new URLSearchParams({
        role: button.dataset.role,
        level
      });

      location.href = `interview.html?${params.toString()}`;
    });
  });

} catch (error) {
  console.error("[ROLES] Gagal memuat posisi:", error);

  grid.innerHTML = `
    <div class="card">
      <p class="muted">
        Gagal memuat daftar posisi: ${esc(error.message)}
      </p>
    </div>
  `;
}
