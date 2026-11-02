import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { isDuplicateEntry } from '../../utils/dbErrors.js';
import { unitsRepository } from './units.repository.js';

/** Bentuk satuan yang dikirim ke frontend (sesuai tipe `Satuan` di frontend). */
export const toUnitDto = (unit) => ({ id: String(unit.id), nama: unit.name });

/** Bentuk satuan untuk halaman admin (sesuai tipe `SatuanAdmin` di frontend). */
const toUnitAdminDto = (unit) => ({
  ...toUnitDto(unit),
  aktif: Boolean(unit.isActive),
  jumlah_pengguna: Number(unit.userCount ?? 0),
  dibuat_pada: unit.createdAt,
});

const duplicateName = () =>
  AppError.conflict('Satuan dengan nama ini sudah ada', [{ field: 'nama', message: 'Satuan dengan nama ini sudah ada' }]);

export function createUnitsService({ repository = unitsRepository, auditor = audit } = {}) {
  async function findOrFail(id) {
    const unit = await repository.findById(id);
    if (!unit) throw AppError.notFound('Satuan tidak ditemukan');
    return unit;
  }

  return {
    /** Cari satuan/instansi untuk pilihan pendaftaran; hasil dibatasi agar tetap ringan walau daftarnya ribuan. */
    async search({ search, limit }) {
      return (await repository.searchActive({ search, limit })).map(toUnitDto);
    },

    /** Daftar lengkap untuk admin (termasuk nonaktif), dengan pencarian & paginasi. */
    async listAdmin({ page, limit, search, status }) {
      const { rows, total } = await repository.listAll({ offset: (page - 1) * limit, limit, search, status });
      return {
        items: rows.map(toUnitAdminDto),
        meta: { page, limit, total, totalPages: Math.max(1, Math.ceil(total / limit)) },
      };
    },

    async create({ nama, aktif = true }) {
      try {
        const unit = await repository.create({ name: nama, isActive: aktif });
        auditor('satuan.tambah', { unitId: unit.id, nama, aktif });
        return toUnitAdminDto(unit);
      } catch (error) {
        if (isDuplicateEntry(error)) throw duplicateName();
        throw error;
      }
    },

    /** Ganti nama dan/atau status. Nonaktif: hilang dari pilihan pendaftaran, akun yang memakainya tetap sah. */
    async update(id, { nama, aktif }) {
      const before = await findOrFail(id);
      const changes = {};
      if (nama !== undefined && nama !== before.name) changes.name = nama;
      if (aktif !== undefined && aktif !== Boolean(before.isActive)) changes.isActive = aktif;
      if (!Object.keys(changes).length) return toUnitAdminDto(before);

      const namaLama = before.name;
      try {
        const unit = await repository.update(id, changes);
        auditor('satuan.ubah', {
          unitId: unit.id,
          ...(changes.name && { namaLama, namaBaru: changes.name }),
          ...('isActive' in changes && { aktif: changes.isActive }),
        });
        return toUnitAdminDto(unit);
      } catch (error) {
        if (isDuplicateEntry(error)) throw duplicateName();
        throw error;
      }
    },
  };
}

export const unitsService = createUnitsService();
