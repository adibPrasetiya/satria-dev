import { success } from '../../utils/response.js';
import { catalogService } from './catalog.service.js';

export const catalogController = {
  async get(req, res) {
    const data = await catalogService.getCatalog();
    return success(res, { data });
  },

  async createControl(req, res) {
    const data = await catalogService.createControl(req.params.kode, req.body);
    return success(res, { statusCode: 201, message: `Kontrol ${data.id} ditambahkan`, data });
  },

  async updateControl(req, res) {
    const data = await catalogService.updateControl(req.params.kode, req.body);
    return success(res, { message: `Kontrol ${data.id} diperbarui`, data });
  },

  async createMethod(req, res) {
    const data = await catalogService.createMethod(req.params.kode, req.body);
    return success(res, { statusCode: 201, message: `Metode ${data.id} ditambahkan`, data });
  },

  async updateMethod(req, res) {
    const data = await catalogService.updateMethod(req.params.kode, req.body);
    return success(res, { message: `Metode ${data.id} diperbarui`, data });
  },
};
