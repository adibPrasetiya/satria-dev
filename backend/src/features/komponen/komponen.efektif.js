// Pemilihan satu baris komponen "dipakai" per produk — baris inilah yang dicocokkan ke CVE. Tanpa I/O.

// Urutan kepercayaan antarsumber untuk produk yang sama. 'manual' selalu menang; di luar itu
// baris yang memiliki versi didahulukan (bukti recon berversi lebih berguna dari isian tanpa versi).
const PERINGKAT_SUMBER = ['manual', 'formulir', 'nuclei', 'banner', 'bundle_js', 'tls'];

const kunciProduk = (k) => `${k.vendor ?? ''}|${k.produk}`;
const skor = (k) => [k.sumber === 'manual' ? 0 : 1, k.versi ? 0 : 1, PERINGKAT_SUMBER.indexOf(k.sumber)];

function lebihBaik(a, b) {
  const [x, y] = [skor(a), skor(b)];
  for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] < y[i];
  return false;
}

/** Salinan `rows` dengan penanda `dipakai` (satu per aplikasi+produk). */
export function pilihEfektif(rows) {
  const terbaik = new Map();
  for (const r of rows) {
    const kunci = `${r.applicationId ?? ''}|${kunciProduk(r)}`;
    if (!terbaik.has(kunci) || lebihBaik(r, terbaik.get(kunci))) terbaik.set(kunci, r);
  }
  const dipakai = new Set([...terbaik.values()].map((r) => r.id));
  return rows.map((r) => ({ ...r, dipakai: dipakai.has(r.id) }));
}
