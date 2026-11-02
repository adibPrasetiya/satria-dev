import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { isDuplicateEntry } from '../../utils/dbErrors.js';
import { unitsRepository } from '../units/units.repository.js';
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
  dibuat_pada: a.createdAt,
  diubah_pada: a.updatedAt,
});

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

const duplicateUrl = () =>
  AppError.conflict('URL dasar ini sudah terdaftar sebagai aset lain', [
    { field: 'url_dasar', message: 'URL dasar ini sudah terdaftar sebagai aset lain' },
  ]);

// Asesor & admin melihat semua aset; pemilik hanya aset satuannya.
const seesAll = (actor) => actor.peran === 'asesor' || actor.peran === 'admin';

export function createApplicationsService({
  repository = applicationsRepository,
  units = unitsRepository,
  auditor = audit,
} = {}) {
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

  async function save(write) {
    try {
      return await write();
    } catch (error) {
      if (isDuplicateEntry(error)) throw duplicateUrl();
      throw error;
    }
  }

  return {
    async list(actor, { page, limit, search }) {
      const unitId = seesAll(actor) ? undefined : Number(actor.satuan_id);
      const { rows, total } = await repository.list({ offset: (page - 1) * limit, limit, search, unitId });
      return {
        items: rows.map(toApplicationDto),
        meta: { page, limit, total, totalPages: Math.max(1, Math.ceil(total / limit)) },
      };
    },

    async get(actor, id) {
      return toApplicationDto(await findVisible(actor, id));
    },

    /** Pemilik selalu mendaftarkan untuk satuannya sendiri; admin boleh memilih satuan. */
    async create(actor, data) {
      const unitId = actor.peran === 'admin' && data.satuan_id ? data.satuan_id : Number(actor.satuan_id);
      if (unitId !== Number(actor.satuan_id)) await assertUnit(unitId);
      const app = await save(() => repository.create({ ...toColumns(data), unitId, ownerId: Number(actor.id) }));
      auditor('aplikasi.daftar', { aplikasiId: app.id, nama: app.name, url: app.baseUrl, unitId });
      return toApplicationDto(app);
    },

    /** Pemilik hanya mengubah aset satuannya dan tidak bisa memindahkan satuan; admin bebas. */
    async update(actor, id, data) {
      const before = await findVisible(actor, id);
      const changes = toColumns(data);
      if (actor.peran === 'admin' && data.satuan_id && data.satuan_id !== before.unitId) {
        await assertUnit(data.satuan_id);
        changes.unitId = data.satuan_id;
      }
      const changed = Object.keys(changes).filter((key) => (changes[key] ?? null) !== (before[key] ?? null));
      if (!changed.length) return toApplicationDto(before);

      const app = await save(() => repository.update(before.id, Object.fromEntries(changed.map((key) => [key, changes[key]]))));
      auditor('aplikasi.ubah', { aplikasiId: app.id, nama: app.name, kolom: changed });
      return toApplicationDto(app);
    },
  };
}

export const applicationsService = createApplicationsService();
