import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createScansService } = await import('../src/features/scans/scans.service.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

const pemilikA = { id: '10', peran: 'pemilik', satuan_id: '1' };
const pemilikB = { id: '11', peran: 'pemilik', satuan_id: '2' };
const admin = { id: '1', peran: 'admin', satuan_id: '9' };
const asesor = { id: '20', peran: 'asesor', satuan_id: '5' };

// Metode AUTH-1.3 seperti di katalog (subset relevan).
const METODE = [
  { code: 'AUTH-1.3-T01', checkId: 'auth.password_policy.min_length', testPoint: 'registrasi', kind: 'otomatis', engine: 'custom', requiresAuth: false, profile: 'aman' },
  { code: 'AUTH-1.3-T02', checkId: 'auth.password_policy.complexity', testPoint: 'registrasi', kind: 'otomatis', engine: 'custom', requiresAuth: false, profile: 'aman' },
  { code: 'AUTH-1.3-T03', checkId: 'auth.password_policy.min_length+complexity', testPoint: 'reset_password', kind: 'semi_otomatis', engine: 'playwright', requiresAuth: false, profile: 'aman' },
  { code: 'AUTH-1.3-T04', checkId: 'auth.password_policy.min_length+complexity', testPoint: 'ubah_password', kind: 'otomatis', engine: 'custom', requiresAuth: true, profile: 'aman' },
  { code: 'AUTH-1.3-T05', checkId: 'manual.password_expiry', testPoint: 'dokumen', kind: 'manual', engine: 'manual', requiresAuth: false, profile: 'aman' },
];

function fakeRepo(initial = {}) {
  const state = {
    targets: new Map(initial.targets ?? []), // appId -> target
    scans: [],
    tasks: [],
    logs: [],
    seq: 0,
  };
  const repo = {
    _state: state,
    async getTarget(appId) {
      return state.targets.get(appId) ?? null;
    },
    async upsertTarget(appId, data) {
      const t = { applicationId: appId, testPoints: data.testPoints, forms: data.forms };
      state.targets.set(appId, t);
      return t;
    },
    async functionsWithControls() {
      const control = { parameters: { panjang_minimum: 8, wajib: ['huruf_besar'] } };
      return { items: METODE.map((method) => ({ control, method })) };
    },
    async createScan({ applicationId, profile, mode = 'terarah', approach = 'greybox', reconScanId = null }) {
      const id = ++state.seq;
      state.scans.push({ id, applicationId, profile, mode, approach, reconScanId, status: 'berjalan', startedAt: new Date(), finishedAt: null });
      return id;
    },
    async countTestTasks(scanId) {
      return state.tasks.filter((t) => t.scanId === scanId && t.engine !== 'discovery').length;
    },
    async mergeDiscovery(appId, { testPoints, forms, discovery }) {
      const cur = state.targets.get(appId) ?? {};
      const t = { applicationId: appId, testPoints: { ...testPoints }, forms: { ...forms }, discovery };
      state.targets.set(appId, t);
      return t;
    },
    async insertTasks(rows) {
      for (const r of rows) state.tasks.push({ id: ++state.seq, ...r });
    },
    async findScanById(id) {
      return state.scans.find((s) => s.id === id) ?? null;
    },
    async listScans({ applicationId, applicationIds }) {
      return state.scans.filter(
        (s) => (applicationId ? s.applicationId === applicationId : true) && (applicationIds ? applicationIds.includes(s.applicationId) : true),
      );
    },
    async tasksByScan(scanId) {
      return state.tasks.filter((t) => t.scanId === scanId);
    },
    async logsByScan(scanId) {
      return state.logs.filter((l) => l.scanId === scanId);
    },
    async insertLog(scanId, level, message, data = null) {
      state.logs.push({ id: ++state.seq, scanId, level, message, data, createdAt: new Date() });
    },
    async setScanStatus(id, status, finishedAt) {
      const s = state.scans.find((x) => x.id === id);
      Object.assign(s, { status, finishedAt: finishedAt ?? s.finishedAt });
    },
    async finishPendingTasksAsCancelled(scanId) {
      for (const t of state.tasks) if (t.scanId === scanId && t.status !== 'selesai') t.status = 'selesai';
    },
    async countUnfinished(scanId) {
      return state.tasks.filter((t) => t.scanId === scanId && t.status !== 'selesai').length;
    },
  };
  return repo;
}

function fakeApps() {
  const rows = [
    { id: 1, unitId: 1, baseUrl: 'http://a.test' },
    { id: 2, unitId: 2, baseUrl: 'http://b.test' },
  ];
  return {
    findById: async (id) => rows.find((r) => r.id === id) ?? null,
    list: async ({ unitId }) => ({ rows: rows.filter((r) => !unitId || r.unitId === unitId), total: rows.length }),
  };
}

const targetRegistrasi = [
  [
    1,
    {
      applicationId: 1,
      testPoints: {
        registrasi: { tersedia: true, url: 'http://a.test/register', metode_http: 'POST' },
        reset_password: { tersedia: true, url: 'http://a.test/reset', metode_http: 'POST' },
        ubah_password: { tersedia: true, url: 'http://a.test/ubah', metode_http: 'POST' },
      },
      forms: {},
    },
  ],
];

describe('scans.service', () => {
  let repo;
  let events;
  let service;

  beforeEach(() => {
    repo = fakeRepo({ targets: targetRegistrasi });
    events = [];
    service = createScansService({
      repository: repo,
      applications: fakeApps(),
      events: { siarkan: (id, e) => events.push([id, e]) },
      auditor: () => {},
    });
  });

  it('menolak mulai scan bila persiapan uji belum diisi', async () => {
    const repo2 = fakeRepo(); // tanpa target
    const svc = createScansService({ repository: repo2, applications: fakeApps(), events: { siarkan() {} }, auditor() {} });
    await assert.rejects(() => svc.mulai(asesor, '1'), /Persiapan pengujian belum diisi/);
  });

  it('seed task AUTH-1.3: T01/T02/T03 antre, T04 & T05 selesai dengan status khusus', async () => {
    const scan = await service.mulai(asesor, '1');
    const h = scan.hasil;
    assert.equal(h['AUTH-1.3-T01'].status, 'antre');
    assert.equal(h['AUTH-1.3-T02'].status, 'antre');
    // T03 playwright -> kini didukung worker (engine playwright), titik reset_password tersedia
    assert.equal(h['AUTH-1.3-T03'].status, 'antre');
    // T04 butuh akun uji (belum ada)
    assert.equal(h['AUTH-1.3-T04'].status, 'tidak_dapat_diverifikasi');
    // T05 manual -> out of scope pengujian otomatis (tetap menunggu tinjauan asesor)
    assert.equal(h['AUTH-1.3-T05'].status, 'luar_cakupan');
    assert.equal(h['AUTH-1.3-T05'].menunggu_tinjauan, true);
    assert.equal(scan.status, 'berjalan'); // masih ada T01/T02 antre
  });

  it('metode tidak_berlaku bila titik uji tidak tersedia', async () => {
    // target hanya punya registrasi; ubah_password tidak tersedia -> T04 tetap tidak_dapat_diverifikasi (butuh auth lebih dulu dicek),
    // tetapi metode yang titik ujinya tak ada akan tidak_berlaku. Uji dengan target kosong untuk registrasi.
    repo._state.targets.set(1, { applicationId: 1, testPoints: { registrasi: { tersedia: false } }, forms: {} });
    const scan = await service.mulai(asesor, '1');
    assert.equal(scan.hasil['AUTH-1.3-T01'].status, 'tidak_berlaku');
  });

  it('scan tanpa task antre langsung selesai', async () => {
    repo._state.targets.set(1, { applicationId: 1, testPoints: { registrasi: { tersedia: false } }, forms: {} });
    const scan = await service.mulai(asesor, '1');
    assert.equal(scan.status, 'selesai');
  });

  it('pemilik lain tidak bisa melihat scan (404)', async () => {
    const scan = await service.mulai(asesor, '1');
    await assert.rejects(() => service.get(pemilikB, scan.id), /tidak ditemukan/);
  });

  it('pemilik hanya melihat hasil: tidak bisa memulai, menyiapkan, atau menghentikan pengujian (403)', async () => {
    const scan = await service.mulai(asesor, '1');
    const dto = await service.get(pemilikA, scan.id);
    assert.equal(dto.id, scan.id);
    await assert.rejects(() => service.mulai(pemilikA, '1'), { statusCode: 403 });
    await assert.rejects(() => service.batalkan(pemilikA, scan.id), { statusCode: 403 });
    await assert.rejects(() => service.getTarget(pemilikA, '1'), { statusCode: 403 });
    await assert.rejects(() => service.simpanTarget(pemilikA, '1', { test_points: {}, forms: {} }), { statusCode: 403 });
  });

  it('admin bisa melihat & membatalkan scan', async () => {
    const scan = await service.mulai(asesor, '1');
    const dibatalkan = await service.batalkan(admin, scan.id);
    assert.equal(dibatalkan.status, 'dibatalkan');
    assert.ok(events.some(([, e]) => e.tipe === 'status' && e.status === 'dibatalkan'));
  });

  it('simpanTarget menyimpan pemetaan titik uji', async () => {
    const r = await service.simpanTarget(asesor, '1', {
      test_points: { registrasi: { tersedia: true, url: 'http://a.test/x', metode_http: 'POST' } },
      forms: {},
    });
    assert.equal(r.test_points.registrasi.tersedia, true);
  });

  it('mode eksploratif: hanya menyemai task penemuan (belum ada task pengujian)', async () => {
    const repo2 = fakeRepo(); // tanpa target — tak perlu persiapan untuk eksploratif
    const svc = createScansService({ repository: repo2, applications: fakeApps(), events: { siarkan() {} }, auditor() {} });
    const scan = await svc.mulai(asesor, '1', { mode: 'eksploratif' });
    assert.equal(scan.mode, 'eksploratif');
    assert.equal(scan.status, 'berjalan');
    assert.equal(repo2._state.tasks.length, 1);
    assert.equal(repo2._state.tasks[0].engine, 'discovery');
  });

  it('black box: akun tidak disimpan, scan bertanda blackbox; terarah & pakai discovery ditolak', async () => {
    const repo2 = fakeRepo();
    let disimpan = null;
    repo2.mergeAccounts = async (_id, data) => (disimpan = data);
    const svc = createScansService({ repository: repo2, applications: fakeApps(), events: { siarkan() {} }, auditor() {} });
    const scan = await svc.mulai(asesor, '1', {
      mode: 'eksploratif',
      pendekatan: 'blackbox',
      accounts: { daftar: [{ username: 'a', password: 'b' }] },
      options: { izinkan_penguncian: false },
    });
    assert.equal(scan.pendekatan, 'blackbox');
    assert.equal(repo2._state.scans.at(-1).approach, 'blackbox');
    assert.equal(disimpan.accounts, null, 'akun dari klien diabaikan');
    assert.ok(repo2._state.logs.some((l) => /black box/.test(l.message)));
    await assert.rejects(svc.mulai(asesor, '1', { mode: 'terarah', pendekatan: 'blackbox' }), { statusCode: 400 });
  });

  it('black box memakai ulang penemuan hanya bila penemuan itu tanpa login; tak butuh akun tersimpan', async () => {
    const opsi = { mode: 'eksploratif', pendekatan: 'blackbox', pakaiDiscovery: true };
    repo._state.targets.set(1, { ...targetRegistrasi[0][1], accounts: null, discovery: { terautentikasi: true } });
    await assert.rejects(service.mulai(asesor, '1', opsi), { statusCode: 400 });

    repo._state.targets.set(1, { ...targetRegistrasi[0][1], accounts: null, discovery: { terautentikasi: false } });
    const scan = await service.mulai(asesor, '1', opsi);
    assert.equal(scan.pendekatan, 'blackbox');
    const tasks = repo._state.tasks.filter((t) => t.scanId === Number(scan.id));
    assert.equal(tasks.some((t) => t.engine === 'discovery'), false);
    assert.ok(tasks.length > 0);
  });

  it('seedPhase2 menyemai task pengujian setelah penemuan & idempoten', async () => {
    const repo2 = fakeRepo();
    const svc = createScansService({ repository: repo2, applications: fakeApps(), events: { siarkan() {} }, auditor() {} });
    const scan = await svc.mulai(asesor, '1', { mode: 'eksploratif' });
    // simulasikan penemuan mengisi target
    await repo2.mergeDiscovery(1, {
      testPoints: { registrasi: { tersedia: true, url: 'http://a.test/r', metode_http: 'POST', sumber: 'otomatis' } },
      forms: {},
      discovery: {},
    });
    const n1 = await svc.seedPhase2(Number(scan.id));
    assert.ok(n1 >= 1, 'ada task pengujian disemai');
    const n2 = await svc.seedPhase2(Number(scan.id));
    assert.equal(n2, 0, 'tidak menyemai ulang');
  });

  it('getTarget: akun tanpa sandi/seed + ringkasan penemuan terakhir', async () => {
    repo._state.targets.set(1, {
      applicationId: 1,
      testPoints: {},
      forms: {},
      accounts: { daftar: [{ username: 'u1', password: 'rahasia', totp_secret: 'JBSWY3DPEHPK3PXP' }, { username: 'u2', password: 'x' }] },
      discovery: { waktu: '2026-10-26T01:00:00.000Z', jumlah_endpoint_unik: 2, endpoints_lengkap: [{ metode_http: 'GET', path_template: '/a' }] },
    });
    const t = await service.getTarget(asesor, '1');
    assert.deepEqual(t.akun, [
      { username: 'u1', ada_sandi: true, ada_totp: true },
      { username: 'u2', ada_sandi: true, ada_totp: false },
    ]);
    assert.equal(JSON.stringify(t).includes('rahasia'), false);
    assert.equal(JSON.stringify(t).includes('JBSWY3DPEHPK3PXP'), false);
    assert.equal(t.discovery.jumlah_endpoint_unik, 2);
    assert.equal(t.discovery.contoh_endpoint[0].path, '/a');
    assert.equal(t.discovery.endpoints_lengkap, undefined);
  });

  it('getTarget: aplikasi tanpa persiapan → akun kosong, discovery null', async () => {
    const repo2 = fakeRepo();
    const svc = createScansService({ repository: repo2, applications: fakeApps(), events: { siarkan() {} }, auditor() {} });
    const t = await svc.getTarget(asesor, '1');
    assert.deepEqual(t.akun, []);
    assert.equal(t.discovery, null);
  });

  it('eksploratif + pakaiDiscovery: lewati penemuan, langsung semai task pengujian', async () => {
    repo._state.targets.set(1, {
      ...targetRegistrasi[0][1],
      accounts: { daftar: [{ username: 'u1', password: 'p' }, { username: 'u2', password: 'p' }] },
      discovery: { waktu: '2026-10-26T01:00:00.000Z', jumlah_endpoint_unik: 5 },
    });
    const scan = await service.mulai(asesor, '1', { mode: 'eksploratif', pakaiDiscovery: true });
    const tasks = repo._state.tasks.filter((t) => t.scanId === Number(scan.id));
    assert.equal(tasks.some((t) => t.engine === 'discovery'), false);
    assert.ok(tasks.length > 0);
    assert.ok(repo._state.logs.some((l) => /hasil penemuan terakhir/.test(l.message)));
  });

  it('pakai ulang penemuan merujuk scan sumber recon (tanpa menyalin data); scan ber-penemuan merujuk dirinya', async () => {
    repo._state.targets.set(1, {
      ...targetRegistrasi[0][1],
      accounts: { daftar: [{ username: 'u1', password: 'p' }, { username: 'u2', password: 'p' }] },
      discovery: { waktu: '2026-10-26T01:00:00.000Z', scan_id: '41' },
    });
    const ulang = await service.mulai(asesor, '1', { mode: 'eksploratif', pakaiDiscovery: true });
    assert.equal(ulang.recon_scan_id, '41');
    assert.equal(repo._state.scans.at(-1).reconScanId, 41);
    const baru = await service.mulai(asesor, '1', { mode: 'eksploratif' });
    assert.equal(baru.recon_scan_id, baru.id);
  });

  it('log ber-data (peristiwa penemuan) ikut di DTO; log biasa tanpa data', async () => {
    const scan = await service.mulai(asesor, '1', { mode: 'eksploratif' });
    await repo.insertLog(Number(scan.id), 'info', 'Spec ditemukan', { v: 1, jenis: 'docs', url: 'http://a.test/openapi.json' });
    const dto = await service.get(pemilikA, scan.id);
    const ber = dto.log.find((l) => l.pesan === 'Spec ditemukan');
    assert.equal(ber.data.jenis, 'docs');
    assert.equal('data' in dto.log[0], false);
  });

  it('eksploratif + pakaiDiscovery ditolak bila belum ada penemuan', async () => {
    await assert.rejects(
      () => service.mulai(asesor, '1', { mode: 'eksploratif', pakaiDiscovery: true }),
      /Belum ada hasil penemuan/,
    );
  });
});
