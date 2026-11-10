import Joi from 'joi';
import { ROLES } from '../../config/app.js';

export const listUsersSchema = Joi.object({
  page: Joi.number().integer().min(1).default(1),
  limit: Joi.number().integer().valid(10, 25, 50, 100).default(25),
  search: Joi.string().trim().allow('').max(100).default(''),
  // pending = menunggu verifikasi; verified = terverifikasi & aktif; inactive = terverifikasi tapi dinonaktifkan.
  status: Joi.string().valid('pending', 'verified', 'inactive', '').default(''),
});

export const userIdSchema = Joi.object({
  id: Joi.number().integer().positive().required(),
});

export const verifyUserSchema = Joi.object({
  peran: Joi.string()
    .valid(...ROLES)
    .default('pemilik'),
});

export const updateRoleSchema = Joi.object({
  peran: Joi.string()
    .valid(...ROLES)
    .required(),
});

export const updateStatusSchema = Joi.object({
  aktif: Joi.boolean().required(),
});
