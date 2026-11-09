import { pool } from '../../db/index.js';

// Data untuk menghitung ringkasan penilaian scan (lihat verdict.service.js).
export const verdictRepository = {
  /** Kontrol aktif katalog × metode aktifnya (kontrol tanpa metode aktif tetap muncul dengan methodCode NULL). */
  async controls() {
    const [rows] = await pool.query(
      `SELECT c.code AS controlCode, c.default_severity AS controlSeverity, c.aggregation,
              m.code AS methodCode, m.severity AS methodSeverity
       FROM catalog_controls c
       LEFT JOIN catalog_methods m ON m.control_id = c.id AND m.is_active = TRUE
       WHERE c.is_active = TRUE`,
    );
    return rows;
  },

  /** Status hasil tiap task selesai + severity metodenya (NULL untuk task di luar katalog, mis. penemuan). */
  async taskResults(scanIds) {
    const [rows] = await pool.query(
      `SELECT t.scan_id AS scanId, t.method_code AS methodCode, m.severity,
              JSON_UNQUOTE(JSON_EXTRACT(t.result, '$.status')) AS status
       FROM scan_tasks t
       LEFT JOIN catalog_methods m ON m.code = t.method_code
       WHERE t.scan_id IN (?) AND t.status = 'selesai'`,
      [scanIds],
    );
    return rows;
  },

  /** Scan selesai yang ringkasannya belum dihitung (terbaru dulu: yang tampil di daftar aplikasi). */
  async finishedWithoutVerdict(limit) {
    const [rows] = await pool.query(
      "SELECT id FROM scans WHERE status = 'selesai' AND verdict IS NULL ORDER BY id DESC LIMIT ?",
      [limit],
    );
    return rows.map((r) => Number(r.id));
  },

  async saveSummary(scanId, { verdict, score, temuan }) {
    await pool.query(
      `UPDATE scans SET verdict = ?, score = ?, findings_critical = ?, findings_high = ?, findings_medium = ?,
              findings_low = ? WHERE id = ?`,
      [verdict, score, temuan.kritis, temuan.tinggi, temuan.sedang, temuan.rendah, scanId],
    );
  },
};
