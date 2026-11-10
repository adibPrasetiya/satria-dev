import { and, eq, isNull, or } from 'drizzle-orm';
import { db } from '../../db/index.js';
import { emailVerificationTokens, passwordResetTokens, refreshTokens, units, users } from '../../db/schema.js';
import { revokeUserSessions } from '../../db/sessions.js';
import { unitsRepository } from '../units/units.repository.js';

const affectedRows = ([result]) => result.affectedRows;

// Baris users + nama satuan (`unit`) untuk toPublicUser.
const findUser = async (where) => {
  const [row] = await db.select().from(users).innerJoin(units, eq(units.id, users.unitId)).where(where).limit(1);
  return row ? { ...row.users, unit: row.units.name } : null;
};

export const authenticationRepository = {
  findUserByEmail: (email) => findUser(eq(users.email, email)),

  findUserById: (id) => findUser(eq(users.id, id)),

  findActiveUnitById: (id) => unitsRepository.findActiveById(id),

  async emailOrNrpExists(email, nrp) {
    const [row] = await db
      .select({ id: users.id })
      .from(users)
      .where(or(eq(users.email, email), eq(users.nrp, nrp)))
      .limit(1);
    return Boolean(row);
  },

  /** Hanya kolom yang diisi yang diperiksa. */
  async isTaken({ email, nrp }) {
    const [row] = await db
      .select({ id: users.id })
      .from(users)
      .where(email ? eq(users.email, email) : eq(users.nrp, nrp))
      .limit(1);
    return Boolean(row);
  },

  async createUser(data) {
    const [result] = await db.insert(users).values(data);
    return this.findUserById(result.insertId);
  },

  async updateUser(id, data) {
    await db.update(users).set(data).where(eq(users.id, id));
  },

  async createRefreshToken({ userId, tokenHash, expiresAt, userAgent, ip }) {
    await db.insert(refreshTokens).values({ userId, tokenHash, expiresAt, userAgent, ip });
  },

  async findRefreshTokenByHash(tokenHash) {
    const [token] = await db.select().from(refreshTokens).where(eq(refreshTokens.tokenHash, tokenHash)).limit(1);
    return token ?? null;
  },

  /** @returns {Promise<boolean>} false jika token sudah di-revoke sebelumnya (race/reuse). */
  async revokeRefreshToken(id, reason) {
    const result = await db
      .update(refreshTokens)
      .set({ revokedAt: new Date(), revokedReason: reason })
      .where(and(eq(refreshTokens.id, id), isNull(refreshTokens.revokedAt)));
    return affectedRows(result) > 0;
  },

  async revokeAllRefreshTokensForUser(userId, reason) {
    await revokeUserSessions(db, userId, reason);
  },

  /** Token reset baru membatalkan token lama yang belum dipakai: hanya tautan terakhir yang berlaku. */
  async createPasswordResetToken({ userId, tokenHash, expiresAt, now }) {
    await db.transaction(async (tx) => {
      await tx
        .update(passwordResetTokens)
        .set({ usedAt: now })
        .where(and(eq(passwordResetTokens.userId, userId), isNull(passwordResetTokens.usedAt)));
      await tx.insert(passwordResetTokens).values({ userId, tokenHash, expiresAt });
    });
  },

  async findPasswordResetTokenByHash(tokenHash) {
    const [token] = await db.select().from(passwordResetTokens).where(eq(passwordResetTokens.tokenHash, tokenHash)).limit(1);
    return token ?? null;
  },

  /** Token verifikasi baru membatalkan token lama yang belum dipakai: hanya tautan terakhir yang berlaku. */
  async createEmailVerificationToken({ userId, tokenHash, expiresAt, now }) {
    await db.transaction(async (tx) => {
      await tx
        .update(emailVerificationTokens)
        .set({ usedAt: now })
        .where(and(eq(emailVerificationTokens.userId, userId), isNull(emailVerificationTokens.usedAt)));
      await tx.insert(emailVerificationTokens).values({ userId, tokenHash, expiresAt });
    });
  },

  async findEmailVerificationTokenByHash(tokenHash) {
    const [token] = await db.select().from(emailVerificationTokens).where(eq(emailVerificationTokens.tokenHash, tokenHash)).limit(1);
    return token ?? null;
  },

  /**
   * Tandai token terpakai (hanya bila belum, agar dua klik bersamaan tidak sama-sama berhasil) dan
   * verifikasi akun dalam satu transaksi. `verifiedBy` dibiarkan null = terverifikasi lewat email.
   * @returns {Promise<boolean>} false jika token ternyata sudah dipakai.
   */
  async verifyEmail({ userId, tokenId, verifiedAt }) {
    return db.transaction(async (tx) => {
      const used = await tx
        .update(emailVerificationTokens)
        .set({ usedAt: verifiedAt })
        .where(and(eq(emailVerificationTokens.id, tokenId), isNull(emailVerificationTokens.usedAt)));
      if (affectedRows(used) === 0) return false;
      await tx.update(users).set({ isVerified: true, verifiedAt }).where(and(eq(users.id, userId), eq(users.isVerified, false)));
      return true;
    });
  },

  /** Ganti kata sandi (pengguna yang sedang masuk): hash baru + cabut semua sesi dalam satu transaksi. */
  async changePassword({ userId, passwordHash, passwordChangedAt }) {
    await db.transaction(async (tx) => {
      await tx.update(users).set({ passwordHash, passwordChangedAt }).where(eq(users.id, userId));
      await revokeUserSessions(tx, userId, 'password_change');
    });
  },

  /**
   * Set kata sandi baru dari tautan reset dalam satu transaksi: token ditandai terpakai (hanya bila belum,
   * agar dua permintaan bersamaan tidak sama-sama berhasil), penguncian dibuka, dan semua sesi dicabut.
   * @returns {Promise<boolean>} false jika token ternyata sudah dipakai.
   */
  async resetPassword({ userId, tokenId, passwordHash, passwordChangedAt }) {
    return db.transaction(async (tx) => {
      const used = await tx
        .update(passwordResetTokens)
        .set({ usedAt: passwordChangedAt })
        .where(and(eq(passwordResetTokens.id, tokenId), isNull(passwordResetTokens.usedAt)));
      if (affectedRows(used) === 0) return false;

      await tx
        .update(users)
        .set({ passwordHash, passwordChangedAt, failedLoginCount: 0, lockedUntil: null })
        .where(eq(users.id, userId));
      await revokeUserSessions(tx, userId, 'password_change');
      return true;
    });
  },
};
