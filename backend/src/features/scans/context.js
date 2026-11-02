// Membentuk payload yang dibaca worker (worker/satya_worker/models.py):
// ScanContext (context) + MetodeSpec (metode). Nama field snake_case sesuai
// yang diharapkan from_dict() di worker.

/** Akun uji dari target.accounts → bentuk list yang dibaca worker (ScanContext.akun_uji).
 *  Mendukung bentuk baru `accounts.daftar: [...]` (jalur otomatis, N akun) maupun bentuk lama
 *  `{ utama, penguncian }` (jalur terarah). Hanya akun ber-username+password yang disertakan;
 *  kunci dibangkitkan akun_uji_1..N agar worker/check dapat merujuk `akun_uji_1` dst. */
function buildAkunUji(accounts) {
  const sumber = Array.isArray(accounts?.daftar)
    ? accounts.daftar
    : [accounts?.utama, accounts?.penguncian];
  const out = [];
  for (const a of sumber) {
    if (!a?.username || !a?.password) continue;
    out.push({
      kunci: `akun_uji_${out.length + 1}`,
      username: a.username,
      password: a.password,
      terisi: true,
      totp_secret: a.totp_secret || null,
      totp_digits: a.totp_digits ?? null,
      totp_period: a.totp_period ?? null,
      totp_algoritma: a.totp_algoritma ?? null,
    });
  }
  return out;
}

/** Bagian ScanContext (tanpa daftar metode). Kata sandi akun uji hanya di memori. */
export function buildContext({ scan, application, target }) {
  const opt = target?.options ?? {};
  const disc = target?.discovery ?? {};
  return {
    scan_id: String(scan.id),
    aplikasi_id: String(application.id),
    base_url: application.baseUrl,
    // Hint spec OpenAPI untuk fase penemuan (opsional; worker mencari otomatis bila kosong).
    openapi_url: opt.openapi_url ?? '',
    titik_uji: target?.testPoints ?? {},
    form: target?.forms ?? {},
    akun_uji: buildAkunUji(target?.accounts),
    intrusif: {
      izinkan_penguncian: Boolean(opt.izinkan_penguncian),
      jendela_mulai: opt.jendela_mulai ?? '',
      jendela_selesai: opt.jendela_selesai ?? '',
    },
    // Inventaris & kandidat uji hasil discovery — dibaca check hilir (validasi input,
    // kontrol akses, konfigurasi, dll.) agar tak perlu mengklasifikasi ulang.
    endpoints: disc.endpoints_lengkap ?? [],
    flows: disc.flows ?? [],
    kandidat_uji: disc.kandidat_uji ?? null,
  };
}

/** Satu MetodeSpec untuk worker. `control` menyumbang parameter default (mis. panjang_minimum). */
export function buildMetodeSpec({ method, control }) {
  const parameter = { ...(control?.parameters ?? {}), ...(method.parameters ?? {}) };
  return {
    id: method.code,
    check_id: method.checkId,
    titik_uji: method.testPoint,
    nama: method.name,
    kriteria_lulus: method.passCriteria,
    butuh_autentikasi: Boolean(method.requiresAuth),
    profil: method.profile,
    engine: method.engine,
    parameter,
  };
}
