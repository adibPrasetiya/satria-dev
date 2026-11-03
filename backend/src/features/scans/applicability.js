// Port ringkas dari penerapanMetode() di frontend/src/lib/catalog.ts.
// Memutuskan apakah sebuah metode dijalankan worker, atau langsung berstatus
// tidak_berlaku / tidak_dapat_diverifikasi berdasarkan persiapan uji (scan_targets).

// Titik uji yang selalu berlaku dan tidak perlu dipetakan pengguna.
export const TITIK_UJI_TETAP = ['global', 'dokumen'];

// Engine yang dieksekusi worker (nuclei → asesor sampai didukung).
// 'zap' butuh worker engine zap + ZAP terkonfigurasi; 'playwright' butuh worker engine playwright
// (browser Chromium terpasang); 'sslyze' butuh worker engine sslyze (paket sslyze terpasang) untuk
// fungsi Keamanan Komunikasi (COMM). Bila worker/alatnya tak tersedia, check melapor
// tidak_dapat_diverifikasi saat runtime (tidak menghakimi). PENTING: pastikan ada worker dengan
// engine terkait yang berjalan agar task tak menggantung di antrean.
const ENGINE_DIDUKUNG = new Set(['custom', 'zap', 'playwright', 'sslyze']);

/**
 * Akun uji utama terisi (punya username+password) → metode butuh_autentikasi bisa jalan.
 * Mendukung dua bentuk penyimpanan: `accounts.daftar` (wizard otomatis) dan `accounts.utama`
 * (persiapan manual) — sama dengan `context.buildAkunUji`.
 */
export const akunUtamaAda = (target) => {
  const acc = target.accounts;
  const daftar = Array.isArray(acc?.daftar) ? acc.daftar : [acc?.utama];
  return daftar.some((a) => !!(a && a.username && a.password));
};

/**
 * @param {{ testPoints?: Record<string, {tersedia?: boolean}>, accounts?: object, options?: {izinkan_penguncian?: boolean} }} target
 * @param {{ testPoint: string, kind: string, engine: string, requiresAuth: boolean, profile: string }} method
 * @returns {{ jalan: true } | { jalan: false, status: 'tidak_berlaku'|'tidak_dapat_diverifikasi', alasan: string }}
 */
/**
 * Titik uji fungsi Validasi Input diturunkan dari inventaris penemuan bila belum dipetakan
 * (hasil penemuan lama belum mencatat `api`/`form_input`): `api` = ada endpoint API,
 * `form_input` = ada endpoint API yang menerima field body/query.
 */
export function titikDariInventaris(target, testPoint) {
  if (testPoint !== 'api' && testPoint !== 'form_input') return false;
  const eps = Array.isArray(target.discovery?.endpoints_lengkap) ? target.discovery.endpoints_lengkap : [];
  const api = eps.filter((e) => (e?.lapisan ?? 'api') === 'api');
  if (testPoint === 'api') return api.length > 0;
  return api.some((e) => (e.request_fields ?? []).some((f) => f?.lokasi === 'body' || f?.lokasi === 'query'));
}

export function penerapanMetode(target, method) {
  const titikTetap = TITIK_UJI_TETAP.includes(method.testPoint);
  if (!titikTetap && !target.testPoints?.[method.testPoint]?.tersedia && !titikDariInventaris(target, method.testPoint)) {
    return {
      jalan: false,
      status: 'tidak_berlaku',
      alasan: `Titik uji "${method.testPoint}" tidak tersedia pada aplikasi.`,
    };
  }
  if (method.kind === 'manual' || method.engine === 'manual') {
    return {
      jalan: false,
      status: 'tidak_dapat_diverifikasi',
      alasan: 'Metode manual — menunggu tinjauan asesor.',
    };
  }
  if (method.requiresAuth && !akunUtamaAda(target)) {
    return {
      jalan: false,
      status: 'tidak_dapat_diverifikasi',
      alasan: 'Membutuhkan akun uji, tetapi akun uji belum diisi.',
    };
  }
  if (method.profile === 'intrusif' && !target.options?.izinkan_penguncian) {
    return {
      jalan: false,
      status: 'tidak_dapat_diverifikasi',
      alasan: 'Izin pengujian berisiko (penguncian akun) belum diberikan.',
    };
  }
  if (!ENGINE_DIDUKUNG.has(method.engine)) {
    return {
      jalan: false,
      status: 'tidak_dapat_diverifikasi',
      alasan: `Engine "${method.engine}" belum didukung worker (diserahkan asesor).`,
    };
  }
  return { jalan: true };
}

/** true bila metode manual (menunggu tinjauan asesor, bukan sekadar belum didukung). */
export const butuhTinjauan = (method) => method.kind === 'manual' || method.engine === 'manual';
