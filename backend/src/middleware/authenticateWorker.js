import { timingSafeEqual } from 'node:crypto';
import { env } from '../config/env.js';
import { AppError } from '../utils/AppError.js';

/** Perbandingan string tahan-waktu (menghindari timing attack pada token). */
function samaAman(a, b) {
  const ba = Buffer.from(a, 'utf8');
  const bb = Buffer.from(b, 'utf8');
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

/**
 * Lindungi endpoint /internal yang dipakai worker pengujian.
 * Worker mengirim header `X-Worker-Token`; dicocokkan dengan WORKER_TOKEN.
 * Tanpa WORKER_TOKEN dikonfigurasi, seluruh endpoint /internal ditolak.
 */
export function authenticateWorker(req, res, next) {
  const token = req.get('x-worker-token') ?? '';
  if (!env.worker.token || !token || !samaAman(token, env.worker.token)) {
    return next(AppError.unauthorized('Token worker tidak valid'));
  }
  return next();
}
