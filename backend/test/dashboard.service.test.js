import assert from 'node:assert/strict';
import { after, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { hitungPeta } = await import('../src/features/dashboard/dashboard.service.js');
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
const hasilMetode = (scanId, lulus, gagal) => [
  ...Array.from({ length: lulus }, (_, i) => ({ scanId, kode: `L-${i}`, status: 'lulus' })),
  ...gagal.map(([kode, severity]) => ({ scanId, kode, nama: `Metode ${kode}`, severity, status: 'gagal' })),
];

describe('dashboard.service hitungPeta', () => {
  const data = hitungPeta({
    satuan,
    aplikasi: [
      { aplikasiId: 1, unitId: 3, scanId: 10 }, // Kodim Bogor: 3 lulus 1 gagal → 75
      { aplikasiId: 2, unitId: 4, scanId: 11 }, // sub-satuan tanpa lokasi → naik ke Kodim Bogor: 1/2 → 50
      { aplikasiId: 3, unitId: 2, scanId: 12 }, // Kodam: semua lulus → 100
      { aplikasiId: 4, unitId: 5, scanId: 13 }, // satuan tanpa induk berlokasi → tak terpetakan
      { aplikasiId: 5, unitId: 3, scanId: null }, // belum pernah selesai diuji
    ],
    hasil: [
      ...hasilMetode(10, 3, [['INPV-01', 'kritis']]),
      ...hasilMetode(11, 1, [['INPV-01', 'kritis']]),
      ...hasilMetode(12, 4, []),
      ...hasilMetode(13, 2, []),
    ],
  });

  it('menghitung kekuatan rata-rata per satuan dan menaikkan aplikasi ke induk berlokasi terdekat', () => {
    const bogor = data.titik.find((t) => t.id === '3');
    assert.equal(bogor.kekuatan, 63); // (75 + 50) / 2
    assert.equal(bogor.jumlah_aplikasi, 2);
    assert.equal(bogor.kotama, '2');
    assert.deepEqual(bogor.kerentanan, [{ kode: 'INPV-01', nama: 'Metode INPV-01', tingkat: 'kritis', aplikasi: 2 }]);
    assert.equal(bogor.lat, -6.6);
    assert.equal(data.titik.find((t) => t.id === '2').kekuatan, 100);
  });

  it('melaporkan aplikasi yang belum terpetakan / belum diuji, dan daftar Kotama berlokasi', () => {
    assert.deepEqual(data.ringkasan, { aplikasi_terpetakan: 3, aplikasi_belum_terpetakan: 1, aplikasi_belum_diuji: 1 });
    assert.deepEqual(
      data.kotama.map((k) => [k.id, k.nama, k.sebutan]),
      [['2', 'Kodam III', 'Siliwangi']],
    );
  });
});
