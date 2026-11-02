import { Router } from 'express';
import { requireRole } from '../../middleware/requireRole.js';
import { validate } from '../../middleware/validate.js';
import { catalogController } from './catalog.controller.js';
import {
  codeParamSchema,
  createControlSchema,
  createMethodSchema,
  updateControlSchema,
  updateMethodSchema,
} from './catalog.validation.js';

// Katalog kontrol: semua peran membaca; hanya admin yang menambah/mengubah kontrol & metode pengujian.
export const catalogRouter = Router();

const admin = requireRole('admin');
const kode = validate(codeParamSchema, 'params');

catalogRouter.get('/', catalogController.get);
catalogRouter.post('/functions/:kode/controls', admin, kode, validate(createControlSchema), catalogController.createControl);
catalogRouter.patch('/controls/:kode', admin, kode, validate(updateControlSchema), catalogController.updateControl);
catalogRouter.post('/controls/:kode/methods', admin, kode, validate(createMethodSchema), catalogController.createMethod);
catalogRouter.patch('/methods/:kode', admin, kode, validate(updateMethodSchema), catalogController.updateMethod);
