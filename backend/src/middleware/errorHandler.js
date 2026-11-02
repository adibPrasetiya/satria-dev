import { env } from '../config/env.js';
import { AppError } from '../utils/AppError.js';
import { logger } from '../utils/logger.js';
import { failure } from '../utils/response.js';

// eslint-disable-next-line no-unused-vars
export function errorHandler(err, req, res, next) {
  if (err instanceof AppError) {
    if (err.statusCode >= 500) logger.error(err.message, requestDetails(req, err));
    // 4xx adalah kesalahan klien: cukup debug, dengan detail validasi agar mudah ditelusuri saat development.
    else logger.debug(`${err.statusCode} ${err.message}`, { errorCode: err.code, errors: err.details });
    return failure(res, { statusCode: err.statusCode, message: err.message, errors: err.details, code: err.code });
  }

  // Body JSON rusak / terlalu besar dari express.json()
  if (err.type === 'entity.parse.failed' || err.type === 'entity.too.large') {
    logger.warn('Body request tidak valid', { type: err.type, method: req.method, path: req.originalUrl.split('?')[0] });
    return failure(res, { statusCode: err.status, message: 'Body request tidak valid' });
  }

  logger.error(err?.message ?? String(err), requestDetails(req, err));
  // Kode request ditampilkan ke pengguna agar bisa dilaporkan dan dicari di log server.
  const code = req.id ? ` (kode: ${req.id})` : '';
  return failure(res, {
    statusCode: 500,
    message: `Terjadi kesalahan pada server${code}`,
    errors: env.isProduction ? undefined : [{ message: err.message, stack: err.stack }],
  });
}

/** Konteks error untuk log: endpoint, query, dan body (sudah disamarkan logger) agar bug bisa direproduksi. */
function requestDetails(req, err) {
  return {
    stack: err?.stack,
    errorCode: err?.code,
    method: req.method,
    path: req.originalUrl.split('?')[0],
    query: req.query,
    body: req.body,
  };
}
