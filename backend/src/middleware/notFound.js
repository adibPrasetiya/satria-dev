import { AppError } from '../utils/AppError.js';

export function notFound(req, res, next) {
  next(AppError.notFound(`Endpoint ${req.method} ${req.originalUrl} tidak ditemukan`));
}
