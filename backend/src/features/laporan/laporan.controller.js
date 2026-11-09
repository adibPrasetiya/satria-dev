import { success } from '../../utils/response.js';
import { laporanService } from './laporan.service.js';

export const laporanController = {
  /** Generate laporan AI untuk satu pengujian (disimpan hanya bila riwayat terakhir). */
  async generate(req, res) {
    const data = await laporanService.generate(req.user, req.params.id);
    return success(res, {
      message: data.ai?.disimpan ? 'Laporan disusun & disimpan' : 'Laporan disusun (tidak disimpan: bukan riwayat terakhir)',
      data,
    });
  },
};
