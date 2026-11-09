// Konteks untuk AI penyusun laporan: selengkap mungkin agar rekomendasi tepat sasaran, tetapi TANPA
// informasi sensitif. Murni (tanpa I/O) agar mudah diuji.
//
// DIKIRIM  : profil teknis aplikasi (lingkungan, klasifikasi data, teknologi), metode uji (pendekatan,
//            mode, profil, durasi, acuan), putusan & skor, ringkasan per fungsi keamanan, serta tiap
//            temuan (kode/nama metode, kontrol, severity, titik uji, kriteria lulus, ringkasan hasil).
// TIDAK    : nama aplikasi, satuan, PIC & kontak, URL/host/IP target, akun & kredensial uji, nilai
//            token/cookie/header, bukti request/response mentah, nomor laporan.
// Teks hasil uji dari worker tetap disaring (`sanitasi`) karena bisa memuat URL, host, akun, atau token.

const SENSITIF =
  /(pass(?:word|wd)?|sandi|token|secret|rahasia|authorization|auth|api[-_]?key|cookie|session|sesi|sid|otp|totp|mfa|credential|kredensial|bearer|jwt|nik|nip|nrp|kartu|card|cvv|pin)/i;

const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const USERNAME_GENERIK = new Set([
  'admin', 'administrator', 'root', 'user', 'users', 'test', 'tester', 'guest', 'demo', 'operator',
  'pengguna', 'penguji', 'superadmin', 'staff', 'staf', 'member', 'pegawai', 'uji',
]);

/**
 * Saring teks bebas: URL → path saja (host disamarkan), host/nama target & istilah privat → placeholder,
 * email/IP/JWT/nilai panjang → placeholder, pasangan kunci=nilai sensitif → nilai disamarkan.
 * @param {string} teks
 * @param {{ host?: string, privat?: { kata: string, ganti: string }[] }} opsi
 */
export function sanitasi(teks, { host = '', privat = [] } = {}) {
  if (!teks) return '';
  let s = String(teks);

  // URL lengkap → [host]/path (ID numerik / UUID pada path diganti {id}).
  s = s.replace(/\bhttps?:\/\/[^\s"'<>)]+/gi, (url) => {
    try {
      const u = new URL(url);
      const path = u.pathname
        .replace(/\/\d+(?=\/|$)/g, '/{id}')
        .replace(/\/[0-9a-f]{8}-[0-9a-f-]{27,}(?=\/|$)/gi, '/{id}');
      return `[host]${path === '/' ? '' : path}`;
    } catch {
      return '[url]';
    }
  });
  if (host) s = s.replace(new RegExp(escapeRegex(host), 'gi'), '[host]');
  for (const { kata, ganti } of privat) {
    const k = kata?.trim();
    if (!k || k.length < 3) continue;
    // Batas kata hanya di sisi yang berupa karakter kata (agar "admin_cuti" tak cocok di "admin_cuti2").
    const awal = /^\w/.test(k) ? '\\b' : '';
    const akhir = /\w$/.test(k) ? '\\b' : '';
    s = s.replace(new RegExp(`${awal}${escapeRegex(k)}${akhir}`, 'gi'), ganti);
  }

  s = s
    .replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, '[email]')
    .replace(/\beyJ[\w-]+\.[\w-]+\.[\w-]+/g, '[token]')
    .replace(/\bBearer\s+[\w.~+/=-]+/gi, 'Bearer [token]')
    .replace(/\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b/g, '[ip]')
    .replace(/\b[a-f0-9]{24,}\b/gi, '[nilai]')
    .replace(/\b[A-Za-z0-9+/_-]{32,}={0,2}/g, '[nilai]');

  // kunci=nilai / kunci: nilai / "kunci":"nilai" dengan kunci sensitif → nilai disamarkan.
  s = s.replace(
    /(["']?)([\w.-]{2,40})\1(\s*[:=]\s*)(["']?)([^\s"',;&]+)\4/g,
    (m, q, kunci, sep, q2) => (SENSITIF.test(kunci) ? `${q}${kunci}${q}${sep}${q2}[disamarkan]${q2}` : m),
  );
  return s.length > 600 ? `${s.slice(0, 600)}…` : s;
}

/**
 * Susun konteks AI dari data scan.
 * @param {object} d
 * @param {{ name: string, unit: string, picName: string, baseUrl: string, environment: string, dataClassification: string, techFrontend?: string, techBackend?: string, techDatabase?: string, techServer?: string }} d.aplikasi
 * @param {{ approach: string, mode: string, profile: string, startedAt: Date|string, finishedAt?: Date|string|null, verdict?: string|null, score?: number|null }} d.scan
 * @param {object[]} d.metode baris task + katalog (lihat laporan.repository.metodeScan)
 * @param {string[]} [d.akunUji] username akun uji (disamarkan bila muncul di teks)
 * @param {string} [d.acuan] regulasi acuan katalog
 */
export function susunKonteks({ aplikasi, scan, metode, akunUji = [], acuan = '' }) {
  let host = '';
  try {
    host = new URL(aplikasi.baseUrl).host;
  } catch {
    /* URL tak valid → tanpa penyaringan host */
  }
  const privat = [
    { kata: aplikasi.name, ganti: '[aplikasi]' },
    { kata: aplikasi.unit, ganti: '[satuan]' },
    { kata: aplikasi.picName, ganti: '[pic]' },
    // Username akun uji yang spesifik disamarkan; kata generik (admin, user, …) bukan informasi
    // sensitif dan justru bermakna dalam temuan (mis. "fungsi admin"), jadi dibiarkan.
    ...akunUji.filter((u) => !USERNAME_GENERIK.has(u.trim().toLowerCase())).map((u) => ({ kata: u, ganti: '[akun_uji]' })),
  ];
  const bersih = (t) => sanitasi(t, { host, privat });

  const statusDari = (m) => m.result?.status ?? (m.status === 'selesai' ? 'tidak_dapat_diverifikasi' : m.status);
  const perFungsi = new Map();
  const hitungan = { lulus: 0, gagal: 0, tidak_dapat_diverifikasi: 0, tidak_berlaku: 0, luar_cakupan: 0 };
  for (const m of metode) {
    const st = statusDari(m);
    if (st in hitungan) hitungan[st] += 1;
    if (!m.functionCode) continue;
    const f = perFungsi.get(m.functionCode) ?? { kode: m.functionCode, nama: m.functionName, lulus: 0, gagal: 0, belum_terverifikasi: 0 };
    if (st === 'lulus') f.lulus += 1;
    else if (st === 'gagal') f.gagal += 1;
    else if (st === 'tidak_dapat_diverifikasi') f.belum_terverifikasi += 1;
    perFungsi.set(m.functionCode, f);
  }

  const URUT = { kritis: 0, tinggi: 1, sedang: 2, rendah: 3, info: 4 };
  const temuan = metode
    .filter((m) => statusDari(m) === 'gagal' && m.severity && m.severity !== 'info')
    .sort((a, b) => (URUT[a.severity] ?? 9) - (URUT[b.severity] ?? 9))
    .map((m) => ({
      metode_id: m.methodCode,
      nama: m.methodName,
      fungsi: m.functionName ? `${m.functionCode} — ${m.functionName}` : m.functionCode,
      kontrol: m.controlRef ? `${m.controlRef}: ${m.controlDescription}` : m.controlDescription,
      severity: m.severity,
      titik_uji: m.testPoint,
      kriteria_lulus: m.passCriteria,
      hasil: bersih(m.result?.ringkasan),
      detail: bersih(m.result?.detail),
    }));

  const menit = scan.finishedAt
    ? Math.max(1, Math.round((new Date(scan.finishedAt) - new Date(scan.startedAt)) / 60000))
    : null;

  return {
    aplikasi: {
      lingkungan: aplikasi.environment,
      klasifikasi_data: aplikasi.dataClassification,
      teknologi: Object.fromEntries(
        [
          ['frontend', aplikasi.techFrontend],
          ['backend', aplikasi.techBackend],
          ['basis_data', aplikasi.techDatabase],
          ['server', aplikasi.techServer],
        ].filter(([, v]) => v),
      ),
    },
    pengujian: {
      pendekatan: scan.approach === 'blackbox' ? 'Black Box (tanpa akun uji & informasi internal)' : 'Grey Box (dengan akun uji terbatas)',
      mode: scan.mode === 'eksploratif' ? 'eksploratif (penemuan otomatis)' : 'terarah',
      profil: scan.profile,
      durasi_menit: menit,
      acuan,
    },
    hasil: {
      putusan: scan.verdict ?? null,
      skor_kepatuhan: scan.score ?? null,
      jumlah_metode_uji_per_status: hitungan,
      per_fungsi: [...perFungsi.values()],
    },
    temuan,
    belum_terverifikasi: metode
      .filter((m) => statusDari(m) === 'tidak_dapat_diverifikasi' && m.methodName)
      .slice(0, 40)
      .map((m) => ({ metode_id: m.methodCode, nama: m.methodName })),
  };
}

/** Prompt penyusunan laporan (bahasa Indonesia, keluaran JSON ketat). */
export function bangunPrompt(konteks) {
  return `Anda adalah auditor keamanan aplikasi web senior yang menyusun laporan asesmen kelaikan keamanan
untuk instansi pemerintah/militer Indonesia, mengacu pada standar keamanan aplikasi BSSN dan OWASP.

Data hasil pengujian (sudah disamarkan; placeholder seperti [host], [aplikasi], [akun_uji], [token]
menggantikan informasi sensitif — jangan berspekulasi tentang nilai aslinya):
${JSON.stringify(konteks, null, 2)}

Catatan data: "jumlah_metode_uji_per_status" dan "per_fungsi" menghitung METODE UJI (bukan kontrol);
"skor_kepatuhan" adalah persentase kontrol lulus dari kontrol teruji. Jangan menyebut angka metode sebagai jumlah kontrol.

Tugas:
1. "ringkasan_eksekutif": 2–4 paragraf bahasa Indonesia formal untuk pimpinan non-teknis: kondisi
   keamanan secara umum, putusan kelaikan beserta alasannya, risiko utama terhadap layanan/data, dan
   prioritas tindak lanjut. Jangan sebut nama produk/vendor yang tidak ada di data.
2. "rekomendasi": SATU entri untuk SETIAP temuan pada data (gunakan metode_id yang sama persis), berisi:
   - "judul": tindakan perbaikan singkat (≤ 12 kata)
   - "prioritas": "segera" | "tinggi" | "sedang" | "rendah" (selaraskan dengan severity & dampak)
   - "penjelasan": 2–3 kalimat — mengapa ini berisiko & dampaknya bila dieksploitasi
   - "langkah": 3–6 langkah teknis konkret yang dapat dikerjakan tim pengembang/administrator,
     disesuaikan dengan teknologi aplikasi bila diketahui
   - "verifikasi": cara memastikan perbaikan berhasil (mengacu kriteria lulus)
3. "rekomendasi_umum": 3–5 rekomendasi strategis (proses, tata kelola, pengujian ulang), termasuk
   tindak lanjut untuk metode yang belum terverifikasi bila ada.

Balas HANYA dengan JSON valid berbentuk:
{"ringkasan_eksekutif": "...", "rekomendasi": [{"metode_id": "...", "judul": "...", "prioritas": "...",
"penjelasan": "...", "langkah": ["..."], "verifikasi": "..."}], "rekomendasi_umum": ["..."]}`;
}
