import { success } from '../../utils/response.js';
import { unitsService } from './units.service.js';

export const unitsAdminController = {
  async list(req, res) {
    const data = await unitsService.listAdmin(req.query);
    return success(res, { data });
  },

  async create(req, res) {
    const data = await unitsService.create(req.body);
    return success(res, { statusCode: 201, message: `Satuan "${data.nama}" ditambahkan`, data });
  },

  async update(req, res) {
    const data = await unitsService.update(req.params.id, req.body);
    return success(res, { message: 'Satuan diperbarui', data });
  },
};
