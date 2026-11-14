import { Router } from 'express';
import { requireRole } from '../../middleware/requireRole.js';
import { validate } from '../../middleware/validate.js';
import { komponenController } from '../komponen/komponen.controller.js';
import { komponenParamsSchema, tambahKomponenSchema } from '../komponen/komponen.validation.js';
import { applicationsController } from './applications.controller.js';
import {
  applicationIdSchema,
  createApplicationSchema,
  listApplicationsSchema,
  updateApplicationSchema,
} from './applications.validation.js';

// Aset aplikasi: semua peran bisa melihat (pemilik terbatas satuannya); mendaftar, mengubah, dan
// mengarsipkan hanya pemilik/admin. Tidak ada hapus permanen — aset diarsipkan agar riwayat tetap utuh.
export const applicationsRouter = Router();

applicationsRouter.get('/', validate(listApplicationsSchema, 'query'), applicationsController.list);
applicationsRouter.get('/:id', validate(applicationIdSchema, 'params'), applicationsController.get);
applicationsRouter.post('/', requireRole('pemilik', 'admin'), validate(createApplicationSchema), applicationsController.create);
applicationsRouter.patch(
  '/:id',
  requireRole('pemilik', 'admin'),
  validate(applicationIdSchema, 'params'),
  validate(updateApplicationSchema),
  applicationsController.update,
);
applicationsRouter.post(
  '/:id/arsip',
  requireRole('pemilik', 'admin'),
  validate(applicationIdSchema, 'params'),
  applicationsController.arsipkan,
);
applicationsRouter.post(
  '/:id/pulihkan',
  requireRole('pemilik', 'admin'),
  validate(applicationIdSchema, 'params'),
  applicationsController.pulihkan,
);

// Inventaris komponen (dasar pencocokan CVE): semua peran dapat melihat aset yang terlihat olehnya; koreksi manual
// oleh pemilik (aset satuannya), asesor, atau admin.
applicationsRouter.get('/:id/komponen', validate(applicationIdSchema, 'params'), komponenController.list);
applicationsRouter.post(
  '/:id/komponen',
  validate(applicationIdSchema, 'params'),
  validate(tambahKomponenSchema),
  komponenController.tambah,
);
applicationsRouter.delete('/:id/komponen/:komponenId', validate(komponenParamsSchema, 'params'), komponenController.hapus);
