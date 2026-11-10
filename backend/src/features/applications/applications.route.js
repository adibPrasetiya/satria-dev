import { Router } from 'express';
import { requireRole } from '../../middleware/requireRole.js';
import { validate } from '../../middleware/validate.js';
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
