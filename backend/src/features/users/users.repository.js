import { and, count, desc, eq, like, or } from 'drizzle-orm';
import { db } from '../../db/index.js';
import { units, users } from '../../db/schema.js';
import { revokeUserSessions } from '../../db/sessions.js';
import { likePattern } from '../../utils/likePattern.js';

// Kolom yang boleh keluar dari repository (tanpa password_hash).
const columns = {
  id: users.id,
  name: users.name,
  employmentStatus: users.employmentStatus,
  rank: users.rank,
  nrp: users.nrp,
  unit: units.name,
  unitId: users.unitId,
  email: users.email,
  role: users.role,
  isVerified: users.isVerified,
  verifiedAt: users.verifiedAt,
  isActive: users.isActive,
  lastLoginAt: users.lastLoginAt,
  createdAt: users.createdAt,
};

const withUnit = eq(units.id, users.unitId);

const STATUS_FILTER = {
  pending: () => eq(users.isVerified, false),
  verified: () => and(eq(users.isVerified, true), eq(users.isActive, true)),
  inactive: () => and(eq(users.isVerified, true), eq(users.isActive, false)),
};

function buildFilter({ search, status }) {
  const conditions = [];
  if (search) {
    const pattern = likePattern(search);
    conditions.push(
      or(like(users.name, pattern), like(users.rank, pattern), like(users.email, pattern), like(users.nrp, pattern), like(units.name, pattern)),
    );
  }
  if (status) conditions.push(STATUS_FILTER[status]());
  return conditions.length ? and(...conditions) : undefined;
}

export const usersRepository = {
  async list({ offset, limit, ...filters }) {
    const where = buildFilter(filters);
    const [rows, [{ total }]] = await Promise.all([
      db.select(columns).from(users).innerJoin(units, withUnit).where(where).orderBy(desc(users.createdAt), desc(users.id)).limit(limit).offset(offset),
      db.select({ total: count() }).from(users).innerJoin(units, withUnit).where(where),
    ]);
    return { rows, total };
  },

  async findById(id) {
    const [user] = await db.select(columns).from(users).innerJoin(units, withUnit).where(eq(users.id, id)).limit(1);
    return user ?? null;
  },

  async countActiveAdmins() {
    const [{ total }] = await db
      .select({ total: count() })
      .from(users)
      .where(and(eq(users.role, 'admin'), eq(users.isActive, true), eq(users.isVerified, true)));
    return total;
  },

  async verify(id, { role, verifiedBy, verifiedAt }) {
    await db.update(users).set({ isVerified: true, role, verifiedBy, verifiedAt }).where(eq(users.id, id));
    return this.findById(id);
  },

  /** Hapus pendaftaran yang ditolak; hanya akun yang belum diverifikasi. */
  async removePending(id) {
    await db.delete(users).where(and(eq(users.id, id), eq(users.isVerified, false)));
  },

  /** Ganti peran → semua sesi user dicabut agar ia masuk ulang dengan menu & hak akses peran baru. */
  async setRole(id, role) {
    await db.transaction(async (tx) => {
      await tx.update(users).set({ role }).where(eq(users.id, id));
      await revokeUserSessions(tx, id, 'role_change');
    });
    return this.findById(id);
  },

  /** Nonaktif → semua sesi user dicabut sehingga ia langsung keluar. */
  async setActive(id, isActive) {
    await db.transaction(async (tx) => {
      await tx.update(users).set({ isActive }).where(eq(users.id, id));
      if (!isActive) await revokeUserSessions(tx, id, 'deactivated');
    });
    return this.findById(id);
  },
};
