import {
  signUp,
  signIn,
  isSupabaseConfigured,
  isValidLoginEmail,
  redirectIfAuthenticated,
} from "../core/auth.js";

const $ = (id) => document.getElementById(id);

const form = $("authForm");
const message = $("authMessage");

let mode = "login";

// =====================================================
// MESSAGE
// =====================================================

function showMessage(text, type = "") {
  if (!message) return;

  message.textContent = text;
  message.className = `auth-message ${type}`.trim();
}

// =====================================================
// LOADING
// =====================================================

function setLoading(loading) {
  const button = $("submitBtn");

  if (!button) return;

  button.disabled = loading;

  button.textContent = loading
    ? mode === "register"
      ? "Membuat akun..."
      : "Memproses..."
    : mode === "register"
      ? "Buat akun"
      : "Masuk";
}

// =====================================================
// SWITCH MODE
// =====================================================

function setMode(nextMode) {
  mode = nextMode;

  const registering = mode === "register";

  $("loginTab").classList.toggle("active", !registering);
  $("registerTab").classList.toggle("active", registering);

  $("formTitle").textContent = registering
    ? "Buat akun FOKARA"
    : "Masuk ke akunmu";

  $("formSubtitle").textContent = registering
    ? "Buat akun menggunakan email dan password pilihanmu."
    : "Lanjutkan latihan wawancaramu bersama FOKARA.";

  $("nameWrap").hidden = !registering;
  $("fullName").required = registering;

  $("confirmWrap").hidden = !registering;
  $("confirmPassword").required = registering;

  $("password").autocomplete = registering
    ? "new-password"
    : "current-password";

  $("password").placeholder = registering
    ? "Buat password minimal 8 karakter"
    : "Masukkan password";

  $("submitBtn").textContent = registering
    ? "Buat akun"
    : "Masuk";

  $("switchPrompt").textContent = registering
    ? "Sudah punya akun?"
    : "Belum punya akun?";

  $("switchMode").textContent = registering
    ? "Masuk sekarang"
    : "Daftar sekarang";

  $("email").placeholder = "nama@gmail.com";

  showMessage("");
}

// =====================================================
// BUTTON EVENTS
// =====================================================

$("loginTab").addEventListener("click", () => {
  setMode("login");
});

$("registerTab").addEventListener("click", () => {
  setMode("register");
});

$("switchMode").addEventListener("click", () => {
  setMode(mode === "login" ? "register" : "login");
});

// =====================================================
// TOGGLE PASSWORD
// =====================================================

$("togglePassword").addEventListener("click", () => {
  const input = $("password");

  input.type = input.type === "password"
    ? "text"
    : "password";

  $("togglePassword").textContent =
    input.type === "password" ? "Lihat" : "Sembunyikan";
});

// =====================================================
// INITIALIZATION
// =====================================================

if (!form) {
  console.error("[AUTH] Form authForm tidak ditemukan.");
} else if (!isSupabaseConfigured()) {
  showMessage("Konfigurasi Supabase belum lengkap.", "error");
  $("submitBtn").disabled = true;
} else {
  await redirectIfAuthenticated();
}

// =====================================================
// FORM SUBMISSION
// =====================================================

if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!isSupabaseConfigured()) {
      showMessage("Supabase belum dikonfigurasi.", "error");
      return;
    }

    const email = $("email").value.trim().toLowerCase();
    const fullName = $("fullName").value.trim();
    const password = $("password").value;
    const confirmPassword = $("confirmPassword").value;

    // =================================================
    // VALIDATION
    // =================================================

    if (!email) {
      showMessage("Masukkan alamat email.", "error");
      return;
    }

    if (!isValidLoginEmail(email)) {
      showMessage(
        "Email harus menggunakan format nama@gmail.com.",
        "error"
      );
      return;
    }

    if (!password) {
      showMessage("Masukkan password.", "error");
      return;
    }

    if (mode === "register") {
      if (fullName.length < 2) {
        showMessage(
          "Nama lengkap minimal 2 karakter.",
          "error"
        );
        return;
      }

      if (password.length < 8) {
        showMessage(
          "Password minimal 8 karakter.",
          "error"
        );
        return;
      }

      if (password !== confirmPassword) {
        showMessage(
          "Konfirmasi password belum sama.",
          "error"
        );
        return;
      }
    }

    // =================================================
    // SUBMIT
    // =================================================

    setLoading(true);
    showMessage("");

    try {
      // ===============================================
      // REGISTER
      // ===============================================

      if (mode === "register") {
        const data = await signUp({
          name: fullName,
          email,
          password,
        });

        // Dengan Confirm email nonaktif, Supabase
        // seharusnya langsung mengembalikan session.
        if (data.session && data.user) {
          localStorage.setItem(
            "semraut.auth.uid",
            data.user.id
          );

          localStorage.setItem(
            "semraut.auth.email",
            data.user.email || email
          );

          showMessage(
            "Akun berhasil dibuat! Mengarahkan ke FOKARA...",
            "success"
          );

          location.replace("index.html");
          return;
        }

        // Jika session tidak tersedia, kemungkinan
        // pengaturan Confirm email Supabase masih aktif.
        showMessage(
          "Akun berhasil dibuat, tetapi sesi login belum tersedia. Pastikan Confirm email di Supabase sudah dinonaktifkan, lalu coba login.",
          "error"
        );

        $("email").value = email;
        $("password").value = "";
        $("confirmPassword").value = "";

        return;
      }

      // ===============================================
      // LOGIN
      // ===============================================

      await signIn({
        email,
        password,
      });

      showMessage(
        "Login berhasil! Mengarahkan ke FOKARA...",
        "success"
      );

      location.replace("index.html");

    } catch (error) {
      console.error("[AUTH ERROR]", error);

      showMessage(
        error.message || "Terjadi kesalahan saat autentikasi.",
        "error"
      );

    } finally {
      setLoading(false);
    }
  });
}

// =====================================================
// DEFAULT MODE
// =====================================================

setMode("login");

console.log("[AUTH] Login JavaScript berhasil dimuat.");