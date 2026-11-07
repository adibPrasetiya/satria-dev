import { randomUUID } from 'node:crypto';
import { logger } from '../utils/logger.js';
import { runWithContext } from '../utils/requestContext.js';

// Request yang tidak perlu dicatat: health check.
const SKIP = [/^\/health$/];

// Lalu lintas rutin worker (heartbeat & klaim tanpa task, tiap beberapa detik per worker) membanjiri log;
// saat sukses dicatat di level `silly` (tersembunyi pada LOG_LEVEL=debug ke atas). Galat tetap warn/error.
const RUTIN = [/^\/api\/v1\/internal\/workers\/heartbeat$/, /^\/api\/v1\/internal\/tasks\/claim$/];

const levelFor = (status, path) =>
  status >= 500 ? 'error' : status >= 400 ? 'warn' : RUTIN.some((p) => p.test(path)) ? 'silly' : 'http';

/**
 * Beri setiap request kode unik (header X-Request-Id) dan catat ringkasannya setelah selesai.
 * Body request TIDAK dicatat agar kata sandi & data pribadi tidak masuk log.
 */
export function requestLogger(req, res, next) {
  const requestId = randomUUID().replace(/-/g, '').slice(0, 10);
  const context = { requestId, ip: req.ip };
  req.id = requestId;
  res.set('X-Request-Id', requestId);

  const skip = SKIP.some((pattern) => pattern.test(req.path));
  const startedAt = process.hrtime.bigint();

  res.on('finish', () => {
    if (skip) return;
    const durationMs = Math.round(Number(process.hrtime.bigint() - startedAt) / 1e6);
    logger.log(levelFor(res.statusCode, req.originalUrl.split('?')[0]), `${req.method} ${req.originalUrl.split('?')[0]} ${res.statusCode} ${durationMs}ms`, {
      requestId,
      userId: context.userId,
      username: context.username,
      method: req.method,
      path: req.originalUrl.split('?')[0],
      status: res.statusCode,
      durationMs,
      bytes: Number(res.get('content-length')) || undefined,
      ip: req.ip,
      userAgent: req.get('user-agent'),
    });
  });

  runWithContext(context, next);
}
