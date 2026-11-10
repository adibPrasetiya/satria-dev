import { success } from '../../utils/response.js';
import { usersService } from './users.service.js';

export const usersController = {
  async list(req, res) {
    const data = await usersService.list(req.query);
    return success(res, { data });
  },

  async verify(req, res) {
    const data = await usersService.verify(req.user, req.params.id, req.body);
    return success(res, { message: `Akun ${data.nama} diverifikasi sebagai ${data.peran}`, data });
  },

  async reject(req, res) {
    await usersService.reject(req.user, req.params.id);
    return success(res, { message: 'Pendaftaran ditolak dan datanya dihapus' });
  },

  async setRole(req, res) {
    const data = await usersService.setRole(req.user, req.params.id, req.body);
    return success(res, { message: `Peran ${data.nama} diubah menjadi ${data.peran}`, data });
  },

  async setStatus(req, res) {
    const data = await usersService.setStatus(req.user, req.params.id, req.body);
    return success(res, { message: data.aktif ? 'Akun berhasil diaktifkan' : 'Akun berhasil dinonaktifkan', data });
  },
};
