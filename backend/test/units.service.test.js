import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createUnitsService } = await import('../src/features/units/units.service.js');
const { createUnitSchema, listUnitsAdminSchema, searchUnitsSchema, updateUnitSchema } = await import(
  '../src/features/units/units.validation.js'
);
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

const NOW = new Date('2026-10-22T08:00:00.000Z');
const dup = () => Object.assign(new Error('Failed query'), { cause: { code: 'ER_DUP_ENTRY' } });

const baris = (data) => ({
  parentId: null,
  type: 'SATUAN',
  address: null,
  city: null,
  provinceCode: null,
  latitude: null,
  longitude: null,
  isActive: true,
  userCount: 0,
  appCount: 0,
  childCount: 0,
  createdAt: NOW,
  ...data,
});

// Repository palsu di memori: nama unik tanpa membedakan huruf besar (seperti collation MySQL),
// leluhur & tinggi sub-pohon dihitung dari parentId seperti query rekursif aslinya.
function repoMemori(rows) {
  const byId = (id) => rows.find((u) => u.id === Number(id));
  const leluhur = (id) => {
    const hasil = [];
    for (let u = byId(byId(id)?.parentId); u; u = byId(u.parentId)) hasil.unshift({ id: u.id, name: u.name });
    return hasil;
  };
  const tinggi = (id) => Math.max(0, ...rows.filter((u) => u.parentId === Number(id)).map((u) => 1 + tinggi(u.id)));
  const cekNama = (name, kecuali) => {
    if (rows.some((u) => u.id !== kecuali && u.name.toLowerCase() === name.toLowerCase())) throw dup();
  };
  return {
    searchActive: async ({ search }) => rows.filter((u) => u.isActive && u.name.toLowerCase().includes(search)),
    listAll: async ({ status, parentId }) => {
      const r = rows
        .filter((u) => (status === 'aktif' ? u.isActive : status === 'nonaktif' ? !u.isActive : true))
        .filter((u) => parentId === undefined || u.parentId === parentId);
      return { rows: r, total: r.length };
    },
    findById: async (id) => byId(id) ?? null,
    ancestorsOf: async (ids) => new Map(ids.map((id) => [Number(id), leluhur(id)])),
    subtreeHeight: async (id) => tinggi(id),
    create: async (data) => {
      cekNama(data.name);
      const unit = baris({ id: rows.length + 1, ...data });
      rows.push(unit);
      return unit;
    },
    update: async (id, data) => {
      if (data.name) cekNama(data.name, Number(id));
      return Object.assign(byId(id), data);
    },
  };
}

describe('units.service (publik)', () => {
  it('pencarian menyertakan jenis & jalur induk, tanpa alamat/koordinat', async () => {
    const rows = [
      baris({ id: 1, name: 'Mabes TNI', type: 'MABES' }),
      baris({ id: 2, name: 'Kodam Jaya', type: 'KOTAMA', parentId: 1 }),
      baris({ id: 3, name: 'Kodim 0501/Jakarta Pusat', type: 'KODIM', parentId: 2, latitude: '-6.170000' }),
    ];
    const service = createUnitsService({ repository: repoMemori(rows) });
    assert.deepEqual(await service.search({ search: 'kodim', limit: 20 }), [
      { id: '3', nama: 'Kodim 0501/Jakarta Pusat', jenis: 'KODIM', jalur: 'Mabes TNI › Kodam Jaya' },
    ]);
  });

  it('skema membatasi jumlah hasil (bawaan 20, maksimal 50)', () => {
    assert.deepEqual(searchUnitsSchema.validate({}).value, { search: '', limit: 20 });
    assert.equal(searchUnitsSchema.validate({ search: '  siber ' }).value.search, 'siber');
    assert.ok(searchUnitsSchema.validate({ limit: 1000 }).error);
  });
});

describe('units.service (admin)', () => {
  let rows;
  let events;
  let service;

  beforeEach(() => {
    rows = [
      baris({ id: 1, name: 'Mabes TNI', type: 'MABES', provinceCode: '31', childCount: 1 }),
      baris({ id: 2, name: 'Kodam Jaya', type: 'KOTAMA', parentId: 1, childCount: 1, userCount: 3 }),
      baris({ id: 3, name: 'Kodim 0501', type: 'KODIM', parentId: 2, latitude: '-6.175400', longitude: '106.827200' }),
      baris({ id: 4, name: 'Satuan Lama', isActive: false }),
    ];
    events = [];
    service = createUnitsService({ repository: repoMemori(rows), auditor: (e, d) => events.push([e, d]) });
  });

  it('list per induk: hanya sub-satuan langsung, lengkap dengan leluhur, provinsi, dan koordinat angka', async () => {
    const { items, meta } = await service.listAdmin({ page: 1, limit: 50, search: '', status: '', induk: 2 });
    assert.equal(items.length, 1);
    assert.deepEqual(items[0], {
      id: '3',
      nama: 'Kodim 0501',
      jenis: 'KODIM',
      jalur: 'Mabes TNI › Kodam Jaya',
      induk_id: '2',
      leluhur: [
        { id: '1', nama: 'Mabes TNI' },
        { id: '2', nama: 'Kodam Jaya' },
      ],
      alamat: null,
      kota: null,
      provinsi_kode: null,
      provinsi: null,
      latitude: -6.1754,
      longitude: 106.8272,
      aktif: true,
      jumlah_pengguna: 0,
      jumlah_aplikasi: 0,
      jumlah_sub: 0,
      dibuat_pada: NOW,
    });
    assert.deepEqual(meta, { page: 1, limit: 50, total: 1, totalPages: 1 });

    const akar = await service.listAdmin({ page: 1, limit: 50, search: '', status: 'aktif', induk: 'akar' });
    assert.deepEqual(
      akar.items.map((s) => [s.nama, s.provinsi]),
      [['Mabes TNI', 'DKI Jakarta']],
    );
  });

  it('tambah sub-satuan dengan alamat tercatat di audit; nama duplikat ditolak 409', async () => {
    const baru = await service.create({
      nama: 'Koramil 01/Gambir',
      jenis: 'KORAMIL',
      induk_id: 3,
      alamat: 'Jl. Tanah Abang II',
      kota: 'Jakarta Pusat',
      provinsi_kode: '31',
      latitude: -6.17,
      longitude: 106.82,
    });
    assert.equal(baru.jalur, 'Mabes TNI › Kodam Jaya › Kodim 0501');
    assert.equal(baru.provinsi, 'DKI Jakarta');
    assert.deepEqual(events, [
      ['satuan.tambah', { unitId: 5, nama: 'Koramil 01/Gambir', jenis: 'KORAMIL', indukId: 3, aktif: true }],
    ]);
    await assert.rejects(service.create({ nama: 'kodam jaya' }), { statusCode: 409 });
  });

  it('induk harus ada dan koordinat harus berpasangan', async () => {
    await assert.rejects(service.create({ nama: 'Yatim', induk_id: 99 }), { statusCode: 400 });
    await assert.rejects(service.create({ nama: 'Setengah', latitude: -6.2 }), { statusCode: 400 });
    await assert.rejects(service.update(3, { latitude: null }), { statusCode: 400 });
    assert.equal((await service.update(3, { latitude: null, longitude: null })).latitude, null);
  });

  it('pindah induk menolak siklus (ke diri sendiri / ke sub-satuannya) dan memindahkan sub-pohon', async () => {
    await assert.rejects(service.update(2, { induk_id: 2 }), { statusCode: 400 });
    await assert.rejects(service.update(1, { induk_id: 3 }), { statusCode: 400 });
    const pindah = await service.update(2, { induk_id: null });
    assert.equal(pindah.jalur, '');
    assert.equal((await service.getAdmin(3)).jalur, 'Kodam Jaya');
    assert.deepEqual(events.at(-1), ['satuan.ubah', { unitId: 2, indukLama: 1, indukBaru: null, kolom: ['parentId'] }]);
  });

  it('kedalaman hierarki dibatasi', async () => {
    let induk = 3;
    await assert.rejects(
      (async () => {
        for (let i = 0; i < 10; i += 1) induk = (await service.create({ nama: `Sub ${i}`, induk_id: induk })).id;
      })(),
      { statusCode: 400, message: /maksimal/ },
    );
  });

  it('ubah nama & status mencatat nilai lama→baru; tanpa perubahan tidak menulis apa pun', async () => {
    await service.update(1, { nama: 'Markas Besar TNI' });
    await service.update(4, { aktif: true });
    await service.update(4, { aktif: true, alamat: '' });
    assert.deepEqual(events, [
      ['satuan.ubah', { unitId: 1, namaLama: 'Mabes TNI', namaBaru: 'Markas Besar TNI', kolom: ['name'] }],
      ['satuan.ubah', { unitId: 4, aktif: true, kolom: ['isActive'] }],
    ]);
    await assert.rejects(service.update(1, { nama: 'Satuan Lama' }), { statusCode: 409 });
    await assert.rejects(service.update(99, { aktif: false }), { statusCode: 404 });
  });

  it('skema merapikan nama, memvalidasi jenis/provinsi/koordinat, dan meminta minimal satu perubahan', () => {
    const { value } = createUnitSchema.validate({ nama: '  Kodim   0501 ' });
    assert.equal(value.nama, 'Kodim 0501');
    assert.equal(value.jenis, 'SATUAN');
    assert.equal(value.induk_id, null);
    assert.ok(createUnitSchema.validate({ nama: ' ' }).error);
    assert.ok(createUnitSchema.validate({ nama: 'X Y', jenis: 'POLDA' }).error);
    assert.ok(createUnitSchema.validate({ nama: 'X Y', provinsi_kode: '99' }).error);
    // Koordinat tertukar (lng di kolom lat) ditolak karena di luar wilayah Indonesia.
    assert.ok(createUnitSchema.validate({ nama: 'X Y', latitude: 106.8, longitude: -6.2 }).error);
    assert.ok(updateUnitSchema.validate({}).error);
    assert.equal(updateUnitSchema.validate({ aktif: false }).error, undefined);
    assert.equal(updateUnitSchema.validate({ alamat: null, provinsi_kode: '' }).error, undefined);
    assert.equal(listUnitsAdminSchema.validate({ induk: 'akar' }).value.induk, 'akar');
    assert.equal(listUnitsAdminSchema.validate({ induk: '7' }).value.induk, 7);
    assert.ok(listUnitsAdminSchema.validate({ induk: 'semua' }).error);
  });
});
