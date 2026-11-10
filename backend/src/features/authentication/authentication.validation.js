import Joi from 'joi';

export const email = Joi.string()
  .trim()
  .lowercase()
  .max(160)
  .email({ tlds: { allow: false } })
  .required()
  .messages({ 'string.email': 'Format email belum benar', 'any.required': 'Email wajib diisi', 'string.empty': 'Email wajib diisi' });

// Kebijakan kata sandi kontrol BSSN 1.3; sama dengan SYARAT_SANDI di frontend (src/lib/validasi.ts).
export const newPassword = Joi.string()
  .min(8)
  .max(72) // bcrypt hanya memproses 72 byte pertama
  .pattern(/[A-Z]/, 'huruf besar')
  .pattern(/[a-z]/, 'huruf kecil')
  .pattern(/\d/, 'angka')
  .pattern(/[^A-Za-z0-9]/, 'simbol')
  .required()
  .messages({
    'string.min': 'Kata sandi minimal 8 karakter',
    'string.max': 'Kata sandi maksimal 72 karakter',
    'string.pattern.name': 'Kata sandi harus mengandung minimal satu {#name}',
    'any.required': 'Kata sandi wajib diisi',
  });

const refreshToken = Joi.string().trim().max(128).required();

export const name = Joi.string().trim().min(3).max(100).required().messages({
  'string.min': 'Nama lengkap minimal 3 karakter',
  'any.required': 'Nama lengkap wajib diisi',
  'string.empty': 'Nama lengkap wajib diisi',
});

export const nrp = Joi.string()
  .trim()
  .pattern(/^\d{6,18}$/)
  .required()
  .messages({ 'string.pattern.base': 'NRP/NIP berupa 6–18 digit angka', 'any.required': 'NRP/NIP wajib diisi' });

// Id dari daftar satuan (GET /units); keberadaannya dicek di service.
export const unitId = Joi.number().integer().positive().required().messages({
  'any.required': 'Satuan wajib dipilih',
  'number.base': 'Satuan wajib dipilih',
  'number.integer': 'Satuan tidak valid',
  'number.positive': 'Satuan tidak valid',
});

export const employmentStatus = Joi.string()
  .valid('TNI', 'PNS')
  .required()
  .messages({ 'any.only': 'Status harus TNI atau PNS', 'any.required': 'Status wajib dipilih' });

export const rank = Joi.string().trim().min(2).max(60).required().messages({
  'string.min': 'Pangkat/golongan wajib dipilih',
  'string.max': 'Pangkat/golongan terlalu panjang',
  'any.required': 'Pangkat/golongan wajib dipilih',
  'string.empty': 'Pangkat/golongan wajib dipilih',
});

export const registerSchema = Joi.object({
  nama: name,
  status_kepegawaian: employmentStatus,
  pangkat: rank,
  // NIP PNS selalu 18 digit; NRP militer 6–18 digit.
  nrp: Joi.when('status_kepegawaian', {
    is: 'PNS',
    then: Joi.string()
      .trim()
      .pattern(/^\d{18}$/)
      .required()
      .messages({ 'string.pattern.base': 'NIP berupa 18 digit angka', 'any.required': 'NIP wajib diisi' }),
    otherwise: nrp,
  }),
  satuan_id: unitId,
  email,
  password: newPassword,
});

// Cek ketersediaan satu kolom per permintaan (stepper pendaftaran memeriksa NRP lalu email).
export const availabilitySchema = Joi.object({ nrp: nrp.optional(), email: email.optional() })
  .xor('nrp', 'email')
  .messages({ 'object.missing': 'Isi NRP/NIP atau email', 'object.xor': 'Periksa NRP/NIP atau email, satu per permintaan' });

export const changePasswordSchema = Joi.object({
  passwordLama: Joi.string().max(72).required().messages({
    'any.required': 'Kata sandi saat ini wajib diisi',
    'string.empty': 'Kata sandi saat ini wajib diisi',
  }),
  passwordBaru: newPassword,
});

export const loginSchema = Joi.object({
  // Saat login cukup dicek panjangnya; format tidak divalidasi agar pesan sama untuk semua kegagalan.
  email: Joi.string().trim().lowercase().max(160).required(),
  password: Joi.string().max(72).required(),
});

export const refreshSchema = Joi.object({ refreshToken });

export const logoutSchema = Joi.object({ refreshToken });

export const forgotPasswordSchema = Joi.object({ email });

export const verifyEmailSchema = Joi.object({ token: Joi.string().trim().max(128).required() });

export const resendVerificationSchema = Joi.object({ email });

export const resetPasswordSchema = Joi.object({
  token: Joi.string().trim().max(128).required(),
  password: newPassword,
});
