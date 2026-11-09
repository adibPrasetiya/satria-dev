import { env } from '../../config/env.js';
import { AppError } from '../../utils/AppError.js';
import { buildContext, buildMetodeSpec } from '../scans/context.js';
import * as scanEvents from '../scans/scanEvents.js';
import { scansRepository } from '../scans/scans.repository.js';
import { scansService } from '../scans/scans.service.js';
import { applicationsRepository } from '../applications/applications.repository.js';
import { workersService } from '../workers/workers.service.js';

// Batas ukuran peristiwa terstruktur pada log (worker mengirim batch kecil).
const MAKS_DATA_LOG = 64_000;

/** Format Date -> 'YYYY-MM-DD HH:MM:SS' UTC (dibandingkan dengan locked_at di MySQL, zona +00:00). */
function mysqlUtc(date) {
  return date.toISOString().slice(0, 19).replace('T', ' ');
}

export function createInternalService({
  repository = scansRepository,
  applications = applicationsRepository,
  scans = scansService,
  events = scanEvents,
  workers = workersService,
} = {}) {
  /**
   * Klaim satu task antre untuk worker. Mengembalikan spec metode + context,
   * atau null bila tak ada pekerjaan.
   */
  async function claim({ workerId, engines }) {
    // Kembalikan dulu task yang macet (worker mati) ke antrean.
    // Lease diperpanjang heartbeat worker; lease kedaluwarsa = worker mati.
    const staleBefore = mysqlUtc(new Date(Date.now() - env.worker.taskTimeoutMs));
    const { dikembalikan, dihentikan } = await repository.requeueStale(staleBefore, env.worker.maksPercobaan);
    for (const t of dikembalikan) {
      const pesan = `Worker ${t.lockedBy ?? '?'} terputus saat menjalankan ${t.methodCode}; task dikembalikan ke antrean.`;
      await repository.insertLog(t.scanId, 'peringatan', pesan);
      events.siarkan(t.scanId, { tipe: 'log', log: { waktu: new Date().toISOString(), level: 'peringatan', pesan } });
      events.siarkan(t.scanId, { tipe: 'worker', peristiwa: 'terputus', worker_id: t.lockedBy, metode_id: t.methodCode });
    }
    for (const t of dihentikan) {
      const pesan = `${t.methodCode}: dihentikan — worker berulang kali terputus (${t.attempts} percobaan).`;
      await repository.insertLog(t.scanId, 'peringatan', pesan);
      events.siarkan(t.scanId, { tipe: 'metode', hasil: { metode_id: t.methodCode, status: 'tidak_dapat_diverifikasi', ringkasan: pesan, bukti: [] } });
      await scans.finalizeIfDone(t.scanId);
    }

    const task = await repository.claimNextTask({ engines, workerId });
    if (!task) {
      await workers.catatSelesai(workerId).catch(() => {});
      return null;
    }
    await workers.catatKlaim(workerId, engines, task).catch(() => {});
    events.siarkan(task.scanId, { tipe: 'worker', peristiwa: 'diklaim', worker_id: workerId, metode_id: task.methodCode });

    const scan = await repository.findScanById(task.scanId);

    // Task penemuan (mode eksploratif): spec sintetis, tak ada entri katalog.
    if (task.engine === 'discovery') {
      if (!scan) {
        await repository.completeTask(task.id, {
          result: { metode_id: task.methodCode, status: 'tidak_dapat_diverifikasi', ringkasan: 'Scan tidak ditemukan.', bukti: [] },
          durationMs: 0,
        });
        return null;
      }
      const application = await applications.findById(scan.applicationId);
      // Sertakan target agar akun uji (+ totp_secret) & opsi ikut mengalir ke fase penemuan
      // — memungkinkan penemuan endpoint di balik autentikasi.
      const discoveryTarget = await repository.getTarget(scan.applicationId);
      events.siarkan(scan.id, { tipe: 'log', log: { waktu: new Date().toISOString(), level: 'info', pesan: 'Fase penemuan berjalan…' } });
      return {
        task_id: String(task.id),
        scan_id: String(scan.id),
        metode: { id: task.methodCode, check_id: task.checkId, titik_uji: 'global', engine: 'discovery', nama: 'Penemuan otomatis' },
        context: buildContext({ scan, application, target: discoveryTarget }),
      };
    }

    const mc = await repository.methodWithControl(task.methodCode);
    if (!mc || !scan) {
      // Data katalog/scan hilang; tandai task selesai agar tidak macet.
      await repository.completeTask(task.id, {
        result: { metode_id: task.methodCode, status: 'tidak_dapat_diverifikasi', ringkasan: 'Metode tidak ditemukan di katalog.', bukti: [] },
        durationMs: 0,
      });
      await scans.finalizeIfDone(task.scanId);
      return null;
    }

    const application = await applications.findById(scan.applicationId);
    const target = await repository.getTarget(scan.applicationId);

    events.siarkan(scan.id, { tipe: 'metode', hasil: { metode_id: task.methodCode, status: 'berjalan', bukti: [] } });

    return {
      task_id: String(task.id),
      scan_id: String(scan.id),
      metode: buildMetodeSpec(mc),
      context: buildContext({ scan, application, target }),
    };
  }

  /** Terima HasilMetode dari worker, simpan, siarkan, dan finalisasi scan bila selesai. */
  async function result(taskId, hasil) {
    const task = await repository.findTaskById(Number(taskId));
    if (!task) throw AppError.notFound('Task tidak ditemukan');
    if (task.status === 'selesai') return { ok: true }; // idempoten
    await workers.catatSelesai(task.lockedBy).catch(() => {});

    const finalHasil = { bukti: [], ...hasil, metode_id: hasil.metode_id ?? task.methodCode };
    await repository.completeTask(task.id, { result: finalHasil, durationMs: hasil.durasi_ms });
    events.siarkan(task.scanId, { tipe: 'metode', hasil: finalHasil });

    const LABEL = { lulus: 'PASS', gagal: 'FAILED', luar_cakupan: 'OUT OF SCOPE', tidak_berlaku: 'tidak berlaku' };
    const ringkas =
      finalHasil.status === 'gagal'
        ? `${task.methodCode}: FAILED — ${finalHasil.ringkasan ?? ''}`
        : `${task.methodCode}: ${LABEL[finalHasil.status] ?? finalHasil.status}`;
    const level = finalHasil.status === 'gagal' ? 'peringatan' : 'info';
    await repository.insertLog(task.scanId, level, ringkas);
    events.siarkan(task.scanId, { tipe: 'log', log: { waktu: new Date().toISOString(), level, pesan: ringkas } });

    await scans.finalizeIfDone(task.scanId);
    return { ok: true };
  }

  /**
   * Terima hasil fase penemuan (mode eksploratif) dari worker discovery:
   * simpan ke scan_targets (tanpa menimpa manual), lalu semai task fase pengujian.
   */
  async function discovery(scanId, payload) {
    const scan = await repository.findScanById(Number(scanId));
    if (!scan) throw AppError.notFound('Pengujian tidak ditemukan');
    // Scan dibatalkan selama penemuan → jangan simpan/semai apa pun (worker mungkin belum menerima sinyal batal).
    if (scan.status !== 'berjalan') return { disemai: 0, dibatalkan: true };

    await repository.mergeDiscovery(scan.applicationId, {
      testPoints: payload.test_points ?? {},
      forms: payload.forms ?? {},
      // Cap waktu + asal scan agar uji ulang dapat menampilkan "penemuan terakhir".
      discovery: { ...(payload.ringkasan ?? {}), waktu: new Date().toISOString(), scan_id: String(scan.id) },
    });

    const rk = payload.ringkasan ?? {};
    const titik = (rk.titik_ditemukan ?? []).join(', ') || 'tidak ada';
    const auth = rk.terautentikasi ? ' (terautentikasi)' : '';
    const pesanUtama = `Penemuan selesai${auth}: ${rk.jumlah_halaman ?? 0} halaman HTML, titik uji terdeteksi [${titik}].`;
    const logs = [pesanUtama];
    if (rk.jumlah_endpoint_unik != null) {
      logs.push(`Inventaris endpoint: ${rk.jumlah_endpoint_unik} endpoint unik, ${(rk.flows ?? []).length} alur proses bisnis terpetakan.`);
    }
    if (rk.openapi) {
      logs.push(
        `OpenAPI '${rk.openapi.judul ?? ''}' — ${rk.openapi.jumlah_endpoint ?? 0} endpoint di base ${rk.openapi.base_api ?? ''}.`,
      );
    }
    if (rk.katana?.tersedia) {
      logs.push(`Katana: ${rk.katana.jumlah ?? 0} URL/endpoint ditemukan${rk.katana.terautentikasi ? ' (terautentikasi)' : ''}.`);
    }
    if (rk.ai) {
      if (rk.ai.tersedia) logs.push(`AI enrichment via ${rk.ai.provider} (${rk.ai.model}).`);
      else if (rk.ai.galat) logs.push(`AI enrichment dilewati: ${rk.ai.galat}.`);
    }
    if (rk.zap) {
      if (rk.zap.terjangkau === false) logs.push('ZAP: target tidak terjangkau (0 URL).');
      else if (rk.zap.gagal) logs.push(`ZAP: pengayaan gagal (${rk.zap.gagal}).`);
      else logs.push(`ZAP: ${rk.zap.jumlah_url ?? 0} URL, ${rk.zap.jumlah_alert ?? 0} temuan awal pasif.`);
    }
    for (const pesan of logs) {
      await repository.insertLog(scan.id, 'info', pesan);
      events.siarkan(scan.id, { tipe: 'log', log: { waktu: new Date().toISOString(), level: 'info', pesan } });
    }

    const disemai = await scans.seedPhase2(scan.id);
    events.siarkan(scan.id, { tipe: 'status', status: 'berjalan' });
    return { disemai };
  }

  async function log(taskId, { level, pesan, data = null }) {
    const task = await repository.findTaskById(Number(taskId));
    if (!task) throw AppError.notFound('Task tidak ditemukan');
    if (data && JSON.stringify(data).length > MAKS_DATA_LOG) throw AppError.badRequest('Data log terlalu besar');
    await repository.insertLog(task.scanId, level, pesan, data);
    events.siarkan(task.scanId, { tipe: 'log', log: { waktu: new Date().toISOString(), level, pesan, ...(data ? { data } : {}) } });
    return { ok: true };
  }

  return { claim, result, log, discovery };
}

export const internalService = createInternalService();
