import { Router } from 'express';
import { applicationsRouter } from '../features/applications/applications.route.js';
import { authProtectedRouter } from '../features/authentication/authentication.route.js';
import { catalogRouter } from '../features/catalog/catalog.route.js';
import { dashboardRouter } from '../features/dashboard/dashboard.route.js';
import { appsScanRouter, scansRouter } from '../features/scans/scans.route.js';
import { unitsAdminRouter } from '../features/units/units.admin.route.js';
import { usersRouter } from '../features/users/users.route.js';
import { workersRouter } from '../features/workers/workers.route.js';
import { authenticate } from '../middleware/authenticate.js';

const router = Router();

// Semua route di bawah ini wajib membawa access token yang valid dari akun terverifikasi & aktif.
router.use(authenticate);

router.use('/auth', authProtectedRouter);
router.use('/users', usersRouter);
router.use('/admin/units', unitsAdminRouter);
router.use('/applications', applicationsRouter);
router.use('/catalog', catalogRouter);
router.use('/scans', scansRouter);
router.use('/workers', workersRouter);
router.use('/dashboard', dashboardRouter);
// POST /apps/:id/scans & PUT /apps/:id/scan-target (kontrak frontend memakai /apps, bukan /applications).
router.use('/apps', appsScanRouter);

export default router;
