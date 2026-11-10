import { AppError } from '../../utils/AppError.js';
import { audit } from '../../utils/audit.js';
import { secondsPrecision, toPublicUser } from '../authentication/authentication.service.js';
import { usersRepository } from './users.repository.js';

const toUserDto = (user) => ({
  ...toPublicUser(user),
  status: !user.isVerified ? 'pending' : user.isActive ? 'verified' : 'inactive',
  diverifikasi_pada: user.verifiedAt ?? null,
  masuk_terakhir: user.lastLoginAt ?? null,
  dibuat_pada: user.createdAt,
});

export function createUsersService({ repository = usersRepository, now = () => new Date(), auditor = audit } = {}) {
  async function findOrFail(id) {
    const user = await repository.findById(id);
    if (!user) throw AppError.notFound('Pengguna tidak ditemukan');
    return user;
  }

  /** Admin tidak boleh mengubah status akunnya sendiri lewat menu pengguna. */
  function assertNotSelf(actor, id) {
    if (String(id) === actor.id) throw AppError.badRequest('Anda tidak dapat mengubah akun Anda sendiri');
  }

  return {
    async list({ page, limit, search, status }) {
      const { rows, total } = await repository.list({ offset: (page - 1) * limit, limit, search, status });
      return {
        items: rows.map(toUserDto),
        meta: { page, limit, total, totalPages: Math.max(1, Math.ceil(total / limit)) },
      };
    },

    /** Setujui pendaftaran: akun bisa dipakai masuk dengan peran yang dipilih admin. */
    async verify(actor, id, { peran }) {
      const user = await findOrFail(id);
      if (user.isVerified) throw AppError.conflict('Akun ini sudah diverifikasi');
      const verified = await repository.verify(id, { role: peran, verifiedBy: Number(actor.id), verifiedAt: secondsPrecision(now()) });
      auditor('pengguna.verifikasi', { targetUserId: user.id, targetEmail: user.email, peran });
      return toUserDto(verified);
    },

    /** Tolak pendaftaran: data akun yang belum diverifikasi dihapus. */
    async reject(actor, id) {
      assertNotSelf(actor, id);
      const user = await findOrFail(id);
      if (user.isVerified) throw AppError.badRequest('Akun yang sudah diverifikasi tidak bisa ditolak; nonaktifkan saja');
      await repository.removePending(id);
      auditor('pengguna.tolak', { targetUserId: user.id, targetEmail: user.email, targetNrp: user.nrp });
    },

    /** Ubah peran akun terverifikasi. Sesi pengguna dicabut sehingga ia masuk ulang dengan peran baru. */
    async setRole(actor, id, { peran }) {
      assertNotSelf(actor, id);
      const user = await findOrFail(id);
      if (!user.isVerified) throw AppError.badRequest('Verifikasi akun terlebih dahulu');
      if (user.role === peran) return toUserDto(user);
      if (user.role === 'admin' && user.isActive && (await repository.countActiveAdmins()) <= 1) {
        throw AppError.badRequest('Harus ada minimal satu administrator yang aktif');
      }
      const dari = user.role;
      const updated = await repository.setRole(id, peran);
      auditor('pengguna.peran', { targetUserId: user.id, targetEmail: user.email, dari, ke: peran });
      return toUserDto(updated);
    },

    async setStatus(actor, id, { aktif }) {
      assertNotSelf(actor, id);
      const user = await findOrFail(id);
      if (!user.isVerified) throw AppError.badRequest('Verifikasi akun terlebih dahulu');
      if (user.isActive === aktif) return toUserDto(user);
      if (!aktif && user.role === 'admin' && (await repository.countActiveAdmins()) <= 1) {
        throw AppError.badRequest('Harus ada minimal satu administrator yang aktif');
      }
      const updated = await repository.setActive(id, aktif);
      auditor('pengguna.status', { targetUserId: user.id, targetEmail: user.email, aktif });
      return toUserDto(updated);
    },
  };
}

export const usersService = createUsersService();
