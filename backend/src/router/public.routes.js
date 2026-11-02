import { Router } from 'express';
import { authPublicRouter } from '../features/authentication/authentication.route.js';
import { unitsRouter } from '../features/units/units.route.js';

const router = Router();

router.use('/auth', authPublicRouter);
router.use('/units', unitsRouter);

export default router;
