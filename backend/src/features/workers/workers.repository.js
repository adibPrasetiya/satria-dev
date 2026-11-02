import { pool } from '../../db/index.js';

// Akses data registry worker & antrean task. SQL langsung (mysql2) agar waktu selalu UTC_TIMESTAMP()
// — dibandingkan dengan `locked_at` yang juga ditulis UTC (lihat scans.repository.claimNextTask).
export const workersRepository = {
  /** Upsert status worker (heartbeat/klaim). `mulai_pada` hanya diisi saat baris dibuat. */
  async upsert({ id, engines, status, taskId = null, scanId = null, tahap = null, versi = null, host = null }) {
    await pool.query(
      `INSERT INTO workers (id, engines, status, task_id, scan_id, tahap, versi, host, mulai_pada, terakhir_terlihat)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, UTC_TIMESTAMP(), UTC_TIMESTAMP())
       ON DUPLICATE KEY UPDATE
         -- Dievaluasi PERTAMA (memakai nilai lama): worker yang hidup lagi setelah berhenti/lama hilang → sesi baru.
         mulai_pada = IF(status = 'berhenti' OR terakhir_terlihat < UTC_TIMESTAMP() - INTERVAL 5 MINUTE, UTC_TIMESTAMP(), mulai_pada),
         engines = VALUES(engines), status = VALUES(status), task_id = VALUES(task_id),
         scan_id = VALUES(scan_id), tahap = VALUES(tahap), versi = COALESCE(VALUES(versi), versi),
         host = COALESCE(VALUES(host), host), terakhir_terlihat = UTC_TIMESTAMP()`,
      [id.slice(0, 100), JSON.stringify(engines ?? []), status, taskId, scanId, tahap?.slice(0, 120) ?? null, versi, host],
    );
  },

  async setStatus(id, status, { taskId = null, scanId = null, tahap = null } = {}) {
    await pool.query(
      'UPDATE workers SET status = ?, task_id = ?, scan_id = ?, tahap = ?, terakhir_terlihat = UTC_TIMESTAMP() WHERE id = ?',
      [status, taskId, scanId, tahap, id],
    );
  },

  /** Perpanjang lease task yang sedang dikerjakan worker ini. */
  async perpanjangLease(taskId, workerId) {
    await pool.query(
      "UPDATE scan_tasks SET locked_at = UTC_TIMESTAMP() WHERE id = ? AND locked_by = ? AND status = 'berjalan'",
      [taskId, workerId.slice(0, 100)],
    );
  },

  /** Status scan pemilik task (untuk sinyal pembatalan ke worker). */
  async scanUntukTask(taskId) {
    const [rows] = await pool.query(
      'SELECT t.scan_id AS scanId, s.status AS scanStatus FROM scan_tasks t JOIN scans s ON s.id = t.scan_id WHERE t.id = ?',
      [taskId],
    );
    return rows[0] ?? null;
  },

  /** Semua worker yang terlihat 24 jam terakhir + umur heartbeat (detik) + aplikasi yang dikerjakan. */
  async daftar() {
    const [rows] = await pool.query(
      `SELECT w.id, w.engines, w.status, w.task_id AS taskId, w.scan_id AS scanId, w.tahap, w.versi, w.host,
              w.mulai_pada AS mulaiPada, w.terakhir_terlihat AS terakhirTerlihat,
              TIMESTAMPDIFF(SECOND, w.terakhir_terlihat, UTC_TIMESTAMP()) AS umurDetik,
              a.id AS aplikasiId, a.name AS aplikasi, a.unit_id AS unitId
       FROM workers w
       LEFT JOIN scans s ON s.id = w.scan_id
       LEFT JOIN applications a ON a.id = s.application_id
       WHERE w.terakhir_terlihat > UTC_TIMESTAMP() - INTERVAL 1 DAY
       ORDER BY w.id`,
    );
    return rows.map((r) => ({ ...r, engines: typeof r.engines === 'string' ? JSON.parse(r.engines) : r.engines ?? [] }));
  },

  /** Task yang belum selesai pada scan berjalan, urut antrean (sama dengan urutan klaim: t.id). */
  async taskAktif() {
    const [rows] = await pool.query(
      `SELECT t.id, t.scan_id AS scanId, t.engine, t.status, s.application_id AS aplikasiId, a.name AS aplikasi, a.unit_id AS unitId
       FROM scan_tasks t
       JOIN scans s ON s.id = t.scan_id
       JOIN applications a ON a.id = s.application_id
       WHERE s.status = 'berjalan' AND t.status IN ('antre', 'berjalan')
       ORDER BY t.id`,
    );
    return rows;
  },

  /** Rata-rata durasi task per engine (500 task selesai terakhir) — dasar perkiraan waktu tunggu. */
  async rataDurasi() {
    const [rows] = await pool.query(
      `SELECT engine, AVG(duration_ms) AS rata FROM (
         SELECT engine, duration_ms FROM scan_tasks
         WHERE status = 'selesai' AND duration_ms IS NOT NULL AND duration_ms > 0
         ORDER BY id DESC LIMIT 500
       ) x GROUP BY engine`,
    );
    return Object.fromEntries(rows.map((r) => [r.engine, Number(r.rata)]));
  },

  /** Scan yang masih berjalan untuk satu aplikasi (penjaga satu pengujian aktif per aplikasi). */
  async scanAktifAplikasi(applicationId) {
    const [rows] = await pool.query("SELECT id FROM scans WHERE application_id = ? AND status = 'berjalan' ORDER BY id DESC LIMIT 1", [applicationId]);
    return rows[0]?.id ?? null;
  },
};
