import { AppError } from '../utils/AppError.js';
import { audit } from '../utils/audit.js';

/** Dipasang setelah `authenticate`: `requireRole('admin')` atau `requireRole('asesor', 'admin')`. */
export function requireRole(...roles) {
  return (req, res, next) => {
    if (roles.includes(req.user?.peran)) return next();
    audit('akses.ditolak', { peran: req.user?.peran, dibutuhkan: roles, method: req.method, path: req.originalUrl.split('?')[0] });
    return next(AppError.forbidden('Anda tidak memiliki akses ke fitur ini'));
  };
}
