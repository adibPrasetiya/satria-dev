import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { hitungTemuan, nilaiKelaikan, statusKontrol } = await import('../src/features/scans/verdict.js');
const { createVerdictService } = await import('../src/features/scans/verdict.service.js');
const { pool } = await import('../src/db/index.js');
await pool.end();

const k = (severity, methods, aggregation = 'semua_lulus') => ({
  severity,
  aggregation,
  methods: methods.map(([code, sev = 'sedang']) => ({ code, severity: sev })),
});
const hasil = (obj) => new Map(Object.entries(obj));

describe('verdict: statusKontrol', () => {
  it('semua_lulus: satu gagal → gagal; belum ada hasil → belum terverifikasi', () => {
    const kontrol = k('tinggi', [['A'], ['B']]);
    assert.equal(statusKontrol(kontrol, hasil({ A: 'lulus', B: 'gagal' })), 'gagal');
    assert.equal(statusKontrol(kontrol, hasil({ A: 'lulus' })), 'tidak_dapat_diverifikasi');
    assert.equal(statusKontrol(kontrol, hasil({ A: 'lulus', B: 'lulus' })), 'lulus');
  });

  it('out of scope tidak dinilai: kontrol yang seluruhnya out of scope → luar_cakupan', () => {
    assert.equal(statusKontrol(k('tinggi', [['A'], ['B']]), hasil({ A: 'lulus', B: 'luar_cakupan' })), 'lulus');
    assert.equal(statusKontrol(k('tinggi', [['A']]), hasil({ A: 'luar_cakupan' })), 'luar_cakupan');
    const r = nilaiKelaikan([k('tinggi', [['A']]), k('sedang', [['B']])], hasil({ A: 'lulus', B: 'luar_cakupan' }));
    assert.deepEqual(r, { putusan: 'laik', skor: 100 }, 'out of scope tidak membuat laik bersyarat');
  });

  it('minimal_satu: satu lulus cukup; metode info & tidak_berlaku diabaikan', () => {
    const kontrol = k('sedang', [['A'], ['B'], ['I', 'info']], 'minimal_satu');
    assert.equal(statusKontrol(kontrol, hasil({ A: 'gagal', B: 'lulus', I: 'gagal' })), 'lulus');
    assert.equal(statusKontrol(k('sedang', [['A']]), hasil({ A: 'tidak_berlaku' })), 'tidak_berlaku');
  });
});

describe('verdict: nilaiKelaikan', () => {
  it('kontrol kritis/tinggi gagal → tidak laik', () => {
    const r = nilaiKelaikan([k('tinggi', [['A']]), k('rendah', [['B']])], hasil({ A: 'gagal', B: 'lulus' }));
    assert.deepEqual(r, { putusan: 'tidak_laik', skor: 50 });
  });

  it('hanya kontrol sedang gagal → laik bersyarat; semua lulus → laik', () => {
    assert.equal(nilaiKelaikan([k('sedang', [['A']]), k('tinggi', [['B']])], hasil({ A: 'gagal', B: 'lulus' })).putusan, 'laik_bersyarat');
    assert.deepEqual(nilaiKelaikan([k('tinggi', [['A']])], hasil({ A: 'lulus' })), { putusan: 'laik', skor: 100 });
  });

  it('ada kontrol belum terverifikasi → laik bersyarat walau skor 100', () => {
    const r = nilaiKelaikan([k('tinggi', [['A']]), k('sedang', [['B']])], hasil({ A: 'lulus' }));
    assert.deepEqual(r, { putusan: 'laik_bersyarat', skor: 100 });
  });
});

describe('verdict: hitungTemuan', () => {
  it('menghitung metode gagal per severity; info & task di luar katalog diabaikan', () => {
    const n = hitungTemuan([
      { status: 'gagal', severity: 'kritis' },
      { status: 'gagal', severity: 'tinggi' },
      { status: 'gagal', severity: 'tinggi' },
      { status: 'lulus', severity: 'kritis' },
      { status: 'gagal', severity: 'info' },
      { status: 'gagal', severity: null },
      { status: 'gagal', severity: 'rendah' },
    ]);
    assert.deepEqual(n, { kritis: 1, tinggi: 2, sedang: 0, rendah: 1 });
  });
});

describe('verdict.service', () => {
  const repo = (tersimpan) => ({
    controls: async () => [
      { controlCode: 'C1', controlSeverity: 'tinggi', aggregation: 'semua_lulus', methodCode: 'M1', methodSeverity: 'tinggi' },
      { controlCode: 'C2', controlSeverity: 'sedang', aggregation: 'semua_lulus', methodCode: 'M2', methodSeverity: 'sedang' },
    ],
    taskResults: async () => [
      { scanId: 7, methodCode: 'M1', status: 'gagal', severity: 'tinggi' },
      { scanId: 7, methodCode: 'M2', status: 'lulus', severity: 'sedang' },
      { scanId: 8, methodCode: 'M1', status: 'lulus', severity: 'tinggi' },
      { scanId: 8, methodCode: 'M2', status: 'lulus', severity: 'sedang' },
    ],
    finishedWithoutVerdict: async () => [7, 8],
    saveSummary: async (id, data) => tersimpan.set(id, data),
  });

  it('menyimpan putusan, skor, dan temuan tiap scan yang belum dihitung', async () => {
    const tersimpan = new Map();
    const n = await createVerdictService({ repository: repo(tersimpan) }).lengkapiYangKosong();
    assert.equal(n, 2);
    assert.deepEqual(tersimpan.get(7), {
      verdict: 'tidak_laik',
      score: 50,
      temuan: { kritis: 0, tinggi: 1, sedang: 0, rendah: 0 },
    });
    assert.equal(tersimpan.get(8).verdict, 'laik');
  });

  it('galat saat melengkapi tidak menggagalkan pemanggil', async () => {
    const svc = createVerdictService({
      repository: { finishedWithoutVerdict: async () => { throw new Error('db mati'); } },
      log: { warn() {} },
    });
    assert.equal(await svc.lengkapiYangKosong(), 0);
  });
});
