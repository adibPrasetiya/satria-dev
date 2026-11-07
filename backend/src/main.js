// Entry tunggal aplikasi: `node src/main.js [serve|migrate|create-admin|seed-catalog|sync-catalog|seed-satuan]`.
import { createAdmin } from './cli/createAdmin.js';
import { seedCatalog } from './cli/seedCatalog.js';
import { seedSatuan } from './cli/seedSatuan.js';
import { syncCatalog } from './cli/syncCatalog.js';
import { pool } from './db/index.js';
import { runMigrations } from './db/migrate.js';
import { startServer } from './index.js';
import { errorMessage } from './utils/errorMessage.js';

const COMMANDS = {
  serve: () => startServer(),

  async migrate() {
    await runMigrations();
    console.log('Migrasi database selesai');
  },

  'create-admin': () => createAdmin(),

  'seed-catalog': () => seedCatalog(),

  'sync-catalog': () => syncCatalog(),

  'seed-satuan': () => seedSatuan(),
};

// Perintah selain `serve` selesai sekali jalan, jadi koneksi DB ditutup setelahnya.
const ONE_SHOT = new Set(['migrate', 'create-admin', 'seed-catalog', 'sync-catalog', 'seed-satuan']);

const command = process.argv[2] ?? 'serve';
const run = COMMANDS[command];

if (!run) {
  console.error(`Perintah "${command}" tidak dikenal. Gunakan: ${Object.keys(COMMANDS).join(' | ')}`);
  process.exit(1);
}

async function main() {
  try {
    await run();
  } catch (error) {
    console.error(errorMessage(error));
    process.exitCode = 1;
  } finally {
    if (ONE_SHOT.has(command)) await pool.end();
  }
}

main();
