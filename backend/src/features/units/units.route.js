import { Router } from 'express';
import { validate } from '../../middleware/validate.js';
import { unitsController } from './units.controller.js';
import { searchUnitsSchema } from './units.validation.js';

// Publik: daftar satuan dibutuhkan di halaman pendaftaran sebelum pengguna punya akun.
// GET /units?search=kata&limit=20 — pencarian, bukan seluruh daftar.
export const unitsRouter = Router();

unitsRouter.get('/', validate(searchUnitsSchema, 'query'), unitsController.list);
