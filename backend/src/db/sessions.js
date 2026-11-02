import { and, eq, isNull } from 'drizzle-orm';
import { refreshTokens } from './schema.js';

/**
 * Cabut semua refresh token aktif milik user. `executor` boleh `db` atau `tx` (di dalam transaksi).
 * `reason` menentukan apakah pemakaian ulang token nanti dianggap pencurian (hanya 'rotated').
 */
export function revokeUserSessions(executor, userId, reason) {
  return executor
    .update(refreshTokens)
    .set({ revokedAt: new Date(), revokedReason: reason })
    .where(and(eq(refreshTokens.userId, userId), isNull(refreshTokens.revokedAt)));
}
