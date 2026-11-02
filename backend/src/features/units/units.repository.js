import { and, asc, count, eq, like } from 'drizzle-orm';
import { db } from '../../db/index.js';
import { units, users } from '../../db/schema.js';
import { likePattern } from '../../utils/likePattern.js';

const columns = { id: units.id, name: units.name };

// Kolom untuk halaman admin: termasuk status & jumlah akun yang memakai satuan.
const adminColumns = {
  id: units.id,
  name: units.name,
  isActive: units.isActive,
  createdAt: units.createdAt,
  userCount: count(users.id),
};

const STATUS_FILTER = {
  aktif: () => eq(units.isActive, true),
  nonaktif: () => eq(units.isActive, false),
};

function buildAdminFilter({ search, status }) {
  const conditions = [];
  if (search) conditions.push(like(units.name, likePattern(search)));
  if (status) conditions.push(STATUS_FILTER[status]());
  return conditions.length ? and(...conditions) : undefined;
}

const selectAdmin = () => db.select(adminColumns).from(units).leftJoin(users, eq(users.unitId, units.id)).groupBy(units.id);

export const unitsRepository = {
  /** Satuan aktif yang namanya mengandung `search` (kosong = semua), urut nama, maksimal `limit`. */
  async searchActive({ search = '', limit }) {
    const where = search ? and(eq(units.isActive, true), like(units.name, likePattern(search))) : eq(units.isActive, true);
    return db.select(columns).from(units).where(where).orderBy(asc(units.name)).limit(limit);
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
      selectAdmin().where(where).orderBy(asc(units.name)).limit(limit).offset(offset),
      db.select({ total: count() }).from(units).where(where),
    ]);
    return { rows, total };
  },

  async findById(id) {
    const [unit] = await selectAdmin().where(eq(units.id, id)).limit(1);
    return unit ?? null;
  },

  /** @throws galat MySQL ER_DUP_ENTRY bila nama sudah dipakai (kolom name UNIQUE). */
  async create({ name, isActive }) {
    const [result] = await db.insert(units).values({ name, isActive });
    return this.findById(result.insertId);
  },

  async update(id, data) {
    await db.update(units).set(data).where(eq(units.id, id));
    return this.findById(id);
  },
};
