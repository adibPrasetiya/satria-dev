import Joi from 'joi';

export const scanIdSchema = Joi.object({ id: Joi.number().integer().positive().required() });
export const appIdSchema = Joi.object({ id: Joi.number().integer().positive().required() });
export const listScansSchema = Joi.object({ app: Joi.number().integer().positive() });

// Akun uji. `totp_secret` (seed base32 TOTP) dulu terbuang karna stripUnknown; kini eksplisit.
const akun = Joi.object({
  username: Joi.string().trim().allow('').max(160).default(''),
  password: Joi.string().allow('').max(200).default(''),
  totp_secret: Joi.string().trim().allow('').max(400).default(''),
  // Parameter TOTP dari URI otpauth (QR). Opsional; worker memakai default 6/30/SHA1.
  totp_digits: Joi.number().integer().valid(6, 7, 8),
  totp_period: Joi.number().integer().min(15).max(120),
  totp_algoritma: Joi.string().uppercase().valid('SHA1', 'SHA256', 'SHA512'),
});

// Opsi scan (izin uji berisiko + jendela waktu + hint OpenAPI).
const opsiUji = Joi.object({
  izinkan_penguncian: Joi.boolean().default(false),
  jendela_mulai: Joi.string().allow('').max(40).default(''),
  jendela_selesai: Joi.string().allow('').max(40).default(''),
  panjang_minimum: Joi.number().integer().min(1).max(256),
  wajib: Joi.array().items(Joi.string().max(40)).max(10),
  // Hint URL spec OpenAPI untuk mode eksploratif (opsional).
  openapi_url: Joi.string().trim().allow('').uri({ scheme: ['http', 'https'] }).max(500),
});

// Daftar akun uji jalur otomatis (N≥2 didukung; validasi "min 2 terisi" di FE/service).
const daftarAkun = Joi.object({ daftar: Joi.array().items(akun).max(10).default([]) });

// Body saat memulai scan. mode eksploratif memerlukan persetujuan pengguna (pemindaian aktif),
// dan boleh menyertakan akun uji + opsi yang disimpan ke scan_targets sebelum fase penemuan.
export const mulaiScanSchema = Joi.object({
  mode: Joi.string().valid('terarah', 'eksploratif').default('terarah'),
  persetujuan: Joi.boolean().when('mode', {
    is: 'eksploratif',
    then: Joi.valid(true).required().messages({ 'any.only': 'Persetujuan pemindaian aktif wajib untuk mode eksploratif' }),
    otherwise: Joi.optional(),
  }),
  // Grey box: memakai akun uji terbatas. Black box: tanpa akun (akun tersimpan pun tidak dipakai).
  pendekatan: Joi.string()
    .valid('greybox', 'blackbox')
    .default('greybox')
    .messages({ 'any.only': 'Pendekatan pengujian tidak valid' }),
  accounts: daftarAkun.optional(),
  options: opsiUji.optional(),
  // Uji ulang: pakai hasil penemuan tersimpan (lewati fase penemuan).
  pakai_discovery: Joi.boolean().default(false),
});

// Persiapan uji (scan_targets). Bentuk longgar: pemetaan titik uji -> URL & template form.
const pemetaanTitik = Joi.object({
  tersedia: Joi.boolean().default(false),
  url: Joi.string().trim().allow('').uri({ scheme: ['http', 'https'] }).max(500).default(''),
  metode_http: Joi.string().trim().uppercase().valid('GET', 'POST', 'PUT', 'PATCH', 'DELETE').default('POST'),
  catatan: Joi.string().trim().allow('').max(300),
});

const formTitik = Joi.object({
  // registrasi
  field_dasar: Joi.object().pattern(Joi.string().max(60), Joi.any()).default({}),
  field_sandi: Joi.string().trim().max(60).default('password'),
  field_unik: Joi.array().items(Joi.string().max(60)).max(20).default([]),
  tipe_body: Joi.string().valid('json', 'form').default('json'),
  status_sukses: Joi.array().items(Joi.number().integer().min(100).max(599)).max(20).default([200, 201, 202]),
  // login
  field_username: Joi.string().trim().max(60),
  field_password: Joi.string().trim().max(60),
  penanda_berhasil: Joi.string().trim().allow('').max(200),
  penanda_gagal: Joi.string().trim().allow('').max(200),
  // ubah kata sandi
  field_lama: Joi.string().trim().max(60),
  field_baru: Joi.string().trim().max(60),
  // reset
  field_identitas: Joi.string().trim().max(60),
  email: Joi.string().trim().allow('').max(160),
});

export const saveTargetSchema = Joi.object({
  test_points: Joi.object().pattern(Joi.string().max(40), pemetaanTitik).required(),
  forms: Joi.object().pattern(Joi.string().max(40), formTitik).default({}),
  // Terima bentuk lama (utama/penguncian, jalur terarah) & baru (daftar[], jalur otomatis).
  accounts: Joi.object({ utama: akun, penguncian: akun, daftar: Joi.array().items(akun).max(10) }).default({}),
  options: opsiUji.default({}),
});
