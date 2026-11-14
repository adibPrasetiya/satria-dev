import { and, eq, inArray, isNull, isNotNull, sql } from 'drizzle-orm';
import { db, pool } from '../../db/index.js';
import { aplikasiKomponen, applications, cve, cveCpe, cvePaket, sinkronIntel } from '../../db/schema.js';

const POTONGAN = 500;
const potong = (arr, n = POTONGAN) => Array.from({ length: Math.ceil(arr.length / n) }, (_, i) => arr.slice(i * n, i * n + n));

export const intelRepository = {
  /**
   * Simpan CVE dari NVD (upsert) beserta rentang CPE-nya (diganti utuh). Flag KEV hanya dinaikkan dari NVD,
   * tak pernah diturunkan — sinkron KEV yang menjadi sumber kebenaran.
   */
  async simpanNvd(daftar) {
    for (const bagian of potong(daftar, 200)) {
      await db.transaction(async (tx) => {
        for (const { cve: c, cpe } of bagian) {
          const { id, kev, kevDitambahkan, kevTenggat, ...ubah } = c;
          await tx
            .insert(cve)
            .values(c)
            .onDuplicateKeyUpdate({
              set: {
                ...ubah,
                kev: sql`(${cve.kev} OR ${kev})`,
                kevDitambahkan: sql`COALESCE(${cve.kevDitambahkan}, ${kevDitambahkan})`,
                kevTenggat: sql`COALESCE(${cve.kevTenggat}, ${kevTenggat})`,
              },
            });
          await tx.delete(cveCpe).where(eq(cveCpe.cveId, id));
          if (cpe.length) await tx.insert(cveCpe).values(cpe.map((r) => ({ ...r, cveId: id })));
        }
      });
    }
  },

  /** Advisory OSV: CVE dibuat bila belum ada (data NVD tak ditimpa), lalu catat paket@versi terdampak. */
  async simpanOsv(c, purl, versi) {
    await db.insert(cve).ignore().values(c);
    await db.insert(cvePaket).ignore().values({ cveId: c.id, purl, versi });
  },

  /** Hapus catatan OSV lama untuk paket@versi (sebelum diisi hasil query terbaru). */
  async resetPaket(purl, versi) {
    await db.delete(cvePaket).where(and(eq(cvePaket.purl, purl), eq(cvePaket.versi, versi)));
  },

  async idCveAda(ids) {
    const ada = new Set();
    for (const bagian of potong(ids)) {
      const rows = await db.select({ id: cve.id }).from(cve).where(inArray(cve.id, bagian));
      for (const r of rows) ada.add(r.id);
    }
    return ada;
  },

  /** Terapkan katalog KEV: semua flag direset lalu dinaikkan untuk CVE yang terdaftar (yang ada di tabel). */
  async terapkanKev(entri) {
    const peta = new Map(entri.map((e) => [e.cveID, e]));
    const ada = [...(await this.idCveAda([...peta.keys()]))];
    await db.transaction(async (tx) => {
      await tx.update(cve).set({ kev: false }).where(eq(cve.kev, true));
      for (const id of ada) {
        const e = peta.get(id);
        await tx
          .update(cve)
          .set({
            kev: true,
            kevDitambahkan: e.dateAdded ?? null,
            kevTenggat: e.dueDate ?? null,
            kevRansomware: e.knownRansomwareCampaignUse === 'Known',
          })
          .where(eq(cve.id, id));
      }
    });
    return ada.length;
  },

  /** ID CVE (format CVE-) yang perlu skor EPSS: semua bila `semua`, selain itu yang belum punya skor. */
  async idUntukEpss({ semua }) {
    const rows = await db
      .select({ id: cve.id })
      .from(cve)
      .where(and(sql`${cve.id} LIKE 'CVE-%'`, semua ? undefined : isNull(cve.epss)));
    return rows.map((r) => r.id);
  },

  async terapkanEpss(data) {
    for (const bagian of potong(data, 200)) {
      await db.transaction(async (tx) => {
        for (const d of bagian) {
          await tx
            .update(cve)
            .set({ epss: String(d.epss), epssPersentil: String(d.percentile) })
            .where(eq(cve.id, d.cve));
        }
      });
    }
  },

  /** Produk CPE di inventaris aset aktif (tak terarsip): [{ vendor, produk }]. */
  async produkInventaris() {
    return db
      .selectDistinct({ vendor: aplikasiKomponen.vendor, produk: aplikasiKomponen.produk })
      .from(aplikasiKomponen)
      .innerJoin(applications, eq(applications.id, aplikasiKomponen.applicationId))
      .where(and(isNotNull(aplikasiKomponen.vendor), isNull(applications.archivedAt)));
  },

  /** purl berversi di inventaris aset aktif → [{ purl }] (mis. "pkg:npm/jquery@3.4.1"). */
  async paketInventaris() {
    const rows = await db
      .selectDistinct({ purl: aplikasiKomponen.purl })
      .from(aplikasiKomponen)
      .innerJoin(applications, eq(applications.id, aplikasiKomponen.applicationId))
      .where(and(sql`${aplikasiKomponen.purl} LIKE '%@%'`, isNull(applications.archivedAt)));
    return rows.map((r) => r.purl);
  },

  async status(kunci) {
    const [row] = await db.select().from(sinkronIntel).where(eq(sinkronIntel.kunci, kunci)).limit(1);
    return row ?? null;
  },

  async semuaStatus() {
    return db.select().from(sinkronIntel);
  },

  async catatStatus(kunci, { status, kursor, pesan = null }) {
    const set = { status, pesan: pesan?.slice(0, 2000) ?? null, ...(kursor !== undefined ? { kursor } : {}) };
    await db
      .insert(sinkronIntel)
      .values({ kunci, ...set })
      .onDuplicateKeyUpdate({ set: { ...set, updatedAt: new Date() } });
  },

  /**
   * Kunci tunggal sinkron (lintas proses: server & CLI PM2). Berhasil bila tak ada sinkron berjalan, atau
   * yang tercatat berjalan sudah basi (> 3 jam — proses mati di tengah jalan).
   */
  async ambilKunci(kunci) {
    const [ubah] = await pool.query(
      `UPDATE sinkron_intel SET status = 'berjalan', pesan = NULL, updated_at = NOW()
       WHERE kunci = ? AND (status <> 'berjalan' OR updated_at < NOW() - INTERVAL 3 HOUR)`,
      [kunci],
    );
    if (ubah.affectedRows === 1) return true;
    const [baru] = await pool.query(
      `INSERT IGNORE INTO sinkron_intel (kunci, status, updated_at) VALUES (?, 'berjalan', NOW())`,
      [kunci],
    );
    return baru.affectedRows === 1;
  },
};
