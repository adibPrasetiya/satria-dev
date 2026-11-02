import { success } from '../../utils/response.js';
import { applicationsService } from './applications.service.js';

export const applicationsController = {
  async list(req, res) {
    const data = await applicationsService.list(req.user, req.query);
    return success(res, { data });
  },

  async get(req, res) {
    const data = await applicationsService.get(req.user, req.params.id);
    return success(res, { data });
  },

  async create(req, res) {
    const data = await applicationsService.create(req.user, req.body);
    return success(res, { statusCode: 201, message: `Aplikasi "${data.nama}" terdaftar`, data });
  },

  async update(req, res) {
    const data = await applicationsService.update(req.user, req.params.id, req.body);
    return success(res, { message: 'Data aplikasi diperbarui', data });
  },
};
