import { pool } from '../../db/index.js';

// Data penyusunan laporan AI & penyimpanannya di scans.ai_analysis.
export const laporanRepository = {
  /** Task pengujian scan (tanpa penemuan) + metadata katalog metode/kontrol/fungsi. */
  async metodeScan(scanId) {
    const [rows] = await pool.query(
      `SELECT t.method_code AS methodCode, t.status, t.result,
              m.name AS methodName, m.severity, m.pass_criteria AS passCriteria, m.test_point AS testPoint,
              c.ref_number AS controlRef, c.description AS controlDescription,
              f.code AS functionCode, f.name AS functionName
       FROM scan_tasks t
       LEFT JOIN catalog_methods m ON m.code = t.method_code
       LEFT JOIN catalog_controls c ON c.id = m.control_id
       LEFT JOIN catalog_functions f ON f.id = c.function_id
       WHERE t.scan_id = ? AND t.engine <> 'discovery'
       ORDER BY f.sort, c.sort, m.sort, t.id`,
      [scanId],
    );
    return rows.map((r) => ({ ...r, result: typeof r.result === 'string' ? JSON.parse(r.result) : r.result }));
  },

  /** Regulasi acuan katalog (sampul & konteks AI). */
  async acuan() {
    const [rows] = await pool.query('SELECT regulation FROM catalog_meta ORDER BY id DESC LIMIT 1');
    return rows[0]?.regulation ?? '';
  },

  /** Username akun uji tersimpan untuk aplikasi (hanya untuk disamarkan dari teks; sandi tak dibaca). */
  async akunUji(applicationId) {
    const [rows] = await pool.query('SELECT accounts FROM scan_targets WHERE application_id = ?', [applicationId]);
    let acc = rows[0]?.accounts;
    if (typeof acc === 'string') acc = JSON.parse(acc);
    if (!acc) return [];
    const daftar = Array.isArray(acc.daftar) ? acc.daftar : [acc.utama, acc.penguncian];
    return daftar.map((a) => a?.username).filter(Boolean);
  },

  /** ID scan SELESAI terakhir sebuah aplikasi (null bila belum ada). */
  async scanSelesaiTerakhir(applicationId) {
    const [rows] = await pool.query(
      `SELECT id FROM scans WHERE application_id = ? AND status = 'selesai'
       ORDER BY finished_at DESC, id DESC LIMIT 1`,
      [applicationId],
    );
    return rows[0] ? Number(rows[0].id) : null;
  },

  /** Simpan laporan untuk scan ini dan hapus laporan tersimpan pada scan lain aplikasi yang sama. */
  async simpan(applicationId, scanId, analisis) {
    await pool.query('UPDATE scans SET ai_analysis = ? WHERE id = ?', [JSON.stringify(analisis), scanId]);
    await pool.query('UPDATE scans SET ai_analysis = NULL WHERE application_id = ? AND id <> ? AND ai_analysis IS NOT NULL', [
      applicationId,
      scanId,
    ]);
  },

};
