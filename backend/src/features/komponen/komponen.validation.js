import Joi from 'joi';
import { KATEGORI_KOMPONEN } from '../../db/schema.js';

export const komponenParamsSchema = Joi.object({
  id: Joi.number().integer().positive().required(),
  komponenId: Joi.number().integer().positive().required(),
});

export const tambahKomponenSchema = Joi.object({
  kategori: Joi.string()
    .valid(...KATEGORI_KOMPONEN)
    .required()
    .messages({ 'any.only': 'Kategori komponen tidak valid', 'any.required': 'Kategori komponen wajib dipilih' }),
  teks: Joi.string().trim().replace(/\s+/g, ' ').min(2).max(100).required().messages({
    'string.empty': 'Komponen wajib diisi',
    'any.required': 'Komponen wajib diisi',
    'string.min': 'Komponen minimal 2 karakter',
    'string.max': 'Komponen maksimal 100 karakter',
  }),
});
