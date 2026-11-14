import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { isDuplicateEntry } from '../../utils/dbErrors.js';
import { logger } from '../../utils/logger.js';
import { komponenService } from '../komponen/komponen.service.js';
import { unitsRepository } from '../units/units.repository.js';
import { verdictService } from '../scans/verdict.service.js';
import { applicationsRepository } from './applications.repository.js';

/** Bentuk aset yang dikirim ke frontend (field dasar tipe `Aplikasi` di frontend). */
const toApplicationDto = (a) => ({
  id: String(a.id),
  nama: a.name,
  deskripsi: a.description ?? '',
  satuan: a.unit,
  satuan_id: String(a.unitId),
  pic_nama: a.picName,
  pic_kontak: a.picContact,
  url_dasar: a.baseUrl,
  lingkungan: a.environment,
  klasifikasi_data: a.dataClassification,
  teknologi: {
    frontend: a.techFrontend ?? '',
    backend: a.techBackend ?? '',
    database: a.techDatabase ?? '',
    server: a.techServer ?? '',
  },
  pemilik_id: a.ownerId ? String(a.ownerId) : null,
  diarsipkan_pada: a.archivedAt ?? null,
  dibuat_pada: a.createdAt,
  diubah_pada: a.updatedAt,
});

/** Ringkasan pengujian terakhir untuk baris daftar aplikasi. */
const toTestSummary = (r) => {
  const selesai = r.finishedScanId && r.verdict;
  return {
    scan_terakhir_pada: r.lastScanAt ?? null,
    berjalan: Boolean(Number(r.running)),
    scan_selesai_id: r.finishedScanId ? String(r.finishedScanId) : null,
    selesai_pada: r.finishedAt ?? null,
    putusan: selesai ? r.verdict : null,
    skor: selesai ? Number(r.score) : null,
    temuan: selesai
      ? {
          kritis: Number(r.findingsCritical ?? 0),
          tinggi: Number(r.findingsHigh ?? 0),
          sedang: Number(r.findingsMedium ?? 0),
          rendah: Number(r.findingsLow ?? 0),
        }
      : null,
  };
};

const FIELD_COLUMNS = {
  nama: 'name',
  deskripsi: 'description',
  pic_nama: 'picName',
  pic_kontak: 'picContact',
  url_dasar: 'baseUrl',
  lingkungan: 'environment',
  klasifikasi_data: 'dataClassification',
};
const TECH_COLUMNS = { frontend: 'techFrontend', backend: 'techBackend', database: 'techDatabase', server: 'techServer' };

/** Field DTO → kolom tabel (hanya yang dikirim; teknologi kosong disimpan NULL). */
function toColumns(data) {
  const columns = {};
  for (const [field, column] of Object.entries(FIELD_COLUMNS)) if (data[field] !== undefined) columns[column] = data[field];
  for (const [key, column] of Object.entries(TECH_COLUMNS)) {
    if (data.teknologi?.[key] !== undefined) columns[column] = data.teknologi[key] || null;
  }
  return columns;
}

const duplicateUrl = (terarsip = null) => {
  const pesan = terarsip
    ? `URL dasar ini milik aset terarsip "${terarsip.name}" — pulihkan dari daftar arsip alih-alih mendaftar ulang`
    : 'URL dasar ini sudah terdaftar sebagai aset lain';
  return AppError.conflict(pesan, [{ field: 'url_dasar', message: pesan }]);
};

const sudahDiarsipkan = () =>
  AppError.conflict('Aplikasi ini diarsipkan. Pulihkan dari daftar arsip lebih dulu untuk mengubah atau mengujinya.');

// Asesor & admin melihat semua aset; pemilik hanya aset satuannya.
const seesAll = (actor) => actor.peran === 'asesor' || actor.peran === 'admin';

export function createApplicationsService({
  repository = applicationsRepository,
  units = unitsRepository,
  auditor = audit,
  // Pelengkap ringkasan penilaian scan lama (scans/verdict.service). Bawaan no-op agar tes tidak butuh DB.
  penilai = { lengkapiYangKosong: async () => 0 },
  // Sinkron field teknologi → inventaris komponen (dasar pencocokan CVE). Bawaan no-op agar tes tidak butuh DB.
  komponen = { sinkronFormulir: async () => 0 },
} = {}) {
  /** Kegagalan sinkron komponen tidak menggagalkan simpan aset; komponen dapat dibentuk ulang lewat backfill. */
  async function sinkronKomponen(app) {
    try {
      await komponen.sinkronFormulir(app.id, toApplicationDto(app).teknologi);
    } catch (error) {
      logger.warn('Sinkron komponen aplikasi gagal', { aplikasiId: app.id, error: error.message });
    }
  }

  /** Aset di luar cakupan dijawab 404 (bukan 403) agar keberadaannya tidak bocor. */
  async function findVisible(actor, id) {
    const app = await repository.findById(Number(id));
    if (!app || (!seesAll(actor) && String(app.unitId) !== actor.satuan_id)) {
      throw AppError.notFound('Aplikasi tidak ditemukan');
    }
    return app;
  }

  async function assertUnit(unitId) {
    if (!(await units.findActiveById(unitId))) {
      throw AppError.badRequest('Data yang dikirim tidak valid', [
        { field: 'satuan_id', message: 'Satuan tidak ditemukan atau nonaktif' },
      ]);
    }
  }

  async function save(write, baseUrl) {
    try {
      return await write();
    } catch (error) {
      if (isDuplicateEntry(error)) {
        const lain = baseUrl && repository.findByBaseUrl ? await repository.findByBaseUrl(baseUrl).catch(() => null) : null;
        throw duplicateUrl(lain?.archivedAt ? lain : null);
      }
      throw error;
    }
  }

  return {
    /**
     * Daftar aplikasi berhalaman (filter, urut, paginasi di DB) beserta ringkasan pengujian terakhir.
     * `ringkasan: true` menambahkan jumlah per putusan & opsi satuan ke `meta`.
     */
    async list(actor, { page, limit, search, lingkungan, klasifikasi, satuan_id, putusan, arsip = 'aktif', sort, order, ringkasan }) {
      const unitId = seesAll(actor) ? undefined : Number(actor.satuan_id);
      // Scan lama (sebelum ringkasan disimpan) dilengkapi dulu agar filter putusan/urut skor akurat.
      await penilai.lengkapiYangKosong();

      const filters = { unitId, search, lingkungan, klasifikasi, satuanId: satuan_id, putusan, arsip };
      const [{ rows, total }, perPutusan, satuan] = await Promise.all([
        repository.list({ ...filters, offset: (page - 1) * limit, limit, sort, order }),
        ringkasan ? repository.countByVerdict(filters) : null,
        ringkasan ? repository.unitsWithApplications({ unitId, arsip }) : null,
      ]);

      const meta = { page, limit, total, totalPages: Math.max(1, Math.ceil(total / limit)), sort, order };
      if (ringkasan) {
        const jumlah = { semua: 0, laik: 0, laik_bersyarat: 0, tidak_laik: 0, belum: 0 };
        for (const r of perPutusan) {
          const n = Number(r.n);
          jumlah.semua += n;
          if (r.putusan in jumlah) jumlah[r.putusan] += n;
        }
        meta.ringkasan = jumlah;
        meta.opsi_satuan = satuan.map((u) => ({ id: String(u.id), nama: u.name, jumlah: Number(u.n) }));
      }
      return { items: rows.map((r) => ({ ...toApplicationDto(r), pengujian: toTestSummary(r) })), meta };
    },

    async get(actor, id) {
      return toApplicationDto(await findVisible(actor, id));
    },

    /** Pemilik selalu mendaftarkan untuk satuannya sendiri; admin boleh memilih satuan. */
    async create(actor, data) {
      const unitId = actor.peran === 'admin' && data.satuan_id ? data.satuan_id : Number(actor.satuan_id);
      if (unitId !== Number(actor.satuan_id)) await assertUnit(unitId);
      const app = await save(() => repository.create({ ...toColumns(data), unitId, ownerId: Number(actor.id) }), data.url_dasar);
      auditor('aplikasi.daftar', { aplikasiId: app.id, nama: app.name, url: app.baseUrl, unitId });
      await sinkronKomponen(app);
      return toApplicationDto(app);
    },

    /** Pemilik hanya mengubah aset satuannya dan tidak bisa memindahkan satuan; admin bebas. */
    async update(actor, id, data) {
      const before = await findVisible(actor, id);
      if (before.archivedAt) throw sudahDiarsipkan();
      const changes = toColumns(data);
      if (actor.peran === 'admin' && data.satuan_id && data.satuan_id !== before.unitId) {
        await assertUnit(data.satuan_id);
        changes.unitId = data.satuan_id;
      }
      const changed = Object.keys(changes).filter((key) => (changes[key] ?? null) !== (before[key] ?? null));
      if (!changed.length) return toApplicationDto(before);

      const app = await save(
        () => repository.update(before.id, Object.fromEntries(changed.map((key) => [key, changes[key]]))),
        changes.baseUrl,
      );
      auditor('aplikasi.ubah', { aplikasiId: app.id, nama: app.name, kolom: changed });
      if (changed.some((key) => Object.values(TECH_COLUMNS).includes(key))) await sinkronKomponen(app);
      return toApplicationDto(app);
    },

    /**
     * Arsipkan aset (pengganti hapus): disembunyikan dari daftar & tak bisa diuji/diubah, riwayat scan
     * dan laporannya tetap tersimpan. Ditolak bila masih ada pengujian berjalan. Idempoten.
     */
    async arsipkan(actor, id) {
      const app = await findVisible(actor, id);
      if (app.archivedAt) return toApplicationDto(app);
      if (await repository.adaScanBerjalan(app.id)) {
        throw AppError.conflict('Masih ada pengujian yang berjalan pada aplikasi ini. Hentikan pengujian lebih dulu, lalu arsipkan.');
      }
      const hasil = await repository.setArsip(app.id, new Date());
      auditor('aplikasi.arsip', { aplikasiId: app.id, nama: app.name, oleh: actor.id });
      return toApplicationDto(hasil);
    },

    /** Kembalikan aset dari arsip. Idempoten. */
    async pulihkan(actor, id) {
      const app = await findVisible(actor, id);
      if (!app.archivedAt) return toApplicationDto(app);
      const hasil = await repository.setArsip(app.id, null);
      auditor('aplikasi.pulihkan', { aplikasiId: app.id, nama: app.name, oleh: actor.id });
      return toApplicationDto(hasil);
    },
  };
}

export const applicationsService = createApplicationsService({ penilai: verdictService, komponen: komponenService });
