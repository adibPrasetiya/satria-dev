// Pencocokan ulang otomatis saat komponen aset berubah (formulir, koreksi manual, hasil recon).
import { env } from '../../config/env.js';
import { logger } from '../../utils/logger.js';
import { peristiwaKomponen } from '../komponen/komponen.events.js';
import { intelService } from './intel.service.js';
import { kerentananService } from './kerentanan.service.js';

const JEDA_COCOK_MS = 2_000;
// Produk baru perlu riwayat CVE dari NVD dulu; ditunda agar beberapa perubahan beruntun cukup satu sinkron.
const JEDA_SINKRON_MS = 30_000;

/** Dipasang sekali saat server start. */
export function pasangLanggananKomponen({ cocok = kerentananService, intel = intelService, peristiwa = peristiwaKomponen } = {}) {
  const tertunda = new Map();
  let timerSinkron = null;

  peristiwa.on('berubah', (applicationId) => {
    clearTimeout(tertunda.get(applicationId));
    const timer = setTimeout(() => {
      tertunda.delete(applicationId);
      cocok
        .cocokkanAplikasi(applicationId)
        .catch((error) => logger.warn('Pencocokan CVE aplikasi gagal', { aplikasiId: applicationId, error: error.message }));
    }, JEDA_COCOK_MS);
    timer.unref();
    tertunda.set(applicationId, timer);

    if (!env.cve.syncEnabled) return;
    clearTimeout(timerSinkron);
    timerSinkron = setTimeout(() => {
      intel.sinkron({ ringan: true }).catch((error) => logger.warn(`[intel CVE] sinkron ringan gagal: ${error.message}`));
    }, JEDA_SINKRON_MS);
    timerSinkron.unref();
  });
}
