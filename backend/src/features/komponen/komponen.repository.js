import { and, asc, eq } from 'drizzle-orm';
import { db } from '../../db/index.js';
import { aplikasiKomponen } from '../../db/schema.js';

export const komponenRepository = {
  async listByApplication(applicationId) {
    return db
      .select()
      .from(aplikasiKomponen)
      .where(eq(aplikasiKomponen.applicationId, applicationId))
      .orderBy(asc(aplikasiKomponen.kategori), asc(aplikasiKomponen.nama), asc(aplikasiKomponen.id));
  },

  async findById(id) {
    const [row] = await db.select().from(aplikasiKomponen).where(eq(aplikasiKomponen.id, id)).limit(1);
    return row ?? null;
  },

  /** Ganti seluruh komponen satu sumber milik aplikasi (dipakai sinkron formulir & hasil recon). */
  async gantiSumber(applicationId, sumber, items, { scanId = null } = {}) {
    await db.transaction(async (tx) => {
      await tx
        .delete(aplikasiKomponen)
        .where(and(eq(aplikasiKomponen.applicationId, applicationId), eq(aplikasiKomponen.sumber, sumber)));
      if (items.length) {
        const sekarang = new Date();
        await tx
          .insert(aplikasiKomponen)
          .values(items.map((it) => ({ ...it, applicationId, sumber, scanId, terakhirTerlihat: sekarang })));
      }
    });
  },

  /** Tambah/timpa satu komponen (unik per aplikasi+produk+sumber). */
  async upsert(applicationId, sumber, item) {
    const baris = { ...item, applicationId, sumber, terakhirTerlihat: new Date() };
    const { applicationId: _a, sumber: _s, produk: _p, ...ubah } = baris;
    await db.insert(aplikasiKomponen).values(baris).onDuplicateKeyUpdate({ set: ubah });
    const [row] = await db
      .select()
      .from(aplikasiKomponen)
      .where(
        and(
          eq(aplikasiKomponen.applicationId, applicationId),
          eq(aplikasiKomponen.produk, item.produk),
          eq(aplikasiKomponen.sumber, sumber),
        ),
      )
      .limit(1);
    return row;
  },

  async hapus(id) {
    await db.delete(aplikasiKomponen).where(eq(aplikasiKomponen.id, id));
  },
};
