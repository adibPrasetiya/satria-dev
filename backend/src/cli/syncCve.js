// `npm run cve:sync [-- --ringan]` — sinkron intel kerentanan (NVD, KEV, OSV, EPSS) lalu cocokkan ke aset.
// Dijadwalkan lewat PM2 (`satya-sync-cve`, lihat ecosystem.config.cjs). Aman diulang: hanya satu sinkron
// berjalan pada satu waktu (kunci di tabel sinkron_intel).
import { intelService } from '../features/kerentanan/intel.service.js';

const rincian = (l) => {
  if (!l.ok) return `GAGAL: ${l.pesan}`;
  if (l.dilewati) return 'dilewati';
  const { kunci: _k, ok: _o, ...isi } = l;
  return JSON.stringify(isi);
};

export async function syncCve() {
  const hasil = await intelService.sinkron({ ringan: process.argv.includes('--ringan') });
  if (hasil === null) return console.log('Sinkron intel kerentanan lain sedang berjalan; dilewati.');
  if (hasil.dinonaktifkan) return console.log('CVE_SYNC_ENABLED=false; sinkron dilewati.');
  for (const l of hasil.langkah) console.log(`  ${l.kunci.padEnd(16)} ${rincian(l)}`);
  console.log(`Sinkron intel kerentanan selesai: ${hasil.ringkasan}`);
}
