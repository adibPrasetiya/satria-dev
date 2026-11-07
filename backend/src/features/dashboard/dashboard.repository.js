import { pool } from '../../db/index.js';

// Data mentah untuk peta Indeks Ketahanan Keamanan Siber. SQL langsung (mysql2): tiga query ringan,
// agregasinya dikerjakan di dashboard.service agar mudah diuji tanpa DB.
export const dashboardRepository = {
  /** Semua satuan aktif (pohon kecil; dipakai untuk mencari induk terdekat yang punya lokasi). */
  async satuan() {
    const [rows] = await pool.query(
      `SELECT id, parent_id AS parentId, name, type, province_code AS provinceCode, latitude, longitude
       FROM units WHERE is_active = TRUE`,
    );
    return rows;
  },

  /** Tiap aplikasi + scan SELESAI terakhirnya (null bila belum pernah selesai diuji). */
  async aplikasiDanScanTerakhir() {
    const [rows] = await pool.query(
      `SELECT a.id AS aplikasiId, a.unit_id AS unitId,
              (SELECT s.id FROM scans s
               WHERE s.application_id = a.id AND s.status = 'selesai'
               ORDER BY s.finished_at DESC, s.id DESC LIMIT 1) AS scanId
       FROM applications a`,
    );
    return rows;
  },

  /** Hasil metode (lulus/gagal saja) dari scan-scan tertentu, beserta nama & severity metode di katalog. */
  async hasilMetode(scanIds) {
    if (!scanIds.length) return [];
    const [rows] = await pool.query(
      `SELECT t.scan_id AS scanId, t.method_code AS kode, m.name AS nama, m.severity AS severity,
              JSON_UNQUOTE(JSON_EXTRACT(t.result, '$.status')) AS status
       FROM scan_tasks t
       LEFT JOIN catalog_methods m ON m.code = t.method_code
       WHERE t.scan_id IN (?) AND t.status = 'selesai'
         AND JSON_UNQUOTE(JSON_EXTRACT(t.result, '$.status')) IN ('lulus', 'gagal')`,
      [scanIds],
    );
    return rows;
  },
};
