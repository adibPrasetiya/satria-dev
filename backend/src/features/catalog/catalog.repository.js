import { asc, eq, max } from 'drizzle-orm';
import { db } from '../../db/index.js';
import { catalogControls, catalogFunctions, catalogMeta, catalogMethods, catalogTestPoints } from '../../db/schema.js';

const findBy = async (table, column, value) => {
  const [row] = await db.select().from(table).where(eq(column, value)).limit(1);
  return row ?? null;
};

export const catalogRepository = {
  /** Seluruh katalog (termasuk butir nonaktif), terurut sesuai `sort`. */
  async getAll() {
    const [[meta], testPoints, functions, controls, methods] = await Promise.all([
      db.select().from(catalogMeta).limit(1),
      db.select().from(catalogTestPoints).orderBy(asc(catalogTestPoints.sort)),
      db.select().from(catalogFunctions).orderBy(asc(catalogFunctions.sort)),
      db.select().from(catalogControls).orderBy(asc(catalogControls.sort), asc(catalogControls.id)),
      db.select().from(catalogMethods).orderBy(asc(catalogMethods.sort), asc(catalogMethods.id)),
    ]);
    return { meta: meta ?? null, testPoints, functions, controls, methods };
  },

  findFunctionByCode: (code) => findBy(catalogFunctions, catalogFunctions.code, code),
  findControlByCode: (code) => findBy(catalogControls, catalogControls.code, code),
  findMethodByCode: (code) => findBy(catalogMethods, catalogMethods.code, code),
  findTestPoint: (code) => findBy(catalogTestPoints, catalogTestPoints.code, code),

  async listMethodCodes(controlId) {
    const rows = await db.select({ code: catalogMethods.code }).from(catalogMethods).where(eq(catalogMethods.controlId, controlId));
    return rows.map((r) => r.code);
  },

  async nextControlSort(functionId) {
    const [{ value }] = await db.select({ value: max(catalogControls.sort) }).from(catalogControls).where(eq(catalogControls.functionId, functionId));
    return (value ?? -1) + 1;
  },

  async nextMethodSort(controlId) {
    const [{ value }] = await db.select({ value: max(catalogMethods.sort) }).from(catalogMethods).where(eq(catalogMethods.controlId, controlId));
    return (value ?? -1) + 1;
  },

  /** @throws galat MySQL ER_DUP_ENTRY bila kode sudah ada. */
  async createControl(data) {
    const [result] = await db.insert(catalogControls).values(data);
    return findBy(catalogControls, catalogControls.id, result.insertId);
  },

  async updateControl(id, data) {
    await db.update(catalogControls).set(data).where(eq(catalogControls.id, id));
    return findBy(catalogControls, catalogControls.id, id);
  },

  /** @throws galat MySQL ER_DUP_ENTRY bila kode sudah ada. */
  async createMethod(data) {
    const [result] = await db.insert(catalogMethods).values(data);
    return findBy(catalogMethods, catalogMethods.id, result.insertId);
  },

  async updateMethod(id, data) {
    await db.update(catalogMethods).set(data).where(eq(catalogMethods.id, id));
    return findBy(catalogMethods, catalogMethods.id, id);
  },
};
