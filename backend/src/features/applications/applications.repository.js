import { and, count, desc, eq, like, or } from 'drizzle-orm';
import { db } from '../../db/index.js';
import { applications, units } from '../../db/schema.js';
import { likePattern } from '../../utils/likePattern.js';

// Baris aplikasi + nama satuan (`unit`) untuk DTO.
const columns = {
  id: applications.id,
  name: applications.name,
  description: applications.description,
  unitId: applications.unitId,
  unit: units.name,
  ownerId: applications.ownerId,
  picName: applications.picName,
  picContact: applications.picContact,
  baseUrl: applications.baseUrl,
  environment: applications.environment,
  dataClassification: applications.dataClassification,
  techFrontend: applications.techFrontend,
  techBackend: applications.techBackend,
  techDatabase: applications.techDatabase,
  techServer: applications.techServer,
  createdAt: applications.createdAt,
  updatedAt: applications.updatedAt,
};

const withUnit = eq(units.id, applications.unitId);

function buildFilter({ search, unitId }) {
  const conditions = [];
  // Cakupan satuan (pemilik); undefined = semua satuan (asesor/admin).
  if (unitId) conditions.push(eq(applications.unitId, unitId));
  if (search) {
    const pattern = likePattern(search);
    conditions.push(or(like(applications.name, pattern), like(applications.baseUrl, pattern), like(units.name, pattern)));
  }
  return conditions.length ? and(...conditions) : undefined;
}

export const applicationsRepository = {
  async list({ offset, limit, ...filters }) {
    const where = buildFilter(filters);
    const [rows, [{ total }]] = await Promise.all([
      db
        .select(columns)
        .from(applications)
        .innerJoin(units, withUnit)
        .where(where)
        .orderBy(desc(applications.createdAt), desc(applications.id))
        .limit(limit)
        .offset(offset),
      db.select({ total: count() }).from(applications).innerJoin(units, withUnit).where(where),
    ]);
    return { rows, total };
  },

  async findById(id) {
    const [row] = await db.select(columns).from(applications).innerJoin(units, withUnit).where(eq(applications.id, id)).limit(1);
    return row ?? null;
  },

  /** @throws galat MySQL ER_DUP_ENTRY bila URL dasar sudah terdaftar. */
  async create(data) {
    const [result] = await db.insert(applications).values(data);
    return this.findById(result.insertId);
  },

  async update(id, data) {
    await db.update(applications).set(data).where(eq(applications.id, id));
    return this.findById(id);
  },
};
