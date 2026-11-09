import { success } from '../../utils/response.js';
import * as scanEvents from './scanEvents.js';
import { scansService } from './scans.service.js';

export const scansController = {
  async list(req, res) {
    const data = await scansService.list(req.user, req.query);
    return success(res, { data });
  },

  async get(req, res) {
    const data = await scansService.get(req.user, req.params.id);
    return success(res, { data });
  },

  async mulai(req, res) {
    const data = await scansService.mulai(req.user, req.params.id, {
      mode: req.body?.mode,
      pendekatan: req.body?.pendekatan,
      accounts: req.body?.accounts,
      options: req.body?.options,
      pakaiDiscovery: req.body?.pakai_discovery === true,
      versiSk: req.body?.persetujuan_sk,
    });
    return success(res, { statusCode: 201, message: 'Pengujian dimulai', data });
  },

  async getTarget(req, res) {
    const data = await scansService.getTarget(req.user, req.params.id);
    return success(res, { data });
  },

  async batalkan(req, res) {
    const data = await scansService.batalkan(req.user, req.params.id);
    return success(res, { message: 'Pengujian dibatalkan', data });
  },

  async simpanTarget(req, res) {
    const data = await scansService.simpanTarget(req.user, req.params.id, req.body);
    return success(res, { message: 'Persiapan pengujian disimpan', data });
  },

  /** SSE: aliran EventScan (metode/log/status) untuk satu scan. */
  async events(req, res) {
    const scanId = Number(req.params.id);
    // Pastikan aktor boleh melihat scan ini (lempar 404/403 sebelum membuka aliran).
    await scansService.get(req.user, scanId);

    res.set({
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    });
    res.flushHeaders?.();
    res.write(': terhubung\n\n');

    const kirim = (event) => res.write(`data: ${JSON.stringify(event)}\n\n`);
    const berhenti = scanEvents.berlangganan(scanId, kirim);

    // Ping berkala agar koneksi/proxy tidak menutup aliran saat idle.
    const ping = setInterval(() => res.write(': ping\n\n'), 25_000);

    req.on('close', () => {
      clearInterval(ping);
      berhenti();
    });
  },
};
