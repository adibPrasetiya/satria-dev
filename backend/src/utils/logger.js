import path from 'node:path';
import winston from 'winston';
import DailyRotateFile from 'winston-daily-rotate-file';
import { env } from '../config/env.js';
import { getContext } from './requestContext.js';

const { combine, timestamp, errors, json, colorize, printf } = winston.format;

// Relatif terhadap folder kerja aplikasi (tetap benar setelah dibundel ke dist/).
export const LOG_ROOT = path.resolve(process.cwd(), env.log.dir);
// Nama file log harian: satya-YYYY-MM-DD.log.
export const LOG_FILE_PREFIX = 'satya-';
export const LOG_RETENTION = '14d';

const SENSITIVE_KEY = /password|token|authorization|secret|apikey|cookie|resend/i;
const MAX_DEPTH = 6;

/** Salinan `value` dengan nilai key sensitif (password, token, dsb.) diganti '[disamarkan]'. */
export function redact(value, depth = 0) {
  if (value === null || typeof value !== 'object' || value instanceof Date) return value;
  if (depth >= MAX_DEPTH) return '[terlalu dalam]';
  if (Array.isArray(value)) return value.map((item) => redact(item, depth + 1));
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, SENSITIVE_KEY.test(key) ? '[disamarkan]' : redact(item, depth + 1)]),
  );
}

// Field bawaan winston yang tidak perlu disamarkan (Symbol level/message tetap aman karena bukan key string).
const RESERVED = new Set(['level', 'message', 'timestamp', 'stack']);

const redactFormat = winston.format((info) => {
  for (const key of Object.keys(info)) {
    if (RESERVED.has(key)) continue;
    info[key] = SENSITIVE_KEY.test(key) ? '[disamarkan]' : redact(info[key]);
  }
  return info;
});

// Sisipkan kode request, user, dan IP dari request yang sedang berjalan (lihat requestContext.js).
const contextFormat = winston.format((info) => {
  const context = getContext();
  if (context) {
    info.requestId ??= context.requestId;
    if (context.userId) info.userId ??= context.userId;
    if (context.username) info.username ??= context.username;
    if (context.ip) info.ip ??= context.ip;
  }
  return info;
});

// Sudah tampil di teks baris (mis. "POST /path 400 12ms"), atau terlalu ramai untuk dibaca di terminal.
const DEV_HIDDEN = new Set(['requestId', 'ip', 'userAgent', 'kategori', 'method', 'path', 'status', 'durationMs', 'bytes']);

// Stack error backend sudah diawali pesannya; stack dari browser belum tentu, jadi pesan ditambahkan.
// Metadata lain (userId, event, alasan, dsb.) ditampilkan ringkas di akhir baris.
const devFormat = printf(({ level, message, timestamp: time, stack, requestId, kategori, ...meta }) => {
  const body = !stack ? message : stack.includes(message) ? stack : `${message}\n${stack}`;
  const extra = Object.entries(meta).filter(([key, value]) => !DEV_HIDDEN.has(key) && value !== undefined);
  const metaText = extra.length ? ` ${JSON.stringify(Object.fromEntries(extra))}` : '';
  const tag = kategori === 'audit' ? ' [AUDIT]' : '';
  return `${time} ${level}:${requestId ? ` [${requestId}]` : ''}${tag} ${body}${metaText}`;
});

const isTest = env.nodeEnv === 'test';

const transports = [
  new winston.transports.Console({
    format: env.isProduction
      ? json()
      : combine(colorize(), timestamp({ format: 'HH:mm:ss' }), devFormat),
    handleExceptions: true,
    handleRejections: true,
  }),
];

// File JSON per hari (satu baris = satu entri). Nonaktif bawaan; aktifkan dengan LOG_TO_FILE=true.
if (env.log.toFile && !isTest) {
  transports.push(
    new DailyRotateFile({
      dirname: LOG_ROOT,
      filename: `${LOG_FILE_PREFIX}%DATE%.log`,
      datePattern: 'YYYY-MM-DD',
      maxSize: '20m',
      maxFiles: LOG_RETENTION,
      format: json(),
      handleExceptions: true,
      handleRejections: true,
    }),
  );
}

export const logger = winston.createLogger({
  level: env.log.level,
  silent: isTest,
  format: combine(timestamp(), errors({ stack: true }), contextFormat(), redactFormat()),
  transports,
});
