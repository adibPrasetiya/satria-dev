import { and, eq, inArray, isNull } from 'drizzle-orm';
import { db, pool } from '../../db/index.js';
import { aplikasiKomponen, applications } from '../../db/schema.js';
import { likePattern } from '../../utils/likePattern.js';

const POTONGAN = 400;
const potong = (arr, n = POTONGAN) => Array.from({ length: Math.ceil(arr.length / n) }, (_, i) => arr.slice(i * n, i * n + n));

const AKTIF = ['terdampak', 'kemungkinan'];

// Baris hasil + data CVE + aset untuk daftar/UI.
const KOLOM_DAFTAR = `k.id, k.application_id AS applicationId, a.name AS aplikasi, a.unit_id AS unitId, u.name AS satuan,
  a.environment, a.data_classification AS dataClassification,
  k.cve_id AS cveId, k.vendor, k.produk, k.nama_komponen AS namaKomponen, k.versi, k.sumber_komponen AS sumberKomponen,
  k.status, k.alasan, k.prioritas, k.catatan, k.ditangani_oleh AS ditanganiOleh, du.name AS ditanganiNama,
  k.ditangani_pada AS ditanganiPada, k.pertama_ditemukan AS pertamaDitemukan, k.terakhir_dievaluasi AS terakhirDievaluasi,
  c.ringkasan, c.dipublikasi_pada AS dipublikasiPada, c.diubah_pada AS diubahPada, c.cvss_skor AS cvssSkor,
  c.cvss_vektor AS cvssVektor, c.severitas, c.cwe, c.referensi, c.status_analisis AS statusAnalisis, c.kev,
  c.kev_ditambahkan AS kevDitambahkan, c.kev_tenggat AS kevTenggat, c.kev_ransomware AS kevRansomware,
  c.epss, c.epss_persentil AS epssPersentil, c.sumber AS sumberCve`;
const DARI = `FROM aset_kerentanan k
  JOIN cve c ON c.id = k.cve_id
  JOIN applications a ON a.id = k.application_id
  JOIN units u ON u.id = a.unit_id
  LEFT JOIN users du ON du.id = k.ditangani_oleh`;

function where({ unitId, applicationId, status, kev, severitas, search }) {
  const kondisi = ['a.archived_at IS NULL'];
  const params = [];
  const tambah = (k, ...v) => {
    kondisi.push(k);
    params.push(...v);
  };
  if (unitId) tambah('a.unit_id = ?', unitId);
  if (applicationId) tambah('k.application_id = ?', applicationId);
  const daftarStatus = status?.length ? status : AKTIF;
  kondisi.push(`k.status IN (${daftarStatus.map(() => '?').join(', ')})`);
  params.push(...daftarStatus);
  if (kev) kondisi.push('c.kev = 1');
  if (severitas) tambah('c.severitas = ?', severitas);
  if (search) {
    kondisi.push('(k.cve_id LIKE ? OR k.nama_komponen LIKE ? OR a.name LIKE ? OR c.ringkasan LIKE ?)');
    const pola = likePattern(search);
    params.push(pola, pola, pola, pola);
  }
  return { sql: `WHERE ${kondisi.join(' AND ')}`, params };
}

const URUT = {
  prioritas: 'k.prioritas DESC, c.kev DESC, k.pertama_ditemukan DESC',
  terbaru: 'k.pertama_ditemukan DESC, k.prioritas DESC',
  publikasi: 'c.dipublikasi_pada DESC, k.prioritas DESC',
};

export const kerentananRepository = {
  /** Komponen aplikasi aktif (semua aplikasi bila `applicationIds` kosong) + konteks aset untuk prioritas. */
  async komponenAplikasi(applicationIds) {
    const syarat = [isNull(applications.archivedAt)];
    if (applicationIds?.length) syarat.push(inArray(aplikasiKomponen.applicationId, applicationIds));
    return db
      .select({
        id: aplikasiKomponen.id,
        applicationId: aplikasiKomponen.applicationId,
        vendor: aplikasiKomponen.vendor,
        produk: aplikasiKomponen.produk,
        nama: aplikasiKomponen.nama,
        versi: aplikasiKomponen.versi,
        purl: aplikasiKomponen.purl,
        cpe: aplikasiKomponen.cpe,
        sumber: aplikasiKomponen.sumber,
        keyakinan: aplikasiKomponen.keyakinan,
        environment: applications.environment,
        dataClassification: applications.dataClassification,
      })
      .from(aplikasiKomponen)
      .innerJoin(applications, eq(applications.id, aplikasiKomponen.applicationId))
      .where(and(...syarat));
  },

  async idAplikasiAktif() {
    const rows = await db.select({ id: applications.id }).from(applications).where(isNull(applications.archivedAt));
    return rows.map((r) => r.id);
  },

  /** Rentang CPE untuk pasangan [vendor, produk] (CVE yang ditolak diabaikan). */
  async cpeUntukPasangan(pasangan) {
    const hasil = [];
    for (const bagian of potong(pasangan)) {
      if (!bagian.length) continue;
      const [rows] = await pool.query(
        `SELECT p.cve_id AS cveId, p.vendor, p.produk, p.versi, p.versi_mulai_incl AS versiMulaiIncl,
                p.versi_mulai_excl AS versiMulaiExcl, p.versi_akhir_incl AS versiAkhirIncl, p.versi_akhir_excl AS versiAkhirExcl
         FROM cve_cpe p JOIN cve c ON c.id = p.cve_id
         WHERE c.status_analisis <> 'ditolak' AND (p.vendor, p.produk) IN (${bagian.map(() => '(?, ?)').join(', ')})`,
        bagian.flat(),
      );
      hasil.push(...rows);
    }
    return hasil;
  },

  /** Hasil OSV positif untuk purl berversi ("pkg:npm/jquery@3.4.1"). */
  async paketUntuk(purlBerversi) {
    const hasil = [];
    for (const bagian of potong(purlBerversi)) {
      if (!bagian.length) continue;
      const [rows] = await pool.query(
        `SELECT p.cve_id AS cveId, p.purl, p.versi FROM cve_paket p JOIN cve c ON c.id = p.cve_id
         WHERE c.status_analisis <> 'ditolak' AND CONCAT(p.purl, '@', p.versi) IN (${bagian.map(() => '?').join(', ')})`,
        bagian,
      );
      hasil.push(...rows);
    }
    return hasil;
  },

  async infoCve(ids) {
    const peta = new Map();
    for (const bagian of potong(ids)) {
      if (!bagian.length) continue;
      const [rows] = await pool.query(
        `SELECT id, kev, epss, cvss_skor AS cvssSkor, severitas, dipublikasi_pada AS dipublikasiPada FROM cve WHERE id IN (${bagian.map(() => '?').join(', ')})`,
        bagian,
      );
      for (const r of rows) peta.set(r.id, { ...r, kev: Boolean(r.kev) });
    }
    return peta;
  },

  /** Kunci hasil yang sudah ada untuk aplikasi: "cveId|produk" → status. */
  async kunciHasil(applicationId) {
    const [rows] = await pool.query('SELECT cve_id AS cveId, produk, status FROM aset_kerentanan WHERE application_id = ?', [
      applicationId,
    ]);
    return new Map(rows.map((r) => [`${r.cveId}|${r.produk}`, r.status]));
  },

  /**
   * Simpan hasil pencocokan satu aplikasi. Status manual (ditangani/dikecualikan) dipertahankan; hasil otomatis
   * yang tak muncul lagi menjadi 'kedaluwarsa'.
   */
  async simpanHasil(applicationId, hasil, waktu) {
    const conn = await pool.getConnection();
    try {
      await conn.beginTransaction();
      for (const bagian of potong(hasil, 200)) {
        if (!bagian.length) continue;
        await conn.query(
          `INSERT INTO aset_kerentanan
             (application_id, cve_id, vendor, produk, nama_komponen, versi, sumber_komponen, status, alasan, prioritas,
              pertama_ditemukan, terakhir_dievaluasi)
           VALUES ${bagian.map(() => '(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)').join(', ')}
           ON DUPLICATE KEY UPDATE
             vendor = VALUES(vendor), nama_komponen = VALUES(nama_komponen), versi = VALUES(versi),
             sumber_komponen = VALUES(sumber_komponen), alasan = VALUES(alasan), prioritas = VALUES(prioritas),
             status = IF(status IN ('ditangani', 'dikecualikan'), status, VALUES(status)),
             terakhir_dievaluasi = VALUES(terakhir_dievaluasi)`,
          bagian.flatMap((h) => [
            applicationId,
            h.cveId,
            h.vendor,
            h.produk,
            h.namaKomponen,
            h.versi,
            h.sumberKomponen,
            h.status,
            h.alasan,
            h.prioritas,
            waktu,
            waktu,
          ]),
        );
      }
      await conn.query(
        `UPDATE aset_kerentanan
         SET status = 'kedaluwarsa', alasan = 'Tidak lagi cocok dengan komponen aset (versi diperbarui atau komponen dihapus).'
         WHERE application_id = ? AND status IN ('terdampak', 'kemungkinan') AND terakhir_dievaluasi < ?`,
        [applicationId, waktu],
      );
      await conn.commit();
    } catch (error) {
      await conn.rollback();
      throw error;
    } finally {
      conn.release();
    }
  },

  async list({ offset, limit, sort = 'prioritas', ...filters }) {
    const w = where(filters);
    const [[rows], [[{ total }]]] = await Promise.all([
      pool.query(`SELECT ${KOLOM_DAFTAR} ${DARI} ${w.sql} ORDER BY ${URUT[sort] ?? URUT.prioritas}, k.id DESC LIMIT ? OFFSET ?`, [
        ...w.params,
        limit,
        offset,
      ]),
      pool.query(`SELECT COUNT(*) AS total ${DARI} ${w.sql}`, w.params),
    ]);
    return { rows, total: Number(total) };
  },

  async findById(id) {
    const [[row]] = await pool.query(`SELECT ${KOLOM_DAFTAR} ${DARI} WHERE k.id = ?`, [id]);
    return row ?? null;
  },

  async ubahStatus(id, { status, catatan, oleh }) {
    const manual = status === 'ditangani' || status === 'dikecualikan';
    await pool.query(
      `UPDATE aset_kerentanan SET status = ?, catatan = ?, ditangani_oleh = ?, ditangani_pada = ? WHERE id = ?`,
      [status, catatan ?? null, manual ? oleh : null, manual ? new Date() : null, id],
    );
  },

  /** Ringkasan untuk strip statistik/dasbor (aset aktif dalam cakupan `unitId`). */
  async ringkasan({ unitId, applicationId } = {}) {
    const params = [];
    let cakupan = 'a.archived_at IS NULL';
    if (unitId) {
      cakupan += ' AND a.unit_id = ?';
      params.push(unitId);
    }
    if (applicationId) {
      cakupan += ' AND k.application_id = ?';
      params.push(applicationId);
    }
    const [[r]] = await pool.query(
      `SELECT
         SUM(k.status = 'terdampak') AS terdampak,
         SUM(k.status = 'kemungkinan') AS kemungkinan,
         SUM(k.status = 'ditangani') AS ditangani,
         SUM(k.status = 'dikecualikan') AS dikecualikan,
         SUM(k.status IN ('terdampak', 'kemungkinan') AND c.kev = 1) AS kev,
         SUM(k.status IN ('terdampak', 'kemungkinan') AND c.severitas = 'kritis') AS kritis,
         SUM(k.status IN ('terdampak', 'kemungkinan') AND k.pertama_ditemukan >= NOW() - INTERVAL 7 DAY) AS baru7hari,
         COUNT(DISTINCT IF(k.status IN ('terdampak', 'kemungkinan'), k.application_id, NULL)) AS aplikasi
       FROM aset_kerentanan k JOIN cve c ON c.id = k.cve_id JOIN applications a ON a.id = k.application_id
       WHERE ${cakupan}`,
      params,
    );
    return Object.fromEntries(Object.entries(r).map(([k, v]) => [k, Number(v ?? 0)]));
  },

  /** Kecocokan 'terdampak' yang belum diberitahukan dan mendesak (KEV atau kritis), dengan email pemilik aset. */
  async untukNotifikasi() {
    const [rows] = await pool.query(
      `SELECT k.id, k.application_id AS applicationId, a.name AS aplikasi, o.email, o.name AS pemilik,
              k.cve_id AS cveId, k.nama_komponen AS namaKomponen, k.versi, c.kev, c.severitas, c.cvss_skor AS cvssSkor,
              c.ringkasan
       FROM aset_kerentanan k JOIN cve c ON c.id = k.cve_id JOIN applications a ON a.id = k.application_id
       JOIN users o ON o.id = a.owner_id AND o.is_active = 1
       WHERE a.archived_at IS NULL AND k.status = 'terdampak' AND k.diberitahu_pada IS NULL
         AND (c.kev = 1 OR c.severitas = 'kritis')
       ORDER BY k.prioritas DESC`,
    );
    return rows;
  },

  async tandaiDiberitahu(ids) {
    for (const bagian of potong(ids)) {
      if (bagian.length) await pool.query(`UPDATE aset_kerentanan SET diberitahu_pada = NOW() WHERE id IN (?)`, [bagian]);
    }
  },
};
