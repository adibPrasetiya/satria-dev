import { ipKeyGenerator, rateLimit } from 'express-rate-limit';
import { audit } from '../utils/audit.js';
import { failure } from '../utils/response.js';

// Setiap limiter diberi nama agar log menunjukkan batas mana yang terlampaui.
const limiter = (nama, options) =>
  rateLimit({
    standardHeaders: 'draft-8',
    legacyHeaders: false,
    handler: (req, res, next, opts) => {
      audit('rate_limit.terlampaui', { limiter: nama, method: req.method, path: req.originalUrl.split('?')[0] });
      return failure(res, { statusCode: opts.statusCode, message: opts.message });
    },
    ...options,
  });

// Lapis kedua di depan penguncian akun per-pengguna (authentication.service): membatasi tebakan
// dari satu IP ke satu email. Hanya percobaan gagal yang dihitung.
export const loginLimiter = limiter('login', {
  windowMs: 15 * 60 * 1000,
  limit: 10,
  skipSuccessfulRequests: true,
  keyGenerator: (req) => `${ipKeyGenerator(req.ip)}:${req.body?.email ?? ''}`,
  message: 'Terlalu banyak percobaan masuk, coba lagi dalam 15 menit',
});

export const registerLimiter = limiter('daftar', {
  windowMs: 60 * 60 * 1000,
  limit: 10,
  message: 'Terlalu banyak pendaftaran dari jaringan ini, coba lagi nanti',
});

// Cek NRP/email terdaftar (stepper pendaftaran) bisa dipakai menebak akun, jadi dibatasi ketat per IP.
export const availabilityLimiter = limiter('cek_ketersediaan', {
  windowMs: 15 * 60 * 1000,
  limit: 10,
  message: 'Terlalu banyak pemeriksaan data, coba lagi dalam 15 menit',
});

// Ganti kata sandi: batasi tebakan kata sandi lama bila sesi dicuri. Per pengguna (bukan IP), hanya yang gagal dihitung.
export const changePasswordLimiter = limiter('ganti_sandi', {
  windowMs: 15 * 60 * 1000,
  limit: 5,
  skipSuccessfulRequests: true,
  keyGenerator: (req) => `user:${req.user?.id ?? ipKeyGenerator(req.ip)}`,
  message: 'Terlalu banyak percobaan ganti kata sandi, coba lagi dalam 15 menit',
});

// Lupa & reset kata sandi: cegah banjir email dan tebakan token.
export const passwordResetLimiter = limiter('reset_sandi', {
  windowMs: 15 * 60 * 1000,
  limit: 10,
  message: 'Terlalu banyak permintaan, coba lagi dalam 15 menit',
});

// Verifikasi email & kirim ulang tautan: cegah tebak token dan banjir email ke pendaftar.
export const emailVerificationLimiter = limiter('verifikasi_email', {
  windowMs: 15 * 60 * 1000,
  limit: 10,
  message: 'Terlalu banyak permintaan, coba lagi dalam 15 menit',
});

// Generate laporan AI: tiap panggilan memakan kuota/biaya provider AI. Per pengguna.
export const laporanAiLimiter = limiter('laporan_ai', {
  windowMs: 60 * 60 * 1000,
  limit: 20,
  keyGenerator: (req) => `user:${req.user?.id ?? ipKeyGenerator(req.ip)}`,
  message: 'Terlalu banyak permintaan generate laporan, coba lagi dalam 1 jam',
});
