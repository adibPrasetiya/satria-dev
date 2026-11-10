import { success } from '../../utils/response.js';
import { internalService } from './internal.service.js';
import { workersService } from '../workers/workers.service.js';
import { simpanGambar } from '../evidence/evidence.service.js';

export const internalController = {
  async claim(req, res) {
    const data = await internalService.claim({
      workerId: req.body.worker_id ?? 'worker',
      engines: req.body.engines?.length ? req.body.engines : ['custom'],
    });
    if (!data) return res.status(204).end();
    return success(res, { message: 'Task diklaim', data });
  },

  async heartbeat(req, res) {
    const data = await workersService.heartbeat(req.body);
    return success(res, { message: 'Heartbeat diterima', data });
  },

  async berhenti(req, res) {
    await workersService.berhenti(req.body.worker_id);
    return success(res, { message: 'Worker ditandai berhenti' });
  },

  async result(req, res) {
    await internalService.result(req.params.id, req.body.hasil ?? req.body);
    return success(res, { message: 'Hasil diterima' });
  },

  async log(req, res) {
    // `data` = peristiwa penemuan terstruktur (graf visualisasi); tanpa ini UI hanya menerima teks log.
    await internalService.log(req.params.id, { level: req.body.level ?? 'info', pesan: req.body.pesan ?? '', data: req.body.data ?? null });
    return success(res, { message: 'Log diterima' });
  },

  async discovery(req, res) {
    const data = await internalService.discovery(req.params.id, req.body);
    return success(res, { message: 'Penemuan diterima', data });
  },

  async evidence(req, res) {
    const data = await simpanGambar(req.params.id, req.body.gambar);
    return success(res, { message: 'Bukti gambar disimpan', data });
  },
};
