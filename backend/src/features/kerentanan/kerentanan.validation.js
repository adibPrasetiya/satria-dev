import Joi from 'joi';
import { SEVERITIES, STATUS_KERENTANAN } from '../../db/schema.js';

const kosong = (s) => s.empty('');
const POLA_STATUS = new RegExp(`^(${STATUS_KERENTANAN.join('|')})(,(${STATUS_KERENTANAN.join('|')}))*$`);

export const listKerentananSchema = Joi.object({
  page: Joi.number().integer().min(1).default(1),
  limit: Joi.number().integer().valid(10, 25, 50, 100).default(25),
  aplikasi_id: kosong(Joi.number().integer().positive()),
  // Kode provinsi BPS 2 digit dari satuan pemilik aset (sama dengan dasar peta dasbor).
  provinsi: kosong(Joi.string().pattern(/^\d{2}$/)).messages({ 'string.pattern.base': 'Kode provinsi tidak valid' }),
  // Daftar status dipisah koma; kosong = yang masih aktif (terdampak, kemungkinan).
  status: kosong(Joi.string().pattern(POLA_STATUS)).messages({ 'string.pattern.base': 'Status tidak valid' }),
  kev: Joi.boolean().default(false),
  severitas: kosong(Joi.string().valid(...SEVERITIES)).messages({ 'any.only': 'Severitas tidak valid' }),
  search: Joi.string().trim().allow('').max(100).default(''),
  sort: Joi.string().valid('prioritas', 'terbaru', 'publikasi').default('prioritas'),
});

export const kerentananIdSchema = Joi.object({ id: Joi.number().integer().positive().required() });

const PESAN_CATATAN = 'Catatan wajib diisi (mis. tambalan yang diterapkan atau alasan pengecualian)';

export const ubahStatusSchema = Joi.object({
  status: Joi.string().valid('ditangani', 'dikecualikan', 'buka').required().messages({ 'any.only': 'Status tidak valid' }),
  catatan: Joi.when('status', {
    is: 'buka',
    then: Joi.string().trim().allow('').max(1000),
    otherwise: Joi.string().trim().min(5).max(1000).required().messages({
      'any.required': PESAN_CATATAN,
      'string.empty': PESAN_CATATAN,
      'string.min': 'Catatan minimal 5 karakter',
    }),
  }),
});
