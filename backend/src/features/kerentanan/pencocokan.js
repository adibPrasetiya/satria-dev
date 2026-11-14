// Inti pencocokan komponen ↔ CVE dan skor prioritas. Tanpa I/O — mudah diuji.
import { dalamRentang, uraikanRentang } from './versi.js';

const PERINGKAT = { ya: 2, mungkin: 1, tidak: 0 };
const DISTRO = /ubuntu|debian|deb\d|\.el\d|el\d|centos|rhel|alpine|\+dfsg/i;

const label = (k) => `${k.nama}${k.versi ? ` ${k.versi}` : ''} (sumber: ${k.sumber})`;

/**
 * Evaluasi satu komponen terhadap rentang CPE (sudah difilter ke vendor/produk kerabatnya) dan hasil OSV.
 * → Map cveId → { status: 'terdampak' | 'kemungkinan', alasan }.
 */
export function evaluasiKomponen(k, cpeRows = [], paketRows = []) {
  const terbaik = new Map();
  for (const r of cpeRows) {
    const hasil = dalamRentang(k.versi, r);
    if (hasil === 'tidak') continue;
    const lama = terbaik.get(r.cveId);
    if (!lama || PERINGKAT[hasil] > PERINGKAT[lama.hasil]) terbaik.set(r.cveId, { hasil, r });
  }

  const keluaran = new Map();
  for (const [cveId, { hasil, r }] of terbaik) {
    const rentang = uraikanRentang(r);
    let status = hasil === 'ya' ? 'terdampak' : 'kemungkinan';
    let alasan;
    if (!k.versi) {
      alasan = `Versi ${k.nama} tidak diketahui (sumber: ${k.sumber}); produk ini rentan pada ${rentang}. Konfirmasi versinya.`;
    } else if (hasil === 'mungkin') {
      alasan = `${label(k)} kurang rinci untuk rentang rentan ${rentang}. Lengkapi versi hingga patch.`;
    } else {
      alasan = `${label(k)} berada dalam rentang rentan ${rentang}.`;
      if (k.keyakinan === 'rendah') {
        status = 'kemungkinan';
        alasan += ' Identifikasi komponen berkeyakinan rendah.';
      }
      if (DISTRO.test(k.versi)) alasan += ' Versi paket distro — periksa apakah tambalan sudah di-backport.';
    }
    keluaran.set(cveId, { status, alasan: alasan.slice(0, 500) });
  }

  // OSV mengevaluasi paket@versi secara persis → terdampak (mengalahkan hasil CPE).
  for (const p of paketRows) {
    keluaran.set(p.cveId, { status: 'terdampak', alasan: `OSV: paket ${p.purl}@${p.versi} terdampak advisory ini.`.slice(0, 500) });
  }
  return keluaran;
}

const DUA_TAHUN_MS = 2 * 365 * 24 * 60 * 60 * 1000;

/**
 * Komponen tanpa versi cocok dengan SELURUH riwayat CVE produknya (ribuan untuk MySQL/PHP) — terlalu bising.
 * Untuk itu hanya diperingatkan CVE yang dieksploitasi aktif (KEV), atau kritis/tinggi yang terbit ≤ 2 tahun.
 */
export function layakTanpaVersi(c = {}, sekarang = new Date()) {
  if (c.kev) return true;
  if (c.severitas !== 'kritis' && c.severitas !== 'tinggi') return false;
  const terbit = c.dipublikasiPada ? new Date(c.dipublikasiPada).getTime() : 0;
  return sekarang.getTime() - terbit <= DUA_TAHUN_MS;
}

const CVSS_DARI_SEVERITAS = { kritis: 9.5, tinggi: 8, sedang: 5.5, rendah: 2.5, info: 0 };
const BOBOT_LINGKUNGAN = { produksi: 5, staging: 2, pengembangan: 0 };
const BOBOT_KLASIFIKASI = { rahasia: 5, terbatas: 3, biasa: 0 };

/**
 * Skor prioritas 0–100: dieksploitasi aktif (KEV) → peluang eksploitasi (EPSS) → keparahan (CVSS),
 * ditambah bobot aset (lingkungan produksi, klasifikasi data). 'kemungkinan' diberi bobot 60%.
 */
export function hitungPrioritas(c, status, app = {}) {
  const cvss = c.cvssSkor !== null && c.cvssSkor !== undefined ? Number(c.cvssSkor) : (CVSS_DARI_SEVERITAS[c.severitas] ?? 5);
  let skor =
    (c.kev ? 40 : 0) +
    Math.round(Number(c.epss ?? 0) * 30) +
    Math.min(25, Math.round(cvss * 2.5)) +
    (BOBOT_LINGKUNGAN[app.environment] ?? 0) +
    (BOBOT_KLASIFIKASI[app.dataClassification] ?? 0);
  if (status === 'kemungkinan') skor = Math.round(skor * 0.6);
  return Math.max(0, Math.min(100, skor));
}

/** Tingkat untuk UI: 'segera' | 'tinggi' | 'sedang' | 'rendah'. */
export function tingkatPrioritas(skor, kev = false) {
  if (kev || skor >= 70) return 'segera';
  if (skor >= 45) return 'tinggi';
  if (skor >= 25) return 'sedang';
  return 'rendah';
}
