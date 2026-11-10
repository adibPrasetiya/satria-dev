import { Router } from 'express';
import Joi from 'joi';
import { validate } from '../../middleware/validate.js';
import { sajikanGambar } from './evidence.service.js';

// Penyajian bukti gambar (PNG) — PUBLIK (capability URL): nama berkas acak 32-hex tak tertebak.
// Tanpa auth JWT agar dapat dimuat tag <img> (Bearer token tak bisa dikirim <img>). Dipasang di
// public.routes.js SEBELUM middleware authenticate.
export const evidencePublicRouter = Router();

const paramSchema = Joi.object({
  scanId: Joi.number().integer().positive().required(),
  file: Joi.string()
    .pattern(/^[0-9a-f]{32}\.png$/)
    .required(),
});

evidencePublicRouter.get('/:scanId/:file', validate(paramSchema, 'params'), async (req, res, next) => {
  try {
    await sajikanGambar(req.params.scanId, req.params.file, res);
  } catch (err) {
    next(err);
  }
});
