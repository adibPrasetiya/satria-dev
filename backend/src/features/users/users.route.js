import { Router } from 'express';
import { requireRole } from '../../middleware/requireRole.js';
import { validate } from '../../middleware/validate.js';
import { usersController } from './users.controller.js';
import { listUsersSchema, updateRoleSchema, updateStatusSchema, userIdSchema, verifyUserSchema } from './users.validation.js';

// Pengelolaan pengguna & verifikasi pendaftaran: khusus administrator.
export const usersRouter = Router();

usersRouter.use(requireRole('admin'));

usersRouter.get('/', validate(listUsersSchema, 'query'), usersController.list);
usersRouter.patch('/:id/verify', validate(userIdSchema, 'params'), validate(verifyUserSchema), usersController.verify);
usersRouter.patch('/:id/role', validate(userIdSchema, 'params'), validate(updateRoleSchema), usersController.setRole);
usersRouter.patch('/:id/status', validate(userIdSchema, 'params'), validate(updateStatusSchema), usersController.setStatus);
usersRouter.delete('/:id', validate(userIdSchema, 'params'), usersController.reject);
