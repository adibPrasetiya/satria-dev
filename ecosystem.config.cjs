// Konfigurasi PM2 untuk server dev SATYA.
// Dijalankan dari root repo:  pm2 reload ecosystem.config.cjs --update-env
//
// Catatan: FRONTEND tidak ada di sini. Frontend memakai adapter-static,
// jadi `npm run build` menghasilkan file statis di frontend/build/ yang
// disajikan oleh Nginx (lihat deploy/README-DEPLOY di PR / instruksi).
module.exports = {
  apps: [
    {
      name: 'satya-backend',
      cwd: './backend',
      script: 'src/main.js',
      args: 'serve',
      instances: 1,
      autorestart: true,
      max_restarts: 10,
      env: { NODE_ENV: 'production' }
      // PORT, DATABASE_URL, JWT_ACCESS_SECRET dibaca backend dari backend/.env (dotenv)
    },
    {
      name: 'satya-worker',
      cwd: './worker',
      script: '.venv/bin/python', // biner venv (Linux); worker butuh Python 3.13
      interpreter: 'none',        // jalankan biner langsung, jangan bungkus node
      args: '-m satya_worker.main', // mode LOOP: poll backend /internal/tasks/claim
      autorestart: true,
      max_restarts: 10,
      env: { PYTHONUNBUFFERED: '1' }
      // BACKEND_URL, WORKER_TOKEN dibaca worker dari worker/.env
    },
    {
      // Sinkron intel kerentanan (NVD + CISA KEV + EPSS + OSV) lalu cocokkan ke komponen aset.
      // Proses sekali jalan yang dipicu cron tiap 6 jam; aman bila tumpang-tindih (kunci di DB).
      name: 'satya-sync-cve',
      cwd: './backend',
      script: 'src/main.js',
      args: 'sync-cve',
      instances: 1,
      autorestart: false,
      cron_restart: '15 */6 * * *',
      env: { NODE_ENV: 'production' }
      // NVD_API_KEY, CVE_SYNC_ENABLED, HTTPS_PROXY/NODE_USE_ENV_PROXY dibaca dari backend/.env
    }
  ]
};
