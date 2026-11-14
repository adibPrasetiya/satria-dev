import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { ambilVersi, dariTeknologi, uraiTeks } = await import('../src/features/komponen/komponen.parser.js');
const { createKomponenService, pilihEfektif } = await import('../src/features/komponen/komponen.service.js');
const { createApplicationsService } = await import('../src/features/applications/applications.service.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

const ringkas = (items) => items.map((k) => [k.vendor, k.produk, k.versi]);

describe('komponen.parser', () => {
  it('memisahkan beberapa komponen dalam satu isian', () => {
    assert.deepEqual(ringkas(uraiTeks('Laravel 10 + PHP 8.2-fpm')), [
      ['laravel', 'framework', '10'],
      ['php', 'php', '8.2'],
    ]);
    assert.deepEqual(ringkas(uraiTeks('Nginx di Ubuntu 22.04')), [
      ['f5', 'nginx', null],
      ['canonical', 'ubuntu_linux', '22.04'],
    ]);
  });

  it('format banner "produk/versi" tetap satu komponen', () => {
    assert.deepEqual(ringkas(uraiTeks('nginx/1.18.0')), [['f5', 'nginx', '1.18.0']]);
  });

  it('alias terpanjang menang', () => {
    assert.deepEqual(ringkas(uraiTeks('Apache Tomcat 9.0.80')), [['apache', 'tomcat', '9.0.80']]);
    assert.deepEqual(ringkas(uraiTeks('Spring Boot 3.1.4')), [['vmware', 'spring_boot', '3.1.4']]);
    assert.deepEqual(ringkas(uraiTeks('Ruby on Rails 7')), [['rubyonrails', 'rails', '7']]);
  });

  it('alias dicocokkan per kata utuh', () => {
    // "go" tidak boleh cocok di dalam "django"/"mongo".
    assert.deepEqual(ringkas(uraiTeks('Django 4.2')), [['djangoproject', 'django', '4.2']]);
    assert.deepEqual(ringkas(uraiTeks('mongo')), [['mongodb', 'mongodb', null]]);
  });

  it('membentuk CPE & purl', () => {
    const [k] = uraiTeks('jQuery 3.4.1', 'frontend');
    assert.equal(k.cpe, 'cpe:2.3:a:jquery:jquery:3.4.1:*:*:*:*:*:*:*');
    assert.equal(k.purl, 'pkg:npm/jquery@3.4.1');
    assert.equal(k.kategori, 'frontend');
    const [os] = uraiTeks('Ubuntu');
    assert.equal(os.cpe, 'cpe:2.3:o:canonical:ubuntu_linux:*:*:*:*:*:*:*:*');
  });

  it('produk tak dikenal tetap dicatat dengan keyakinan rendah', () => {
    const [k] = uraiTeks('Windows Server 2019');
    assert.equal(k.vendor, null);
    assert.equal(k.produk, 'windows-server');
    assert.equal(k.versi, '2019');
    assert.equal(k.keyakinan, 'rendah');
    assert.equal(k.cpe, null);
  });

  it('mengabaikan isian kosong/sampah', () => {
    assert.deepEqual(uraiTeks(''), []);
    assert.deepEqual(uraiTeks('-'), []);
    assert.deepEqual(uraiTeks(null), []);
  });

  it('ambilVersi mempertahankan akhiran berangka saja', () => {
    assert.equal(ambilVersi(' 8.0.32-0ubuntu0.20.04'), '8.0.32-0ubuntu0.20.04');
    assert.equal(ambilVersi(' 8.2-fpm'), '8.2');
    assert.equal(ambilVersi(' v1.2.3'), '1.2.3');
    assert.equal(ambilVersi(' tanpa versi'), null);
  });

  it('dariTeknologi: satu baris per produk, yang berversi didahulukan', () => {
    const items = dariTeknologi({ frontend: 'Laravel Blade', backend: 'Laravel 10', database: 'MySQL 8', server: '' });
    assert.deepEqual(ringkas(items), [
      ['laravel', 'framework', '10'],
      ['oracle', 'mysql', '8'],
    ]);
    assert.equal(items[0].kategori, 'backend');
  });
});

describe('komponen.pilihEfektif', () => {
  const k = (id, sumber, versi) => ({ id, vendor: 'f5', produk: 'nginx', sumber, versi });

  it('manual selalu menang', () => {
    const r = pilihEfektif([k(1, 'banner', '1.18.0'), k(2, 'manual', null)]);
    assert.deepEqual(r.filter((x) => x.dipakai).map((x) => x.id), [2]);
  });

  it('di luar manual, baris berversi didahulukan', () => {
    const r = pilihEfektif([k(1, 'formulir', null), k(2, 'banner', '1.18.0')]);
    assert.deepEqual(r.filter((x) => x.dipakai).map((x) => x.id), [2]);
  });

  it('sama-sama berversi → formulir di atas recon', () => {
    const r = pilihEfektif([k(1, 'banner', '1.18.0'), k(2, 'formulir', '1.20.1')]);
    assert.deepEqual(r.filter((x) => x.dipakai).map((x) => x.id), [2]);
  });
});

describe('komponen.service', () => {
  let rows;
  let apps;
  let events;
  let service;

  const pemilikA = { id: '10', peran: 'pemilik', satuan_id: '1' };
  const pemilikB = { id: '11', peran: 'pemilik', satuan_id: '2' };
  const asesor = { id: '20', peran: 'asesor', satuan_id: '2' };

  beforeEach(() => {
    rows = [];
    events = [];
    apps = { 1: { id: 1, unitId: 1, archivedAt: null }, 2: { id: 2, unitId: 1, archivedAt: new Date() } };
    let seq = 0;
    service = createKomponenService({
      auditor: (e, d) => events.push([e, d]),
      aplikasi: { findById: async (id) => apps[id] ?? null },
      repository: {
        listByApplication: async (appId) => rows.filter((r) => r.applicationId === appId),
        findById: async (id) => rows.find((r) => r.id === id) ?? null,
        gantiSumber: async (appId, sumber, items) => {
          rows = rows.filter((r) => !(r.applicationId === appId && r.sumber === sumber));
          for (const it of items) rows.push({ ...it, id: ++seq, applicationId: appId, sumber });
        },
        upsert: async (appId, sumber, item) => {
          const lama = rows.find((r) => r.applicationId === appId && r.sumber === sumber && r.produk === item.produk);
          if (lama) return Object.assign(lama, item);
          const baru = { ...item, id: ++seq, applicationId: appId, sumber };
          rows.push(baru);
          return baru;
        },
        hapus: async (id) => {
          rows = rows.filter((r) => r.id !== id);
        },
      },
    });
  });

  it('sinkronFormulir mengganti komponen formulir saja', async () => {
    await service.tambahManual(pemilikA, 1, { kategori: 'server', teks: 'nginx 1.18.0' });
    await service.sinkronFormulir(1, { backend: 'Laravel 10', server: 'Nginx' });
    await service.sinkronFormulir(1, { backend: 'Laravel 11' });
    const { items, ringkasan } = await service.list(pemilikA, 1);
    assert.deepEqual(
      items.map((k) => [k.produk, k.sumber, k.versi, k.dipakai]),
      [
        ['nginx', 'manual', '1.18.0', true],
        ['framework', 'formulir', '11', true],
      ],
    );
    assert.deepEqual(ringkasan, { produk: 2, dikenali: 2, berversi: 2 });
  });

  it('aset satuan lain dijawab 404', async () => {
    await assert.rejects(service.list(pemilikB, 1), { statusCode: 404 });
    await service.list(asesor, 1);
  });

  it('teks tak bermakna ditolak', async () => {
    await assert.rejects(service.tambahManual(pemilikA, 1, { kategori: 'server', teks: '12' }), { statusCode: 400 });
  });

  it('aset terarsip tak bisa diubah', async () => {
    await assert.rejects(service.tambahManual(pemilikA, 2, { kategori: 'server', teks: 'nginx' }), { statusCode: 409 });
  });

  it('hanya komponen manual yang bisa dihapus', async () => {
    await service.sinkronFormulir(1, { server: 'Nginx' });
    const formulir = rows[0];
    await assert.rejects(service.hapus(pemilikA, 1, formulir.id), { statusCode: 409 });

    await service.tambahManual(pemilikA, 1, { kategori: 'server', teks: 'nginx 1.18.0' });
    const manual = rows.find((r) => r.sumber === 'manual');
    const { items } = await service.hapus(pemilikA, 1, manual.id);
    assert.deepEqual(items.map((k) => k.sumber), ['formulir']);
    assert.equal(events.at(-1)[0], 'komponen.hapus');
  });

  it('simpanRecon mengurai teks worker & mengganti per sumber', async () => {
    const n = await service.simpanRecon(1, 7, [
      { sumber: 'banner', kategori: 'server', teks: 'Apache/2.4.41 (Ubuntu)', keyakinan: 'tinggi', bukti: 'Server: Apache/2.4.41 (Ubuntu)' },
      { sumber: 'banner', kategori: 'backend', teks: 'PHP', keyakinan: 'rendah', bukti: 'cookie PHPSESSID' },
      { sumber: 'bundle_js', kategori: 'library', teks: 'jQuery 3.4.1', keyakinan: 'tinggi', bukti: 'vendor.js' },
    ]);
    assert.equal(n, 4);
    const banner = rows.filter((r) => r.sumber === 'banner').map((r) => [r.produk, r.versi, r.keyakinan]);
    assert.deepEqual(banner, [
      ['http_server', '2.4.41', 'tinggi'],
      ['ubuntu_linux', null, 'tinggi'],
      ['php', null, 'rendah'],
    ]);
    assert.equal(rows.find((r) => r.produk === 'jquery').purl, 'pkg:npm/jquery@3.4.1');

    // Laporan berikutnya untuk sumber banner menggantikan seluruh banner lama; bundle_js tetap.
    await service.simpanRecon(1, 8, [{ sumber: 'banner', kategori: 'server', teks: 'nginx/1.24.0', keyakinan: 'tinggi' }]);
    assert.deepEqual(rows.map((r) => [r.sumber, r.produk]).sort(), [
      ['banner', 'nginx'],
      ['bundle_js', 'jquery'],
    ]);
  });

  it('komponen aplikasi lain dijawab 404', async () => {
    rows.push({ id: 99, applicationId: 3, sumber: 'manual', produk: 'x' });
    await assert.rejects(service.hapus(pemilikA, 1, 99), { statusCode: 404 });
  });
});

describe('applications.service → sinkron komponen', () => {
  const pemilik = { id: '10', peran: 'pemilik', satuan_id: '1' };
  const DATA = {
    nama: 'Sistem Uji',
    pic_nama: 'Mayor Uji',
    pic_kontak: '0812',
    url_dasar: 'https://uji.contoh.mil.id',
    lingkungan: 'produksi',
    klasifikasi_data: 'terbatas',
    teknologi: { frontend: '', backend: 'Laravel 10', database: '', server: '' },
  };

  function buat(sinkron) {
    const rows = [];
    return createApplicationsService({
      auditor: () => {},
      komponen: { sinkronFormulir: async (id, tek) => sinkron.push([id, tek]) },
      repository: {
        findById: async (id) => rows.find((r) => r.id === id) ?? null,
        create: async (data) => {
          const r = { id: rows.length + 1, ...data };
          rows.push(r);
          return r;
        },
        update: async (id, data) => Object.assign(rows.find((r) => r.id === id), data),
      },
    });
  }

  it('sinkron saat daftar & saat field teknologi berubah saja', async () => {
    const sinkron = [];
    const service = buat(sinkron);
    const app = await service.create(pemilik, DATA);
    assert.deepEqual(sinkron, [[1, { frontend: '', backend: 'Laravel 10', database: '', server: '' }]]);

    await service.update(pemilik, app.id, { nama: 'Sistem Uji 2' });
    assert.equal(sinkron.length, 1);

    await service.update(pemilik, app.id, { teknologi: { server: 'nginx 1.18.0' } });
    assert.deepEqual(sinkron.at(-1), [1, { frontend: '', backend: 'Laravel 10', database: '', server: 'nginx 1.18.0' }]);
  });

  it('kegagalan sinkron tidak menggagalkan simpan aset', async () => {
    const service = createApplicationsService({
      auditor: () => {},
      komponen: {
        sinkronFormulir: async () => {
          throw new Error('db mati');
        },
      },
      repository: { create: async (data) => ({ id: 1, ...data }) },
    });
    const app = await service.create(pemilik, DATA);
    assert.equal(app.id, '1');
  });
});
