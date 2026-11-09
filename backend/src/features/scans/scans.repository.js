import { and, desc, eq, inArray, ne } from 'drizzle-orm';
import { db, pool } from '../../db/index.js';
import { applications, catalogControls, catalogFunctions, catalogMethods, scanLogs, scans, scanTargets, scanTasks } from '../../db/schema.js';

export const scansRepository = {
  // --- Persiapan uji (scan_targets) ---

  async getTarget(applicationId) {
    const [row] = await db.select().from(scanTargets).where(eq(scanTargets.applicationId, applicationId)).limit(1);
    return row ?? null;
  },

  async upsertTarget(applicationId, { testPoints, forms, accounts = null, options = null }) {
    const set = { testPoints, forms, accounts, options };
    await db
      .insert(scanTargets)
      .values({ applicationId, ...set })
      .onDuplicateKeyUpdate({ set });
    return this.getTarget(applicationId);
  },

  /** Simpan akun uji (+opsi) tanpa menimpa test_points/forms/discovery yang sudah ada.
   *  Dipakai jalur otomatis: akun diisi di wizard lalu discovery mengisi sisanya. */
  async mergeAccounts(applicationId, { accounts = null, options = null }) {
    const current = (await this.getTarget(applicationId)) ?? {};
    const set = {
      testPoints: current.testPoints ?? {},
      forms: current.forms ?? {},
      accounts: accounts ?? current.accounts ?? null,
      options: { ...(current.options ?? {}), ...(options ?? {}) },
      discovery: current.discovery ?? null,
    };
    await db
      .insert(scanTargets)
      .values({ applicationId, ...set })
      .onDuplicateKeyUpdate({ set });
    return this.getTarget(applicationId);
  },

  // --- Katalog (hanya yang dibutuhkan seeding) ---

  /** Kontrol + metode aktifnya berdasarkan kode kontrol (mis. 'AUTH-1.3'). */
  async controlWithMethods(controlCode) {
    const [control] = await db.select().from(catalogControls).where(eq(catalogControls.code, controlCode)).limit(1);
    if (!control) return null;
    const methods = await db
      .select()
      .from(catalogMethods)
      .where(and(eq(catalogMethods.controlId, control.id), eq(catalogMethods.isActive, true)));
    return { control, methods };
  },

  /** Semua kontrol aktif sebuah fungsi keamanan (mis. 'AUTH') + metode aktif per kontrol. */
  async functionWithControls(functionCode) {
    const [fn] = await db.select().from(catalogFunctions).where(eq(catalogFunctions.code, functionCode)).limit(1);
    if (!fn) return null;
    const controls = await db
      .select()
      .from(catalogControls)
      .where(and(eq(catalogControls.functionId, fn.id), eq(catalogControls.isActive, true)));
    const out = [];
    for (const control of controls) {
      const methods = await db
        .select()
        .from(catalogMethods)
        .where(and(eq(catalogMethods.controlId, control.id), eq(catalogMethods.isActive, true)));
      for (const method of methods) out.push({ control, method });
    }
    return { function: fn, items: out };
  },

  /** Gabungan metode dari beberapa fungsi keamanan (mis. ['AUTH','SESS']), urut sesuai daftar. */
  async functionsWithControls(functionCodes) {
    const out = [];
    for (const code of functionCodes) {
      const fw = await this.functionWithControls(code);
      if (fw) out.push(...fw.items);
    }
    return { items: out };
  },

  async methodWithControl(methodCode) {
    const [method] = await db.select().from(catalogMethods).where(eq(catalogMethods.code, methodCode)).limit(1);
    if (!method) return null;
    const [control] = await db.select().from(catalogControls).where(eq(catalogControls.id, method.controlId)).limit(1);
    return { method, control: control ?? null };
  },

  // --- Scan ---

  async createScan({ applicationId, profile = 'aman', mode = 'terarah', approach = 'greybox', reconScanId = null }) {
    const [res] = await db.insert(scans).values({ applicationId, profile, mode, approach, reconScanId, status: 'berjalan' });
    return res.insertId;
  },

  /** Simpan ringkasan penemuan ke scan_targets tanpa menimpa nilai manual. */
  async mergeDiscovery(applicationId, { testPoints, forms, discovery }) {
    const current = (await this.getTarget(applicationId)) ?? {};
    const curTP = current.testPoints ?? {};
    const curForms = current.forms ?? {};
    // Manual menang: titik/form yang sudah diisi manual (sumber != 'otomatis') tidak ditimpa.
    const mergedTP = { ...testPoints };
    for (const [k, v] of Object.entries(curTP)) {
      if (v && v.sumber !== 'otomatis') mergedTP[k] = v; // pertahankan manual
    }
    const mergedForms = { ...forms };
    for (const [k, v] of Object.entries(curForms)) {
      if (curTP[k] && curTP[k].sumber !== 'otomatis') mergedForms[k] = v;
    }
    const set = {
      testPoints: mergedTP,
      forms: mergedForms,
      accounts: current.accounts ?? null,
      options: current.options ?? null,
      discovery,
    };
    await db
      .insert(scanTargets)
      .values({ applicationId, ...set })
      .onDuplicateKeyUpdate({ set });
    return this.getTarget(applicationId);
  },

  async insertTasks(rows) {
    if (rows.length) await db.insert(scanTasks).values(rows);
  },

  async findScanById(id) {
    const [row] = await db.select().from(scans).where(eq(scans.id, id)).limit(1);
    return row ?? null;
  },

  /** Scan milik satu aplikasi (terbaru dulu). `applicationIds` membatasi cakupan (pemilik). */
  async listScans({ applicationId, applicationIds }) {
    const conds = [];
    if (applicationId) conds.push(eq(scans.applicationId, applicationId));
    if (applicationIds) conds.push(inArray(scans.applicationId, applicationIds.length ? applicationIds : [-1]));
    return db
      .select()
      .from(scans)
      .where(conds.length ? and(...conds) : undefined)
      .orderBy(desc(scans.startedAt), desc(scans.id))
      .limit(50);
  },

  async tasksByScan(scanId) {
    return db.select().from(scanTasks).where(eq(scanTasks.scanId, scanId));
  },

  /** Jumlah task non-penemuan pada scan (0 = fase pengujian belum disemai). */
  async countTestTasks(scanId) {
    const [row] = await pool.query(
      "SELECT COUNT(*) AS n FROM scan_tasks WHERE scan_id = ? AND engine <> 'discovery'",
      [scanId],
    );
    return Number(row[0]?.n ?? 0);
  },

  async logsByScan(scanId) {
    return db.select().from(scanLogs).where(eq(scanLogs.scanId, scanId)).orderBy(scanLogs.id);
  },

  async insertLog(scanId, level, message, data = null) {
    await db.insert(scanLogs).values({ scanId, level, message: message.slice(0, 500), data });
  },

  /** Hapus laporan AI tersimpan pada scan lain aplikasi (hanya riwayat terakhir yang menyimpan laporan). */
  async hapusLaporanLain(applicationId, kecualiScanId) {
    await pool.query(
      'UPDATE scans SET ai_analysis = NULL WHERE application_id = ? AND id <> ? AND ai_analysis IS NOT NULL',
      [applicationId, kecualiScanId],
    );
  },

  async setScanStatus(id, status, finishedAt) {
    await db.update(scans).set({ status, ...(finishedAt ? { finishedAt } : {}) }).where(eq(scans.id, id));
  },

  /** Saat scan dibatalkan: task yang masih antre diselesaikan dengan hasil "dibatalkan". */
  async finishPendingTasksAsCancelled(scanId) {
    await db
      .update(scanTasks)
      .set({ status: 'selesai', result: { status: 'tidak_dapat_diverifikasi', ringkasan: 'Pengujian dibatalkan.', bukti: [] } })
      .where(and(eq(scanTasks.scanId, scanId), ne(scanTasks.status, 'selesai')));
  },

  // --- Task (dipakai worker lewat /internal) ---

  async findTaskById(id) {
    const [row] = await db.select().from(scanTasks).where(eq(scanTasks.id, id)).limit(1);
    return row ?? null;
  },

  async completeTask(id, { result, durationMs }) {
    await db
      .update(scanTasks)
      .set({ status: 'selesai', result, durationMs: durationMs ?? null, lockedBy: null, lockedAt: null })
      .where(eq(scanTasks.id, id));
  },

  /** Jumlah task yang belum selesai pada sebuah scan (0 = scan boleh difinalisasi). */
  async countUnfinished(scanId) {
    const [row] = await pool.query(
      'SELECT COUNT(*) AS n FROM scan_tasks WHERE scan_id = ? AND status <> ?',
      [scanId, 'selesai'],
    );
    return Number(row[0]?.n ?? 0);
  },

  /**
   * Task yang lease-nya kedaluwarsa (worker mati): dikembalikan ke antrean, atau — bila sudah
   * `maksPercobaan` kali — diselesaikan "tidak dapat diverifikasi" agar tak berputar tanpa akhir.
   * @returns {Promise<{dikembalikan: object[], dihentikan: object[]}>}
   */
  async requeueStale(staleBeforeIso, maksPercobaan = 3) {
    const [rows] = await pool.query(
      "SELECT id, scan_id AS scanId, method_code AS methodCode, locked_by AS lockedBy, attempts FROM scan_tasks WHERE status = 'berjalan' AND locked_at IS NOT NULL AND locked_at < ?",
      [staleBeforeIso],
    );
    const dikembalikan = [];
    const dihentikan = [];
    for (const t of rows) {
      if (t.attempts >= maksPercobaan) {
        const ringkasan = `Worker berulang kali terputus saat menjalankan metode ini (${t.attempts} percobaan).`;
        await pool.query(
          "UPDATE scan_tasks SET status = 'selesai', locked_by = NULL, locked_at = NULL, result = ? WHERE id = ? AND status = 'berjalan'",
          [JSON.stringify({ metode_id: t.methodCode, status: 'tidak_dapat_diverifikasi', ringkasan, bukti: [] }), t.id],
        );
        dihentikan.push(t);
      } else {
        await pool.query("UPDATE scan_tasks SET status = 'antre', locked_by = NULL, locked_at = NULL WHERE id = ? AND status = 'berjalan'", [t.id]);
        dikembalikan.push(t);
      }
    }
    return { dikembalikan, dihentikan };
  },

  /**
   * Klaim satu task antre untuk engine tertentu (SELECT ... FOR UPDATE SKIP LOCKED
   * di dalam transaksi agar dua worker tidak mengambil task yang sama).
   * @returns {Promise<object|null>} baris task yang sudah ditandai 'berjalan', atau null.
   */
  async claimNextTask({ engines, workerId }) {
    const conn = await pool.getConnection();
    try {
      await conn.beginTransaction();
      const placeholders = engines.map(() => '?').join(',');
      const [rows] = await conn.query(
        `SELECT t.id FROM scan_tasks t
         JOIN scans s ON s.id = t.scan_id
         WHERE t.status = 'antre' AND t.engine IN (${placeholders}) AND s.status = 'berjalan'
         ORDER BY t.id
         LIMIT 1
         FOR UPDATE SKIP LOCKED`,
        engines,
      );
      if (!rows.length) {
        await conn.commit();
        return null;
      }
      const taskId = rows[0].id;
      await conn.query(
        "UPDATE scan_tasks SET status = 'berjalan', locked_by = ?, locked_at = UTC_TIMESTAMP(), attempts = attempts + 1 WHERE id = ?",
        [workerId.slice(0, 100), taskId],
      );
      await conn.commit();
      return this.findTaskById(taskId);
    } catch (e) {
      await conn.rollback();
      throw e;
    } finally {
      conn.release();
    }
  },
};
