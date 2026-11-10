import { pool } from '../../db/index.js';

// Data mentah untuk peta Indeks Ketahanan Keamanan Siber. SQL langsung (mysql2): dua query ringan —
// tidak menyentuh scan_tasks karena skor & jumlah temuan sudah tersimpan per scan (lihat
// scans/verdict.service). Agregasi dikerjakan di dashboard.service agar mudah diuji tanpa DB.
export const dashboardRepository = {
  /** Semua satuan aktif (pohon kecil; dipakai untuk mencari induk terdekat yang punya lokasi). */
  async satuan() {
    const [rows] = await pool.query(
      `SELECT id, parent_id AS parentId, name, type, province_code AS provinceCode, latitude, longitude
       FROM units WHERE is_active = TRUE`,
    );
    return rows;
  },

  /** Tiap aplikasi + ringkasan scan SELESAI terakhirnya (skor & jumlah temuan per severity; null bila belum). */
  async aplikasiRingkas() {
    const [rows] = await pool.query(
      `SELECT a.id AS aplikasiId, a.unit_id AS unitId, f.id AS scanId, f.score,
              f.findings_critical AS kritis, f.findings_high AS tinggi,
              f.findings_medium AS sedang, f.findings_low AS rendah
       FROM applications a
       LEFT JOIN scans f ON f.id = (
         SELECT s.id FROM scans s
         WHERE s.application_id = a.id AND s.status = 'selesai'
         ORDER BY s.finished_at DESC, s.id DESC LIMIT 1
       )
       WHERE a.archived_at IS NULL`,
    );
    return rows;
  },
};
