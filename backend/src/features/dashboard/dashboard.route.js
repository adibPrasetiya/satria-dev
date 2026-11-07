import { Router } from 'express';
import { success } from '../../utils/response.js';
import { dashboardService } from './dashboard.service.js';

// Dasbor: data agregat (tanpa nama aplikasi) untuk semua pengguna login.
export const dashboardRouter = Router();

// GET /dashboard/peta — titik satuan berlokasi + kekuatan & kerentanan; frontend memuat ulang tiap 10 menit.
dashboardRouter.get('/peta', async (req, res) => {
  const data = await dashboardService.peta();
  return success(res, { message: 'Peta indeks ketahanan', data });
});
