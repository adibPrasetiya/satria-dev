import Joi from 'joi';
import { DATA_CLASSIFICATIONS, ENVIRONMENTS, VERDICTS } from '../../db/schema.js';

const teks = (min, max, label) =>
  Joi.string()
    .trim()
    .replace(/\s+/g, ' ')
    .min(min)
    .max(max)
    .messages({
      'string.empty': `${label} wajib diisi`,
      'any.required': `${label} wajib diisi`,
      'string.min': `${label} minimal ${min} karakter`,
      'string.max': `${label} maksimal ${max} karakter`,
    });

// URL dasar disimpan tanpa garis miring di akhir agar "https://a.mil.id/" dan "https://a.mil.id" dianggap sama.
const urlDasar = Joi.string()
  .trim()
  .max(255)
  .uri({ scheme: ['http', 'https'] })
  .replace(/\/+$/, '')
  .messages({
    'string.uri': 'URL dasar harus diawali http:// atau https://',
    'string.uriCustomScheme': 'URL dasar harus diawali http:// atau https://',
    'string.empty': 'URL dasar wajib diisi',
    'any.required': 'URL dasar wajib diisi',
  });

const opsional = (label) => Joi.string().trim().allow('').max(100).messages({ 'string.max': `${label} maksimal 100 karakter` });

const fields = {
  nama: teks(3, 150, 'Nama aplikasi'),
  deskripsi: Joi.string().trim().allow('').max(2000).messages({ 'string.max': 'Deskripsi maksimal 2000 karakter' }),
  // Hanya dipakai admin; pemilik selalu memakai satuannya sendiri.
  satuan_id: Joi.number().integer().positive().messages({ 'number.base': 'Satuan tidak valid' }),
  pic_nama: teks(3, 100, 'Nama PIC'),
  pic_kontak: teks(3, 100, 'Kontak PIC'),
  url_dasar: urlDasar,
  lingkungan: Joi.string()
    .valid(...ENVIRONMENTS)
    .messages({ 'any.only': 'Lingkungan tidak valid', 'any.required': 'Lingkungan wajib dipilih' }),
  klasifikasi_data: Joi.string()
    .valid(...DATA_CLASSIFICATIONS)
    .messages({ 'any.only': 'Klasifikasi data tidak valid', 'any.required': 'Klasifikasi data wajib dipilih' }),
  teknologi: Joi.object({
    frontend: opsional('Teknologi frontend'),
    backend: opsional('Teknologi backend'),
    database: opsional('Basis data'),
    server: opsional('Server'),
  }),
};

export const createApplicationSchema = Joi.object({
  ...fields,
  nama: fields.nama.required(),
  pic_nama: fields.pic_nama.required(),
  pic_kontak: fields.pic_kontak.required(),
  url_dasar: fields.url_dasar.required(),
  lingkungan: fields.lingkungan.required(),
  klasifikasi_data: fields.klasifikasi_data.required(),
});

export const updateApplicationSchema = Joi.object(fields).min(1).messages({ 'object.min': 'Tidak ada data yang diubah' });

/** Kolom urut daftar aplikasi (lihat applications.repository: URUT). */
export const SORT_FIELDS = ['nama', 'satuan', 'lingkungan', 'klasifikasi', 'skor', 'temuan', 'uji', 'dibuat'];

const kosongJadiUndefined = (schema) => schema.empty('');

export const listApplicationsSchema = Joi.object({
  page: Joi.number().integer().min(1).default(1),
  limit: Joi.number().integer().valid(10, 25, 50, 100).default(100),
  search: Joi.string().trim().allow('').max(100).default(''),
  lingkungan: kosongJadiUndefined(Joi.string().valid(...ENVIRONMENTS)).messages({ 'any.only': 'Lingkungan tidak valid' }),
  klasifikasi: kosongJadiUndefined(Joi.string().valid(...DATA_CLASSIFICATIONS)).messages({
    'any.only': 'Klasifikasi data tidak valid',
  }),
  satuan_id: kosongJadiUndefined(Joi.number().integer().positive()).messages({ 'number.base': 'Satuan tidak valid' }),
  // Putusan scan selesai terakhir; 'belum' = belum pernah selesai diuji.
  putusan: kosongJadiUndefined(Joi.string().valid(...VERDICTS, 'belum')).messages({ 'any.only': 'Putusan tidak valid' }),
  // Status arsip: 'aktif' (bawaan, sembunyikan terarsip) | 'arsip' (hanya terarsip) | 'semua'.
  arsip: Joi.string().valid('aktif', 'arsip', 'semua').default('aktif').messages({ 'any.only': 'Filter arsip tidak valid' }),
  sort: Joi.string()
    .valid(...SORT_FIELDS)
    .default('dibuat'),
  order: Joi.string().valid('asc', 'desc').default('desc'),
  // Sertakan ringkasan jumlah per putusan & opsi satuan (untuk strip statistik & filter di halaman daftar).
  ringkasan: Joi.boolean().default(false),
});

export const applicationIdSchema = Joi.object({
  id: Joi.number().integer().positive().required(),
});
