import { eq } from 'drizzle-orm';
import { db, pool } from '../../db/index.js';
import { applications, units } from '../../db/schema.js';
import { likePattern } from '../../utils/likePattern.js';

// Baris aplikasi + nama satuan (`unit`) untuk DTO.
const columns = {
  id: applications.id,
  name: applications.name,
  description: applications.description,
  unitId: applications.unitId,
  unit: units.name,
  ownerId: applications.ownerId,
  picName: applications.picName,
  picContact: applications.picContact,
  baseUrl: applications.baseUrl,
  environment: applications.environment,
  dataClassification: applications.dataClassification,
  techFrontend: applications.techFrontend,
  techBackend: applications.techBackend,
  techDatabase: applications.techDatabase,
  techServer: applications.techServer,
  archivedAt: applications.archivedAt,
  createdAt: applications.createdAt,
  updatedAt: applications.updatedAt,
};

const withUnit = eq(units.id, applications.unitId);

// --- Daftar aplikasi (SQL langsung): tiap baris digabung dengan scan SELESAI terakhirnya (alias `f`) yang
// menyimpan putusan, skor, dan jumlah temuan (diisi verdict.service), sehingga filter & urut dikerjakan di DB.

const SCAN_SELESAI_TERAKHIR = `(SELECT s.id FROM scans s WHERE s.application_id = a.id AND s.status = 'selesai'
  ORDER BY s.finished_at DESC, s.id DESC LIMIT 1)`;
const UJI_TERAKHIR = '(SELECT MAX(s.started_at) FROM scans s WHERE s.application_id = a.id)';
const BERJALAN = "EXISTS(SELECT 1 FROM scans s WHERE s.application_id = a.id AND s.status = 'berjalan')";
const DARI = `FROM applications a
  JOIN units u ON u.id = a.unit_id
  LEFT JOIN scans f ON f.id = ${SCAN_SELESAI_TERAKHIR}`;

/** Kolom urut → ekspresi SQL (whitelist; tidak pernah dari input mentah). Enum diurutkan menurut urutan definisinya. */
const URUT = {
  nama: ['a.name'],
  satuan: ['u.name', 'a.name'],
  lingkungan: ['a.environment'],
  klasifikasi: ['a.data_classification'],
  skor: ['f.score'],
  // Temuan: kritis dulu, lalu tinggi, sedang, rendah (leksikografis).
  temuan: ['f.findings_critical', 'f.findings_high', 'f.findings_medium', 'f.findings_low'],
  uji: [UJI_TERAKHIR],
  dibuat: ['a.created_at'],
};
// Kolom yang bisa kosong (belum diuji) selalu ditaruh di akhir, apa pun arah urutnya.
const BISA_KOSONG = new Set(['skor', 'temuan', 'uji']);

function orderBy(sort, order) {
  const arah = order === 'asc' ? 'ASC' : 'DESC';
  const ekspresi = URUT[sort] ?? URUT.dibuat;
  const bagian = BISA_KOSONG.has(sort) ? [`(${ekspresi[0]} IS NULL) ASC`] : [];
  return [...bagian, ...ekspresi.map((e) => `${e} ${arah}`), 'a.id DESC'].join(', ');
}

/** Status arsip → kondisi SQL. 'aktif' (bawaan) menyembunyikan aplikasi terarsip; 'semua' tanpa filter. */
function kondisiArsip(arsip = 'aktif') {
  if (arsip === 'arsip') return 'a.archived_at IS NOT NULL';
  if (arsip === 'semua') return null;
  return 'a.archived_at IS NULL';
}

/** WHERE + parameter. `tanpaPutusan`: abaikan filter putusan (untuk hitungan per putusan). */
function where({ unitId, search, lingkungan, klasifikasi, satuanId, putusan, arsip }, { tanpaPutusan = false } = {}) {
  const conds = [];
  const params = [];
  const tambah = (sql, ...nilai) => {
    conds.push(sql);
    params.push(...nilai);
  };
  const ar = kondisiArsip(arsip);
  if (ar) tambah(ar);
  // Cakupan satuan (pemilik); undefined = semua satuan (asesor/admin).
  if (unitId) tambah('a.unit_id = ?', unitId);
  if (search) {
    const pola = likePattern(search);
    tambah('(a.name LIKE ? OR a.base_url LIKE ? OR u.name LIKE ? OR a.pic_name LIKE ?)', pola, pola, pola, pola);
  }
  if (lingkungan) tambah('a.environment = ?', lingkungan);
  if (klasifikasi) tambah('a.data_classification = ?', klasifikasi);
  if (satuanId) tambah('a.unit_id = ?', satuanId);
  if (putusan && !tanpaPutusan) {
    if (putusan === 'belum') tambah('f.id IS NULL');
    else tambah('f.verdict = ?', putusan);
  }
  return { sql: conds.length ? `WHERE ${conds.join(' AND ')}` : '', params };
}

export const applicationsRepository = {
  /**
   * Halaman daftar aplikasi beserta ringkasan pengujian terakhir.
   * @returns {{ rows: object[], total: number }}
   */
  async list({ offset, limit, sort = 'dibuat', order = 'desc', ...filters }) {
    const w = where(filters);
    const [[rows], [[{ total }]]] = await Promise.all([
      pool.query(
        `SELECT a.id, a.name, a.description, a.unit_id AS unitId, u.name AS unit, a.owner_id AS ownerId,
                a.pic_name AS picName, a.pic_contact AS picContact, a.base_url AS baseUrl,
                a.environment, a.data_classification AS dataClassification,
                a.tech_frontend AS techFrontend, a.tech_backend AS techBackend,
                a.tech_database AS techDatabase, a.tech_server AS techServer,
                a.archived_at AS archivedAt, a.created_at AS createdAt, a.updated_at AS updatedAt,
                ${UJI_TERAKHIR} AS lastScanAt, ${BERJALAN} AS running,
                f.id AS finishedScanId, f.finished_at AS finishedAt, f.verdict, f.score,
                f.findings_critical AS findingsCritical, f.findings_high AS findingsHigh,
                f.findings_medium AS findingsMedium, f.findings_low AS findingsLow
         ${DARI} ${w.sql}
         ORDER BY ${orderBy(sort, order)}
         LIMIT ? OFFSET ?`,
        [...w.params, limit, offset],
      ),
      pool.query(`SELECT COUNT(*) AS total ${DARI} ${w.sql}`, w.params),
    ]);
    return { rows, total: Number(total) };
  },

  /** Jumlah aplikasi per putusan (filter lain tetap berlaku) — untuk strip statistik/facet. */
  async countByVerdict(filters) {
    const w = where(filters, { tanpaPutusan: true });
    const [rows] = await pool.query(
      `SELECT COALESCE(f.verdict, IF(f.id IS NULL, 'belum', NULL)) AS putusan, COUNT(*) AS n
       ${DARI} ${w.sql} GROUP BY putusan`,
      w.params,
    );
    return rows;
  },

  /** Satuan yang punya aplikasi dalam cakupan (opsi filter satuan), mengikuti filter arsip. */
  async unitsWithApplications({ unitId, arsip }) {
    const conds = [kondisiArsip(arsip), unitId ? 'a.unit_id = ?' : null].filter(Boolean);
    const [rows] = await pool.query(
      `SELECT u.id, u.name, COUNT(*) AS n FROM applications a JOIN units u ON u.id = a.unit_id
       ${conds.length ? `WHERE ${conds.join(' AND ')}` : ''} GROUP BY u.id, u.name ORDER BY u.name`,
      unitId ? [unitId] : [],
    );
    return rows;
  },

  /** Aplikasi ber-URL dasar tertentu (untuk pesan duplikat yang menyebut bila aset itu terarsip). */
  async findByBaseUrl(baseUrl) {
    const [row] = await db.select(columns).from(applications).innerJoin(units, withUnit).where(eq(applications.baseUrl, baseUrl)).limit(1);
    return row ?? null;
  },

  /** True bila aplikasi masih punya scan berstatus 'berjalan'. */
  async adaScanBerjalan(id) {
    const [[row]] = await pool.query(
      "SELECT EXISTS(SELECT 1 FROM scans WHERE application_id = ? AND status = 'berjalan') AS ada",
      [id],
    );
    return Boolean(Number(row.ada));
  },

  /** Tandai/lepas arsip. `waktu` null = pulihkan. */
  async setArsip(id, waktu) {
    await db.update(applications).set({ archivedAt: waktu }).where(eq(applications.id, id));
    return this.findById(id);
  },

  async findById(id) {
    const [row] = await db.select(columns).from(applications).innerJoin(units, withUnit).where(eq(applications.id, id)).limit(1);
    return row ?? null;
  },

  /** @throws galat MySQL ER_DUP_ENTRY bila URL dasar sudah terdaftar. */
  async create(data) {
    const [result] = await db.insert(applications).values(data);
    return this.findById(result.insertId);
  },

  async update(id, data) {
    await db.update(applications).set(data).where(eq(applications.id, id));
    return this.findById(id);
  },
};
