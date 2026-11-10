import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createApplicationsService } = await import('../src/features/applications/applications.service.js');
const { createApplicationSchema, listApplicationsSchema, updateApplicationSchema } = await import('../src/features/applications/applications.validation.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

const NOW = new Date('2026-10-22T08:00:00.000Z');
const UNITS = { 1: 'Satuan A', 2: 'Satuan B', 3: 'Satuan Nonaktif' };
const dup = () => Object.assign(new Error('Failed query'), { cause: { code: 'ER_DUP_ENTRY' } });

const pemilikA = { id: '10', peran: 'pemilik', satuan_id: '1' };
const pemilikB = { id: '11', peran: 'pemilik', satuan_id: '2' };
const asesor = { id: '20', peran: 'asesor', satuan_id: '2' };
const admin = { id: '1', peran: 'admin', satuan_id: '2' };

const DATA = {
  nama: 'Sistem Informasi Personel',
  deskripsi: '',
  pic_nama: 'Mayor Uji',
  pic_kontak: '0812-0000-0000',
  url_dasar: 'https://sipers.contoh.mil.id',
  lingkungan: 'produksi',
  klasifikasi_data: 'terbatas',
  teknologi: { frontend: 'Svelte', backend: '', database: 'MySQL', server: '' },
};

describe('applications.service', () => {
  let rows;
  let events;
  let service;
  let berjalan;

  beforeEach(() => {
    rows = [];
    events = [];
    berjalan = new Set();
    // Repository palsu: URL unik, join nama satuan.
    const withUnit = (r) => ({ ...r, unit: UNITS[r.unitId], createdAt: NOW, updatedAt: NOW });
    service = createApplicationsService({
      auditor: (e, d) => events.push([e, d]),
      units: { findActiveById: async (id) => (id === 1 || id === 2 ? { id } : null) },
      repository: {
        list: async ({ unitId }) => {
          const r = rows.filter((a) => !unitId || a.unitId === unitId).map(withUnit);
          return { rows: r, total: r.length };
        },
        findById: async (id) => {
          const r = rows.find((a) => a.id === id);
          return r ? withUnit(r) : null;
        },
        create: async (data) => {
          if (rows.some((a) => a.baseUrl === data.baseUrl)) throw dup();
          const r = { id: rows.length + 1, ...data };
          rows.push(r);
          return withUnit(r);
        },
        update: async (id, data) => {
          if (data.baseUrl && rows.some((a) => a.id !== id && a.baseUrl === data.baseUrl)) throw dup();
          return withUnit(Object.assign(rows.find((a) => a.id === id), data));
        },
        findByBaseUrl: async (url) => {
          const r = rows.find((a) => a.baseUrl === url);
          return r ? withUnit(r) : null;
        },
        adaScanBerjalan: async (id) => berjalan.has(id),
        setArsip: async (id, waktu) => withUnit(Object.assign(rows.find((a) => a.id === id), { archivedAt: waktu })),
      },
    });
  });

  it('pemilik mendaftar untuk satuannya sendiri walau mengirim satuan lain; tercatat di audit', async () => {
    const app = await service.create(pemilikA, { ...DATA, satuan_id: 2 });
    assert.equal(app.satuan_id, '1');
    assert.equal(app.satuan, 'Satuan A');
    assert.equal(app.pemilik_id, '10');
    assert.deepEqual(app.teknologi, { frontend: 'Svelte', backend: '', database: 'MySQL', server: '' });
    assert.equal(events[0][0], 'aplikasi.daftar');
  });

  it('admin boleh memilih satuan, tetapi satuan nonaktif ditolak', async () => {
    assert.equal((await service.create(admin, { ...DATA, satuan_id: 1 })).satuan_id, '1');
    await assert.rejects(service.create(admin, { ...DATA, url_dasar: 'https://lain.mil.id', satuan_id: 3 }), { statusCode: 400 });
  });

  it('URL dasar yang sudah terdaftar ditolak 409', async () => {
    await service.create(pemilikA, DATA);
    await assert.rejects(service.create(pemilikB, DATA), { statusCode: 409 });
  });

  it('pemilik hanya melihat aset satuannya; asesor & admin melihat semua; lintas satuan = 404', async () => {
    await service.create(pemilikA, DATA);
    await service.create(pemilikB, { ...DATA, url_dasar: 'https://b.mil.id' });
    const q = { page: 1, limit: 100, search: '' };
    assert.deepEqual((await service.list(pemilikA, q)).items.map((a) => a.satuan), ['Satuan A']);
    assert.equal((await service.list(asesor, q)).items.length, 2);
    assert.equal((await service.list(admin, q)).meta.total, 2);
    await assert.rejects(service.get(pemilikB, '1'), { statusCode: 404 });
    await assert.rejects(service.update(pemilikB, '1', { nama: 'Ambil alih' }), { statusCode: 404 });
    assert.equal((await service.get(asesor, '1')).nama, DATA.nama);
  });

  it('ubah hanya menulis kolom yang berubah; pemilik tidak bisa memindahkan satuan', async () => {
    await service.create(pemilikA, DATA);
    events = [];
    const app = await service.update(pemilikA, '1', { nama: 'SIPERS v2', lingkungan: 'produksi', satuan_id: 2 });
    assert.equal(app.nama, 'SIPERS v2');
    assert.equal(app.satuan_id, '1');
    assert.deepEqual(events, [['aplikasi.ubah', { aplikasiId: 1, nama: 'SIPERS v2', kolom: ['name'] }]]);
    await service.update(pemilikA, '1', { nama: 'SIPERS v2' });
    assert.equal(events.length, 1, 'tanpa perubahan tidak ada audit');
    assert.equal((await service.update(admin, '1', { satuan_id: 2 })).satuan_id, '2');
  });

  it('daftar: filter diteruskan ke repository; ringkasan pengujian & facet di meta', async () => {
    let diterima;
    const svc = createApplicationsService({
      penilai: { lengkapiYangKosong: async () => (diterima = { ...diterima, dilengkapi: true }) },
      repository: {
        list: async (args) => {
          diterima = { ...diterima, args };
          return {
            total: 2,
            rows: [
              { id: 1, name: 'A', unitId: 1, unit: 'Satuan A', lastScanAt: NOW, running: 0, finishedScanId: 9,
                finishedAt: NOW, verdict: 'tidak_laik', score: 60, findingsCritical: 1, findingsHigh: 2,
                findingsMedium: 0, findingsLow: 3 },
              { id: 2, name: 'B', unitId: 1, unit: 'Satuan A', lastScanAt: NOW, running: 1, finishedScanId: null },
            ],
          };
        },
        countByVerdict: async () => [
          { putusan: 'tidak_laik', n: 1 },
          { putusan: 'belum', n: 4 },
        ],
        unitsWithApplications: async ({ unitId }) => [{ id: unitId, name: 'Satuan A', n: 5 }],
      },
    });
    const hasil = await svc.list(pemilikA, {
      page: 2, limit: 10, search: 'x', putusan: 'tidak_laik', satuan_id: 1, sort: 'temuan', order: 'desc', ringkasan: true,
    });
    assert.equal(diterima.dilengkapi, true);
    assert.deepEqual(diterima.args, {
      unitId: 1, search: 'x', lingkungan: undefined, klasifikasi: undefined, satuanId: 1, putusan: 'tidak_laik',
      arsip: 'aktif', offset: 10, limit: 10, sort: 'temuan', order: 'desc',
    });
    assert.deepEqual(hasil.items[0].pengujian.temuan, { kritis: 1, tinggi: 2, sedang: 0, rendah: 3 });
    assert.equal(hasil.items[0].pengujian.putusan, 'tidak_laik');
    assert.deepEqual(hasil.items[1].pengujian, {
      scan_terakhir_pada: NOW, berjalan: true, scan_selesai_id: null, selesai_pada: null, putusan: null, skor: null, temuan: null,
    });
    assert.deepEqual(hasil.meta.ringkasan, { semua: 5, laik: 0, laik_bersyarat: 0, tidak_laik: 1, belum: 4 });
    assert.deepEqual(hasil.meta.opsi_satuan, [{ id: '1', nama: 'Satuan A', jumlah: 5 }]);
    assert.equal(hasil.meta.totalPages, 1);
  });

  it('arsipkan: tersimpan & tercatat audit, idempoten; aset terarsip tak bisa diubah; pulihkan mengembalikan', async () => {
    const app = await service.create(pemilikA, DATA);
    assert.equal(app.diarsipkan_pada, null);

    const arsip = await service.arsipkan(pemilikA, app.id);
    assert.ok(arsip.diarsipkan_pada instanceof Date);
    assert.deepEqual(events.at(-1), ['aplikasi.arsip', { aplikasiId: 1, nama: DATA.nama, oleh: '10' }]);
    const n = events.length;
    await service.arsipkan(pemilikA, app.id); // idempoten: tak ada audit ganda
    assert.equal(events.length, n);

    await assert.rejects(service.update(pemilikA, app.id, { nama: 'Nama Baru' }), { statusCode: 409 });

    const pulih = await service.pulihkan(pemilikA, app.id);
    assert.equal(pulih.diarsipkan_pada, null);
    assert.equal(events.at(-1)[0], 'aplikasi.pulihkan');
    assert.equal((await service.update(pemilikA, app.id, { nama: 'Nama Baru' })).nama, 'Nama Baru');
  });

  it('arsipkan ditolak bila masih ada pengujian berjalan; lintas satuan = 404', async () => {
    const app = await service.create(pemilikA, DATA);
    berjalan.add(1);
    await assert.rejects(service.arsipkan(pemilikA, app.id), { statusCode: 409 });
    berjalan.clear();
    await assert.rejects(service.arsipkan(pemilikB, app.id), { statusCode: 404 });
    assert.ok((await service.arsipkan(admin, app.id)).diarsipkan_pada);
  });

  it('mendaftar ulang URL milik aset terarsip → 409 yang menyarankan pulihkan', async () => {
    const app = await service.create(pemilikA, DATA);
    await service.arsipkan(pemilikA, app.id);
    await assert.rejects(service.create(pemilikA, DATA), (e) => e.statusCode === 409 && /terarsip/.test(e.message) && /pulihkan/.test(e.message));
  });

  it('skema daftar: filter arsip bawaan "aktif" dan di-whitelist', () => {
    assert.equal(listApplicationsSchema.validate({}).value.arsip, 'aktif');
    assert.equal(listApplicationsSchema.validate({ arsip: 'arsip' }).value.arsip, 'arsip');
    assert.ok(listApplicationsSchema.validate({ arsip: 'dihapus' }).error);
  });

  it('skema daftar: kolom urut & putusan di-whitelist; nilai kosong diabaikan', () => {
    const ok = listApplicationsSchema.validate({ putusan: '', lingkungan: '', sort: 'skor', ringkasan: 'true' });
    assert.ifError(ok.error);
    assert.equal(ok.value.putusan, undefined);
    assert.equal(ok.value.ringkasan, true);
    assert.equal(ok.value.order, 'desc');
    assert.ok(listApplicationsSchema.validate({ sort: 'a.id; DROP TABLE x' }).error);
    assert.ok(listApplicationsSchema.validate({ putusan: 'hampir' }).error);
    assert.ok(listApplicationsSchema.validate({ limit: 1000 }).error);
  });

  it('skema: URL harus http(s) dan garis miring akhir dibuang; ubah butuh minimal satu field', () => {
    assert.equal(createApplicationSchema.validate({ ...DATA, url_dasar: 'https://a.mil.id/' }).value.url_dasar, 'https://a.mil.id');
    assert.ok(createApplicationSchema.validate({ ...DATA, url_dasar: 'ftp://a.mil.id' }).error);
    assert.ok(createApplicationSchema.validate({ ...DATA, lingkungan: 'uji' }).error);
    assert.ok(createApplicationSchema.validate({ ...DATA, nama: undefined }).error);
    assert.ok(updateApplicationSchema.validate({}).error);
  });
});
