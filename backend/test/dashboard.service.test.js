import assert from 'node:assert/strict';
import { after, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { hitungPeta, rincianProvinsi, createDashboardService } = await import('../src/features/dashboard/dashboard.service.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

// Pohon: Mabes (berlokasi) → Kodam III/Siliwangi (berlokasi) → Kodim Bogor (berlokasi) → Unit tanpa lokasi.
// Satuan Lepas: akar tanpa lokasi.
const satuan = [
  { id: 1, parentId: null, name: 'Mabesad', type: 'MABES', provinceCode: '31', latitude: '-6.18', longitude: '106.83' },
  { id: 2, parentId: 1, name: 'Kodam III/Siliwangi', type: 'KOTAMA', provinceCode: '32', latitude: '-6.91', longitude: '107.61' },
  { id: 3, parentId: 2, name: 'Kodim Bogor', type: 'KODIM', provinceCode: '32', latitude: '-6.6', longitude: '106.8' },
  { id: 4, parentId: 3, name: 'Unit Siber Bogor', type: 'SATUAN', provinceCode: null, latitude: null, longitude: null },
  { id: 5, parentId: null, name: 'Satuan Lepas', type: 'SATUAN', provinceCode: null, latitude: null, longitude: null },
];
// Ringkasan scan selesai terakhir per aplikasi (skor & jumlah temuan tersimpan di tabel scans).
const aplikasi = [
  { aplikasiId: 1, unitId: 3, scanId: 10, score: 75, kritis: 1, tinggi: 2, sedang: 0, rendah: 1 }, // Kodim Bogor
  { aplikasiId: 2, unitId: 4, scanId: 11, score: 50, kritis: 1, tinggi: 0, sedang: 3, rendah: 0 }, // naik ke Kodim Bogor
  { aplikasiId: 3, unitId: 2, scanId: 12, score: 100, kritis: 0, tinggi: 0, sedang: 0, rendah: 0 }, // Kodam
  { aplikasiId: 4, unitId: 5, scanId: 13, score: 90, kritis: 0, tinggi: 1, sedang: 0, rendah: 0 }, // tak terpetakan
  { aplikasiId: 5, unitId: 3, scanId: null, score: null }, // belum pernah selesai diuji
];

describe('dashboard.service hitungPeta (ringkas)', () => {
  const data = hitungPeta({ satuan, aplikasi });

  it('kekuatan = rata-rata skor tersimpan; aplikasi naik ke induk berlokasi terdekat', () => {
    const bogor = data.titik.find((t) => t.id === '3');
    assert.equal(bogor.kekuatan, 63); // (75 + 50) / 2
    assert.equal(bogor.jumlah_aplikasi, 2);
    assert.equal(bogor.kotama, '2');
    assert.equal(bogor.lat, -6.6);
    assert.equal(data.titik.find((t) => t.id === '2').kekuatan, 100);
  });

  it('sebaran severity nasional dari seluruh aplikasi teruji (termasuk yang tak terpetakan)', () => {
    assert.deepEqual(data.nasional.sebaran, { kritis: 2, tinggi: 3, sedang: 3, rendah: 1 });
  });

  it('melaporkan aplikasi yang belum terpetakan / belum diuji, dan daftar Kotama berlokasi', () => {
    assert.deepEqual(data.ringkasan, { aplikasi_terpetakan: 3, aplikasi_belum_terpetakan: 1, aplikasi_belum_diuji: 1 });
    assert.deepEqual(
      data.kotama.map((k) => [k.id, k.nama, k.sebutan]),
      [['2', 'Kodam III', 'Siliwangi']],
    );
  });

  it('rincian provinsi: indeks tertimbang & sebaran severity provinsi', () => {
    const jabar = rincianProvinsi(data, '32');
    assert.equal(jabar.satuan, 2);
    assert.equal(jabar.aplikasi, 3);
    assert.equal(jabar.indeks, 75.3); // (63×2 + 100×1) / 3
    assert.deepEqual(jabar.sebaran, { kritis: 2, tinggi: 2, sedang: 3, rendah: 1 });
    assert.deepEqual(rincianProvinsi(data, '99'), {
      kode: '99',
      satuan: 0,
      aplikasi: 0,
      indeks: null,
      sebaran: { kritis: 0, tinggi: 0, sedang: 0, rendah: 0 },
    });
  });
});

describe('dashboard.service (cache 10 menit)', () => {
  it('peta ringkas tanpa rincian internal; rincian provinsi memakai data cache; diperbarui setelah 10 menit', async () => {
    let query = 0;
    let waktu = 0;
    const svc = createDashboardService({
      repository: {
        satuan: async () => satuan,
        aplikasiRingkas: async () => {
          query += 1;
          return aplikasi;
        },
      },
      penilai: { lengkapiYangKosong: async () => 0 },
      sekarang: () => waktu,
    });
    const peta = await svc.peta();
    assert.ok(peta.versi);
    assert.ok(peta.titik.every((t) => !('_sebaran' in t)), 'rincian internal tidak ikut dikirim');
    const jabar = await svc.provinsi('32');
    assert.equal(jabar.versi, peta.versi);
    assert.equal(query, 1, 'rincian provinsi tidak mengulang query');
    waktu = 9 * 60_000;
    await svc.peta();
    assert.equal(query, 1, 'masih dalam 10 menit → cache');
    waktu = 10 * 60_000 + 1;
    await svc.peta();
    assert.equal(query, 2, 'lewat 10 menit → muat ulang');
  });
});
