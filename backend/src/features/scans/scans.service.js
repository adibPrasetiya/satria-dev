import { workersService } from '../workers/workers.service.js';
import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { applicationsRepository } from '../applications/applications.repository.js';
import { butuhTinjauan, penerapanMetode } from './applicability.js';
import * as scanEvents from './scanEvents.js';
import * as workerEvents from '../workers/workerEvents.js';
import { scansRepository } from './scans.repository.js';
import { verdictService } from './verdict.service.js';

// Fungsi keamanan yang dinilai worker tahap ini (Autentikasi, Manajemen Sesi, Kontrol Akses,
// Validasi Input, Keamanan Komunikasi).
const FUNGSI = ['AUTH', 'SESS', 'ACCS', 'INPV', 'COMM', 'APIS', 'ERRL', 'DATA', 'FILE', 'CONF', 'CRYP', 'MALC', 'BLOG'];

const seesAll = (actor) => actor.peran === 'asesor' || actor.peran === 'admin';

/** Hasil per metode untuk DTO: task selesai -> result tersimpan; selain itu status antre/berjalan. */
function taskToHasil(task) {
  if (task.status !== 'selesai') {
    return { metode_id: task.methodCode, status: task.status, bukti: [] };
  }
  const r = task.result ?? { metode_id: task.methodCode, status: 'tidak_dapat_diverifikasi', bukti: [] };
  return { bukti: [], ...r, metode_id: r.metode_id ?? task.methodCode };
}

/** Akun uji tersimpan sebagai daftar: bentuk baru `{daftar}` atau lama `{utama, penguncian}`. */
function daftarAkun(accounts) {
  if (!accounts) return [];
  const list = Array.isArray(accounts.daftar) ? accounts.daftar : [accounts.utama, accounts.penguncian];
  return list.filter((a) => a?.username?.trim());
}

/** Ringkasan penemuan untuk ditampilkan (tanpa inventaris lengkap). */
function ringkasDiscovery(d, cadanganWaktu = null) {
  if (!d || !Object.keys(d).length) return null;
  const endpoints = Array.isArray(d.endpoints_lengkap) ? d.endpoints_lengkap : [];
  return {
    waktu: d.waktu ?? cadanganWaktu ?? null, // data lama tanpa cap waktu → updatedAt baris
    scan_id: d.scan_id ?? null,
    jumlah_halaman: d.jumlah_halaman ?? 0,
    jumlah_endpoint_unik: d.jumlah_endpoint_unik ?? endpoints.length,
    jumlah_alur: Array.isArray(d.flows) ? d.flows.length : 0,
    titik_ditemukan: d.titik_ditemukan ?? [],
    terautentikasi: !!d.terautentikasi,
    openapi: d.openapi ? { judul: d.openapi.judul ?? '', jumlah_endpoint: d.openapi.jumlah_endpoint ?? 0 } : null,
    kandidat: d.kandidat_uji?.ringkas_kategori ?? {},
    contoh_endpoint: endpoints.slice(0, 20).map((e) => ({
      metode_http: e.metode_http,
      path: e.path_template,
      butuh_autentikasi: !!e.butuh_autentikasi,
    })),
  };
}

function toScanDto(scan, tasks, logs) {
  return {
    id: String(scan.id),
    aplikasi_id: String(scan.applicationId),
    profil: scan.profile,
    mode: scan.mode ?? 'terarah',
    pendekatan: scan.approach ?? 'greybox',
    status: scan.status,
    dimulai_pada: scan.startedAt,
    ...(scan.finishedAt ? { selesai_pada: scan.finishedAt } : {}),
    hasil: Object.fromEntries(tasks.map((t) => [t.methodCode, taskToHasil(t)])),
    // Laporan AI tersimpan (hanya ada pada scan selesai terakhir aplikasi).
    ...(scan.aiAnalysis ? { ai: { ...scan.aiAnalysis, disimpan: true } } : {}),
    log: logs.map((l) => ({ waktu: l.createdAt, level: l.level, pesan: l.message, ...(l.data ? { data: l.data } : {}) })),
  };
}

export function createScansService({
  repository = scansRepository,
  applications = applicationsRepository,
  events = scanEvents,
  auditor = audit,
  // Koordinasi worker (registry/antrean). null di tes unit → penjaga & info antrean dilewati.
  gerbang = null,
  // Sinyal perubahan antrean untuk aliran status worker (SSE).
  antrean = workerEvents,
  // Penghitung putusan/skor/temuan yang disimpan di tabel scans (daftar aplikasi). null di tes unit.
  penilai = null,
} = {}) {
  async function insertTasks(rows) {
    await repository.insertTasks(rows);
    if (rows.some((r) => r.status === 'antre')) antrean.beriTahu();
  }

  /** Aset yang boleh dilihat aktor (pemilik: satuannya); 404 bila di luar cakupan. */
  async function findVisibleApp(actor, appId) {
    const app = await applications.findById(Number(appId));
    if (!app || (!seesAll(actor) && String(app.unitId) !== actor.satuan_id)) {
      throw AppError.notFound('Aplikasi tidak ditemukan');
    }
    return app;
  }

  async function dtoById(scanId) {
    const scan = await repository.findScanById(scanId);
    if (!scan) throw AppError.notFound('Pengujian tidak ditemukan');
    const [tasks, logs] = await Promise.all([repository.tasksByScan(scanId), repository.logsByScan(scanId)]);
    const dto = toScanDto(scan, tasks, logs);
    // Posisi antrean & worker yang mengerjakan (hanya selama berjalan).
    if (gerbang && scan.status === 'berjalan') {
      try {
        dto.antrean = await gerbang.antreanScan(scan.id);
      } catch {
        /* info antrean tak boleh menggagalkan pengambilan scan */
      }
    }
    return dto;
  }

  /** Finalisasi scan bila semua task sudah selesai. Dipakai juga oleh internal.service. */
  async function finalizeIfDone(scanId) {
    if ((await repository.countUnfinished(scanId)) > 0) return false;
    const scan = await repository.findScanById(scanId);
    if (!scan || scan.status !== 'berjalan') return false;
    const finishedAt = new Date();
    await repository.setScanStatus(scanId, 'selesai', finishedAt);
    // Ringkasan penilaian untuk daftar aplikasi; bila gagal, dilengkapi belakangan (lengkapiYangKosong).
    if (penilai) await penilai.nilaiScan(scanId).catch(() => {});
    // Hanya laporan riwayat TERAKHIR yang disimpan: laporan pengujian sebelumnya kini usang.
    if (repository.hapusLaporanLain) {
      await repository.hapusLaporanLain(scan.applicationId, scanId).catch(() => {});
    }

    // Rekapitulasi akhir ke log operasi agar pengguna melihat ringkasan tanpa membuka laporan.
    await tulisRekap(scanId);

    await repository.insertLog(scanId, 'info', 'Pengujian selesai.');
    events.siarkan(scanId, { tipe: 'status', status: 'selesai', selesai_pada: finishedAt.toISOString() });
    auditor('scan.selesai', { scanId: String(scanId) });
    return true;
  }

  /** Tulis beberapa baris rekap (hitungan per status + daftar temuan GAGAL) ke log scan. */
  async function tulisRekap(scanId) {
    const tasks = (await repository.tasksByScan(scanId)).filter((t) => t.engine !== 'discovery');
    const n = { lulus: 0, gagal: 0, tidak_dapat_diverifikasi: 0, tidak_berlaku: 0 };
    const gagal = [];
    for (const t of tasks) {
      const s = t.result?.status ?? t.status;
      if (s in n) n[s] += 1;
      if (s === 'gagal') gagal.push(`${t.methodCode} — ${t.result?.ringkasan ?? ''}`.trim());
    }
    const emit = async (level, pesan) => {
      await repository.insertLog(scanId, level, pesan);
      events.siarkan(scanId, { tipe: 'log', log: { waktu: new Date().toISOString(), level, pesan } });
    };
    await emit('info', '──────── REKAPITULASI ────────');
    await emit('info', `Total metode diuji: ${tasks.length} — Lulus ${n.lulus}, Gagal ${n.gagal}, Perlu tinjauan ${n.tidak_dapat_diverifikasi}, Tidak berlaku ${n.tidak_berlaku}.`);
    if (gagal.length) {
      await emit('peringatan', `Temuan (${gagal.length}):`);
      for (const g of gagal.slice(0, 20)) await emit('peringatan', `  ✗ ${g}`);
      if (gagal.length > 20) await emit('peringatan', `  … dan ${gagal.length - 20} temuan lain.`);
    } else {
      await emit('info', 'Tidak ada temuan berstatus GAGAL.');
    }
  }

  /**
   * Semai task fase pengujian (AUTH + SESS) untuk sebuah scan dari katalog,
   * memakai `target` sebagai penentu keterterapan (applicability). Dipakai oleh
   * mode terarah (langsung) dan mode eksploratif (setelah fase penemuan).
   * @returns {Promise<{antre:number, tidak_berlaku:number, asesor:number, total:number, daftarAntre:string[]}>}
   */
  async function seedTestTasks(scanId, target) {
    const fw = await repository.functionsWithControls(FUNGSI);
    if (!fw || !fw.items.length) {
      throw AppError.badRequest(`Katalog ${FUNGSI.join('/')} belum tersedia; jalankan "npm run catalog:seed"`);
    }
    const ringkas = { antre: 0, tidak_berlaku: 0, asesor: 0, total: 0, daftarAntre: [] };
    const tasks = fw.items.map(({ method }) => {
      const base = { scanId, methodCode: method.code, checkId: method.checkId, engine: method.engine };
      ringkas.total += 1;
      const ap = penerapanMetode(target, method);
      if (ap.jalan) {
        ringkas.antre += 1;
        ringkas.daftarAntre.push(method.code);
        return { ...base, status: 'antre' };
      }
      if (ap.status === 'tidak_berlaku') ringkas.tidak_berlaku += 1;
      else ringkas.asesor += 1;
      const result = {
        metode_id: method.code,
        status: ap.status,
        ringkasan: ap.alasan,
        bukti: [],
        ...(butuhTinjauan(method) ? { menunggu_tinjauan: true } : {}),
      };
      return { ...base, status: 'selesai', result };
    });
    await insertTasks(tasks);
    return ringkas;
  }

  /** Dua baris log ringkas tentang hasil penyemaian metode. */
  async function logSeeding(scanId, r) {
    await repository.insertLog(
      scanId,
      'info',
      `Metode disemai: ${r.total} total → ${r.antre} dijalankan, ${r.tidak_berlaku} tidak berlaku, ${r.asesor} diserahkan asesor.`,
    );
    if (r.daftarAntre.length) {
      await repository.insertLog(scanId, 'info', `Antrean pengujian: ${r.daftarAntre.join(', ')}.`);
    }
  }

  /**
   * Fase 2 untuk scan eksploratif: semai task pengujian setelah penemuan selesai.
   * Idempoten — tidak menyemai ulang bila sudah ada task pengujian.
   * @returns {Promise<number>} jumlah task antre yang baru disemai.
   */
  async function seedPhase2(scanId) {
    const scan = await repository.findScanById(Number(scanId));
    if (!scan) throw AppError.notFound('Pengujian tidak ditemukan');
    if ((await repository.countTestTasks(scanId)) > 0) return 0; // sudah disemai
    const target = (await repository.getTarget(scan.applicationId)) ?? {};
    // Mode eksploratif dijalankan dengan persetujuan pemindaian aktif (divalidasi saat mulai),
    // jadi metode intrusif diizinkan untuk scan ini — override di memori, tidak disimpan ke aset.
    if (scan.mode === 'eksploratif') {
      target.options = { ...(target.options ?? {}), izinkan_penguncian: true };
    }
    const r = await seedTestTasks(scanId, target);
    await repository.insertLog(scanId, 'info', 'Fase pengujian dimulai.');
    await logSeeding(scanId, r);
    return r.antre;
  }

  async function mulai(
    actor,
    appId,
    { mode = 'terarah', pendekatan = 'greybox', accounts = null, options = null, pakaiDiscovery = false } = {},
  ) {
    const app = await findVisibleApp(actor, appId);
    // Black box memakai alur eksploratif yang sama dengan grey box, hanya tanpa akun uji
    // (terarah memakai persiapan + akun yang diisi pengguna, jadi tidak berlaku untuk black box).
    const blackbox = pendekatan === 'blackbox';
    if (blackbox && mode !== 'eksploratif') {
      throw AppError.badRequest('Pengujian black box hanya tersedia untuk mode eksploratif', [
        { field: 'pendekatan', message: 'Gunakan mode eksploratif untuk black box' },
      ]);
    }
    if (blackbox) accounts = null; // akun tidak disimpan maupun dipakai
    // Satu pengujian aktif per aplikasi + harus ada worker aktif untuk engine tahap pertama.
    if (gerbang) await gerbang.gerbangMulai(app.id, mode === 'eksploratif' && !pakaiDiscovery ? 'discovery' : 'custom');

    // Mode eksploratif: cukup URL aset; fase penemuan mengisi persiapan otomatis.
    if (mode === 'eksploratif') {
      // Uji ulang: akun tidak dikirim = pakai akun tersimpan; discovery boleh dipakai ulang.
      const tersimpan = await repository.getTarget(app.id);
      if (pakaiDiscovery && !tersimpan?.discovery) {
        throw AppError.badRequest('Belum ada hasil penemuan tersimpan untuk aplikasi ini', [
          { field: 'pakai_discovery', message: 'Jalankan penemuan (discovery) lebih dulu' },
        ]);
      }
      // Black box boleh memakai ulang penemuan tersimpan hanya bila penemuan itu dijalankan tanpa login,
      // agar pengetahuan dari sesi login (grey box) tidak terbawa.
      if (blackbox && pakaiDiscovery && tersimpan.discovery.terautentikasi) {
        throw AppError.badRequest('Hasil penemuan terakhir diperoleh dengan login; black box perlu penemuan baru', [
          { field: 'pakai_discovery', message: 'Jalankan penemuan ulang untuk black box' },
        ]);
      }
      if (!blackbox && pakaiDiscovery && !accounts && daftarAkun(tersimpan?.accounts).length === 0) {
        throw AppError.badRequest('Akun uji belum tersimpan untuk aplikasi ini', [
          { field: 'accounts', message: 'Isi akun uji lebih dulu' },
        ]);
      }
      // Jalur otomatis: simpan akun uji + opsi dari wizard dulu agar discovery bisa login.
      if (accounts || options) {
        await repository.mergeAccounts(app.id, { accounts: accounts ?? null, options: options ?? null });
      }
      const scanId = await repository.createScan({
        applicationId: app.id,
        profile: 'aman',
        mode,
        approach: blackbox ? 'blackbox' : 'greybox',
      });
      if (pakaiDiscovery) {
        const d = tersimpan.discovery;
        const kapan = d.waktu ? new Date(d.waktu).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' }) : 'tidak diketahui';
        await repository.insertLog(
          scanId,
          'info',
          `Pengujian eksploratif dimulai memakai hasil penemuan terakhir (${kapan}; ${d.jumlah_endpoint_unik ?? 0} endpoint unik) terhadap ${app.baseUrl}.`,
        );
        auditor('scan.mulai', { scanId: String(scanId), aplikasiId: String(app.id), mode, fungsi: FUNGSI.join(','), discovery: 'ulang-pakai' });
        await seedPhase2(scanId);
        await finalizeIfDone(scanId);
        return dtoById(scanId);
      }
      await insertTasks([
        { scanId, methodCode: '_discovery', checkId: 'discovery.crawl', engine: 'discovery', status: 'antre' },
      ]);
      await repository.insertLog(
        scanId,
        'info',
        blackbox
          ? `Pengujian black box dimulai (tanpa akun uji); fase penemuan terhadap ${app.baseUrl}.`
          : `Pengujian eksploratif dimulai; fase penemuan terhadap ${app.baseUrl}.`,
      );
      auditor('scan.mulai', {
        scanId: String(scanId),
        aplikasiId: String(app.id),
        mode,
        pendekatan: blackbox ? 'blackbox' : 'greybox',
        fungsi: FUNGSI.join(','),
      });
      return dtoById(scanId);
    }

    // Mode terarah: butuh data persiapan yang diisi pengguna.
    const target = await repository.getTarget(app.id);
    if (!target) {
      throw AppError.badRequest('Persiapan pengujian belum diisi untuk aplikasi ini', [
        { field: 'scan_target', message: 'Petakan titik uji & form lebih dulu (PUT /apps/:id/scan-target)' },
      ]);
    }

    const scanId = await repository.createScan({ applicationId: app.id, profile: 'aman', mode });
    await repository.insertLog(scanId, 'info', `Pengujian ${FUNGSI.join(' + ')} dimulai (mode terarah).`);
    const r = await seedTestTasks(scanId, target);
    await logSeeding(scanId, r);
    auditor('scan.mulai', { scanId: String(scanId), aplikasiId: String(app.id), mode, fungsi: FUNGSI.join(',') });

    // Semua metode manual/tidak didukung -> langsung selesai.
    await finalizeIfDone(scanId);
    return dtoById(scanId);
  }

  async function get(actor, scanId) {
    const scan = await repository.findScanById(Number(scanId));
    if (!scan) throw AppError.notFound('Pengujian tidak ditemukan');
    await findVisibleApp(actor, scan.applicationId); // lempar 404 bila tak boleh dilihat
    return dtoById(scan.id);
  }

  async function list(actor, query) {
    if (query.app) {
      const app = await findVisibleApp(actor, query.app);
      const rows = await repository.listScans({ applicationId: app.id });
      return Promise.all(rows.map((s) => dtoById(s.id)));
    }
    let rows;
    if (seesAll(actor)) {
      rows = await repository.listScans({});
    } else {
      const { rows: apps } = await applications.list({ unitId: Number(actor.satuan_id), offset: 0, limit: 1000 });
      rows = await repository.listScans({ applicationIds: apps.map((a) => a.id) });
    }
    return Promise.all(rows.map((s) => dtoById(s.id)));
  }

  async function batalkan(actor, scanId) {
    const scan = await repository.findScanById(Number(scanId));
    if (!scan) throw AppError.notFound('Pengujian tidak ditemukan');
    await findVisibleApp(actor, scan.applicationId);
    if (scan.status === 'berjalan') {
      const finishedAt = new Date();
      await repository.setScanStatus(scan.id, 'dibatalkan', finishedAt);
      await repository.finishPendingTasksAsCancelled(scan.id);
      antrean.beriTahu();
      await repository.insertLog(scan.id, 'peringatan', 'Pengujian dibatalkan oleh pengguna.');
      events.siarkan(scan.id, { tipe: 'status', status: 'dibatalkan', selesai_pada: finishedAt.toISOString() });
      auditor('scan.batal', { scanId: String(scan.id), aplikasiId: String(scan.applicationId) });
    }
    return dtoById(scan.id);
  }

  async function simpanTarget(actor, appId, data) {
    const app = await findVisibleApp(actor, appId);
    if (!seesAll(actor) && actor.peran !== 'pemilik') throw AppError.forbidden('Anda tidak memiliki akses ke fitur ini');
    const target = await repository.upsertTarget(app.id, {
      testPoints: data.test_points,
      forms: data.forms,
      accounts: data.accounts ?? null,
      options: data.options ?? null,
    });
    auditor('scan.target.simpan', { aplikasiId: String(app.id) });
    return {
      aplikasi_id: String(app.id),
      test_points: target.testPoints ?? {},
      forms: target.forms ?? {},
      // Kredensial tidak dikembalikan.
    };
  }

  /** Persiapan tersimpan untuk uji ulang: akun (tanpa sandi/seed) + ringkasan penemuan terakhir. */
  async function getTarget(actor, appId) {
    const app = await findVisibleApp(actor, appId);
    if (!seesAll(actor) && actor.peran !== 'pemilik') throw AppError.forbidden('Anda tidak memiliki akses ke fitur ini');
    const target = await repository.getTarget(app.id);
    return {
      aplikasi_id: String(app.id),
      akun: daftarAkun(target?.accounts).map((a) => ({
        username: a.username,
        ada_sandi: !!a.password,
        ada_totp: !!a.totp_secret?.trim?.(),
      })),
      discovery: ringkasDiscovery(target?.discovery, target?.updatedAt ?? null),
    };
  }

  return { mulai, get, list, batalkan, simpanTarget, getTarget, finalizeIfDone, seedPhase2, _internal: { toScanDto, taskToHasil } };
}

export const scansService = createScansService({ gerbang: workersService, penilai: verdictService });
