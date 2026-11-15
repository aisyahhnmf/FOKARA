
import { BRAND } from "./brand.js";
import { settings } from "./store.js";
import { signOut, getCurrentUser } from "./auth.js";

// =====================================================
// ICON
// =====================================================

const ICON = {
  home: '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',

  roles: '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/>',

  report: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',

  history: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',

  settings: '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
};

// =====================================================
// NAVIGATION
// =====================================================

const NAV = [
  { id: "home", label: "Beranda", href: "index.html" },
  { id: "roles", label: "Latihan", href: "pages/roles.html" },
  { id: "report", label: "Laporan", href: "pages/report.html" },
  { id: "history", label: "Riwayat", href: "pages/history.html" },
  { id: "settings", label: "Pengaturan", href: "pages/settings.html" },
];

// =====================================================
// THEME
// =====================================================

export const applyTheme = () => {
  document.documentElement.dataset.theme = settings.get().theme;
};

// =====================================================
// TOAST
// =====================================================

export function toast(msg) {
  let t = document.getElementById("toast");

  if (!t) {
    t = document.createElement("div");
    t.id = "toast";
    t.className = "toast";
    document.body.append(t);
  }

  t.textContent = msg;
  t.classList.add("show");

  clearTimeout(toast.timer);

  toast.timer = setTimeout(() => {
    t.classList.remove("show");
  }, 2600);
}

// =====================================================
// USER PROFILE
// =====================================================

function getDisplayName(user) {
  const metadata = user?.user_metadata || {};

  const name =
    metadata.full_name ||
    metadata.name ||
    metadata.display_name;

  if (name && String(name).trim()) {
    return String(name).trim();
  }

  if (user?.email) {
    return user.email.split("@")[0];
  }

  return "Pengguna FOKARA";
}

function getInitials(name) {
  const words = String(name)
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (!words.length) return "F";

  return words
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join("");
}

async function loadSidebarUser() {
  const nameElement = document.getElementById("sidebarUserName");
  const initialsElement = document.getElementById("sidebarUserInitials");

  if (!nameElement || !initialsElement) return;

  try {
    const user = await getCurrentUser();
    const name = getDisplayName(user);

    nameElement.textContent = name;
    initialsElement.textContent = getInitials(name);

  } catch (error) {
    console.error("[SHELL] Gagal memuat profil pengguna:", error);

    nameElement.textContent = "Pengguna FOKARA";
    initialsElement.textContent = "F";
  }
}

// =====================================================
// MOUNT SHELL
// =====================================================

export function mountShell({
  page,
  title,
  subtitle = "",
  compact = false,
  back = "",
}) {
  applyTheme();

  const root = document.body.dataset.root || "";

  // Navigation
  const nav = NAV.map((n) =>
    `<a href="${root}${n.href}" class="${n.id === page ? "on" : ""}">
      <svg viewBox="0 0 24 24">${ICON[n.id]}</svg>
      <span>${n.label}</span>
    </a>`
  ).join("");

  // Back button
  const backBtn = back
    ? `<a class="icon-btn" href="${back}" title="Kembali" aria-label="Kembali">
        <svg viewBox="0 0 24 24">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </a>`
    : "";

  // FOKARA Logo
  const logo = `
    <a
      class="brand"
      href="${root}index.html"
      aria-label="FOKARA Beranda"
    >
      <img
        class="brand-logo"
        src="${root}assets/img/fokara-logo.png"
        alt="FOKARA"
      >
    </a>
  `;

  // App Layout
  document.body.insertAdjacentHTML(
    "afterbegin",
    `
    <div class="app">

      <aside class="side">

        ${logo}

        <nav class="nav">
          ${nav}
        </nav>

        <div class="pid small muted">

          <div style="
            display:flex;
            align-items:center;
            gap:11px;
            margin-bottom:14px;
          ">

            <div
              id="sidebarUserInitials"
              style="
                width:39px;
                height:39px;
                min-width:39px;
                display:flex;
                align-items:center;
                justify-content:center;
                border-radius:50%;
                background:var(--accent-soft, #d9faf3);
                color:var(--accent-strong, #008f80);
                font-size:14px;
                font-weight:700;
              "
            >
              F
            </div>

            <div style="
              min-width:0;
              display:flex;
              flex-direction:column;
              gap:3px;
            ">

              <span style="font-size:11px;">
                Selamat datang,
              </span>

              <b
                id="sidebarUserName"
                style="
                  color:var(--text);
                  font-size:15px;
                  line-height:1.4;
                  font-weight:700;
                  overflow-wrap:anywhere;
                "
              >
                Memuat nama...
              </b>

            </div>

          </div>

          <button
            class="btn"
            id="logoutBtn"
            type="button"
            style="width:100%"
          >
            Keluar
          </button>

        </div>

      </aside>

      <div class="main${compact ? " compact" : ""}">

        <header class="top">

          ${backBtn}

          <div class="top-title">
            <h1>${title}</h1>
            <div class="muted small">${subtitle}</div>
          </div>

          <div class="top-actions" id="topActions"></div>

        </header>

        <main id="view"></main>

      </div>

    </div>
    `
  );

  // Load User Name
  loadSidebarUser();

  // Move Page Content
  const view = document.getElementById("view");
  const content = document.getElementById("content");

  if (view && content) {
    view.append(content);
  }

  // Logout
  document.getElementById("logoutBtn")?.addEventListener(
    "click",
    async () => {
      if (
        confirm("Yakin ingin keluar dari akun FOKARA?")
      ) {
        try {
          await signOut();
        } catch (error) {
          toast(
            error.message || "Gagal keluar dari akun."
          );
        }
      }
    }
  );

  // Document Title
  document.title = `${title} · ${BRAND.name.join("")}`;
}
