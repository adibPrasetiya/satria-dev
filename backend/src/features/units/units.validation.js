import Joi from 'joi';

export const searchUnitsSchema = Joi.object({
  search: Joi.string().trim().allow('').max(100).default(''),
  limit: Joi.number().integer().min(1).max(50).default(20),
});

// Nama satuan: spasi di tepi dibuang dan spasi ganda dirapikan agar "Satuan  A" tidak dianggap berbeda.
const namaSatuan = Joi.string()
  .trim()
  .replace(/\s+/g, ' ')
  .min(2)
  .max(120)
  .messages({
    'string.empty': 'Nama satuan wajib diisi',
    'string.min': 'Nama satuan minimal 2 karakter',
    'string.max': 'Nama satuan maksimal 120 karakter',
  });

export const listUnitsAdminSchema = Joi.object({
  page: Joi.number().integer().min(1).default(1),
  limit: Joi.number().integer().valid(10, 25, 50, 100).default(50),
  search: Joi.string().trim().allow('').max(100).default(''),
  status: Joi.string().valid('aktif', 'nonaktif', '').default(''),
});

export const unitIdSchema = Joi.object({
  id: Joi.number().integer().positive().required(),
});

export const createUnitSchema = Joi.object({
  nama: namaSatuan.required().messages({ 'any.required': 'Nama satuan wajib diisi' }),
  aktif: Joi.boolean().default(true),
});

export const updateUnitSchema = Joi.object({
  nama: namaSatuan,
  aktif: Joi.boolean(),
})
  .or('nama', 'aktif')
  .messages({ 'object.missing': 'Isi nama atau status satuan' });
