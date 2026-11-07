import { Router } from 'express';
import { requireRole } from '../../middleware/requireRole.js';
import { validate } from '../../middleware/validate.js';
import { unitsAdminController } from './units.admin.controller.js';
import { createUnitSchema, listUnitsAdminSchema, unitIdSchema, updateUnitSchema } from './units.validation.js';

// Pengelolaan daftar satuan kerja: khusus administrator. Terpisah dari GET /units (publik, untuk pendaftaran).
export const unitsAdminRouter = Router();

unitsAdminRouter.use(requireRole('admin'));

unitsAdminRouter.get('/', validate(listUnitsAdminSchema, 'query'), unitsAdminController.list);
unitsAdminRouter.get('/:id', validate(unitIdSchema, 'params'), unitsAdminController.get);
unitsAdminRouter.post('/', validate(createUnitSchema), unitsAdminController.create);
unitsAdminRouter.patch('/:id', validate(unitIdSchema, 'params'), validate(updateUnitSchema), unitsAdminController.update);
