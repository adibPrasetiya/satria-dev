import { logger } from '../../utils/logger.js';
import * as workerEvents from './workerEvents.js';
import { workersService } from './workers.service.js';

// Hub SSE status worker: menggantikan polling GET /workers/status dari tiap tab browser.
// - Satu snapshot DB per perubahan, dipakai bersama semua pelanggan (bukan satu query per tab).
// - Dikirim ke pelanggan hanya bila isinya berbeda dari kiriman terakhirnya.
// - Pemeriksaan berkala ringan selama ada pelanggan, untuk menangkap worker yang mati diam-diam
//   (heartbeat berhenti tanpa sinyal apa pun → statusnya baru berubah menjadi "terputus" setelah timeout).

const PERIKSA_MS = 15_000;
const PING_MS = 25_000;

/** Umur heartbeat berubah tiap detik; tidak dihitung sebagai "perubahan" agar tidak memicu kiriman. */
const sidik = (status) =>
  JSON.stringify(status, (k, v) => (k === 'terakhir_terlihat_detik' ? undefined : v));

export function createWorkerStatusHub({ service = workersService, events = workerEvents, periksaMs = PERIKSA_MS } = {}) {
  /** @type {Set<{ actor: object, kirim: (data: object) => void, terakhir: string | null }>} */
  const pelanggan = new Set();
  let berhenti = null;
  let timer = null;
  let berjalan = null;
  let ulang = false;

  async function siarkan() {
    // Satu penghitungan dalam satu waktu; sinyal yang datang selama menghitung memicu satu putaran lagi.
    if (berjalan) {
      ulang = true;
      return berjalan;
    }
    berjalan = (async () => {
      do {
        ulang = false;
        if (!pelanggan.size) break;
        try {
          const snap = await service.snapshot();
          for (const p of pelanggan) kirimBilaBerubah(p, service.statusDari(snap, p.actor));
        } catch (error) {
          logger.warn(`Gagal menyiarkan status worker: ${error.message}`);
        }
      } while (ulang);
    })().finally(() => {
      berjalan = null;
    });
    return berjalan;
  }

  function kirimBilaBerubah(p, status) {
    const s = sidik(status);
    if (s === p.terakhir) return;
    p.terakhir = s;
    p.kirim(status);
  }

  function mulai() {
    berhenti = events.berlangganan(() => void siarkan());
    timer = setInterval(() => void siarkan(), periksaMs);
    timer.unref?.();
  }

  function selesai() {
    berhenti?.();
    clearInterval(timer);
    berhenti = timer = null;
  }

  return {
    /** Daftarkan pelanggan; status awal langsung dikirim. @returns fungsi berhenti */
    async gabung(actor, kirim) {
      const p = { actor, kirim, terakhir: null };
      pelanggan.add(p);
      if (pelanggan.size === 1) mulai();
      kirimBilaBerubah(p, await service.status(actor));
      return () => {
        pelanggan.delete(p);
        if (!pelanggan.size) selesai();
      };
    },
    get jumlah() {
      return pelanggan.size;
    },
    siarkan,
  };
}

export const workerStatusHub = createWorkerStatusHub();

/** Handler Express: GET /workers/status/stream (SSE). */
export async function streamStatus(req, res) {
  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.flushHeaders?.();
  res.write(': terhubung\n\n');

  let tutup = false;
  let keluar = () => {};
  const mulaiPada = Date.now();
  // Ping berkala agar koneksi/proxy tidak menutup aliran saat tidak ada perubahan.
  const ping = setInterval(() => res.write(': ping\n\n'), PING_MS);
  req.on('close', () => {
    tutup = true;
    clearInterval(ping);
    keluar();
    // Aliran SSE tidak pernah "finish", jadi requestLogger tidak mencatatnya; catat satu baris saat ditutup.
    logger.http(`SSE status worker ditutup setelah ${Math.round((Date.now() - mulaiPada) / 1000)} dtk (${workerStatusHub.jumlah} aktif)`);
  });

  try {
    const lepas = await workerStatusHub.gabung(req.user, (data) => res.write(`data: ${JSON.stringify(data)}\n\n`));
    if (tutup) lepas();
    else {
      keluar = lepas;
      logger.http(`SSE status worker dibuka (${workerStatusHub.jumlah} aktif)`);
    }
  } catch (error) {
    logger.warn(`Gagal membuka aliran status worker: ${error.message}`);
    clearInterval(ping);
    res.end();
  }
}
