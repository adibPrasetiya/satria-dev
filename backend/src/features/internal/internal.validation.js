import Joi from 'joi';

export const taskIdSchema = Joi.object({ id: Joi.number().integer().positive().required() });

const ENGINE_WORKER = Joi.string().valid('custom', 'zap', 'nuclei', 'sslyze', 'playwright', 'discovery');

// Heartbeat worker (registry + perpanjang lease task + sinyal batal).
export const heartbeatSchema = Joi.object({
  worker_id: Joi.string().trim().max(100).required(),
  engines: Joi.array().items(ENGINE_WORKER).max(7).default([]),
  status: Joi.string().valid('siaga', 'sibuk', 'berhenti').default('siaga'),
  task_id: Joi.number().integer().positive().allow(null),
  tahap: Joi.string().allow('', null).max(120),
  versi: Joi.string().allow('', null).max(40),
  host: Joi.string().allow('', null).max(120),
});

export const berhentiSchema = Joi.object({ worker_id: Joi.string().trim().max(100).required() });

export const claimSchema = Joi.object({
  worker_id: Joi.string().trim().max(100).default('worker'),
  engines: Joi.array()
    .items(Joi.string().valid('custom', 'zap', 'nuclei', 'sslyze', 'playwright', 'discovery'))
    .max(7)
    .default(['custom']),
});

// HasilMetode dari worker (longgar; disamarkan di worker, divalidasi bentuk minimal di sini).
const bukti = Joi.object({
  jenis: Joi.string().valid('request_response', 'screenshot', 'dokumen').required(),
  judul: Joi.string().max(300).required(),
  isi: Joi.string().allow('').max(20_000),
  nama_file: Joi.string().max(300),
  waktu: Joi.string().max(40),
}).unknown(true);

const hasil = Joi.object({
  metode_id: Joi.string().max(50),
  status: Joi.string().valid('lulus', 'gagal', 'tidak_berlaku', 'tidak_dapat_diverifikasi').required(),
  ringkasan: Joi.string().allow('').max(1000),
  detail: Joi.string().allow('').max(5000),
  bukti: Joi.array().items(bukti).max(50).default([]),
  // Langkah reproduksi naratif (PoC) per temuan — dibatasi agar hasil tetap ramping.
  poc: Joi.array().items(Joi.string().allow('').max(2000)).max(30).default([]),
  menunggu_tinjauan: Joi.boolean(),
  durasi_ms: Joi.number().integer().min(0),
}).unknown(true);

export const resultSchema = Joi.object({ hasil: hasil.required() });

// Payload fase penemuan dari worker discovery (longgar; worker tepercaya via X-Worker-Token).
const titikOtomatis = Joi.object({
  tersedia: Joi.boolean().default(true),
  url: Joi.string().trim().allow('').max(500).default(''),
  metode_http: Joi.string().trim().uppercase().max(10).default('GET'),
  sumber: Joi.string().valid('otomatis', 'manual').default('otomatis'),
  keyakinan: Joi.string().valid('tinggi', 'sedang', 'rendah').default('sedang'),
  catatan: Joi.string().trim().allow('').max(300).default(''),
}).unknown(true);

export const discoverySchema = Joi.object({
  test_points: Joi.object().pattern(Joi.string().max(40), titikOtomatis).default({}),
  forms: Joi.object().pattern(Joi.string().max(40), Joi.object().unknown(true)).max(30).default({}),
  ringkasan: Joi.object().unknown(true).default({}),
}).unknown(true);

export const logSchema = Joi.object({
  level: Joi.string().valid('info', 'peringatan', 'galat').default('info'),
  pesan: Joi.string().allow('').max(500).required(),
  // Peristiwa terstruktur untuk visualisasi penemuan (lihat worker peristiwa.py).
  data: Joi.object().unknown(true).optional(),
});
