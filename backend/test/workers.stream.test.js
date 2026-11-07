import assert from 'node:assert/strict';
import { after, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createWorkerStatusHub } = await import('../src/features/workers/workers.stream.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

// Event bus & service palsu: snapshot = keadaan yang bisa diubah tes; statusDari menyamarkan per aktor.
function siapkan() {
  const keadaan = { aktif: 1, umur: 3, aplikasi: 'Aplikasi A' };
  let handler = null;
  let snapshotDipanggil = 0;
  const statusDari = (snap, actor) => ({
    aktif: snap.aktif,
    workers: [{ id: 'w1', terakhir_terlihat_detik: snap.umur, aplikasi: actor.peran === 'admin' ? snap.aplikasi : 'Aplikasi satuan lain' }],
  });
  const service = {
    snapshot: async () => (snapshotDipanggil++, { ...keadaan }),
    statusDari,
    status: async (actor) => statusDari({ ...keadaan }, actor),
  };
  const events = {
    berlangganan: (h) => ((handler = h), () => (handler = null)),
  };
  const hub = createWorkerStatusHub({ service, events, periksaMs: 60_000 });
  return { keadaan, hub, sinyal: () => handler?.(), terdaftar: () => !!handler, snapshotDipanggil: () => snapshotDipanggil };
}

describe('hub SSE status worker', () => {
  it('mengirim status awal, lalu hanya saat isinya berubah (umur heartbeat diabaikan)', async () => {
    const { keadaan, hub, sinyal } = siapkan();
    const diterima = [];
    const lepas = await hub.gabung({ peran: 'admin' }, (d) => diterima.push(d));
    assert.equal(diterima.length, 1);

    // Heartbeat biasa: hanya umur yang berubah → tidak ada kiriman.
    keadaan.umur = 12;
    sinyal();
    await hub.siarkan();
    assert.equal(diterima.length, 1);

    // Worker mati → jumlah aktif berubah → terkirim.
    keadaan.aktif = 0;
    sinyal();
    await hub.siarkan();
    assert.equal(diterima.length, 2);
    assert.equal(diterima[1].aktif, 0);
    lepas();
  });

  it('satu snapshot dipakai bersama semua pelanggan; penyamaran tetap per aktor', async () => {
    const { keadaan, hub, snapshotDipanggil } = siapkan();
    const admin = [];
    const pemilik = [];
    await hub.gabung({ peran: 'admin' }, (d) => admin.push(d));
    await hub.gabung({ peran: 'pemilik' }, (d) => pemilik.push(d));
    keadaan.aplikasi = 'Aplikasi B';
    await hub.siarkan();
    assert.equal(snapshotDipanggil(), 1);
    assert.equal(admin.at(-1).workers[0].aplikasi, 'Aplikasi B');
    // Bagi pemilik nama aplikasi satuan lain tetap disamarkan, jadi isinya tidak berubah → tidak dikirim ulang.
    assert.equal(pemilik.length, 1);
    assert.equal(pemilik[0].workers[0].aplikasi, 'Aplikasi satuan lain');
  });

  it('berhenti mendengarkan event saat pelanggan terakhir pergi', async () => {
    const { hub, terdaftar } = siapkan();
    const a = await hub.gabung({ peran: 'admin' }, () => {});
    const b = await hub.gabung({ peran: 'admin' }, () => {});
    assert.ok(terdaftar());
    a();
    assert.ok(terdaftar());
    b();
    assert.equal(terdaftar(), false);
    assert.equal(hub.jumlah, 0);
  });
});
