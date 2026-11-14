import { logger } from '../../utils/logger.js';
import { success } from '../../utils/response.js';
import { intelService } from './intel.service.js';
import { kerentananService } from './kerentanan.service.js';

export const kerentananController = {
  async list(req, res) {
    const data = await kerentananService.list(req.user, req.query);
    return success(res, { data });
  },

  async ringkasan(req, res) {
    const data = await kerentananService.ringkasan(req.user);
    return success(res, { data });
  },

  async ubahStatus(req, res) {
    const data = await kerentananService.ubahStatus(req.user, req.params.id, req.body);
    return success(res, { message: 'Status kerentanan diperbarui', data });
  },

  async statusSinkron(req, res) {
    const data = await intelService.status();
    return success(res, { data });
  },

  /** Sinkron berjalan di latar (bisa beberapa menit); UI memantau lewat GET /kerentanan/sinkron. */
  async sinkron(req, res) {
    intelService
      .sinkron({ paksa: true })
      .then((hasil) => {
        if (hasil === null) logger.info('[intel CVE] sinkron manual dilewati: sinkron lain sedang berjalan');
      })
      .catch((error) => logger.error(`[intel CVE] sinkron manual gagal: ${error.message}`));
    return success(res, { statusCode: 202, message: 'Sinkron intel kerentanan dimulai', data: null });
  },
};
