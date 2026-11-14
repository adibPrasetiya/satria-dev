// Parser teks teknologi bebas ("Laravel 10 + PHP 8.2", "Nginx di Ubuntu 22.04", "nginx/1.18.0") menjadi
// komponen baku (vendor/produk CPE, versi, purl) memakai kamus komponen. Tanpa I/O — mudah diuji.
import { KAMUS_KOMPONEN } from '../../config/kamusKomponen.js';

const MAKS_SEGMEN = 10;
const MAKS_BUKTI = 255;

const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const slug = (s) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9.+#-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100);

/** Identitas baku satu entri kamus. */
function identitas(entri) {
  const [utama] = entri.cpe ?? [];
  const [vendor, produk] = utama ? utama.split(':') : [null, slug(entri.nama)];
  return { vendor, produk, nama: entri.nama, bagian: entri.bagian ?? 'a', purlDasar: entri.purl ?? null };
}

// Semua alias → entri, alias terpanjang dicoba lebih dulu (mis. "apache tomcat" sebelum "apache").
// Batas kata: tak didahului huruf/angka/titik, tak diikuti huruf (angka boleh: "vue3", "php8.2").
const ALIAS = KAMUS_KOMPONEN.flatMap((entri) =>
  entri.alias.map((a) => ({ a, entri: identitas(entri), re: new RegExp(`(?<![a-z0-9.])${escapeRegex(a)}(?![a-z])`, 'g') })),
).sort((x, y) => y.a.length - x.a.length);

// Pemisah antar-komponen dalam satu isian. "/" hanya pemisah bila TIDAK diikuti versi ("nginx/1.18" tetap satu).
const PEMISAH = /\s*(?:[,;+&|()[\]]|\/(?!\s*v?\d))\s*/;

// Versi: inti angka bertitik, akhiran ("-0ubuntu0.20.04", "RC1") hanya dipertahankan bila mengandung angka.
const VERSI = /(?<![0-9a-z.])v?(\d+(?:\.\d+){0,3})([-~+]?[0-9a-z][0-9a-z.~+-]*)?/i;

/** Versi pertama dalam `teks`, atau null. */
export function ambilVersi(teks) {
  const m = VERSI.exec(teks ?? '');
  if (!m) return null;
  const akhiran = m[2] && /\d/.test(m[2]) ? m[2] : '';
  return (m[1] + akhiran).slice(0, 60);
}

const versiCpe = (versi) => (versi && /^[0-9a-z._-]+$/i.test(versi) ? versi : '*');

/** Lengkapi identitas dengan versi → baris komponen (tanpa applicationId/sumber). */
function bentuk(id, { versi, kategori, keyakinan, bukti }) {
  return {
    kategori,
    vendor: id.vendor,
    produk: id.produk,
    nama: id.nama,
    versi,
    cpe: id.vendor ? `cpe:2.3:${id.bagian}:${id.vendor}:${id.produk}:${versiCpe(versi)}:*:*:*:*:*:*:*` : null,
    purl: id.purlDasar ? (versi ? `${id.purlDasar}@${encodeURIComponent(versi)}` : id.purlDasar) : null,
    keyakinan,
    bukti: bukti.slice(0, MAKS_BUKTI),
  };
}

/** Komponen dalam satu segmen: alias kamus yang ditemukan (tak saling tumpang), versi = yang mengikutinya. */
function uraiSegmen(segmen, kategori) {
  const kecil = segmen.toLowerCase();
  const terpakai = [];
  for (const { re, entri } of ALIAS) {
    re.lastIndex = 0;
    for (let m; (m = re.exec(kecil)); ) {
      const [awal, akhir] = [m.index, m.index + m[0].length];
      if (terpakai.some((t) => awal < t.akhir && akhir > t.awal)) continue;
      terpakai.push({ awal, akhir, entri });
    }
  }
  terpakai.sort((x, y) => x.awal - y.awal);

  if (!terpakai.length) {
    // Tak dikenal kamus: tetap dicatat (keyakinan rendah) agar terlihat & bisa dikoreksi/ditambahkan ke kamus.
    const versi = ambilVersi(segmen);
    const namaMentah = (versi ? segmen.slice(0, segmen.toLowerCase().search(VERSI)) : segmen).trim();
    if (!/[a-z]/i.test(namaMentah) || namaMentah.length > 60) return [];
    const id = { vendor: null, produk: slug(namaMentah), nama: namaMentah.slice(0, 100), bagian: 'a', purlDasar: null };
    return id.produk ? [bentuk(id, { versi, kategori, keyakinan: 'rendah', bukti: segmen })] : [];
  }

  return terpakai.map((t, i) => {
    const celah = segmen.slice(t.akhir, terpakai[i + 1]?.awal ?? segmen.length);
    return bentuk(t.entri, { versi: ambilVersi(celah), kategori, keyakinan: 'tinggi', bukti: segmen });
  });
}

/** Urai satu isian teks bebas → daftar komponen (satu per produk). */
export function uraiTeks(teks, kategori = 'lainnya') {
  const bersih = String(teks ?? '').replace(/\s+/g, ' ').trim();
  if (!bersih) return [];
  const segmen = bersih.split(PEMISAH).filter(Boolean).slice(0, MAKS_SEGMEN);
  return gabungUnik(segmen.flatMap((s) => uraiSegmen(s, kategori)));
}

/** Satu komponen per produk; bila produk muncul berulang, yang berversi didahulukan. */
export function gabungUnik(items) {
  const peta = new Map();
  for (const it of items) {
    const lama = peta.get(it.produk);
    if (!lama || (!lama.versi && it.versi)) peta.set(it.produk, it);
  }
  return [...peta.values()];
}

const KATEGORI_FORMULIR = ['frontend', 'backend', 'database', 'server'];

/** Field `teknologi` aset ({frontend, backend, database, server}) → komponen bersumber formulir. */
export function dariTeknologi(teknologi = {}) {
  return gabungUnik(KATEGORI_FORMULIR.flatMap((k) => uraiTeks(teknologi?.[k], k)));
}
