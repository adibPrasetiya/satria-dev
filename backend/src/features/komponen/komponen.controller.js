import { success } from '../../utils/response.js';
import { komponenService } from './komponen.service.js';

export const komponenController = {
  async list(req, res) {
    const data = await komponenService.list(req.user, req.params.id);
    return success(res, { data });
  },

  async tambah(req, res) {
    const data = await komponenService.tambahManual(req.user, req.params.id, req.body);
    return success(res, { statusCode: 201, message: 'Komponen disimpan', data });
  },

  async hapus(req, res) {
    const data = await komponenService.hapus(req.user, req.params.id, req.params.komponenId);
    return success(res, { message: 'Komponen dihapus', data });
  },
};
