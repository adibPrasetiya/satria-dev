import { Router } from 'express';
import Joi from 'joi';
import { validate } from '../../middleware/validate.js';
import { success } from '../../utils/response.js';
import { dashboardService } from './dashboard.service.js';

// Dasbor: data agregat (tanpa nama aplikasi) untuk semua pengguna login.
export const dashboardRouter = Router();

// GET /dashboard/peta — ringkas: titik satuan berlokasi + indeks + sebaran severity nasional.
// Frontend memuat ulang tiap 10 menit; `versi` berubah bila data berubah.
dashboardRouter.get('/peta', async (req, res) => {
  const data = await dashboardService.peta();
  return success(res, { message: 'Peta indeks ketahanan', data });
});

// GET /dashboard/peta/provinsi/:kode — rincian satu provinsi, diambil per provinsi saat disorot.
const kodeProvinsiSchema = Joi.object({
  kode: Joi.string()
    .pattern(/^\d{2}$/)
    .required()
    .messages({ 'string.pattern.base': 'Kode provinsi tidak valid' }),
});
dashboardRouter.get('/peta/provinsi/:kode', validate(kodeProvinsiSchema, 'params'), async (req, res) => {
  const data = await dashboardService.provinsi(req.params.kode);
  return success(res, { message: 'Rincian provinsi', data });
});
