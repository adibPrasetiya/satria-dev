import { dashboardRepository } from './dashboard.repository.js';

// Peta Indeks Ketahanan Keamanan Siber.
//
// - Skor aplikasi = % metode LULUS dari metode yang teruji (lulus + gagal) pada scan selesai terakhirnya.
//   Metode tidak_berlaku / tidak_dapat_diverifikasi tidak dihitung. Aplikasi tanpa metode teruji diabaikan.
// - Aplikasi dihitung ke satuan pemiliknya; bila satuan itu belum punya koordinat, ke induk terdekat yang
//   punya (mis. sub-satuan tanpa lokasi → Kodim/Kodam di atasnya). Tanpa induk berlokasi → tak terpetakan.
// - Kekuatan satuan = rata-rata skor aplikasinya; kerentanan = metode GAGAL (jumlah aplikasi terdampak).
// - Tidak ada nama aplikasi di keluaran (data agregat), sehingga aman untuk semua peran.

const MAKS_KEDALAMAN = 10;

/** Severity katalog → tingkat yang ditampilkan dasbor. */
const TINGKAT = { kritis: 'kritis', tinggi: 'tinggi', sedang: 'sedang', rendah: 'rendah', info: 'rendah' };

const angka = (v) => (v === null || v === undefined ? null : Number(v));

/** "Kodam III/Siliwangi" → { nama: "Kodam III", sebutan: "Siliwangi" }. */
function pecahNama(name) {
  const i = name.indexOf('/');
  return i < 0 ? { nama: name, sebutan: '' } : { nama: name.slice(0, i).trim(), sebutan: name.slice(i + 1).trim() };
}

export function hitungPeta({ satuan, aplikasi, hasil }) {
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

  // Skor & metode gagal per scan.
  const perScan = new Map();
  for (const h of hasil) {
    const v = perScan.get(Number(h.scanId)) ?? { lulus: 0, gagal: [] };
    if (h.status === 'lulus') v.lulus += 1;
    else v.gagal.push(h);
    perScan.set(Number(h.scanId), v);
  }

  const titik = new Map();
  let terpetakan = 0;
  let belumTerpetakan = 0;
  let belumDiuji = 0;
  for (const a of aplikasi) {
    const s = a.scanId ? perScan.get(Number(a.scanId)) : null;
    const teruji = s ? s.lulus + s.gagal.length : 0;
    if (!teruji) {
      belumDiuji += 1;
      continue;
    }
    const lokasi = naikSampai(a.unitId, berlokasi);
    if (!lokasi) {
      belumTerpetakan += 1;
      continue;
    }
    terpetakan += 1;
    const t = titik.get(lokasi.id) ?? { unit: lokasi, skor: [], rentan: new Map() };
    t.skor.push((s.lulus / teruji) * 100);
    for (const g of s.gagal) {
      const k = t.rentan.get(g.kode) ?? {
        kode: g.kode,
        nama: g.nama ?? g.kode,
        tingkat: TINGKAT[g.severity] ?? 'sedang',
        aplikasi: 0,
      };
      k.aplikasi += 1;
      t.rentan.set(g.kode, k);
    }
    titik.set(lokasi.id, t);
  }

  const kotamaDari = (unitId) => naikSampai(unitId, (u) => u.type === 'KOTAMA');
  return {
    titik: [...titik.values()].map(({ unit, skor, rentan }) => ({
      id: String(unit.id),
      nama: unit.name,
      jenis: unit.type,
      kotama: kotamaDari(unit.id) ? String(kotamaDari(unit.id).id) : null,
      lat: angka(unit.latitude),
      lng: angka(unit.longitude),
      provinsi_kode: unit.provinceCode ?? null,
      kekuatan: Math.round(skor.reduce((a, b) => a + b, 0) / skor.length),
      jumlah_aplikasi: skor.length,
      kerentanan: [...rentan.values()],
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
  };
}

export function createDashboardService({ repository = dashboardRepository } = {}) {
  return {
    async peta() {
      const [satuan, aplikasi] = await Promise.all([repository.satuan(), repository.aplikasiDanScanTerakhir()]);
      const scanIds = aplikasi.map((a) => a.scanId).filter(Boolean);
      const hasil = await repository.hasilMetode(scanIds);
      return { ...hitungPeta({ satuan, aplikasi, hasil }), diperbarui: new Date().toISOString() };
    },
  };
}

export const dashboardService = createDashboardService();
