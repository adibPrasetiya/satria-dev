// Pembanding versi & evaluasi rentang versi rentan (konfigurasi CPE NVD). Tanpa I/O.
//
// Mendukung format umum: 1.18.0, 2.4.41, 8.0.32-0ubuntu0.20.04, 1.1.1k (OpenSSL), 7.4.3RC1, v3.6.0.
// Versi pengguna sering kurang presisi ("MySQL 8"): bila batas rentang lebih rinci daripada versi
// komponen dan keduanya sama pada presisi itu, hasilnya 'mungkin' — bukan 'ya' atau 'tidak'.

// Penanda pra-rilis: "1.0.0-rc1" < "1.0.0". Huruf tunggal (1.1.1k) justru rilis SESUDAH 1.1.1.
const PRA_RILIS = new Set(['alpha', 'beta', 'rc', 'pre', 'preview', 'dev', 'snapshot', 'm']);

/** Token versi: angka & huruf terpisah ("8.0.32-0ubuntu0" → [8,0,32,0,"ubuntu",0]). */
export function token(versi) {
  return (String(versi ?? '').toLowerCase().replace(/^v(?=\d)/, '').match(/\d+|[a-z]+/g) ?? []).map((t) =>
    /^\d+$/.test(t) ? Number(t) : t,
  );
}

/** Jumlah segmen angka di bagian inti versi ("8" → 1, "8.0.32-0ubuntu" → 3). */
export function presisi(versi) {
  const m = /^v?(\d+(?:\.\d+)*)/i.exec(String(versi ?? ''));
  return m ? m[1].split('.').length : 0;
}

const praRilis = (t) => typeof t === 'string' && PRA_RILIS.has(t);

/** -1 / 0 / 1 seperti comparator sort. */
export function bandingkan(a, b) {
  const [x, y] = [token(a), token(b)];
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const [p, q] = [x[i], y[i]];
    if (p === undefined) return praRilis(q) ? 1 : -1;
    if (q === undefined) return praRilis(p) ? -1 : 1;
    if (p === q) continue;
    if (typeof p === typeof q) return p < q ? -1 : 1;
    // Angka vs huruf pada posisi sama: angka dianggap lebih baru (1.0.1 > 1.0.rc).
    return typeof p === 'number' ? 1 : -1;
  }
  return 0;
}

/** Potong batas ke `n` segmen inti ("1.20.1" → "1.20" untuk n=2). */
const potong = (versi, n) => /^v?(\d+(?:\.\d+)*)/i.exec(versi)[1].split('.').slice(0, n).join('.');

/**
 * Bandingkan versi komponen dengan batas, memperhitungkan presisi: 'sama' bila versi kurang rinci dan
 * cocok dengan batas pada presisinya (mis. "8" vs "8.0.36") — tidak bisa diputuskan.
 */
function bandingkanBatas(versi, batas) {
  // Versi paket distro ("8.0.32-0ubuntu0.20.04") dibandingkan pada versi hulunya bila batas tak berakhiran.
  if (/[-+~]/.test(versi) && !/[-+~]/.test(batas)) versi = versi.split(/[-+~]/)[0];
  const pv = presisi(versi);
  const pb = presisi(batas);
  if (pv && pb && pv < pb) {
    const c = bandingkan(versi, potong(batas, pv));
    return c === 0 ? 'sama' : c;
  }
  return bandingkan(versi, batas);
}

const tanpaVersi = (v) => v === null || v === undefined || v === '' || v === '*' || v === '-';

/**
 * Apakah `versi` termasuk rentang `r` ({versi, versiMulaiIncl, versiMulaiExcl, versiAkhirIncl, versiAkhirExcl})?
 * → 'ya' | 'mungkin' | 'tidak'. Versi komponen tak diketahui → 'mungkin'.
 */
export function dalamRentang(versi, r) {
  if (tanpaVersi(versi)) return 'mungkin';
  if (!tanpaVersi(r.versi)) {
    const c = bandingkanBatas(versi, r.versi);
    return c === 0 ? 'ya' : c === 'sama' ? 'mungkin' : 'tidak';
  }
  let ragu = false;
  const syarat = [
    [r.versiMulaiIncl, (c) => c >= 0],
    [r.versiMulaiExcl, (c) => c > 0],
    [r.versiAkhirIncl, (c) => c <= 0],
    [r.versiAkhirExcl, (c) => c < 0],
  ];
  for (const [batas, lolos] of syarat) {
    if (tanpaVersi(batas)) continue;
    const c = bandingkanBatas(versi, batas);
    if (c === 'sama') ragu = true;
    else if (!lolos(c)) return 'tidak';
  }
  return ragu ? 'mungkin' : 'ya';
}

/** Teks rentang untuk alasan/UI: "≥ 1.0.0 dan < 1.20.1", "= 1.18.0", "semua versi". */
export function uraikanRentang(r) {
  if (!tanpaVersi(r.versi)) return `= ${r.versi}`;
  const bagian = [
    r.versiMulaiIncl && `≥ ${r.versiMulaiIncl}`,
    r.versiMulaiExcl && `> ${r.versiMulaiExcl}`,
    r.versiAkhirIncl && `≤ ${r.versiAkhirIncl}`,
    r.versiAkhirExcl && `< ${r.versiAkhirExcl}`,
  ].filter(Boolean);
  return bagian.length ? bagian.join(' dan ') : 'semua versi';
}
