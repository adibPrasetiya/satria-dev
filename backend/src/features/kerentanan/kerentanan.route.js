import { Router } from 'express';
import { requireRole } from '../../middleware/requireRole.js';
import { validate } from '../../middleware/validate.js';
import { kerentananController } from './kerentanan.controller.js';
import { kerentananIdSchema, listKerentananSchema, ubahStatusSchema } from './kerentanan.validation.js';

// Intel kerentanan (CVE ↔ aset). Semua peran melihat aset dalam cakupannya (pemilik: satuannya);
// menandai ditangani/dikecualikan oleh pemilik aset, asesor, atau admin; sinkron manual hanya admin.
export const kerentananRouter = Router();

kerentananRouter.get('/', validate(listKerentananSchema, 'query'), kerentananController.list);
kerentananRouter.get('/ringkasan', kerentananController.ringkasan);
kerentananRouter.get('/sinkron', requireRole('asesor', 'admin'), kerentananController.statusSinkron);
kerentananRouter.post('/sinkron', requireRole('admin'), kerentananController.sinkron);
kerentananRouter.patch(
  '/:id/status',
  validate(kerentananIdSchema, 'params'),
  validate(ubahStatusSchema),
  kerentananController.ubahStatus,
);
