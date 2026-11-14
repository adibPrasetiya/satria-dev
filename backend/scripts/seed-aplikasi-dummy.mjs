// Seed aplikasi DUMMY untuk demo intel kerentanan (CVE ↔ aset) — KHUSUS lingkungan dev.
//
//   node scripts/seed-aplikasi-dummy.mjs            → simulasi: hanya menampilkan apa yang akan dihapus/dibuat
//   node scripts/seed-aplikasi-dummy.mjs --ya       → eksekusi
//   ... --tanpa-sinkron                             → lewati sinkron intel CVE sesudahnya
//
// Yang dilakukan saat --ya:
//   1. HAPUS PERMANEN semua aplikasi KECUALI yang bernama "Aplikasi Cuti" — beserta seluruh riwayat
//      pengujian, hasil, log, laporan, komponen, dan kecocokan kerentanannya (FK cascade).
//   2. Buat aplikasi dummy dengan teknologi berversi lama (sengaja rentan) di satuan-satuan berlokasi.
//   3. Bentuk komponen dari field teknologi, lalu sinkron intel (NVD/KEV/EPSS/OSV) + pencocokan.
//
// Domain dummy memakai TLD .test (tidak dapat di-resolve) agar tak ada target sungguhan yang terpindai.
import { pool } from '../src/db/index.js';
import { env } from '../src/config/env.js';
import { komponenService } from '../src/features/komponen/komponen.service.js';

const YA = process.argv.includes('--ya');
const TANPA_SINKRON = process.argv.includes('--tanpa-sinkron');
const DIPERTAHANKAN = 'aplikasi cuti';

// [nama, deskripsi, lingkungan, klasifikasi, {frontend, backend, database, server}]
const DUMMY = [
  ['Sistem Informasi Personel', 'Pengelolaan data personel, mutasi, dan riwayat jabatan.', 'produksi', 'rahasia',
    { frontend: 'jQuery 1.12.4, Bootstrap 3.3.7', backend: 'Laravel 8.40.0 + PHP 7.4.3', database: 'MySQL 5.7.30', server: 'nginx 1.18.0 di Ubuntu 20.04' }],
  ['Portal Layanan Kesehatan', 'Pendaftaran dan rekam layanan kesehatan prajurit dan keluarga.', 'produksi', 'rahasia',
    { frontend: 'React 16.13.1', backend: 'Express 4.17.1 + Node.js 14.15.0', database: 'MongoDB 4.0.3', server: 'nginx 1.20.1' }],
  ['Aplikasi Logistik Gudang', 'Inventaris dan distribusi logistik antar gudang.', 'produksi', 'terbatas',
    { frontend: 'AngularJS 1.5.8', backend: 'Spring Framework 5.3.17, Spring Boot 2.6.5', database: 'PostgreSQL 12.2', server: 'Apache Tomcat 9.0.30' }],
  ['E-Arsip Persuratan', 'Pengarsipan surat masuk/keluar dan disposisi elektronik.', 'produksi', 'terbatas',
    { frontend: 'jQuery 3.4.1', backend: 'PHP 7.2.24', database: 'MariaDB 10.3.22', server: 'Apache 2.4.49' }],
  ['Sistem Pelaporan Insiden', 'Pelaporan dan penanganan insiden keamanan informasi.', 'produksi', 'rahasia',
    { frontend: 'Vue.js 2.6.11', backend: 'Django 2.2.10', database: 'PostgreSQL 11.5', server: 'nginx 1.16.1' }],
  ['Portal Berita Internal', 'Publikasi berita dan pengumuman internal satuan.', 'produksi', 'biasa',
    { frontend: 'jQuery 3.5.1', backend: 'WordPress 5.8.1 + PHP 7.4.3', database: 'MySQL 5.7.33', server: 'Apache 2.4.41' }],
  ['Aplikasi Penggajian', 'Perhitungan tunjangan, potongan, dan slip gaji.', 'produksi', 'rahasia',
    { frontend: 'AngularJS 1.7.8', backend: 'ASP.NET Core 3.1.0', database: 'SQL Server 2019', server: 'IIS 10.0' }],
  ['Sistem Diklat Online', 'Pembelajaran daring dan ujian pendidikan pelatihan.', 'produksi', 'biasa',
    { frontend: 'Bootstrap 4.3.1', backend: 'Moodle 3.9.1 + PHP 7.4.3', database: 'PostgreSQL 12.2', server: 'nginx 1.18.0' }],
  ['Monitoring Jaringan', 'Dasbor pemantauan perangkat dan trafik jaringan.', 'produksi', 'terbatas',
    { frontend: 'Grafana 8.2.6', backend: 'Go 1.16.3', database: 'Elasticsearch 6.8.0', server: 'nginx 1.20.1' }],
  ['Sistem Pengadaan Barang', 'Perencanaan dan pelaksanaan pengadaan barang/jasa.', 'produksi', 'terbatas',
    { frontend: 'jQuery 1.11.3', backend: 'Apache Struts 2.3.31', database: 'Oracle Database 12.2', server: 'Apache Tomcat 8.5.40' }],
  ['Portal JDIH Satuan', 'Jaringan dokumentasi dan informasi hukum.', 'produksi', 'biasa',
    { frontend: 'jQuery 2.2.4', backend: 'Drupal 7.57 + PHP 5.6.40', database: 'MySQL 5.6.40', server: 'Apache 2.4.29' }],
  ['Aplikasi Absensi Biometrik', 'Rekap kehadiran dari mesin biometrik.', 'produksi', 'terbatas',
    { frontend: 'Vue.js 2.5.17', backend: 'CodeIgniter 3.1.9 + PHP 7.0.33', database: 'MySQL 5.7.21', server: 'nginx 1.14.0' }],
  ['Helpdesk TI', 'Tiket layanan dan permintaan dukungan TI.', 'produksi', 'biasa',
    { frontend: 'React 17.0.1', backend: 'Flask 1.1.1 + Python 3.7.3', database: 'Redis 5.0.7, PostgreSQL 10.12', server: 'Gunicorn 19.9.0, nginx 1.18.0' }],
  ['Sistem Manajemen Aset TI', 'Inventaris perangkat keras dan lisensi perangkat lunak.', 'staging', 'terbatas',
    { frontend: 'Angular 12.0.0', backend: 'Spring Boot 2.5.6 + Log4j 2.14.1', database: 'MySQL 8.0.22', server: 'Apache Tomcat 9.0.41' }],
  ['Wiki Dokumentasi Teknis', 'Basis pengetahuan dan dokumentasi sistem.', 'produksi', 'terbatas',
    { frontend: '', backend: 'Confluence 7.13.0', database: 'PostgreSQL 10.12', server: 'nginx 1.18.0' }],
  ['Repositori Kode Internal', 'Repositori kode sumber dan CI/CD internal.', 'produksi', 'rahasia',
    { frontend: '', backend: 'GitLab 13.10.2, Jenkins 2.263.1', database: 'PostgreSQL 12.4, Redis 6.0.9', server: 'nginx 1.18.0' }],
  ['Sistem Kepegawaian PNS', 'Administrasi PNS: kenaikan pangkat, cuti, dan SKP.', 'produksi', 'rahasia',
    { frontend: 'jQuery 3.3.1, Bootstrap 4.1.3', backend: 'Yii 2.0.38 + PHP 7.3.11', database: 'MariaDB 10.4.12', server: 'Apache 2.4.46' }],
  ['Pengelolaan Basis Data', 'Antarmuka administrasi basis data aplikasi satuan.', 'pengembangan', 'terbatas',
    { frontend: '', backend: 'phpMyAdmin 4.8.1 + PHP 7.2.24', database: 'MySQL 5.7.30', server: 'Apache 2.4.38' }],
  ['Single Sign-On Satuan', 'Layanan identitas dan SSO untuk aplikasi internal.', 'produksi', 'rahasia',
    { frontend: '', backend: 'Keycloak 12.0.4', database: 'PostgreSQL 12.2', server: 'nginx 1.18.0, OpenSSL 1.1.1k' }],
  ['Portal Rekrutmen', 'Pendaftaran dan seleksi calon prajurit/PNS.', 'produksi', 'terbatas',
    { frontend: 'Next.js 12.0.7, React 17.0.2', backend: 'NestJS 8.0.0 + Node.js 16.13.0', database: 'PostgreSQL 13.3', server: 'nginx 1.21.3' }],
  ['Sistem Survei Kepuasan', 'Survei kepuasan layanan internal.', 'staging', 'biasa',
    { frontend: 'Svelte 3.38.2', backend: 'FastAPI 0.65.1 + Python 3.8.10', database: 'MongoDB 4.4.6', server: 'Caddy 2.4.3' }],
  ['Aplikasi Kendaraan Dinas', 'Pemakaian, perawatan, dan BBM kendaraan dinas.', 'produksi', 'biasa',
    { frontend: 'jQuery 1.12.4', backend: 'Ruby on Rails 5.2.3', database: 'PostgreSQL 9.6.17', server: 'nginx 1.16.1' }],
];

const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const PIC = ['Mayor Inf. Budi Santoso', 'Kapten Chk. Rina Wulandari', 'Letkol Kav. Agus Pratama', 'Lettu Arh. Dewi Lestari',
  'Penata Muda Hendra Wijaya', 'Kapten Czi. Fajar Nugroho', 'Mayor Ckm. Sri Rahayu', 'Penata Andi Kurniawan'];

async function main() {
  console.log(`Database: ${new URL(env.databaseUrl).pathname.slice(1)} @ ${new URL(env.databaseUrl).hostname} (${env.nodeEnv})`);

  const [semua] = await pool.query('SELECT id, name FROM applications');
  const cuti = semua.filter((a) => a.name.trim().toLowerCase() === DIPERTAHANKAN);
  if (cuti.length !== 1) {
    throw new Error(`Harus ada tepat satu aplikasi bernama "Aplikasi Cuti" (ditemukan ${cuti.length}); dibatalkan demi keamanan.`);
  }
  const hapus = semua.filter((a) => a.id !== cuti[0].id);
  const [[{ nScan }]] = await pool.query('SELECT COUNT(*) AS nScan FROM scans WHERE application_id <> ?', [cuti[0].id]);

  // Satuan berlokasi (agar tampil di peta); satuan milik akun pemilik didahulukan agar pemilik ikut melihat data.
  const [satuan] = await pool.query(
    `SELECT u.id, u.name, (SELECT MIN(us.id) FROM users us WHERE us.unit_id = u.id AND us.role = 'pemilik' AND us.is_active = 1) AS pemilik
     FROM units u WHERE u.is_active = 1 AND u.latitude IS NOT NULL
     ORDER BY (pemilik IS NULL), RAND()`,
  );
  if (!satuan.length) throw new Error('Tidak ada satuan aktif berlokasi untuk menempatkan aplikasi dummy.');

  console.log(`\nDipertahankan : #${cuti[0].id} ${cuti[0].name}`);
  console.log(`Dihapus       : ${hapus.length} aplikasi beserta ${nScan} riwayat pengujian (hasil, log, laporan ikut terhapus)`);
  console.log(`Dibuat        : ${DUMMY.length} aplikasi dummy di ${Math.min(DUMMY.length, satuan.length)} satuan berlokasi`);
  if (!YA) {
    console.log('\nSIMULASI — tidak ada yang diubah. Jalankan ulang dengan --ya untuk mengeksekusi.');
    return;
  }

  const conn = await pool.getConnection();
  const baru = [];
  try {
    await conn.beginTransaction();
    for (const ids of [hapus.map((a) => a.id)]) {
      if (ids.length) await conn.query('DELETE FROM applications WHERE id IN (?)', [ids]);
    }
    for (const [i, [nama, deskripsi, lingkungan, klasifikasi, t]] of DUMMY.entries()) {
      const u = satuan[i % satuan.length];
      const [r] = await conn.query(
        `INSERT INTO applications (name, description, unit_id, owner_id, pic_name, pic_contact, base_url, environment,
           data_classification, tech_frontend, tech_backend, tech_database, tech_server)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [nama, deskripsi, u.id, u.pemilik ?? null, PIC[i % PIC.length], `0812-${String(1000 + i * 37).padStart(4, '0')}-${String(2000 + i * 53).slice(-4)}`,
          `https://${slug(nama)}.dummy.satria.test`, lingkungan, klasifikasi, t.frontend || null, t.backend || null, t.database || null, t.server || null],
      );
      baru.push({ id: r.insertId, nama, teknologi: t });
    }
    await conn.commit();
  } catch (error) {
    await conn.rollback();
    throw error;
  } finally {
    conn.release();
  }
  console.log(`\n✓ ${hapus.length} aplikasi dihapus, ${baru.length} aplikasi dummy dibuat.`);

  let komponen = 0;
  for (const a of baru) komponen += await komponenService.sinkronFormulir(a.id, a.teknologi);
  const [[c]] = await pool.query('SELECT tech_frontend AS frontend, tech_backend AS backend, tech_database AS `database`, tech_server AS server FROM applications WHERE id = ?', [cuti[0].id]);
  komponen += await komponenService.sinkronFormulir(cuti[0].id, c);
  console.log(`✓ ${komponen} komponen dibentuk dari field teknologi.`);

  if (TANPA_SINKRON) {
    console.log('Sinkron intel dilewati (--tanpa-sinkron). Jalankan: npm run cve:sync');
    return;
  }
  console.log('\nSinkron intel kerentanan (NVD per produk baru, KEV, OSV, EPSS) + pencocokan — bisa beberapa menit…');
  const { syncCve } = await import('../src/cli/syncCve.js');
  await syncCve();
}

main()
  .catch((error) => {
    console.error(`GAGAL: ${error.message}`);
    process.exitCode = 1;
  })
  .finally(() => pool.end());
