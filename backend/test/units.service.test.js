import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createUnitsService } = await import('../src/features/units/units.service.js');
const { createUnitSchema, searchUnitsSchema, updateUnitSchema } = await import('../src/features/units/units.validation.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

describe('units.service', () => {
  it('meneruskan kata kunci & batas ke repository dan mengembalikan bentuk { id, nama }', async () => {
    let diterima;
    const service = createUnitsService({
      repository: { searchActive: async (q) => ((diterima = q), [{ id: 7, name: 'Laboratorium Siber' }]) },
    });
    assert.deepEqual(await service.search({ search: 'siber', limit: 20 }), [{ id: '7', nama: 'Laboratorium Siber' }]);
    assert.deepEqual(diterima, { search: 'siber', limit: 20 });
  });

  it('skema membatasi jumlah hasil (bawaan 20, maksimal 50)', () => {
    assert.deepEqual(searchUnitsSchema.validate({}).value, { search: '', limit: 20 });
    assert.equal(searchUnitsSchema.validate({ search: '  siber ' }).value.search, 'siber');
    assert.ok(searchUnitsSchema.validate({ limit: 1000 }).error);
  });
});

describe('units.service (admin)', () => {
  const NOW = new Date('2026-10-22T08:00:00.000Z');
  let rows;
  let events;
  let service;
  const dup = () => Object.assign(new Error('Failed query'), { cause: { code: 'ER_DUP_ENTRY' } });

  // Repository palsu: nama unik tanpa membedakan huruf besar, seperti collation MySQL.
  const repo = () => ({
    listAll: async ({ status }) => {
      const r = rows.filter((u) => (status === 'aktif' ? u.isActive : status === 'nonaktif' ? !u.isActive : true));
      return { rows: r, total: r.length };
    },
    findById: async (id) => rows.find((u) => u.id === id) ?? null,
    create: async ({ name, isActive }) => {
      if (rows.some((u) => u.name.toLowerCase() === name.toLowerCase())) throw dup();
      const unit = { id: rows.length + 1, name, isActive, userCount: 0, createdAt: NOW };
      rows.push(unit);
      return unit;
    },
    update: async (id, data) => {
      if (data.name && rows.some((u) => u.id !== id && u.name.toLowerCase() === data.name.toLowerCase())) throw dup();
      return Object.assign(rows.find((u) => u.id === id), data);
    },
  });

  beforeEach(() => {
    rows = [
      { id: 1, name: 'Laboratorium Siber', isActive: true, userCount: 3, createdAt: NOW },
      { id: 2, name: 'Satuan Lama', isActive: false, userCount: 0, createdAt: NOW },
    ];
    events = [];
    service = createUnitsService({ repository: repo(), auditor: (e, d) => events.push([e, d]) });
  });

  it('list mengembalikan status, jumlah pengguna, dan meta paginasi', async () => {
    const { items, meta } = await service.listAdmin({ page: 1, limit: 50, search: '', status: 'aktif' });
    assert.deepEqual(items, [{ id: '1', nama: 'Laboratorium Siber', aktif: true, jumlah_pengguna: 3, dibuat_pada: NOW }]);
    assert.deepEqual(meta, { page: 1, limit: 50, total: 1, totalPages: 1 });
  });

  it('tambah satuan tercatat di audit; nama duplikat ditolak 409', async () => {
    const baru = await service.create({ nama: 'Detasemen Siber' });
    assert.equal(baru.nama, 'Detasemen Siber');
    assert.deepEqual(events, [['satuan.tambah', { unitId: 3, nama: 'Detasemen Siber', aktif: true }]]);
    assert.equal((await service.create({ nama: 'Satuan Cadangan', aktif: false })).aktif, false);
    await assert.rejects(service.create({ nama: 'laboratorium siber' }), { statusCode: 409 });
  });

  it('ubah nama & status mencatat nilai lama→baru; tanpa perubahan tidak menulis apa pun', async () => {
    await service.update(1, { nama: 'Lab Siber' });
    await service.update(2, { aktif: true });
    await service.update(2, { aktif: true });
    assert.deepEqual(events, [
      ['satuan.ubah', { unitId: 1, namaLama: 'Laboratorium Siber', namaBaru: 'Lab Siber' }],
      ['satuan.ubah', { unitId: 2, aktif: true }],
    ]);
    await assert.rejects(service.update(1, { nama: 'Satuan Lama' }), { statusCode: 409 });
    await assert.rejects(service.update(99, { aktif: false }), { statusCode: 404 });
  });

  it('skema merapikan spasi nama dan meminta minimal satu perubahan', () => {
    assert.equal(createUnitSchema.validate({ nama: '  Detasemen   Siber ' }).value.nama, 'Detasemen Siber');
    assert.ok(createUnitSchema.validate({ nama: ' ' }).error);
    assert.ok(updateUnitSchema.validate({}).error);
    assert.equal(updateUnitSchema.validate({ aktif: false }).error, undefined);
  });
});
