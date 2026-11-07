import { Router } from 'express';
import { success } from '../../utils/response.js';
import { workersService } from './workers.service.js';
import { streamStatus } from './workers.stream.js';

// Status worker pengujian & antrean (semua pengguna login) — dasar indikator header & penjaga tombol Mulai.
export const workersRouter = Router();
workersRouter.get('/status', async (req, res) => {
  const data = await workersService.status(req.user);
  return success(res, { message: 'Status worker', data });
});

// SSE: status dikirim saat berubah saja (pengganti polling /status dari tiap tab).
workersRouter.get('/status/stream', streamStatus);
