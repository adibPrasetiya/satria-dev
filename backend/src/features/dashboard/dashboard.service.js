import { verdictService } from '../scans/verdict.service.js';
import { dashboardRepository } from './dashboard.repository.js';

// Peta Indeks Ketahanan Keamanan Siber — dibuat ringan:
//
// - Memakai ringkasan yang SUDAH tersimpan per scan (scans.score & findings_*; diisi saat scan selesai),
//   bukan menghitung ulang dari scan_tasks: satu query aplikasi + scan selesai terakhirnya.
// - GET /dashboard/peta hanya berisi kebutuhan peta (titik, indeks, jumlah aplikasi) + sebaran severity
//   nasional. Rincian provinsi diambil terpisah per provinsi (GET /dashboard/peta/provinsi/:kode).
// - Data dasar di-cache di memori selama CACHE_MS (10 menit) sehingga panggilan peta & rincian provinsi tidak
//   mengulang query; `versi` berubah bila datanya berubah → frontend tahu kapan membuang cache-nya.
//
// - Skor aplikasi = skor kepatuhan scan selesai terakhirnya (kontrol pass ÷ teruji). Aplikasi tanpa
//   scan selesai/skor diabaikan.
// - Aplikasi dihitung ke satuan pemiliknya; bila satuan itu belum punya koordinat, ke induk terdekat yang
//   punya (mis. sub-satuan tanpa lokasi → Kodim/Kodam di atasnya). Tanpa induk berlokasi → tak terpetakan.
// - Kekuatan satuan = rata-rata skor aplikasinya; sebaran = jumlah temuan (metode FAILED) per severity.
// - Tidak ada nama aplikasi di keluaran (data agregat), sehingga aman untuk semua peran.

const MAKS_KEDALAMAN = 10;
// Data dasbor diperbarui tiap 10 menit (selaras siklus muat ulang frontend).
const CACHE_MS = 10 * 60_000;
const TINGKAT = ['kritis', 'tinggi', 'sedang', 'rendah'];

const angka = (v) => (v === null || v === undefined ? null : Number(v));
const sebaranKosong = () => ({ kritis: 0, tinggi: 0, sedang: 0, rendah: 0 });
const tambahSebaran = (a, b) => {
  for (const k of TINGKAT) a[k] += b[k];
  return a;
};

/** "Kodam III/Siliwangi" → { nama: "Kodam III", sebutan: "Siliwangi" }. */
function pecahNama(name) {
  const i = name.indexOf('/');
  return i < 0 ? { nama: name, sebutan: '' } : { nama: name.slice(0, i).trim(), sebutan: name.slice(i + 1).trim() };
}

/**
 * Hitung titik peta dari satuan & aplikasi (+ ringkasan scan selesai terakhirnya). Murni.
 * @returns {{ titik: object[], kotama: object[], ringkasan: object, nasional: { sebaran: object } }}
 *   `titik[i]._sebaran` (internal) dipakai rincian provinsi; dibuang dari respons peta ringkas.
 */
export function hitungPeta({ satuan, aplikasi }) {
  const perId = new Map(satuan.map((u) => [Number(u.id), u]));
  const berlokasi = (u) => u && angka(u.latitude) !== null && angka(u.longitude) !== null;

  /** Naik dari satuan ini ke akar; kembalikan yang pertama memenuhi `syarat`. */
  function naikSampai(unitId, syarat) {
    let u = perId.get(Number(unitId));
    for (let i = 0; u && i < MAKS_KEDALAMAN; i += 1) {
      if (syarat(u)) return u;
      u = perId.get(Number(u.parentId));
    }
    return null;
  }

  const titik = new Map();
  const nasional = sebaranKosong();
  let terpetakan = 0;
  let belumTerpetakan = 0;
  let belumDiuji = 0;
  for (const a of aplikasi) {
    const skor = angka(a.score);
    if (!a.scanId || skor === null) {
      belumDiuji += 1;
      continue;
    }
    const temuan = {
      kritis: angka(a.kritis) ?? 0,
      tinggi: angka(a.tinggi) ?? 0,
      sedang: angka(a.sedang) ?? 0,
      rendah: angka(a.rendah) ?? 0,
    };
    tambahSebaran(nasional, temuan);
    const lokasi = naikSampai(a.unitId, berlokasi);
    if (!lokasi) {
      belumTerpetakan += 1;
      continue;
    }
    terpetakan += 1;
    const t = titik.get(lokasi.id) ?? { unit: lokasi, skor: [], sebaran: sebaranKosong() };
    t.skor.push(skor);
    tambahSebaran(t.sebaran, temuan);
    titik.set(lokasi.id, t);
  }

  const kotamaDari = (unitId) => naikSampai(unitId, (u) => u.type === 'KOTAMA');
  return {
    titik: [...titik.values()].map(({ unit, skor, sebaran }) => ({
      id: String(unit.id),
      nama: unit.name,
      jenis: unit.type,
      kotama: kotamaDari(unit.id) ? String(kotamaDari(unit.id).id) : null,
      lat: angka(unit.latitude),
      lng: angka(unit.longitude),
      provinsi_kode: unit.provinceCode ?? null,
      kekuatan: Math.round(skor.reduce((x, y) => x + y, 0) / skor.length),
      jumlah_aplikasi: skor.length,
      _sebaran: sebaran,
    })),
    kotama: satuan
      .filter((u) => u.type === 'KOTAMA' && berlokasi(u))
      .map((u) => ({
        id: String(u.id),
        ...pecahNama(u.name),
        lat: angka(u.latitude),
        lng: angka(u.longitude),
        provinsi_kode: u.provinceCode ?? null,
      })),
    ringkasan: {
      aplikasi_terpetakan: terpetakan,
      aplikasi_belum_terpetakan: belumTerpetakan,
      aplikasi_belum_diuji: belumDiuji,
    },
    nasional: { sebaran: nasional },
  };
}

/** Rincian satu provinsi dari hasil hitungPeta. Murni. */
export function rincianProvinsi(dasar, kode) {
  const anggota = dasar.titik.filter((t) => t.provinsi_kode === kode);
  const bobot = anggota.reduce((s, t) => s + t.jumlah_aplikasi, 0);
  return {
    kode,
    satuan: anggota.length,
    aplikasi: bobot,
    // Indeks tertimbang jumlah aplikasi (sama dengan agregasi di frontend).
    indeks: bobot ? Math.round((anggota.reduce((s, t) => s + t.kekuatan * t.jumlah_aplikasi, 0) / bobot) * 10) / 10 : null,
    sebaran: anggota.reduce((s, t) => tambahSebaran(s, t._sebaran), sebaranKosong()),
  };
}

/** Versi data ringkas (berubah bila isi berubah) — kunci cache frontend. */
function versiDari(dasar) {
  const kunci = JSON.stringify([dasar.titik.map((t) => [t.id, t.kekuatan, t.jumlah_aplikasi, t._sebaran]), dasar.nasional]);
  let h = 0;
  for (let i = 0; i < kunci.length; i += 1) h = (Math.imul(31, h) + kunci.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

export function createDashboardService({
  repository = dashboardRepository,
  penilai = verdictService,
  sekarang = () => Date.now(),
} = {}) {
  let cache = null; // { waktu, dasar, versi, diperbarui }

  async function dasarPeta() {
    if (cache && sekarang() - cache.waktu < CACHE_MS) return cache;
    // Scan lama yang ringkasan penilaiannya belum tersimpan dilengkapi dulu (sekali; murah bila sudah lengkap).
    await penilai.lengkapiYangKosong();
    const [satuan, aplikasi] = await Promise.all([repository.satuan(), repository.aplikasiRingkas()]);
    const dasar = hitungPeta({ satuan, aplikasi });
    cache = { waktu: sekarang(), dasar, versi: versiDari(dasar), diperbarui: new Date(sekarang()).toISOString() };
    return cache;
  }

  return {
    /** Ringkas: titik peta + sebaran nasional (tanpa rincian provinsi). */
    async peta() {
      const { dasar, versi, diperbarui } = await dasarPeta();
      return {
        titik: dasar.titik.map(({ _sebaran, ...t }) => t),
        kotama: dasar.kotama,
        ringkasan: dasar.ringkasan,
        nasional: dasar.nasional,
        versi,
        diperbarui,
      };
    },

    /** Rincian satu provinsi (dipanggil per provinsi saat disorot). */
    async provinsi(kode) {
      const { dasar, versi } = await dasarPeta();
      return { ...rincianProvinsi(dasar, kode), versi };
    },
  };
}

export const dashboardService = createDashboardService();
