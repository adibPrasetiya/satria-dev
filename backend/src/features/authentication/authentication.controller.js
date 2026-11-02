import { env } from '../../config/env.js';
import { success } from '../../utils/response.js';
import { authenticationService } from './authentication.service.js';

const requestMeta = (req) => ({ ip: req.ip, userAgent: req.get('user-agent') });

export const authenticationController = {
  async register(req, res) {
    await authenticationService.register(req.body);
    return success(res, {
      statusCode: 202,
      message: 'Pendaftaran diterima. Akun dapat digunakan setelah diverifikasi administrator.',
    });
  },

  async checkAvailability(req, res) {
    const data = await authenticationService.checkAvailability(req.body);
    return success(res, { data });
  },

  async login(req, res) {
    const data = await authenticationService.login(req.body, requestMeta(req));
    return success(res, { message: 'Masuk berhasil', data });
  },

  async refresh(req, res) {
    const data = await authenticationService.refresh(req.body, requestMeta(req));
    return success(res, { message: 'Token berhasil diperbarui', data });
  },

  async forgotPassword(req, res) {
    await authenticationService.forgotPassword(req.body);
    return success(res, {
      statusCode: 202,
      message: `Jika email terdaftar, tautan atur ulang kata sandi telah dikirim dan berlaku ${env.passwordResetTtlMinutes} menit.`,
    });
  },

  async resetPassword(req, res) {
    await authenticationService.resetPassword(req.body);
    return success(res, { message: 'Kata sandi berhasil diubah. Silakan masuk dengan kata sandi baru.' });
  },

  async changePassword(req, res) {
    const data = await authenticationService.changePassword(req.user.id, req.body, requestMeta(req));
    return success(res, { message: 'Kata sandi berhasil diubah. Sesi di perangkat lain telah dikeluarkan.', data });
  },

  async logout(req, res) {
    await authenticationService.logout(req.user.id, req.body);
    return success(res, { message: 'Keluar berhasil' });
  },

  me(req, res) {
    return success(res, { data: req.user });
  },
};
