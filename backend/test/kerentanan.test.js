import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';
process.env.CVE_NOTIF_EMAIL = 'true';

const { bandingkan, dalamRentang, uraikanRentang } = await import('../src/features/kerentanan/versi.js');
const { dariNvd, dariOsv, uraiCpe, severitasDariSkor } = await import('../src/features/kerentanan/intel.normalisasi.js');
const { evaluasiKomponen, hitungPrioritas, layakTanpaVersi, tingkatPrioritas } = await import('../src/features/kerentanan/pencocokan.js');
const { createKerentananService } = await import('../src/features/kerentanan/kerentanan.service.js');
const { cpeTerkait } = await import('../src/features/komponen/komponen.parser.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

describe('kerentanan.versi', () => {
  it('membandingkan versi umum', () => {
    assert.equal(bandingkan('1.18.0', '1.20.1'), -1);
    assert.equal(bandingkan('1.20.1', '1.20.1'), 0);
    assert.equal(bandingkan('2.4.41', '2.4.9'), 1);
    assert.equal(bandingkan('v3.6.0', '3.6.0'), 0);
    assert.equal(bandingkan('1.0.0-rc1', '1.0.0'), -1);
    assert.equal(bandingkan('1.1.1k', '1.1.1'), 1);
    assert.equal(bandingkan('1.1.1k', '1.1.1w'), -1);
  });

  it('rentang batas inklusif/eksklusif', () => {
    const r = { versiMulaiIncl: '1.0.0', versiAkhirExcl: '1.20.1' };
    assert.equal(dalamRentang('1.18.0', r), 'ya');
    assert.equal(dalamRentang('1.20.1', r), 'tidak');
    assert.equal(dalamRentang('0.9.9', r), 'tidak');
    assert.equal(dalamRentang('1.0.0', r), 'ya');
    assert.equal(dalamRentang('1.20.1', { versiAkhirIncl: '1.20.1' }), 'ya');
    assert.equal(dalamRentang('1.0.0', { versiMulaiExcl: '1.0.0' }), 'tidak');
  });

  it('versi persis dan "semua versi"', () => {
    assert.equal(dalamRentang('1.18.0', { versi: '1.18.0' }), 'ya');
    assert.equal(dalamRentang('1.18.1', { versi: '1.18.0' }), 'tidak');
    assert.equal(dalamRentang('5.0', {}), 'ya');
  });

  it('versi kurang rinci → mungkin, bukan ya/tidak', () => {
    assert.equal(dalamRentang('8', { versiAkhirExcl: '8.0.36' }), 'mungkin');
    assert.equal(dalamRentang('8', { versi: '8.0.36' }), 'mungkin');
    assert.equal(dalamRentang('7', { versiAkhirExcl: '8.0.36' }), 'ya');
    assert.equal(dalamRentang('9', { versiAkhirExcl: '8.0.36' }), 'tidak');
  });

  it('versi tak diketahui → mungkin', () => {
    assert.equal(dalamRentang(null, { versiAkhirExcl: '1.0' }), 'mungkin');
  });

  it('versi paket distro dibandingkan pada versi hulunya', () => {
    assert.equal(dalamRentang('8.0.32-0ubuntu0.20.04', { versiAkhirExcl: '8.0.33' }), 'ya');
    assert.equal(dalamRentang('8.0.32-0ubuntu0.20.04', { versi: '8.0.32' }), 'ya');
  });

  it('menguraikan rentang untuk alasan', () => {
    assert.equal(uraikanRentang({ versiMulaiIncl: '1.0', versiAkhirExcl: '2.0' }), '≥ 1.0 dan < 2.0');
    assert.equal(uraikanRentang({ versi: '1.18.0' }), '= 1.18.0');
    assert.equal(uraikanRentang({}), 'semua versi');
  });
});

const ITEM_NVD = {
  cve: {
    id: 'CVE-2021-23017',
    published: '2021-06-01T14:15:09.000',
    lastModified: '2024-11-21T05:51:12.880',
    vulnStatus: 'Modified',
    descriptions: [{ lang: 'en', value: 'A security issue in nginx resolver.' }],
    metrics: {
      cvssMetricV31: [
        { type: 'Primary', cvssData: { baseScore: 7.7, baseSeverity: 'HIGH', vectorString: 'CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:L/I:L/A:H' } },
      ],
    },
    weaknesses: [{ description: [{ value: 'CWE-193' }, { value: 'NVD-CWE-Other' }] }],
    configurations: [
      {
        nodes: [
          {
            operator: 'OR',
            cpeMatch: [
              { vulnerable: true, criteria: 'cpe:2.3:a:f5:nginx:*:*:*:*:*:*:*:*', versionStartIncluding: '0.6.18', versionEndExcluding: '1.20.1' },
              { vulnerable: false, criteria: 'cpe:2.3:o:debian:debian_linux:10.0:*:*:*:*:*:*:*' },
            ],
          },
        ],
      },
    ],
    references: [{ url: 'https://example.test/advisory' }],
  },
};

describe('kerentanan.normalisasi', () => {
  it('item NVD → baris cve + rentang CPE rentan saja', () => {
    const { cve, cpe } = dariNvd(ITEM_NVD);
    assert.equal(cve.id, 'CVE-2021-23017');
    assert.equal(cve.cvssSkor, 7.7);
    assert.equal(cve.severitas, 'tinggi');
    assert.deepEqual(cve.cwe, ['CWE-193']);
    assert.equal(cve.statusAnalisis, 'dianalisis');
    assert.equal(cve.dipublikasiPada.toISOString(), '2021-06-01T14:15:09.000Z');
    assert.deepEqual(cpe, [
      { vendor: 'f5', produk: 'nginx', versi: null, versiMulaiIncl: '0.6.18', versiMulaiExcl: null, versiAkhirIncl: null, versiAkhirExcl: '1.20.1' },
    ]);
  });

  it('CVE ditolak & belum dianalisis', () => {
    assert.equal(dariNvd({ cve: { ...ITEM_NVD.cve, vulnStatus: 'Rejected' } }).cve.statusAnalisis, 'ditolak');
    assert.equal(dariNvd({ cve: { ...ITEM_NVD.cve, vulnStatus: 'Awaiting Analysis', configurations: [] } }).cve.statusAnalisis, 'menunggu');
  });

  it('mengurai CPE dengan karakter ter-escape', () => {
    assert.deepEqual(uraiCpe('cpe:2.3:a:microsoft:asp.net_core:8.0\\:rc1:*:*:*:*:*:*:*'), {
      bagian: 'a',
      vendor: 'microsoft',
      produk: 'asp.net_core',
      versi: '8.0:rc1',
    });
    assert.equal(uraiCpe('bukan-cpe'), null);
  });

  it('advisory OSV memakai alias CVE bila ada', () => {
    const c = dariOsv({ id: 'GHSA-xxxx', aliases: ['CVE-2020-11022'], summary: 'XSS di jQuery', database_specific: { severity: 'MODERATE' } });
    assert.equal(c.id, 'CVE-2020-11022');
    assert.equal(c.severitas, 'sedang');
    assert.equal(dariOsv({ id: 'GHSA-yyyy' }).id, 'GHSA-yyyy');
  });

  it('severitas dari skor', () => {
    assert.equal(severitasDariSkor(9.8), 'kritis');
    assert.equal(severitasDariSkor(5), 'sedang');
    assert.equal(severitasDariSkor(null), null);
  });
});

describe('kerentanan.pencocokan', () => {
  const nginx = (versi, extra = {}) => ({ nama: 'nginx', vendor: 'f5', produk: 'nginx', versi, sumber: 'banner', keyakinan: 'tinggi', ...extra });
  const rentang = [{ cveId: 'CVE-2021-23017', versiMulaiIncl: '0.6.18', versiAkhirExcl: '1.20.1' }];

  it('versi dalam rentang → terdampak', () => {
    const h = evaluasiKomponen(nginx('1.18.0'), rentang);
    assert.equal(h.get('CVE-2021-23017').status, 'terdampak');
    assert.match(h.get('CVE-2021-23017').alasan, /≥ 0\.6\.18 dan < 1\.20\.1/);
  });

  it('versi di luar rentang → tidak dicatat', () => {
    assert.equal(evaluasiKomponen(nginx('1.24.0'), rentang).size, 0);
  });

  it('tanpa versi / keyakinan rendah → kemungkinan', () => {
    assert.equal(evaluasiKomponen(nginx(null), rentang).get('CVE-2021-23017').status, 'kemungkinan');
    assert.equal(evaluasiKomponen(nginx('1.18.0', { keyakinan: 'rendah' }), rentang).get('CVE-2021-23017').status, 'kemungkinan');
  });

  it('versi distro diberi catatan backport', () => {
    assert.match(evaluasiKomponen(nginx('1.18.0-0ubuntu1.4'), rentang).get('CVE-2021-23017').alasan, /backport/);
  });

  it('hasil OSV → terdampak', () => {
    const k = { nama: 'jQuery', versi: '3.4.1', sumber: 'bundle_js', keyakinan: 'tinggi', purl: 'pkg:npm/jquery@3.4.1' };
    const h = evaluasiKomponen(k, [], [{ cveId: 'CVE-2020-11022', purl: 'pkg:npm/jquery', versi: '3.4.1' }]);
    assert.equal(h.get('CVE-2020-11022').status, 'terdampak');
  });

  it('komponen tanpa versi hanya untuk CVE KEV atau tinggi/kritis yang baru', () => {
    const sekarang = new Date('2026-11-14T00:00:00Z');
    assert.equal(layakTanpaVersi({ kev: true, severitas: 'rendah', dipublikasiPada: '2010-01-01' }, sekarang), true);
    assert.equal(layakTanpaVersi({ severitas: 'kritis', dipublikasiPada: '2026-01-01' }, sekarang), true);
    assert.equal(layakTanpaVersi({ severitas: 'kritis', dipublikasiPada: '2020-01-01' }, sekarang), false);
    assert.equal(layakTanpaVersi({ severitas: 'sedang', dipublikasiPada: '2026-10-01' }, sekarang), false);
  });

  it('prioritas: KEV > EPSS > CVSS, dibobot aset', () => {
    const app = { environment: 'produksi', dataClassification: 'rahasia' };
    const kev = hitungPrioritas({ kev: true, epss: 0.9, cvssSkor: 7.5 }, 'terdampak', app);
    const biasa = hitungPrioritas({ kev: false, epss: 0.01, cvssSkor: 7.5 }, 'terdampak', app);
    assert.ok(kev > biasa);
    assert.ok(hitungPrioritas({ cvssSkor: 7.5 }, 'kemungkinan', app) < hitungPrioritas({ cvssSkor: 7.5 }, 'terdampak', app));
    assert.ok(kev <= 100);
    assert.equal(tingkatPrioritas(10, true), 'segera');
    assert.equal(tingkatPrioritas(50), 'tinggi');
    assert.equal(tingkatPrioritas(5), 'rendah');
  });

  it('kerabat CPE dari kamus', () => {
    assert.deepEqual(cpeTerkait('f5', 'nginx').pasangan, [
      ['f5', 'nginx'],
      ['nginx', 'nginx'],
    ]);
    assert.equal(cpeTerkait('canonical', 'ubuntu_linux').bagian, 'o');
    assert.deepEqual(cpeTerkait('acme', 'tak_dikenal').pasangan, [['acme', 'tak_dikenal']]);
  });
});

describe('kerentanan.service', () => {
  let disimpan;
  let status;
  let surat;
  let service;
  const pemilikB = { id: '11', peran: 'pemilik', satuan_id: '2' };

  beforeEach(() => {
    disimpan = [];
    status = [];
    surat = [];
    service = createKerentananService({
      auditor: () => {},
      kirimEmail: async (m) => surat.push(m),
      aplikasi: { findById: async (id) => (id === 1 ? { id: 1, unitId: 1 } : null) },
      repository: {
        komponenAplikasi: async () => [
          { id: 1, applicationId: 1, vendor: 'f5', produk: 'nginx', nama: 'nginx', versi: null, sumber: 'formulir', keyakinan: 'tinggi', environment: 'produksi' },
          { id: 2, applicationId: 1, vendor: 'f5', produk: 'nginx', nama: 'nginx', versi: '1.18.0', sumber: 'banner', keyakinan: 'tinggi', environment: 'produksi' },
        ],
        idAplikasiAktif: async () => [1],
        cpeUntukPasangan: async (pasangan) => {
          assert.deepEqual(pasangan, [
            ['f5', 'nginx'],
            ['nginx', 'nginx'],
          ]);
          return [
            { cveId: 'CVE-2021-23017', vendor: 'f5', produk: 'nginx', versiMulaiIncl: '0.6.18', versiAkhirExcl: '1.20.1' },
            { cveId: 'CVE-2009-0001', vendor: 'nginx', produk: 'nginx', versiAkhirExcl: '0.5' },
          ];
        },
        paketUntuk: async () => [],
        infoCve: async () => new Map([['CVE-2021-23017', { kev: false, epss: '0.5', cvssSkor: '7.7', severitas: 'tinggi' }]]),
        kunciHasil: async () => new Map(),
        simpanHasil: async (appId, baris) => disimpan.push([appId, baris]),
        findById: async (id) => (id === 5 ? { id: 5, applicationId: 1, unitId: 1, cveId: 'CVE-2021-23017', status: 'terdampak' } : null),
        ubahStatus: async (id, s) => status.push([id, s]),
        untukNotifikasi: async () => [
          { id: 7, applicationId: 1, aplikasi: 'Sistem A', email: 'a@contoh.test', pemilik: 'Pemilik', cveId: 'CVE-2023-44487', namaKomponen: 'nginx', versi: '1.18.0', kev: 1 },
        ],
        tandaiDiberitahu: async (ids) => status.push(['diberitahu', ids]),
      },
    });
  });

  it('memakai komponen berversi (banner) dan menyimpan kecocokan yang relevan', async () => {
    const r = await service.cocokkanAplikasi(1);
    assert.equal(r.kecocokanBaru, 1);
    const [[appId, baris]] = disimpan;
    assert.equal(appId, 1);
    assert.equal(baris.length, 1);
    assert.equal(baris[0].cveId, 'CVE-2021-23017');
    assert.equal(baris[0].status, 'terdampak');
    assert.equal(baris[0].sumberKomponen, 'banner');
    assert.ok(baris[0].prioritas > 0);
  });

  it('ubah status: pemilik satuan lain dijawab 404', async () => {
    await assert.rejects(service.ubahStatus(pemilikB, 5, { status: 'ditangani', catatan: 'sudah ditambal' }), { statusCode: 404 });
  });

  it('notifikasi email dikirim per aplikasi lalu ditandai', async () => {
    const n = await service.notifikasi();
    assert.equal(n, 1);
    assert.equal(surat[0].to, 'a@contoh.test');
    assert.match(surat[0].subject, /Sistem A/);
    assert.match(surat[0].text, /CVE-2023-44487/);
    assert.deepEqual(status.at(-1), ['diberitahu', [7]]);
  });

  it('waktu evaluasi tanpa milidetik (DATETIME membulatkan → hasil baru tertandai kedaluwarsa)', async () => {
    let waktu;
    service = createKerentananService({
      repository: {
        komponenAplikasi: async () => [],
        idAplikasiAktif: async () => [1],
        cpeUntukPasangan: async () => [],
        paketUntuk: async () => [],
        infoCve: async () => new Map(),
        kunciHasil: async () => new Map(),
        simpanHasil: async (_id, _baris, w) => {
          waktu = w;
        },
      },
    });
    await service.cocokkanAplikasi(1);
    assert.equal(waktu.getMilliseconds(), 0);
  });

  it('daftar per aplikasi memeriksa cakupan', async () => {
    await assert.rejects(service.list(pemilikB, { page: 1, limit: 25, aplikasi_id: 1 }), { statusCode: 404 });
  });
});
