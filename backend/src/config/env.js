// dotenv membaca `.env` dari process.cwd().
import 'dotenv/config';
import Joi from 'joi';

const schema = Joi.object({
  NODE_ENV: Joi.string().valid('development', 'production', 'test').default('development'),
  PORT: Joi.number().port().default(3000),
  DATABASE_URL: Joi.string().uri({ scheme: ['mysql'] }).required(),
  JWT_ACCESS_SECRET: Joi.string().min(32).required(),
  JWT_ACCESS_EXPIRES_IN: Joi.string().default('15m'),
  REFRESH_TOKEN_TTL_DAYS: Joi.number().integer().min(1).default(7),
  CORS_ORIGIN: Joi.string().default('http://localhost:5173'),
  // Alamat frontend; dipakai untuk menyusun tautan reset kata sandi.
  APP_URL: Joi.string().uri({ scheme: ['http', 'https'] }).default('http://localhost:5173'),
  PASSWORD_RESET_TTL_MINUTES: Joi.number().integer().min(5).max(24 * 60).default(30),
  // Penguncian akun setelah login gagal berturut-turut (kontrol BSSN 1.4).
  LOGIN_MAX_ATTEMPTS: Joi.number().integer().min(3).max(20).default(5),
  LOGIN_LOCK_MINUTES: Joi.number().integer().min(1).max(24 * 60).default(15),
  // Email via Resend; tanpa RESEND_API_KEY tautan reset hanya dicatat di log (development).
  RESEND_API_KEY: Joi.string().allow('').default(''),
  // Alamat pengirim harus dari domain yang sudah diverifikasi di Resend.
  MAIL_FROM: Joi.string().default('SATRIA <onboarding@resend.dev>'),
  // Token layanan worker pengujian (header X-Worker-Token di endpoint /internal).
  // Wajib di production; di dev boleh kosong (endpoint /internal menolak semua request).
  WORKER_TOKEN: Joi.string().allow('').default(''),
  // Lease task: worker memperpanjangnya lewat heartbeat (±10 dtk). Lease yang tak diperbarui selama ini
  // = worker mati → task dikembalikan ke antrean (maks WORKER_MAKS_PERCOBAAN kali).
  WORKER_TASK_TIMEOUT_MS: Joi.number().integer().min(10_000).default(90_000),
  // Worker dianggap aktif bila heartbeat terakhir masih dalam jendela ini.
  WORKER_HEARTBEAT_TIMEOUT_MS: Joi.number().integer().min(5_000).default(45_000),
  WORKER_MAKS_PERCOBAAN: Joi.number().integer().min(1).default(3),
  // AI penyusun laporan (ringkasan eksekutif + rekomendasi). Nama env sama dengan worker.
  // AI_PROVIDER: gemini | anthropic | none; kosong = otomatis (gemini dulu, lalu anthropic bila ada kunci).
  AI_PROVIDER: Joi.string().valid('gemini', 'anthropic', 'none', '').default(''),
  GEMINI_API_KEY: Joi.string().allow('').default(''),
  ANTHROPIC_API_KEY: Joi.string().allow('').default(''),
  // Dipakai bila kunci spesifik provider kosong.
  AI_API_KEY: Joi.string().allow('').default(''),
  // Model untuk provider terpilih; kosong = bawaan provider.
  AI_MODEL: Joi.string().allow('').default(''),
  // Sementara log hanya ke terminal; true = juga tulis file JSON harian di LOG_DIR.
  LOG_TO_FILE: Joi.boolean().default(false),
  LOG_DIR: Joi.string().default('logs'),
  LOG_LEVEL: Joi.string().valid('error', 'warn', 'info', 'http', 'debug').allow(''),
}).unknown(true);

const { value, error } = schema.validate(process.env, { abortEarly: false, convert: true });

if (error) {
  console.error('Konfigurasi environment tidak valid:');
  for (const detail of error.details) console.error(`  - ${detail.message}`);
  process.exit(1);
}

export const env = Object.freeze({
  nodeEnv: value.NODE_ENV,
  isProduction: value.NODE_ENV === 'production',
  port: value.PORT,
  databaseUrl: value.DATABASE_URL,
  jwt: {
    accessSecret: value.JWT_ACCESS_SECRET,
    accessExpiresIn: value.JWT_ACCESS_EXPIRES_IN,
  },
  refreshTokenTtlDays: value.REFRESH_TOKEN_TTL_DAYS,
  worker: {
    token: value.WORKER_TOKEN,
    taskTimeoutMs: value.WORKER_TASK_TIMEOUT_MS,
    heartbeatTimeoutMs: value.WORKER_HEARTBEAT_TIMEOUT_MS,
    maksPercobaan: value.WORKER_MAKS_PERCOBAAN,
  },
  corsOrigin: value.CORS_ORIGIN.split(',').map((origin) => origin.trim()),
  appUrl: value.APP_URL.replace(/\/+$/, ''),
  passwordResetTtlMinutes: value.PASSWORD_RESET_TTL_MINUTES,
  login: {
    maxAttempts: value.LOGIN_MAX_ATTEMPTS,
    lockMinutes: value.LOGIN_LOCK_MINUTES,
  },
  mail: {
    resendApiKey: value.RESEND_API_KEY,
    from: value.MAIL_FROM,
  },
  ai: {
    provider: value.AI_PROVIDER,
    geminiKey: value.GEMINI_API_KEY || value.AI_API_KEY,
    anthropicKey: value.ANTHROPIC_API_KEY || value.AI_API_KEY,
    model: value.AI_MODEL,
  },
  log: {
    toFile: value.LOG_TO_FILE,
    dir: value.LOG_DIR,
    level: value.LOG_LEVEL || (value.NODE_ENV === 'production' ? 'info' : 'debug'),
  },
});
