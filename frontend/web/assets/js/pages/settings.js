
import { requireAuth } from "../core/auth.js";
import { mountShell, applyTheme, toast } from "../core/shell.js";
import { settings, reports } from "../core/store.js";

// =====================================================
// AUTHENTICATION
// =====================================================

const session = await requireAuth();

if (!session?.user?.id) {
  throw new Error("[SETTINGS] Pengguna belum terautentikasi.");
}

// =====================================================
// MOUNT SHELL
// =====================================================

await mountShell({
  page: "settings",
  title: "Pengaturan",
  subtitle: "Tampilan dan preferensi",
});

// =====================================================
// ACCOUNT ID
// =====================================================

const pidText = document.getElementById("pidText");

if (pidText) {
  pidText.textContent = session.user.id;
  console.log("[SETTINGS] Account ID:", session.user.id);
} else {
  console.error("[SETTINGS] Elemen #pidText tidak ditemukan.");
}

// =====================================================
// SETTINGS
// =====================================================

const s = settings.get();

const AVAILABLE_THEMES = ["langit", "mint", "persik"];

// =====================================================
// THEME
// =====================================================

const swatches = document.querySelectorAll(".swatch");

function mark() {
  const currentTheme = settings.get().theme;

  swatches.forEach((button) => {
    const active = button.dataset.theme === currentTheme;

    button.classList.toggle("on", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

swatches.forEach((button) => {
  button.addEventListener("click", () => {
    const theme = button.dataset.theme;

    if (!AVAILABLE_THEMES.includes(theme)) {
      console.warn("[SETTINGS] Tema tidak dikenal:", theme);
      return;
    }

    settings.set({ theme });

    applyTheme();
    mark();

    toast(`Tema ${theme.charAt(0).toUpperCase() + theme.slice(1)} diterapkan`);
  });
});

// =====================================================
// MIRROR CAMERA
// =====================================================

const mirror = document.getElementById("mirror");

if (mirror) {
  mirror.checked = s.mirror;

  mirror.addEventListener("change", () => {
    settings.set({
      mirror: mirror.checked,
    });

    toast("Preferensi mirror kamera disimpan");
  });
}

// =====================================================
// LANGUAGE
// =====================================================

const bahasa = document.getElementById("bahasa");

if (bahasa) {
  bahasa.value = s.bahasa || "id";

  bahasa.addEventListener("change", () => {
    settings.set({
      bahasa: bahasa.value,
    });

    toast("Preferensi bahasa disimpan");
  });
}

// =====================================================
// CLEAR HISTORY
// =====================================================

const clearBtn = document.getElementById("clearBtn");

if (clearBtn) {
  clearBtn.addEventListener("click", () => {
    const history = reports.all();

    if (!history.length) {
      toast("Belum ada riwayat lokal untuk dihapus");
      return;
    }

    const confirmed = confirm(
      `Anda akan menghapus ${history.length} riwayat laporan yang tersimpan di browser ini. Tindakan ini tidak dapat dibatalkan. Lanjutkan?`
    );

    if (!confirmed) return;

    reports.clear();

    toast("Riwayat laporan lokal berhasil dihapus");
  });
}

// =====================================================
// INITIALIZE
// =====================================================

if (!AVAILABLE_THEMES.includes(settings.get().theme)) {
  settings.set({ theme: "langit" });
  applyTheme();
}

mark();

console.log("[SETTINGS] Halaman pengaturan berhasil dimuat.");
