import Joi from 'joi';
import { BATAS_KOORDINAT, JENIS_SATUAN, KODE_PROVINSI } from '../../config/satuan.js';

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

const jenis = Joi.string()
  .valid(...JENIS_SATUAN)
  .messages({ 'any.only': 'Jenis satuan tidak dikenal' });

// Kolom alamat opsional: string kosong/null = kosongkan (service mengubah "" menjadi null).
const teksOpsional = (max, label) =>
  Joi.string()
    .trim()
    .replace(/\s+/g, ' ')
    .max(max)
    .allow('', null)
    .messages({ 'string.max': `${label} maksimal ${max} karakter` });

const koordinat = (min, max, label) =>
  Joi.number()
    .min(min)
    .max(max)
    .precision(6)
    .allow(null)
    .messages({
      'number.base': `${label} harus berupa angka`,
      'number.min': `${label} di luar wilayah Indonesia (${min} s.d. ${max})`,
      'number.max': `${label} di luar wilayah Indonesia (${min} s.d. ${max})`,
    });

const fields = {
  nama: namaSatuan,
  jenis,
  induk_id: Joi.number().integer().positive().allow(null).messages({ 'number.base': 'Satuan induk tidak valid' }),
  aktif: Joi.boolean(),
  alamat: teksOpsional(255, 'Alamat'),
  kota: teksOpsional(100, 'Kabupaten/kota'),
  provinsi_kode: Joi.string()
    .valid(...KODE_PROVINSI)
    .allow('', null)
    .messages({ 'any.only': 'Provinsi tidak dikenal' }),
  latitude: koordinat(BATAS_KOORDINAT.latMin, BATAS_KOORDINAT.latMax, 'Latitude'),
  longitude: koordinat(BATAS_KOORDINAT.lngMin, BATAS_KOORDINAT.lngMax, 'Longitude'),
};

export const listUnitsAdminSchema = Joi.object({
  page: Joi.number().integer().min(1).default(1),
  limit: Joi.number().integer().valid(10, 25, 50, 100).default(50),
  search: Joi.string().trim().allow('').max(100).default(''),
  status: Joi.string().valid('aktif', 'nonaktif', '').default(''),
  jenis: Joi.string()
    .valid(...JENIS_SATUAN)
    .empty(''),
  provinsi: Joi.string()
    .valid(...KODE_PROVINSI)
    .empty(''),
  // 'akar' = satuan tingkat teratas; id = sub-satuan langsung dari satuan itu; tidak diisi = semua tingkat.
  induk: Joi.alternatives(Joi.string().valid('akar'), Joi.number().integer().positive()).empty(''),
});

export const unitIdSchema = Joi.object({
  id: Joi.number().integer().positive().required(),
});

export const createUnitSchema = Joi.object({
  ...fields,
  nama: namaSatuan.required().messages({ 'any.required': 'Nama satuan wajib diisi' }),
  jenis: jenis.default('SATUAN'),
  induk_id: fields.induk_id.default(null),
  aktif: Joi.boolean().default(true),
});

export const updateUnitSchema = Joi.object(fields)
  .min(1)
  .messages({ 'object.min': 'Tidak ada data satuan yang diubah' });
