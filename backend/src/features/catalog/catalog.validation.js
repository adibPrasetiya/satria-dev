import Joi from 'joi';
import { AGGREGATIONS, ENGINES, EVIDENCE_TYPES, METHOD_KINDS, PROFILES, SEVERITIES, VERIFIABILITIES } from '../../db/schema.js';

const teks = (min, max, label) =>
  Joi.string()
    .trim()
    .min(min)
    .max(max)
    .messages({
      'string.empty': `${label} wajib diisi`,
      'any.required': `${label} wajib diisi`,
      'string.min': `${label} minimal ${min} karakter`,
      'string.max': `${label} maksimal ${max} karakter`,
    });

const pilihan = (values, label) =>
  Joi.string()
    .valid(...values)
    .messages({ 'any.only': `${label} tidak valid`, 'any.required': `${label} wajib dipilih` });

// Parameter bebas bentuk (angka, teks, daftar, objek bertingkat) yang dibaca pemeriksa pengujian.
// Dibatasi: nama kunci snake_case, kedalaman & ukuran wajar. null = hapus semua parameter.
const KEDALAMAN_MAKS = 6;
const UKURAN_MAKS = 20_000;
function kedalaman(v, d = 0) {
  if (d > KEDALAMAN_MAKS) return d;
  if (Array.isArray(v)) return Math.max(d, ...v.map((x) => kedalaman(x, d + 1)));
  if (v && typeof v === 'object') return Math.max(d, ...Object.values(v).map((x) => kedalaman(x, d + 1)));
  return d;
}
const parameter = Joi.object()
  .pattern(/^[a-z][a-z0-9_]{0,59}$/, Joi.any())
  .max(30)
  .allow(null)
  .custom((value, helpers) => {
    if (value === null) return value;
    if (JSON.stringify(value).length > UKURAN_MAKS) return helpers.message('Parameter terlalu besar (maks. 20.000 karakter)');
    if (kedalaman(value) > KEDALAMAN_MAKS) return helpers.message('Parameter terlalu bertingkat (maks. 6 tingkat)');
    return value;
  })
  .messages({
    'object.unknown': 'Nama parameter harus huruf kecil/angka/garis bawah dan diawali huruf, mis. batas_percobaan',
    'object.max': 'Maksimal 30 parameter',
    'object.base': 'Parameter harus berupa objek',
  });

// --- Kontrol
const control = {
  uraian: teks(5, 2000, 'Uraian kontrol'),
  verifiabilitas: pilihan(VERIFIABILITIES, 'Verifiabilitas'),
  severity_default: pilihan(SEVERITIES, 'Severity bawaan'),
  agregasi: pilihan(AGGREGATIONS, 'Agregasi'),
  referensi_pendukung: Joi.array().items(Joi.string().trim().min(1).max(100)).max(20).unique(),
  parameter,
};

export const createControlSchema = Joi.object({
  // Kode kontrol dibentuk dari nomor ini (mis. AUTH-1.10), jadi tidak bisa diubah setelah dibuat.
  nomor_referensi: Joi.string()
    .trim()
    .pattern(/^\d+(\.\d+)*$/)
    .max(20)
    .required()
    .messages({ 'string.pattern.base': 'Nomor referensi berupa angka bertitik, mis. 1.10', 'any.required': 'Nomor referensi wajib diisi' }),
  ...control,
  uraian: control.uraian.required(),
  verifiabilitas: control.verifiabilitas.required(),
  severity_default: control.severity_default.required(),
  agregasi: control.agregasi.default('semua_lulus'),
  referensi_pendukung: control.referensi_pendukung.default([]),
});

export const updateControlSchema = Joi.object({ ...control, aktif: Joi.boolean() })
  .min(1)
  .messages({ 'object.min': 'Tidak ada data yang diubah' });

// --- Metode pengujian
const method = {
  nama: teks(3, 255, 'Nama metode'),
  titik_uji: Joi.string().trim().max(40).messages({ 'any.required': 'Titik uji wajib dipilih' }),
  check_id: Joi.string()
    .trim()
    .pattern(/^[a-z0-9_.-]+$/)
    .max(120)
    .messages({ 'string.pattern.base': 'Check ID hanya huruf kecil, angka, titik, garis bawah', 'any.required': 'Check ID wajib diisi' }),
  jenis: pilihan(METHOD_KINDS, 'Jenis'),
  engine: pilihan(ENGINES, 'Engine'),
  profil: pilihan(PROFILES, 'Profil'),
  butuh_autentikasi: Joi.boolean(),
  bukti: Joi.array()
    .items(Joi.string().valid(...EVIDENCE_TYPES))
    .min(1)
    .unique()
    .messages({ 'array.min': 'Pilih minimal satu jenis bukti', 'any.only': 'Jenis bukti tidak valid' }),
  kriteria_lulus: teks(3, 2000, 'Kriteria lulus'),
  efek_samping: Joi.string().trim().allow('').max(2000),
  severity: pilihan(SEVERITIES, 'Severity'),
  parameter,
};

export const createMethodSchema = Joi.object({
  ...method,
  nama: method.nama.required(),
  titik_uji: method.titik_uji.required(),
  check_id: method.check_id.required(),
  jenis: method.jenis.required(),
  engine: method.engine.required(),
  profil: method.profil.required(),
  butuh_autentikasi: method.butuh_autentikasi.default(false),
  bukti: method.bukti.default(['request_response']),
  kriteria_lulus: method.kriteria_lulus.required(),
  efek_samping: method.efek_samping.default(''),
  severity: method.severity.required(),
});

export const updateMethodSchema = Joi.object({ ...method, aktif: Joi.boolean() })
  .min(1)
  .messages({ 'object.min': 'Tidak ada data yang diubah' });

export const codeParamSchema = Joi.object({
  kode: Joi.string().trim().pattern(/^[A-Za-z0-9.-]+$/).max(50).required(),
});
