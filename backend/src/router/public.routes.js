import { Router } from 'express';
import { authPublicRouter } from '../features/authentication/authentication.route.js';
import { evidencePublicRouter } from '../features/evidence/evidence.route.js';
import { unitsRouter } from '../features/units/units.route.js';

const router = Router();

router.use('/auth', authPublicRouter);
router.use('/units', unitsRouter);
// Bukti gambar disajikan via capability URL (tanpa JWT) agar dapat dimuat <img>.
router.use('/evidence', evidencePublicRouter);

export default router;
