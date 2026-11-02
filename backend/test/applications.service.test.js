import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createApplicationsService } = await import('../src/features/applications/applications.service.js');
const { createApplicationSchema, updateApplicationSchema } = await import('../src/features/applications/applications.validation.js');
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

  beforeEach(() => {
    rows = [];
    events = [];
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

  it('skema: URL harus http(s) dan garis miring akhir dibuang; ubah butuh minimal satu field', () => {
    assert.equal(createApplicationSchema.validate({ ...DATA, url_dasar: 'https://a.mil.id/' }).value.url_dasar, 'https://a.mil.id');
    assert.ok(createApplicationSchema.validate({ ...DATA, url_dasar: 'ftp://a.mil.id' }).error);
    assert.ok(createApplicationSchema.validate({ ...DATA, lingkungan: 'uji' }).error);
    assert.ok(createApplicationSchema.validate({ ...DATA, nama: undefined }).error);
    assert.ok(updateApplicationSchema.validate({}).error);
  });
});
