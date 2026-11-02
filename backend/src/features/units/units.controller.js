import { success } from '../../utils/response.js';
import { unitsService } from './units.service.js';

export const unitsController = {
  async list(req, res) {
    const data = await unitsService.search(req.query);
    return success(res, { data });
  },
};
