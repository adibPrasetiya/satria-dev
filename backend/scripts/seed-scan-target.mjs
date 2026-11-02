// Isi scan_targets untuk satu aplikasi agar scan AUTH-1.3 bisa jalan.
// Pakai untuk verifikasi end-to-end (mis. mendaftarkan SATYA sendiri sebagai aset uji).
//
//   node scripts/seed-scan-target.mjs <applicationId> [registerPath]
//
// registerPath default '/api/v1/auth/register' (endpoint registrasi SATYA).
// URL registrasi = applications.base_url + registerPath.
import { pool } from '../src/db/index.js';
import { applicationsRepository } from '../src/features/applications/applications.repository.js';
import { scansRepository } from '../src/features/scans/scans.repository.js';

const appId = Number(process.argv[2]);
const registerPath = process.argv[3] ?? '/api/v1/auth/register';

if (!Number.isInteger(appId) || appId <= 0) {
  console.error('Pemakaian: node scripts/seed-scan-target.mjs <applicationId> [registerPath]');
  process.exit(1);
}

try {
  const app = await applicationsRepository.findById(appId);
  if (!app) {
    console.error(`Aplikasi id=${appId} tidak ditemukan.`);
    process.exit(1);
  }
  const url = app.baseUrl.replace(/\/+$/, '') + registerPath;
  const target = await scansRepository.upsertTarget(appId, {
    testPoints: {
      registrasi: { tersedia: true, url, metode_http: 'POST' },
    },
    forms: {
      registrasi: {
        field_dasar: { nama: 'Akun Uji SATYA', nrp: '199001010000000001', satuan_id: 1, email: 'uji@satya.local' },
        field_sandi: 'password',
        field_unik: ['email', 'nrp'],
        tipe_body: 'json',
        status_sukses: [200, 201, 202],
      },
    },
  });
  console.log(`scan_targets untuk aplikasi ${appId} diisi. Endpoint registrasi: ${url}`);
  console.log(JSON.stringify(target, null, 2));
} finally {
  await pool.end();
}
