import { Router } from 'express';
import { requireRole } from '../../middleware/requireRole.js';
import { validate } from '../../middleware/validate.js';
import { scansController } from './scans.controller.js';
import { laporanAiLimiter } from '../../middleware/rateLimiter.js';
import { laporanController } from '../laporan/laporan.controller.js';
import { appIdSchema, listScansSchema, mulaiScanSchema, saveTargetSchema, scanIdSchema } from './scans.validation.js';

// Endpoint di bawah /scans (semua perlu login; dipasang di protected.routes.js).
// Melihat hasil & laporan: semua peran (pemilik terbatas satuannya); menghentikan: asesor/admin.
export const scansRouter = Router();
scansRouter.get('/', validate(listScansSchema, 'query'), scansController.list);
scansRouter.get('/:id', validate(scanIdSchema, 'params'), scansController.get);
scansRouter.get('/:id/events', validate(scanIdSchema, 'params'), scansController.events);
scansRouter.post('/:id/cancel', requireRole('asesor', 'admin'), validate(scanIdSchema, 'params'), scansController.batalkan);
// Laporan AI (ringkasan eksekutif + rekomendasi temuan); hanya riwayat terakhir yang disimpan.
scansRouter.post('/:id/ai', laporanAiLimiter, validate(scanIdSchema, 'params'), laporanController.generate);

// Endpoint di bawah /apps/:id (mulai scan & persiapan uji): asesor/admin — pemilik hanya melihat hasil.
export const appsScanRouter = Router();
appsScanRouter.post(
  '/:id/scans',
  requireRole('asesor', 'admin'),
  validate(appIdSchema, 'params'),
  validate(mulaiScanSchema),
  scansController.mulai,
);
appsScanRouter.get(
  '/:id/scan-target',
  requireRole('asesor', 'admin'),
  validate(appIdSchema, 'params'),
  scansController.getTarget,
);
appsScanRouter.put(
  '/:id/scan-target',
  requireRole('asesor', 'admin'),
  validate(appIdSchema, 'params'),
  validate(saveTargetSchema),
  scansController.simpanTarget,
);
