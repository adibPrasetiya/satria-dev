import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createCatalogService } = await import('../src/features/catalog/catalog.service.js');
const { createMethodSchema, updateControlSchema } = await import('../src/features/catalog/catalog.validation.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

const dup = () => Object.assign(new Error('Failed query'), { cause: { code: 'ER_DUP_ENTRY' } });

const METODE = {
  nama: 'Header HSTS terpasang',
  titik_uji: 'global',
  check_id: 'tls.hsts',
  jenis: 'otomatis',
  engine: 'custom',
  profil: 'aman',
  butuh_autentikasi: false,
  bukti: ['request_response'],
  kriteria_lulus: 'Header Strict-Transport-Security ada.',
  efek_samping: '',
  severity: 'sedang',
};

describe('catalog.service', () => {
  let db;
  let events;
  let service;

  beforeEach(() => {
    db = {
      meta: { schemaVersion: 1, regulation: 'Per-BSSN 4/2021', section: 'Web', notes: [] },
      testPoints: [{ id: 1, code: 'global', name: 'Seluruh aplikasi', sort: 0 }],
      functions: [{ id: 1, code: 'CRYP', number: 5, name: 'Kriptografi', sort: 0 }],
      controls: [
        { id: 1, code: 'CRYP-5.1', functionId: 1, refNumber: '5.1', description: 'menggunakan TLS', verifiability: 'otomatis', defaultSeverity: 'tinggi', aggregation: 'semua_lulus', refs: ['ASVS V9'], parameters: null, isActive: true, sort: 0 },
      ],
      methods: [
        { id: 1, code: 'CRYP-5.1-T01', controlId: 1, name: 'TLS aktif', testPoint: 'global', checkId: 'tls.enabled', kind: 'otomatis', engine: 'sslyze', profile: 'aman', requiresAuth: 0, evidence: ['request_response'], passCriteria: 'Situs memakai HTTPS.', sideEffect: null, parameters: null, severity: 'tinggi', isActive: 1, sort: 0 },
      ],
    };
    events = [];
    const byCode = (list) => async (code) => list().find((r) => r.code === code) ?? null;
    service = createCatalogService({
      auditor: (e, d) => events.push([e, d]),
      repository: {
        getAll: async () => db,
        findFunctionByCode: byCode(() => db.functions),
        findControlByCode: byCode(() => db.controls),
        findMethodByCode: byCode(() => db.methods),
        findTestPoint: byCode(() => db.testPoints),
        listMethodCodes: async (controlId) => db.methods.filter((m) => m.controlId === controlId).map((m) => m.code),
        nextControlSort: async () => 1,
        nextMethodSort: async () => 1,
        createControl: async (data) => {
          if (db.controls.some((c) => c.code === data.code)) throw dup();
          const row = { id: db.controls.length + 1, isActive: true, ...data };
          db.controls.push(row);
          return row;
        },
        updateControl: async (id, data) => ({ ...Object.assign(db.controls.find((c) => c.id === id), data) }),
        createMethod: async (data) => {
          const row = { id: db.methods.length + 1, isActive: true, ...data };
          db.methods.push(row);
          return row;
        },
        updateMethod: async (id, data) => ({ ...Object.assign(db.methods.find((m) => m.id === id), data) }),
      },
    });
  });

  it('menyusun katalog berbentuk sama dengan YAML (fungsi → kontrol → metode) beserta status aktif', async () => {
    const k = await service.getCatalog();
    assert.equal(k.sumber.peraturan, 'Per-BSSN 4/2021');
    assert.deepEqual(k.titik_uji, [{ id: 'global', nama: 'Seluruh aplikasi' }]);
    const kontrol = k.fungsi_keamanan[0].kontrol[0];
    assert.equal(kontrol.id, 'CRYP-5.1');
    assert.deepEqual(kontrol.referensi_pendukung, ['ASVS V9']);
    assert.equal(kontrol.metode_pengujian[0].butuh_autentikasi, false);
    assert.equal(kontrol.metode_pengujian[0].aktif, true);
  });

  it('tambah kontrol: kode dari fungsi + nomor; kode ganda 409; fungsi tak dikenal 404', async () => {
    const c = await service.createControl('CRYP', { nomor_referensi: '5.2', uraian: 'mengenkripsi data sensitif', verifiabilitas: 'sebagian', severity_default: 'tinggi', agregasi: 'semua_lulus', referensi_pendukung: [] });
    assert.equal(c.id, 'CRYP-5.2');
    assert.deepEqual(events.at(-1), ['katalog.kontrol.tambah', { kode: 'CRYP-5.2', uraian: 'mengenkripsi data sensitif' }]);
    await assert.rejects(service.createControl('CRYP', { nomor_referensi: '5.1', uraian: 'duplikat uraian', verifiabilitas: 'manual', severity_default: 'info' }), { statusCode: 409 });
    await assert.rejects(service.createControl('XXXX', { nomor_referensi: '1.1', uraian: 'tidak ada', verifiabilitas: 'manual', severity_default: 'info' }), { statusCode: 404 });
  });

  it('tambah metode: kode berurutan Tnn; titik uji harus dikenal', async () => {
    assert.equal((await service.createMethod('CRYP-5.1', METODE)).id, 'CRYP-5.1-T02');
    assert.equal((await service.createMethod('CRYP-5.1', METODE)).id, 'CRYP-5.1-T03');
    await assert.rejects(service.createMethod('CRYP-5.1', { ...METODE, titik_uji: 'antah' }), { statusCode: 400 });
  });

  it('ubah hanya menulis kolom yang berubah; menonaktifkan tercatat; tanpa perubahan tidak ada audit', async () => {
    const m = await service.updateMethod('CRYP-5.1-T01', { nama: 'TLS 1.2+ aktif', butuh_autentikasi: false, aktif: false });
    assert.equal(m.nama, 'TLS 1.2+ aktif');
    assert.equal(m.aktif, false);
    assert.deepEqual(events, [['katalog.metode.ubah', { kode: 'CRYP-5.1-T01', kolom: ['name', 'isActive'] }]]);
    await service.updateControl('CRYP-5.1', { referensi_pendukung: ['ASVS V9'] });
    assert.equal(events.length, 1);
    await assert.rejects(service.updateMethod('CRYP-9.9-T01', { nama: 'x y z' }), { statusCode: 404 });
  });

  it('parameter: bisa diubah, urutan kunci tidak dianggap perubahan, objek kosong = dihapus', async () => {
    db.controls[0].parameters = { panjang_minimum: 8, wajib: ['angka'] };
    await service.updateControl('CRYP-5.1', { parameter: { wajib: ['angka'], panjang_minimum: 8 } });
    assert.equal(events.length, 0, 'urutan kunci berbeda bukan perubahan');
    const k = await service.updateControl('CRYP-5.1', { parameter: { panjang_minimum: 12, wajib: ['angka'] } });
    assert.deepEqual(k.parameter, { panjang_minimum: 12, wajib: ['angka'] });
    const m = await service.updateMethod('CRYP-5.1-T01', { parameter: { daftar: [{ nama: 'A', kategori: 'x' }] } });
    assert.deepEqual(m.parameter, { daftar: [{ nama: 'A', kategori: 'x' }] });
    assert.equal((await service.updateMethod('CRYP-5.1-T01', { parameter: {} })).parameter, undefined);
  });

  it('skema parameter: kunci snake_case, null boleh, terlalu dalam ditolak', () => {
    assert.equal(updateControlSchema.validate({ parameter: { batas_idle_menit: 30 } }).error, undefined);
    assert.equal(updateControlSchema.validate({ parameter: null }).error, undefined);
    assert.ok(updateControlSchema.validate({ parameter: { 'Batas Idle': 30 } }).error);
    assert.ok(updateControlSchema.validate({ parameter: [1, 2] }).error);
    assert.ok(updateControlSchema.validate({ parameter: { a: { b: { c: { d: { e: { f: { g: 1 } } } } } } } }).error);
  });

  it('skema: check_id berformat, bukti minimal satu, ubah butuh minimal satu field', () => {
    assert.equal(createMethodSchema.validate(METODE).error, undefined);
    assert.ok(createMethodSchema.validate({ ...METODE, check_id: 'Tidak Valid' }).error);
    assert.ok(createMethodSchema.validate({ ...METODE, bukti: [] }).error);
    assert.ok(updateControlSchema.validate({}).error);
  });
});
