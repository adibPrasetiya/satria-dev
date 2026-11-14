import { app } from './app/app.js';
import { APP_NAME, APP_VERSION } from './config/app.js';
import { env } from './config/env.js';
import { pool } from './db/index.js';
import { pasangLanggananKomponen } from './features/kerentanan/kerentanan.langganan.js';
import { errorMessage } from './utils/errorMessage.js';
import { LOG_ROOT, logger } from './utils/logger.js';

/** Ringkasan konfigurasi saat start (tanpa rahasia) agar salah konfigurasi cepat terlihat. */
function logConfig() {
  const db = new URL(env.databaseUrl);
  logger.info('Konfigurasi', {
    database: `${db.hostname}:${db.port || 3306}${db.pathname}`,
    corsOrigin: env.corsOrigin,
    appUrl: env.appUrl,
    email: env.mail.resendApiKey ? `Resend (${env.mail.from})` : 'nonaktif — isi email dicatat di log',
    logLevel: env.log.level,
    logFile: env.log.toFile ? LOG_ROOT : 'nonaktif (hanya terminal)',
  });
}

/** Cek koneksi MySQL sekali saat start; server tetap jalan, tetapi masalahnya langsung terlihat di log. */
async function checkDatabase() {
  const startedAt = Date.now();
  try {
    await pool.query('SELECT 1');
    logger.info(`Terhubung ke MySQL (${Date.now() - startedAt}ms)`);
  } catch (error) {
    logger.error(errorMessage(error));
  }
}

export function startServer() {
  logConfig();
  // Pencocokan CVE ulang saat komponen aset berubah (formulir, koreksi manual, hasil recon).
  pasangLanggananKomponen();
  const server = app.listen(env.port, () => {
    logger.info(`${APP_NAME} ${APP_VERSION} API berjalan di http://localhost:${env.port} (${env.nodeEnv})`);
    checkDatabase();
  });

  server.on('error', (error) => {
    logger.error(
      error.code === 'EADDRINUSE' ? `Port ${env.port} sudah dipakai proses lain; ubah PORT di .env atau hentikan proses tersebut` : error.message,
      { stack: error.stack },
    );
    process.exit(1);
  });

  function shutdown(signal) {
    logger.info(`${signal} diterima, mematikan server...`);
    server.close(async () => {
      await pool.end();
      logger.info('Server berhenti');
      process.exit(0);
    });
  }

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}
