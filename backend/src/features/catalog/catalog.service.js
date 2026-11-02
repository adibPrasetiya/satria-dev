import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { isDuplicateEntry } from '../../utils/dbErrors.js';
import { catalogRepository } from './catalog.repository.js';

// --- Bentuk respons (sama dengan tipe `Katalog` di frontend; nama field mengikuti YAML).

const toMethodDto = (m) => ({
  id: m.code,
  nama: m.name,
  titik_uji: m.testPoint,
  check_id: m.checkId,
  jenis: m.kind,
  engine: m.engine,
  profil: m.profile,
  butuh_autentikasi: Boolean(m.requiresAuth),
  bukti: m.evidence ?? [],
  kriteria_lulus: m.passCriteria,
  ...(m.sideEffect ? { efek_samping: m.sideEffect } : {}),
  ...(m.parameters ? { parameter: m.parameters } : {}),
  severity: m.severity,
  aktif: Boolean(m.isActive),
});

const toControlDto = (c, methods = []) => ({
  id: c.code,
  nomor_referensi: c.refNumber,
  uraian: c.description,
  verifiabilitas: c.verifiability,
  severity_default: c.defaultSeverity,
  agregasi: c.aggregation,
  referensi_pendukung: c.refs ?? [],
  ...(c.parameters ? { parameter: c.parameters } : {}),
  aktif: Boolean(c.isActive),
  metode_pengujian: methods.map(toMethodDto),
});

// --- Field API → kolom tabel.

const CONTROL_COLUMNS = {
  uraian: 'description',
  verifiabilitas: 'verifiability',
  severity_default: 'defaultSeverity',
  agregasi: 'aggregation',
  referensi_pendukung: 'refs',
  parameter: 'parameters',
  aktif: 'isActive',
};
const METHOD_COLUMNS = {
  nama: 'name',
  titik_uji: 'testPoint',
  check_id: 'checkId',
  jenis: 'kind',
  engine: 'engine',
  profil: 'profile',
  butuh_autentikasi: 'requiresAuth',
  bukti: 'evidence',
  kriteria_lulus: 'passCriteria',
  efek_samping: 'sideEffect',
  severity: 'severity',
  parameter: 'parameters',
  aktif: 'isActive',
};

function toColumns(data, map) {
  const columns = {};
  for (const [field, column] of Object.entries(map)) if (data[field] !== undefined) columns[column] = data[field];
  if ('sideEffect' in columns) columns.sideEffect ||= null;
  // Objek parameter kosong disimpan NULL (tidak ada parameter).
  if (columns.parameters && !Object.keys(columns.parameters).length) columns.parameters = null;
  return columns;
}

// Kolom boolean MySQL bisa terbaca 0/1; samakan sebelum dibandingkan. Array/JSON dibandingkan lewat serialisasi
// dengan kunci terurut, karena MySQL mengurutkan ulang kunci kolom JSON.
const BOOLEAN_COLUMNS = new Set(['isActive', 'requiresAuth']);
const sortKeys = (v) =>
  Array.isArray(v)
    ? v.map(sortKeys)
    : v && typeof v === 'object'
      ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortKeys(v[k])]))
      : v;
const normalize = (key, value) => (BOOLEAN_COLUMNS.has(key) ? Boolean(value) : sortKeys(value ?? null));

/** Hanya kolom yang nilainya berbeda dari data lama. */
const changedColumns = (before, columns) =>
  Object.fromEntries(
    Object.entries(columns).filter(
      ([key, value]) => JSON.stringify(normalize(key, before[key])) !== JSON.stringify(normalize(key, value)),
    ),
  );

const invalid = (field, message) => AppError.badRequest('Data yang dikirim tidak valid', [{ field, message }]);

export function createCatalogService({ repository = catalogRepository, auditor = audit } = {}) {
  async function findOrFail(find, code, label) {
    const row = await find(code);
    if (!row) throw AppError.notFound(`${label} ${code} tidak ditemukan`);
    return row;
  }

  async function assertTestPoint(code) {
    if (code !== undefined && !(await repository.findTestPoint(code))) {
      throw invalid('titik_uji', `Titik uji "${code}" tidak dikenal`);
    }
  }

  return {
    /** Katalog lengkap termasuk butir nonaktif (ditandai `aktif: false`). */
    async getCatalog() {
      const { meta, testPoints, functions, controls, methods } = await repository.getAll();
      const methodsByControl = Map.groupBy(methods, (m) => m.controlId);
      const controlsByFunction = Map.groupBy(controls, (c) => c.functionId);
      return {
        schema_version: meta?.schemaVersion ?? 1,
        sumber: { peraturan: meta?.regulation ?? '', bagian: meta?.section ?? '', catatan: meta?.notes ?? [] },
        titik_uji: testPoints.map((t) => ({ id: t.code, nama: t.name })),
        fungsi_keamanan: functions.map((f) => ({
          id: f.code,
          nomor: f.number,
          nama: f.name,
          kontrol: (controlsByFunction.get(f.id) ?? []).map((c) => toControlDto(c, methodsByControl.get(c.id))),
        })),
      };
    },

    async createControl(functionCode, data) {
      const fn = await findOrFail(repository.findFunctionByCode, functionCode, 'Fungsi keamanan');
      const code = `${fn.code}-${data.nomor_referensi}`;
      try {
        const row = await repository.createControl({
          code,
          functionId: fn.id,
          refNumber: data.nomor_referensi,
          ...toColumns(data, CONTROL_COLUMNS),
          sort: await repository.nextControlSort(fn.id),
        });
        auditor('katalog.kontrol.tambah', { kode: code, uraian: data.uraian });
        return toControlDto(row);
      } catch (error) {
        if (isDuplicateEntry(error)) throw AppError.conflict(`Kontrol ${code} sudah ada`, [{ field: 'nomor_referensi', message: `Kontrol ${code} sudah ada` }]);
        throw error;
      }
    },

    async updateControl(code, data) {
      const before = await findOrFail(repository.findControlByCode, code, 'Kontrol');
      const changes = changedColumns(before, toColumns(data, CONTROL_COLUMNS));
      if (!Object.keys(changes).length) return toControlDto(before);
      const row = await repository.updateControl(before.id, changes);
      auditor('katalog.kontrol.ubah', { kode: code, kolom: Object.keys(changes) });
      return toControlDto(row);
    },

    /** Kode metode berikutnya: <KONTROL>-Tnn (nomor terbesar + 1). */
    async createMethod(controlCode, data) {
      const control = await findOrFail(repository.findControlByCode, controlCode, 'Kontrol');
      await assertTestPoint(data.titik_uji);
      const numbers = (await repository.listMethodCodes(control.id))
        .map((c) => Number(c.match(/-T(\d+)$/)?.[1] ?? 0))
        .filter(Number.isFinite);
      const code = `${control.code}-T${String(Math.max(0, ...numbers) + 1).padStart(2, '0')}`;
      const row = await repository.createMethod({
        code,
        controlId: control.id,
        ...toColumns(data, METHOD_COLUMNS),
        sort: await repository.nextMethodSort(control.id),
      });
      auditor('katalog.metode.tambah', { kode: code, nama: data.nama });
      return toMethodDto(row);
    },

    async updateMethod(code, data) {
      const before = await findOrFail(repository.findMethodByCode, code, 'Metode');
      await assertTestPoint(data.titik_uji);
      const changes = changedColumns(before, toColumns(data, METHOD_COLUMNS));
      if (!Object.keys(changes).length) return toMethodDto(before);
      const row = await repository.updateMethod(before.id, changes);
      auditor('katalog.metode.ubah', { kode: code, kolom: Object.keys(changes) });
      return toMethodDto(row);
    },
  };
}

export const catalogService = createCatalogService();
