import { eq } from 'drizzle-orm';
import { db } from '../db/index.js';
import { units } from '../db/schema.js';
import { SEED_SATUAN } from '../db/seed/satuan.js';

/**
 * Seed hierarki satuan TNI secara IDEMPOTEN (`npm run satuan:seed`), aman dijalankan tiap deploy.
 *
 * - Satuan dicocokkan berdasarkan nama (kolom UNIQUE, tidak membedakan huruf besar).
 * - Belum ada → disisipkan lengkap (jenis, induk, kota, provinsi, koordinat).
 * - Sudah ada → hanya kolom yang MASIH KOSONG yang diisi (induk, kota, provinsi, koordinat; jenis bila
 *   masih bawaan 'SATUAN'). Isian admin tidak pernah ditimpa, satuan tidak pernah dihapus.
 */
export async function seedSatuan({ pohon = SEED_SATUAN, log = console.log } = {}) {
  const hitung = { baru: 0, dilengkapi: 0, tetap: 0 };

  async function simpan(node, parentId) {
    const [nama, prov, lat, lng] = node.kota ?? [];
    const data = {
      name: node.nama,
      type: node.jenis,
      parentId,
      city: nama ?? null,
      provinceCode: prov ?? null,
      latitude: lat ?? null,
      longitude: lng ?? null,
    };
    const [ada] = await db.select().from(units).where(eq(units.name, node.nama)).limit(1);
    let id;
    if (!ada) {
      const [hasil] = await db.insert(units).values(data);
      id = hasil.insertId;
      hitung.baru += 1;
    } else {
      id = ada.id;
      const kosong = {};
      if (ada.parentId == null && parentId != null && parentId !== ada.id) kosong.parentId = parentId;
      if (ada.type === 'SATUAN' && data.type !== 'SATUAN') kosong.type = data.type;
      if (!ada.city && data.city) kosong.city = data.city;
      if (!ada.provinceCode && data.provinceCode) kosong.provinceCode = data.provinceCode;
      if (ada.latitude == null && ada.longitude == null && data.latitude != null) {
        kosong.latitude = data.latitude;
        kosong.longitude = data.longitude;
      }
      if (Object.keys(kosong).length) {
        await db.update(units).set(kosong).where(eq(units.id, ada.id));
        hitung.dilengkapi += 1;
      } else hitung.tetap += 1;
    }
    for (const anak of node.anak ?? []) await simpan(anak, Number(id));
  }

  for (const akar of pohon) await simpan(akar, null);
  log(`Seed satuan: ${hitung.baru} baru, ${hitung.dilengkapi} dilengkapi, ${hitung.tetap} tidak berubah.`);
  return hitung;
}
