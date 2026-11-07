import { and, asc, count, eq, isNull, like, sql } from 'drizzle-orm';
import { MAKS_KEDALAMAN_SATUAN } from '../../config/satuan.js';
import { db } from '../../db/index.js';
import { applications, units, users } from '../../db/schema.js';
import { likePattern } from '../../utils/likePattern.js';

const columns = { id: units.id, name: units.name, type: units.type, parentId: units.parentId };

// Kolom untuk halaman admin: alamat, status, dan jumlah akun/aplikasi/sub-satuan yang merujuknya.
// Subquery terkorelasi (bukan JOIN + GROUP BY) agar tiga hitungan tidak saling menggandakan.
const adminColumns = {
  ...columns,
  address: units.address,
  city: units.city,
  provinceCode: units.provinceCode,
  latitude: units.latitude,
  longitude: units.longitude,
  isActive: units.isActive,
  createdAt: units.createdAt,
  // Nama tabel ditulis eksplisit: di select satu tabel drizzle membuang awalan tabel dari `${kolom}`,
  // sehingga `${units.id}` di dalam subquery akan merujuk `id` milik tabel subquery, bukan satuan luar.
  userCount: sql`(select count(*) from ${users} as u where u.unit_id = units.id)`.mapWith(Number),
  appCount: sql`(select count(*) from ${applications} as a where a.unit_id = units.id)`.mapWith(Number),
  childCount: sql`(select count(*) from ${units} as anak where anak.parent_id = units.id)`.mapWith(Number),
};

const STATUS_FILTER = {
  aktif: () => eq(units.isActive, true),
  nonaktif: () => eq(units.isActive, false),
};

/** `parentId`: undefined = semua tingkat (pencarian datar), null = satuan akar, angka = anak langsung satuan itu. */
function buildAdminFilter({ search, status, type, provinceCode, parentId }) {
  const conditions = [];
  if (search) conditions.push(like(units.name, likePattern(search)));
  if (status) conditions.push(STATUS_FILTER[status]());
  if (type) conditions.push(eq(units.type, type));
  if (provinceCode) conditions.push(eq(units.provinceCode, provinceCode));
  if (parentId === null) conditions.push(isNull(units.parentId));
  else if (parentId !== undefined) conditions.push(eq(units.parentId, parentId));
  return conditions.length ? and(...conditions) : undefined;
}

// Kolom enum diurutkan MySQL menurut urutan definisinya (MABES → … → SATUAN), lalu nama.
const ORDER = [asc(units.type), asc(units.name)];

const rowsOf = (result) => (Array.isArray(result?.[0]) ? result[0] : result);

export const unitsRepository = {
  /** Satuan aktif yang namanya mengandung `search` (kosong = semua), urut jenis lalu nama, maksimal `limit`. */
  async searchActive({ search = '', limit }) {
    const where = search ? and(eq(units.isActive, true), like(units.name, likePattern(search))) : eq(units.isActive, true);
    return db
      .select(columns)
      .from(units)
      .where(where)
      .orderBy(...ORDER)
      .limit(limit);
  },

  async findActiveById(id) {
    const [unit] = await db
      .select(columns)
      .from(units)
      .where(and(eq(units.id, id), eq(units.isActive, true)))
      .limit(1);
    return unit ?? null;
  },

  async listAll({ offset, limit, ...filters }) {
    const where = buildAdminFilter(filters);
    const [rows, [{ total }]] = await Promise.all([
      db
        .select(adminColumns)
        .from(units)
        .where(where)
        .orderBy(...ORDER)
        .limit(limit)
        .offset(offset),
      db.select({ total: count() }).from(units).where(where),
    ]);
    return { rows, total };
  },

  async findById(id) {
    const [unit] = await db.select(adminColumns).from(units).where(eq(units.id, id)).limit(1);
    return unit ?? null;
  },

  /**
   * Leluhur tiap satuan, urut dari akar ke induk langsung: Map<id, [{ id, name }]>.
   * Satu query rekursif untuk semua id sekaligus; dibatasi kedalaman agar data rusak (siklus) tidak berputar.
   */
  async ancestorsOf(ids) {
    const map = new Map(ids.map((id) => [Number(id), []]));
    if (!ids.length) return map;
    const result = await db.execute(sql`
      with recursive leluhur (asal, id, parent_id, name, kedalaman) as (
        select id, id, parent_id, name, 0 from ${units} where id in (${sql.join(ids.map(Number), sql`, `)})
        union all
        select l.asal, u.id, u.parent_id, u.name, l.kedalaman + 1
        from ${units} u join leluhur l on u.id = l.parent_id
        where l.kedalaman < ${MAKS_KEDALAMAN_SATUAN}
      )
      select asal, id, name from leluhur where kedalaman > 0 order by asal, kedalaman desc`);
    for (const row of rowsOf(result)) map.get(Number(row.asal))?.push({ id: Number(row.id), name: row.name });
    return map;
  },

  /** Tinggi sub-pohon di bawah satuan (0 = tidak punya sub-satuan); untuk menjaga batas kedalaman saat dipindah. */
  async subtreeHeight(id) {
    const result = await db.execute(sql`
      with recursive turunan (id, kedalaman) as (
        select id, 0 from ${units} where id = ${Number(id)}
        union all
        select u.id, t.kedalaman + 1 from ${units} u join turunan t on u.parent_id = t.id
        where t.kedalaman < ${MAKS_KEDALAMAN_SATUAN + 1}
      )
      select max(kedalaman) as tinggi from turunan`);
    return Number(rowsOf(result)[0]?.tinggi ?? 0);
  },

  /** @throws galat MySQL ER_DUP_ENTRY bila nama sudah dipakai (kolom name UNIQUE). */
  async create(data) {
    const [result] = await db.insert(units).values(data);
    return this.findById(result.insertId);
  },

  async update(id, data) {
    await db.update(units).set(data).where(eq(units.id, id));
    return this.findById(id);
  },
};
