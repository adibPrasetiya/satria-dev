import { env } from '../../config/env.js';
import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { generateToken, hashToken } from '../../utils/crypto.js';
import { signAccessToken, verifyAccessToken } from '../../utils/jwt.js';
import { logger } from '../../utils/logger.js';
import { sendMail } from '../../utils/mailer.js';
import { hashPassword, verifyPassword } from '../../utils/password.js';
import { authenticationRepository } from './authentication.repository.js';

const INVALID_CREDENTIALS = 'Email atau kata sandi salah';
const INVALID_REFRESH_TOKEN = 'Refresh token tidak valid atau sudah kedaluwarsa';
const INVALID_RESET_LINK = 'Tautan atur ulang kata sandi tidak valid atau sudah kedaluwarsa';
const DAY_MS = 24 * 60 * 60 * 1000;
const MINUTE_MS = 60 * 1000;

/** Bentuk pengguna yang dikirim ke frontend (sesuai tipe `Pengguna` di frontend). */
export const toPublicUser = (user) => ({
  id: String(user.id),
  nama: user.name,
  status_kepegawaian: user.employmentStatus ?? null,
  pangkat: user.rank ?? null,
  nrp: user.nrp,
  email: user.email,
  satuan: user.unit,
  satuan_id: String(user.unitId),
  peran: user.role,
  aktif: Boolean(user.isActive),
  terverifikasi: Boolean(user.isVerified),
});

// Kolom DATETIME MySQL dan klaim `iat` JWT sama-sama presisi detik.
export const secondsPrecision = (date) => new Date(Math.floor(date.getTime() / 1000) * 1000);

const accountPending = () =>
  new AppError(403, 'Akun Anda belum diverifikasi administrator. Silakan tunggu persetujuan.', undefined, 'ACCOUNT_PENDING');
const accountInactive = () => new AppError(403, 'Akun Anda dinonaktifkan. Hubungi administrator.', undefined, 'ACCOUNT_INACTIVE');
const accountLocked = (until, now) => {
  const minutes = Math.max(1, Math.ceil((until.getTime() - now.getTime()) / MINUTE_MS));
  return new AppError(423, `Akun dikunci sementara karena terlalu banyak percobaan gagal. Coba lagi dalam ${minutes} menit.`, undefined, 'ACCOUNT_LOCKED');
};

export function createAuthenticationService({
  repository = authenticationRepository,
  mailer = sendMail,
  now = () => new Date(),
  config = env,
  auditor = audit,
} = {}) {
  async function issueTokens(user, meta = {}) {
    const refreshToken = generateToken();
    await repository.createRefreshToken({
      userId: user.id,
      tokenHash: hashToken(refreshToken),
      expiresAt: new Date(now().getTime() + config.refreshTokenTtlDays * DAY_MS),
      userAgent: meta.userAgent?.slice(0, 255) ?? null,
      ip: meta.ip ?? null,
    });

    return { accessToken: signAccessToken(user), refreshToken, tokenType: 'Bearer', user: toPublicUser(user) };
  }

  return {
    /**
     * Pendaftaran mandiri: akun dibuat sebagai pemilik aplikasi dan belum terverifikasi.
     * Respons selalu sama walau email/NRP sudah terdaftar agar keberadaan akun tidak bocor.
     */
    async register({ nama, status_kepegawaian: employmentStatus, pangkat: rank, nrp, satuan_id: unitId, email, password }) {
      // Daftar satuan bersifat publik, jadi menolaknya di awal tidak membocorkan apa pun.
      if (!(await repository.findActiveUnitById(unitId))) {
        throw AppError.badRequest('Data yang dikirim tidak valid', [{ field: 'satuan_id', message: 'Satuan tidak ditemukan di daftar' }]);
      }
      // Hash dulu agar waktu respons sama untuk email baru maupun yang sudah ada.
      const passwordHash = await hashPassword(password);
      if (await repository.emailOrNrpExists(email, nrp)) {
        auditor('auth.daftar.duplikat', { email, nrp });
        return;
      }
      const user = await repository.createUser({
        name: nama,
        employmentStatus,
        rank,
        nrp,
        unitId,
        email,
        passwordHash,
        role: 'pemilik',
        isVerified: false,
      });
      auditor('auth.daftar', { targetUserId: user?.id, email, nrp, unitId, statusKepegawaian: employmentStatus });
    },

    /**
     * Cek NRP/NIP atau email sebelum lanjut ke langkah berikutnya di stepper pendaftaran.
     * Sengaja membuka enumerasi terbatas demi UX; diredam availabilityLimiter (lihat README).
     */
    async checkAvailability({ nrp, email }) {
      const tersedia = !(await repository.isTaken({ nrp, email }));
      // Nilainya tidak dicatat; kolom & hasil cukup untuk mendeteksi pola enumerasi per IP.
      auditor('auth.cek_ketersediaan', { kolom: nrp ? 'nrp' : 'email', tersedia });
      return { tersedia };
    },

    async login({ email, password }, meta) {
      const user = await repository.findUserByEmail(email);
      const current = now();
      const gagal = (alasan, extra) => auditor('auth.login.gagal', { email, userId: user?.id, alasan, ...extra });
      if (user?.lockedUntil && user.lockedUntil > current) {
        gagal('terkunci', { terkunciSampai: user.lockedUntil });
        throw accountLocked(user.lockedUntil, current);
      }

      // Selalu jalankan bcrypt agar waktu respons tidak membocorkan apakah email terdaftar.
      const passwordValid = await verifyPassword(password, user?.passwordHash);
      if (!user) {
        gagal('email_tidak_terdaftar');
        throw AppError.unauthorized(INVALID_CREDENTIALS);
      }

      if (!passwordValid) {
        const failed = user.failedLoginCount + 1;
        if (failed >= config.login.maxAttempts) {
          const lockedUntil = new Date(current.getTime() + config.login.lockMinutes * MINUTE_MS);
          await repository.updateUser(user.id, { failedLoginCount: 0, lockedUntil });
          gagal('sandi_salah', { percobaan: failed });
          auditor('auth.akun.dikunci', { email, userId: user.id, percobaan: failed, terkunciSampai: lockedUntil });
          throw accountLocked(lockedUntil, current);
        }
        await repository.updateUser(user.id, { failedLoginCount: failed });
        gagal('sandi_salah', { percobaan: failed });
        throw AppError.unauthorized(INVALID_CREDENTIALS);
      }

      // Status akun baru diungkap setelah kata sandi terbukti benar.
      if (!user.isVerified) {
        gagal('belum_diverifikasi');
        throw accountPending();
      }
      if (!user.isActive) {
        gagal('nonaktif');
        throw accountInactive();
      }

      await repository.updateUser(user.id, { failedLoginCount: 0, lockedUntil: null, lastLoginAt: current });
      auditor('auth.login.berhasil', { email, userId: user.id, peran: user.role, userAgent: meta?.userAgent });
      return issueTokens(user, meta);
    },

    async refresh({ refreshToken }, meta) {
      const record = await repository.findRefreshTokenByHash(hashToken(refreshToken));
      if (!record) throw AppError.unauthorized(INVALID_REFRESH_TOKEN);

      if (record.revokedAt) {
        // Token hasil rotasi dipakai ulang: kemungkinan dicuri, cabut semua sesi user.
        // Token yang dicabut karena logout/ganti kata sandi/nonaktif cukup ditolak.
        if (record.revokedReason === 'rotated') {
          await repository.revokeAllRefreshTokensForUser(record.userId, 'reuse');
          auditor('auth.refresh.reuse', { userId: record.userId });
        }
        throw AppError.unauthorized(INVALID_REFRESH_TOKEN);
      }
      if (record.expiresAt <= now()) throw AppError.unauthorized(INVALID_REFRESH_TOKEN);

      const user = await repository.findUserById(record.userId);
      if (!user || !user.isActive || !user.isVerified) throw AppError.unauthorized(INVALID_REFRESH_TOKEN);

      const revoked = await repository.revokeRefreshToken(record.id, 'rotated');
      if (!revoked) {
        await repository.revokeAllRefreshTokensForUser(record.userId, 'reuse');
        auditor('auth.refresh.reuse', { userId: record.userId, balapan: true });
        throw AppError.unauthorized(INVALID_REFRESH_TOKEN);
      }

      return issueTokens(user, meta);
    },

    async logout(userId, { refreshToken }) {
      const record = await repository.findRefreshTokenByHash(hashToken(refreshToken));
      if (record && record.userId === Number(userId) && !record.revokedAt) {
        await repository.revokeRefreshToken(record.id, 'logout');
      }
      auditor('auth.logout', { userId });
    },

    /**
     * Kirim tautan atur ulang kata sandi. Respons ke klien selalu sama (kontrol BSSN 1.5);
     * tautan hanya dibuat untuk akun yang terverifikasi & aktif.
     */
    async forgotPassword({ email }) {
      const user = await repository.findUserByEmail(email);
      if (!user || !user.isVerified || !user.isActive) {
        auditor('auth.lupa_sandi', { email, userId: user?.id, tautanDikirim: false });
        return;
      }

      const token = generateToken();
      const current = now();
      await repository.createPasswordResetToken({
        userId: user.id,
        tokenHash: hashToken(token),
        expiresAt: new Date(current.getTime() + config.passwordResetTtlMinutes * MINUTE_MS),
        now: current,
      });

      const link = `${config.appUrl}/reset-sandi?token=${encodeURIComponent(token)}`;
      try {
        await mailer({
          to: user.email,
          subject: 'Atur ulang kata sandi SATYA',
          text: [
            `Halo ${user.name},`,
            '',
            'Kami menerima permintaan untuk mengatur ulang kata sandi akun SATYA Anda.',
            `Buka tautan berikut dalam ${config.passwordResetTtlMinutes} menit (hanya bisa dipakai sekali):`,
            link,
            '',
            'Abaikan email ini bila Anda tidak meminta atur ulang kata sandi.',
          ].join('\n'),
        });
      } catch (error) {
        // Gagal kirim tidak dibocorkan ke klien (respons tetap sama), cukup dicatat.
        logger.error('Gagal mengirim email atur ulang kata sandi', { userId: user.id, error: error.message });
      }
      auditor('auth.lupa_sandi', { email, userId: user.id, tautanDikirim: true });
    },

    /** Set kata sandi baru dari tautan: token sekali pakai, sesi lama dicabut, penguncian dibuka. */
    async resetPassword({ token, password }) {
      const record = await repository.findPasswordResetTokenByHash(hashToken(token));
      const current = now();
      if (!record || record.usedAt || record.expiresAt <= current) {
        auditor('auth.reset_sandi.gagal', { userId: record?.userId, alasan: !record ? 'token_tidak_dikenal' : record.usedAt ? 'sudah_dipakai' : 'kedaluwarsa' });
        throw AppError.badRequest(INVALID_RESET_LINK);
      }

      const user = await repository.findUserById(record.userId);
      if (!user || !user.isActive || !user.isVerified) {
        auditor('auth.reset_sandi.gagal', { userId: record.userId, alasan: 'akun_tidak_aktif' });
        throw AppError.badRequest(INVALID_RESET_LINK);
      }

      const ok = await repository.resetPassword({
        userId: user.id,
        tokenId: record.id,
        passwordHash: await hashPassword(password),
        passwordChangedAt: secondsPrecision(current),
      });
      if (!ok) {
        auditor('auth.reset_sandi.gagal', { userId: user.id, alasan: 'sudah_dipakai' });
        throw AppError.badRequest(INVALID_RESET_LINK);
      }
      auditor('auth.reset_sandi.berhasil', { userId: user.id, email: user.email });
    },

    /**
     * Ganti kata sandi oleh pengguna yang sedang masuk. Semua sesi lain dicabut; sesi ini mendapat token
     * baru (iat >= passwordChangedAt) agar pengguna tidak perlu masuk ulang.
     */
    async changePassword(userId, { passwordLama, passwordBaru }, meta) {
      const user = await repository.findUserById(Number(userId));
      if (!user || !user.isActive || !user.isVerified) throw AppError.unauthorized();

      if (!(await verifyPassword(passwordLama, user.passwordHash))) {
        auditor('auth.ganti_sandi.gagal', { userId: user.id, alasan: 'sandi_lama_salah' });
        throw AppError.badRequest('Kata sandi saat ini salah', [{ field: 'passwordLama', message: 'Kata sandi saat ini salah' }]);
      }
      if (passwordBaru === passwordLama) {
        throw AppError.badRequest('Data yang dikirim tidak valid', [
          { field: 'passwordBaru', message: 'Kata sandi baru harus berbeda dari yang lama' },
        ]);
      }

      const passwordChangedAt = secondsPrecision(now());
      await repository.changePassword({ userId: user.id, passwordHash: await hashPassword(passwordBaru), passwordChangedAt });
      auditor('auth.ganti_sandi.berhasil', { userId: user.id });
      return issueTokens({ ...user, passwordChangedAt }, meta);
    },

    async authenticate(accessToken) {
      let payload;
      try {
        payload = verifyAccessToken(accessToken);
      } catch {
        throw AppError.unauthorized('Access token tidak valid atau sudah kedaluwarsa');
      }

      const user = await repository.findUserById(Number(payload.sub));
      if (!user || !user.isActive || !user.isVerified) throw AppError.unauthorized();
      if (user.passwordChangedAt && payload.iat * 1000 < user.passwordChangedAt.getTime()) {
        throw AppError.unauthorized('Sesi berakhir karena kata sandi telah diubah, silakan masuk ulang');
      }

      return toPublicUser(user);
    },
  };
}

export const authenticationService = createAuthenticationService();
