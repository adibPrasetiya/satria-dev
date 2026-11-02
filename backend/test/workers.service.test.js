import assert from 'node:assert/strict';
import { after, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createWorkersService, hitungAntrean } = await import('../src/features/workers/workers.service.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

function fakeRepo({ workers = [], tasks = [], rata = {}, scanAktif = null, scanStatus = 'berjalan' } = {}) {
  const catatan = { upsert: [], lease: [], status: [] };
  return {
    catatan,
    async upsert(w) {
      catatan.upsert.push(w);
    },
    async setStatus(id, status) {
      catatan.status.push([id, status]);
    },
    async perpanjangLease(taskId, workerId) {
      catatan.lease.push([taskId, workerId]);
    },
    async scanUntukTask() {
      return { scanId: 7, scanStatus };
    },
    async daftar() {
      return workers;
    },
    async taskAktif() {
      return tasks;
    },
    async rataDurasi() {
      return rata;
    },
    async scanAktifAplikasi() {
      return scanAktif;
    },
  };
}

const workerHidup = { id: 'w1', status: 'sibuk', engines: ['custom', 'discovery'], umurDetik: 3, scanId: 1, taskId: 10, tahap: 'katana' };
const workerMati = { id: 'w2', status: 'siaga', engines: ['custom'], umurDetik: 600 };

describe('hitungAntrean', () => {
  const tasks = [
    { id: 10, scanId: 1, engine: 'discovery', status: 'berjalan' },
    { id: 11, scanId: 1, engine: 'custom', status: 'antre' },
    { id: 20, scanId: 2, engine: 'custom', status: 'antre' },
    { id: 21, scanId: 2, engine: 'custom', status: 'antre' },
  ];
  const rata = { discovery: 100_000, custom: 10_000 };

  it('scan yang sedang dikerjakan berposisi 0', () => {
    const a = hitungAntrean(tasks, { scanId: 1, rata, nAktif: 1 });
    assert.equal(a.sedang_dikerjakan, true);
    assert.equal(a.posisi, 0);
  });

  it('scan kedua menunggu scan pertama; perkiraan dari rata-rata durasi', () => {
    const a = hitungAntrean(tasks, { scanId: 2, rata, nAktif: 1 });
    assert.equal(a.posisi, 2);
    assert.equal(a.di_depan, 2);
    // discovery berjalan (separuh: 50 dtk) + 1 task custom (10 dtk)
    assert.equal(a.perkiraan_tunggu_detik, 60);
  });

  it('scan baru antre di belakang semua task aktif; dibagi jumlah worker', () => {
    const a = hitungAntrean(tasks, { rata, nAktif: 2 });
    assert.equal(a.posisi, 3);
    assert.equal(a.perkiraan_tunggu_detik, 40); // (50+10+10+10)/2
  });
});

describe('heartbeat', () => {
  it('memperpanjang lease task & menandai sibuk', async () => {
    const repo = fakeRepo();
    const svc = createWorkersService({ repository: repo, timeoutMs: 45_000 });
    const r = await svc.heartbeat({ worker_id: 'w1', engines: ['custom'], status: 'sibuk', task_id: 10, tahap: 'katana' });
    assert.deepEqual(r, { batalkan: false });
    assert.deepEqual(repo.catatan.lease, [[10, 'w1']]);
    assert.equal(repo.catatan.upsert[0].status, 'sibuk');
    assert.equal(repo.catatan.upsert[0].scanId, 7);
  });

  it('memberi sinyal batal bila scan sudah dibatalkan', async () => {
    const svc = createWorkersService({ repository: fakeRepo({ scanStatus: 'dibatalkan' }), timeoutMs: 45_000 });
    assert.deepEqual(await svc.heartbeat({ worker_id: 'w1', task_id: 10 }), { batalkan: true });
  });
});

describe('gerbangMulai', () => {
  it('menolak bila aplikasi masih punya scan aktif', async () => {
    const svc = createWorkersService({ repository: fakeRepo({ workers: [workerHidup], scanAktif: 41 }), timeoutMs: 45_000 });
    await assert.rejects(() => svc.gerbangMulai(5, 'discovery'), (e) => e.statusCode === 409 && e.code === 'SCAN_AKTIF' && e.details.scan_id === '41');
  });

  it('menolak bila tak ada worker aktif (heartbeat lama tidak dihitung)', async () => {
    const svc = createWorkersService({ repository: fakeRepo({ workers: [workerMati] }), timeoutMs: 45_000 });
    await assert.rejects(() => svc.gerbangMulai(5, 'custom'), (e) => e.code === 'WORKER_TIDAK_AKTIF');
  });

  it('menolak bila worker aktif tak mendukung engine', async () => {
    const w = { ...workerHidup, engines: ['custom'] };
    const svc = createWorkersService({ repository: fakeRepo({ workers: [w] }), timeoutMs: 45_000 });
    await assert.rejects(() => svc.gerbangMulai(5, 'discovery'), /discovery/);
  });

  it('mengizinkan walau worker sibuk (scan masuk antrean)', async () => {
    const svc = createWorkersService({ repository: fakeRepo({ workers: [workerHidup] }), timeoutMs: 45_000 });
    await svc.gerbangMulai(5, 'discovery');
  });
});

describe('status', () => {
  it('worker dengan heartbeat lama tampil terputus; nama aplikasi satuan lain disamarkan', async () => {
    const repo = fakeRepo({
      workers: [{ ...workerHidup, aplikasi: 'Cuti', unitId: 2 }, workerMati],
      tasks: [{ id: 10, scanId: 1, engine: 'discovery', status: 'berjalan', aplikasi: 'Cuti', unitId: 2 }],
    });
    const svc = createWorkersService({ repository: repo, timeoutMs: 45_000 });
    const s = await svc.status({ peran: 'pemilik', satuan_id: '1' });
    assert.equal(s.aktif, 1);
    assert.equal(s.workers.find((w) => w.id === 'w2').status, 'terputus');
    assert.equal(s.workers.find((w) => w.id === 'w1').sedang.aplikasi, 'Aplikasi satuan lain');
    assert.equal(s.antrean.scan[0].aplikasi, 'Aplikasi satuan lain');
  });
});
