import { MAKS_KEDALAMAN_SATUAN, namaProvinsi } from '../../config/satuan.js';
import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { isDuplicateEntry } from '../../utils/dbErrors.js';
import { unitsRepository } from './units.repository.js';

const PEMISAH_JALUR = ' › ';
/** "" dan undefined = kolom dikosongkan. */
const kosong = (v) => (v === '' || v === undefined ? null : v);
const angka = (v) => (v === null || v === undefined ? null : Number(v));

/**
 * Bentuk satuan untuk pilihan publik (pendaftaran, form aset) — sesuai tipe `Satuan` di frontend.
 * Sengaja tanpa alamat/koordinat: lokasi satuan hanya untuk admin & dasbor, bukan endpoint publik.
 */
export const toUnitDto = (unit, leluhur = []) => ({
  id: String(unit.id),
  nama: unit.name,
  jenis: unit.type,
  jalur: leluhur.map((l) => l.name).join(PEMISAH_JALUR),
});

/** Bentuk satuan untuk halaman admin (sesuai tipe `SatuanAdmin` di frontend). */
const toUnitAdminDto = (unit, leluhur = []) => ({
  ...toUnitDto(unit, leluhur),
  induk_id: unit.parentId ? String(unit.parentId) : null,
  leluhur: leluhur.map((l) => ({ id: String(l.id), nama: l.name })),
  alamat: unit.address ?? null,
  kota: unit.city ?? null,
  provinsi_kode: unit.provinceCode ?? null,
  provinsi: namaProvinsi(unit.provinceCode),
  latitude: angka(unit.latitude),
  longitude: angka(unit.longitude),
  aktif: Boolean(unit.isActive),
  jumlah_pengguna: Number(unit.userCount ?? 0),
  jumlah_aplikasi: Number(unit.appCount ?? 0),
  jumlah_sub: Number(unit.childCount ?? 0),
  dibuat_pada: unit.createdAt,
});

// Nama field API → kolom DB.
const KOLOM = {
  nama: 'name',
  jenis: 'type',
  induk_id: 'parentId',
  alamat: 'address',
  kota: 'city',
  provinsi_kode: 'provinceCode',
  latitude: 'latitude',
  longitude: 'longitude',
  aktif: 'isActive',
};

const fieldError = (field, message, factory = AppError.badRequest) => factory(message, [{ field, message }]);
const duplicateName = () => fieldError('nama', 'Satuan dengan nama ini sudah ada', AppError.conflict);

/** Nilai kolom DB → nilai pembanding yang setara dengan masukan API (decimal MySQL datang sebagai string). */
const nilaiLama = (unit, kolom) => {
  const v = unit[kolom];
  if (kolom === 'isActive') return Boolean(v);
  if (kolom === 'latitude' || kolom === 'longitude') return angka(v);
  return v ?? null;
};

export function createUnitsService({ repository = unitsRepository, auditor = audit } = {}) {
  async function findOrFail(id) {
    const unit = await repository.findById(id);
    if (!unit) throw AppError.notFound('Satuan tidak ditemukan');
    return unit;
  }

  async function withAncestors(rows, toDto) {
    const map = await repository.ancestorsOf(rows.map((r) => r.id));
    return rows.map((r) => toDto(r, map.get(Number(r.id)) ?? []));
  }

  async function getAdmin(id) {
    const [dto] = await withAncestors([await findOrFail(id)], toUnitAdminDto);
    return dto;
  }

  /**
   * Pastikan induk ada, tidak membuat siklus (satuan menjadi induk bagi dirinya / leluhurnya sendiri),
   * dan pohon tidak melampaui batas kedalaman. `id` kosong = satuan baru.
   */
  async function checkParent(parentId, id) {
    if (parentId === null) return;
    if (id !== undefined && Number(parentId) === Number(id))
      throw fieldError('induk_id', 'Satuan tidak bisa menjadi induk bagi dirinya sendiri');
    if (!(await repository.findById(parentId))) throw fieldError('induk_id', 'Satuan induk tidak ditemukan');

    const leluhurInduk = (await repository.ancestorsOf([parentId])).get(Number(parentId)) ?? [];
    if (id !== undefined && leluhurInduk.some((l) => Number(l.id) === Number(id)))
      throw fieldError('induk_id', 'Satuan induk tidak boleh berasal dari sub-satuannya sendiri');

    const tinggi = id === undefined ? 0 : await repository.subtreeHeight(id);
    // Kedalaman induk = jumlah leluhurnya; satuan ini berada satu tingkat di bawahnya.
    if (leluhurInduk.length + 1 + tinggi >= MAKS_KEDALAMAN_SATUAN)
      throw fieldError('induk_id', `Hierarki satuan maksimal ${MAKS_KEDALAMAN_SATUAN} tingkat`);
  }

  /** Koordinat harus lengkap berpasangan (atau keduanya kosong) agar titik di peta tidak setengah jadi. */
  function checkCoordinates({ latitude, longitude }) {
    if ((latitude === null) !== (longitude === null))
      throw fieldError(latitude === null ? 'latitude' : 'longitude', 'Isi latitude dan longitude berpasangan, atau kosongkan keduanya');
  }

  return {
    /** Cari satuan/instansi untuk pilihan pendaftaran; hasil dibatasi agar tetap ringan walau daftarnya ribuan. */
    async search({ search, limit }) {
      return withAncestors(await repository.searchActive({ search, limit }), toUnitDto);
    },

    /**
     * Daftar untuk admin (termasuk nonaktif), dengan pencarian & paginasi.
     * `induk`: 'akar' = satuan tingkat teratas, id = sub-satuan langsung, kosong = semua tingkat.
     */
    async listAdmin({ page, limit, search, status, jenis, provinsi, induk }) {
      const parentId = induk === 'akar' ? null : induk === undefined ? undefined : Number(induk);
      const { rows, total } = await repository.listAll({
        offset: (page - 1) * limit,
        limit,
        search,
        status,
        type: jenis,
        provinceCode: provinsi,
        parentId,
      });
      return {
        items: await withAncestors(rows, toUnitAdminDto),
        meta: { page, limit, total, totalPages: Math.max(1, Math.ceil(total / limit)) },
      };
    },

    getAdmin,

    async create({ nama, jenis = 'SATUAN', induk_id = null, aktif = true, ...lokasi }) {
      const input = {
        nama,
        jenis,
        induk_id,
        aktif,
        alamat: kosong(lokasi.alamat),
        kota: kosong(lokasi.kota),
        provinsi_kode: kosong(lokasi.provinsi_kode),
        latitude: kosong(lokasi.latitude),
        longitude: kosong(lokasi.longitude),
      };
      checkCoordinates(input);
      await checkParent(input.induk_id);
      const data = Object.fromEntries(Object.entries(input).map(([k, v]) => [KOLOM[k], k === 'induk_id' && v ? Number(v) : v]));
      try {
        const unit = await repository.create(data);
        auditor('satuan.tambah', { unitId: unit.id, nama, jenis, indukId: data.parentId, aktif });
        return getAdmin(unit.id);
      } catch (error) {
        if (isDuplicateEntry(error)) throw duplicateName();
        throw error;
      }
    },

    /**
     * Ubah sebagian data. Nonaktif: hilang dari pilihan pendaftaran, akun/aplikasi yang memakainya tetap sah.
     * Pindah induk ikut memindahkan seluruh sub-satuannya.
     */
    async update(id, input) {
      const before = await findOrFail(id);
      const changes = {};
      for (const [field, value] of Object.entries(input)) {
        const kolom = KOLOM[field];
        if (!kolom) continue;
        const baru = field === 'induk_id' && value !== null ? Number(value) : value === '' ? null : value;
        if (baru !== nilaiLama(before, kolom)) changes[kolom] = baru;
      }
      if (!Object.keys(changes).length) return getAdmin(id);

      checkCoordinates({
        latitude: 'latitude' in changes ? changes.latitude : angka(before.latitude),
        longitude: 'longitude' in changes ? changes.longitude : angka(before.longitude),
      });
      if ('parentId' in changes) await checkParent(changes.parentId, id);

      const lama = { name: before.name, parentId: before.parentId ?? null };
      try {
        await repository.update(id, changes);
      } catch (error) {
        if (isDuplicateEntry(error)) throw duplicateName();
        throw error;
      }
      auditor('satuan.ubah', {
        unitId: Number(id),
        ...(changes.name && { namaLama: lama.name, namaBaru: changes.name }),
        ...('isActive' in changes && { aktif: changes.isActive }),
        ...('parentId' in changes && { indukLama: lama.parentId, indukBaru: changes.parentId }),
        kolom: Object.keys(changes),
      });
      return getAdmin(id);
    },
  };
}

export const unitsService = createUnitsService();
