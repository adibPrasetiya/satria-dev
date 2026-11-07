import { env } from '../../config/env.js';
import { AppError } from '../../utils/AppError.js';
import * as workerEvents from './workerEvents.js';
import { workersRepository } from './workers.repository.js';

const seesAll = (actor) => actor.peran === 'asesor' || actor.peran === 'admin';

// Perkiraan durasi task bila belum ada riwayat (ms).
const DURASI_BAWAAN = { discovery: 240_000, playwright: 30_000, zap: 120_000, custom: 6_000 };

/** Worker aktif = belum berhenti & heartbeat masih dalam jendela timeout. */
export function aktif(w, timeoutMs = env.worker.heartbeatTimeoutMs) {
  return w.status !== 'berhenti' && Number(w.umurDetik) * 1000 <= timeoutMs;
}

/**
 * Hitung posisi & perkiraan tunggu dari daftar task aktif (urut klaim).
 * - `scanId` diberikan → untuk scan itu (task milik scan lain yang lebih dulu dihitung "di depan").
 * - tanpa `scanId` → untuk scan BARU (semua task aktif ada di depan).
 */
export function hitungAntrean(tasks, { scanId = null, rata = {}, nAktif = 0 } = {}) {
  const durasi = (engine) => rata[engine] ?? DURASI_BAWAAN[engine] ?? 10_000;
  const milik = scanId == null ? [] : tasks.filter((t) => Number(t.scanId) === Number(scanId));
  const sedangDikerjakan = milik.some((t) => t.status === 'berjalan');
  const pertamaAntre = milik.filter((t) => t.status === 'antre').reduce((m, t) => Math.min(m, Number(t.id)), Infinity);
  const batas = scanId == null ? Infinity : pertamaAntre;
  const depan = tasks.filter((t) => Number(t.scanId) !== Number(scanId) && Number(t.id) < batas);
  const scanDepan = new Set(depan.map((t) => Number(t.scanId)));
  // Task yang sedang berjalan diperkirakan tinggal separuh durasinya.
  const totalMs = depan.reduce((s, t) => s + durasi(t.engine) * (t.status === 'berjalan' ? 0.5 : 1), 0);
  return {
    posisi: sedangDikerjakan ? 0 : scanDepan.size + 1,
    di_depan: depan.length,
    scan_di_depan: scanDepan.size,
    sedang_dikerjakan: sedangDikerjakan,
    perkiraan_tunggu_detik: sedangDikerjakan ? 0 : Math.round(totalMs / Math.max(1, nAktif) / 1000),
    worker_aktif: nAktif,
  };
}

export function createWorkersService({
  repository = workersRepository,
  timeoutMs = env.worker.heartbeatTimeoutMs,
  events = workerEvents,
} = {}) {
  /** Heartbeat worker: perbarui registry & lease task; balas sinyal pembatalan. */
  async function heartbeat({ worker_id: id, engines = [], status = 'siaga', task_id: taskId = null, tahap = null, versi = null, host = null }) {
    let scanId = null;
    let batalkan = false;
    if (taskId) {
      await repository.perpanjangLease(taskId, id);
      const s = await repository.scanUntukTask(taskId);
      scanId = s?.scanId ?? null;
      batalkan = s?.scanStatus === 'dibatalkan';
    }
    await repository.upsert({ id, engines, status: taskId ? 'sibuk' : status === 'berhenti' ? 'berhenti' : 'siaga', taskId, scanId, tahap, versi, host });
    // Heartbeat datang tiap ±10 dtk per worker; hub SSE hanya mengirim bila isinya benar-benar berubah.
    events.beriTahu();
    return { batalkan };
  }

  async function berhenti(id) {
    await repository.setStatus(id, 'berhenti');
    events.beriTahu();
    return { ok: true };
  }

  /** Dicatat saat worker mengklaim / menyelesaikan task (status tampil segera tanpa menunggu heartbeat). */
  async function catatKlaim(id, engines, task) {
    await repository.upsert({ id, engines, status: 'sibuk', taskId: task.id, scanId: task.scanId, tahap: task.methodCode });
    events.beriTahu();
  }
  async function catatSelesai(id) {
    if (id) await repository.setStatus(id, 'siaga');
    events.beriTahu();
  }

  async function _snapshot() {
    const [daftar, tasks, rata] = await Promise.all([repository.daftar(), repository.taskAktif(), repository.rataDurasi()]);
    const hidup = daftar.filter((w) => aktif(w, timeoutMs));
    return { daftar, hidup, tasks, rata };
  }

  /** Ringkasan status untuk header & wizard (nama aplikasi satuan lain disamarkan bagi pemilik). */
  async function status(actor) {
    return statusDari(await _snapshot(), actor);
  }

  /** Status dari snapshot yang sudah diambil — hub SSE memakai satu snapshot untuk semua pelanggan. */
  function statusDari({ daftar, hidup, tasks, rata }, actor) {
    const boleh = (unitId) => !actor || seesAll(actor) || String(unitId) === String(actor.satuan_id);
    const scanMenunggu = [];
    const sudah = new Set();
    for (const t of tasks) {
      const sid = Number(t.scanId);
      if (sudah.has(sid)) continue;
      sudah.add(sid);
      const a = hitungAntrean(tasks, { scanId: sid, rata, nAktif: hidup.length });
      scanMenunggu.push({ scan_id: String(sid), aplikasi: boleh(t.unitId) ? t.aplikasi : 'Aplikasi satuan lain', ...a });
    }
    return {
      aktif: hidup.length,
      sibuk: hidup.filter((w) => w.status === 'sibuk').length,
      siaga: hidup.filter((w) => w.status === 'siaga').length,
      engines: [...new Set(hidup.flatMap((w) => w.engines))],
      workers: daftar.map((w) => ({
        id: w.id,
        status: aktif(w, timeoutMs) ? w.status : 'terputus',
        engines: w.engines,
        versi: w.versi,
        terakhir_terlihat_detik: Number(w.umurDetik),
        sedang: w.taskId && aktif(w, timeoutMs)
          ? { scan_id: w.scanId ? String(w.scanId) : null, aplikasi: boleh(w.unitId) ? w.aplikasi : 'Aplikasi satuan lain', tahap: w.tahap }
          : null,
      })),
      antrean: { task_antre: tasks.filter((t) => t.status === 'antre').length, task_berjalan: tasks.filter((t) => t.status === 'berjalan').length, scan: scanMenunggu },
      scan_baru: hitungAntrean(tasks, { rata, nAktif: hidup.length }),
    };
  }

  /** Posisi antrean & worker yang mengerjakan satu scan (dilampirkan pada DTO scan). */
  async function antreanScan(scanId) {
    const { hidup, tasks, rata } = await _snapshot();
    const a = hitungAntrean(tasks, { scanId, rata, nAktif: hidup.length });
    const w = hidup.find((x) => Number(x.scanId) === Number(scanId) && x.status === 'sibuk');
    return { ...a, worker: w ? { id: w.id, tahap: w.tahap, terakhir_terlihat_detik: Number(w.umurDetik) } : null };
  }

  /**
   * Penjaga sebelum membuat scan: (1) satu pengujian aktif per aplikasi; (2) harus ada worker aktif
   * yang mendukung engine yang dibutuhkan. Worker sibuk tetap boleh (scan masuk antrean).
   */
  async function gerbangMulai(applicationId, engine) {
    const aktifId = await repository.scanAktifAplikasi(applicationId);
    if (aktifId) {
      throw new AppError(409, 'Aplikasi ini masih memiliki pengujian yang berjalan atau mengantre.', { scan_id: String(aktifId) }, 'SCAN_AKTIF');
    }
    const { hidup } = await _snapshot();
    if (!hidup.some((w) => w.engines.includes(engine))) {
      throw new AppError(
        409,
        hidup.length
          ? `Tidak ada worker aktif yang mendukung engine "${engine}".`
          : 'Tidak ada worker pengujian yang aktif. Nyalakan worker lalu coba lagi.',
        { engine, worker_aktif: hidup.length },
        'WORKER_TIDAK_AKTIF',
      );
    }
  }

  return { heartbeat, berhenti, catatKlaim, catatSelesai, status, statusDari, snapshot: _snapshot, antreanScan, gerbangMulai };
}

export const workersService = createWorkersService();
