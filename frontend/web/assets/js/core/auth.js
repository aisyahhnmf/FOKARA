import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// =====================================================
// SUPABASE CONFIGURATION
// =====================================================

const SUPABASE_URL =
  "https://vawpajykzkcdjmlxverl.supabase.co";

const SUPABASE_ANON_KEY =
  "sb_publishable_6U2rV56Acn6hNdPaS1DauA_x4ZQUCMt";

// =====================================================
// INITIALIZE SUPABASE
// =====================================================

export const supabase = createClient(
  SUPABASE_URL,
  SUPABASE_ANON_KEY,
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storage: window.localStorage,
    },
  }
);

// =====================================================
// HELPER
// =====================================================

function getLoginURL() {
  return new URL("./login.html", location.href).href;
}

function getDashboardURL() {
  return new URL("./index.html", location.href).href;
}

// =====================================================
// EMAIL VALIDATION
// =====================================================

export function isValidLoginEmail(email) {
  const value = String(email || "").trim().toLowerCase();

  return /^[a-z0-9._%+-]+@gmail\.com$/.test(value);
}

// =====================================================
// CONFIGURATION CHECK
// =====================================================

export function isSupabaseConfigured() {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
}

// =====================================================
// REGISTER
// =====================================================

export async function signUp({ name, email, password }) {
  const cleanName = String(name || "").trim();
  const cleanEmail = String(email || "").trim().toLowerCase();

  if (!cleanName || !cleanEmail || !password) {
    throw new Error("Semua kolom wajib diisi.");
  }

  if (cleanName.length < 2) {
    throw new Error("Nama lengkap minimal 2 karakter.");
  }

  if (!isValidLoginEmail(cleanEmail)) {
    throw new Error(
      "Email harus menggunakan format nama@gmail.com."
    );
  }

  if (password.length < 8) {
    throw new Error("Password minimal 8 karakter.");
  }

  const { data, error } = await supabase.auth.signUp({
    email: cleanEmail,
    password,
    options: {
      data: {
        full_name: cleanName,
      },
    },
  });

  if (error) throw error;

  return data;
}

// =====================================================
// LOGIN
// =====================================================

export async function signIn({ email, password }) {
  const cleanEmail = String(email || "").trim().toLowerCase();

  if (!cleanEmail || !password) {
    throw new Error("Email dan password wajib diisi.");
  }

  if (!isValidLoginEmail(cleanEmail)) {
    throw new Error(
      "Email harus menggunakan format nama@gmail.com."
    );
  }

  const { data, error } = await supabase.auth.signInWithPassword({
    email: cleanEmail,
    password,
  });

  if (error) throw error;

  if (!data.user || !data.session) {
    throw new Error(
      "Login belum berhasil. Silakan coba kembali."
    );
  }

  localStorage.setItem("semraut.auth.uid", data.user.id);
  localStorage.setItem(
    "semraut.auth.email",
    data.user.email || cleanEmail
  );

  return data;
}

// =====================================================
// GET CURRENT SESSION
// =====================================================

export async function getCurrentSession() {
  const { data, error } = await supabase.auth.getSession();

  if (error) throw error;

  return data.session;
}

// =====================================================
// GET CURRENT USER
// =====================================================

export async function getCurrentUser() {
  const session = await getCurrentSession();

  return session?.user || null;
}

// =====================================================
// REQUIRE AUTH
// =====================================================

export async function requireAuth() {
  try {
    const session = await getCurrentSession();

    if (!session?.user) {
      location.replace(getLoginURL());
      return null;
    }

    // Tidak lagi memeriksa email_confirmed_at.
    // Akun dapat menggunakan FOKARA tanpa verifikasi email.

    localStorage.setItem("semraut.auth.uid", session.user.id);
    localStorage.setItem(
      "semraut.auth.email",
      session.user.email || ""
    );

    return session;
  } catch (error) {
    console.error("[AUTH] Session error:", error);
    location.replace(getLoginURL());
    return null;
  }
}

// =====================================================
// REDIRECT IF ALREADY AUTHENTICATED
// =====================================================

export async function redirectIfAuthenticated() {
  try {
    const session = await getCurrentSession();

    if (session?.user) {
      location.replace(getDashboardURL());
      return session;
    }

    return null;
  } catch (error) {
    console.error("[AUTH] Session check:", error);
    return null;
  }
}

// =====================================================
// RESET PASSWORD
// =====================================================

export async function resetPassword(email) {
  const cleanEmail = String(email || "").trim().toLowerCase();

  if (!cleanEmail) {
    throw new Error("Masukkan email terlebih dahulu.");
  }

  if (!isValidLoginEmail(cleanEmail)) {
    throw new Error(
      "Email harus menggunakan format nama@gmail.com."
    );
  }

  const { error } = await supabase.auth.resetPasswordForEmail(
    cleanEmail,
    {
      redirectTo: new URL(
        "./reset-password.html",
        location.href
      ).href,
    }
  );

  if (error) throw error;
}

// =====================================================
// UPDATE PASSWORD
// =====================================================

export async function updatePassword(newPassword) {
  if (!newPassword || newPassword.length < 8) {
    throw new Error("Password minimal 8 karakter.");
  }

  const { data, error } = await supabase.auth.updateUser({
    password: newPassword,
  });

  if (error) throw error;

  return data;
}

// =====================================================
// SIGN OUT
// =====================================================

export async function signOut() {
  const { error } = await supabase.auth.signOut();

  if (error) throw error;

  localStorage.removeItem("semraut.auth.uid");
  localStorage.removeItem("semraut.auth.email");
  localStorage.removeItem("semraut.pid");

  location.replace(getLoginURL());
}

// =====================================================
// AUTH HEADERS FOR FASTAPI
// =====================================================

export async function getAuthHeaders() {
  const session = await getCurrentSession();

  if (!session?.access_token) {
    throw new Error(
      "Sesi login tidak ditemukan. Silakan login kembali."
    );
  }

  return {
    Authorization: `Bearer ${session.access_token}`,
  };
}

// =====================================================
// AUTH STATE LISTENER
// =====================================================

export function onAuthStateChange(callback) {
  return supabase.auth.onAuthStateChange((event, session) => {
    if (typeof callback === "function") {
      callback(event, session);
    }
  });
}