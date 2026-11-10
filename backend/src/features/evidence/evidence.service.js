import { randomBytes } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { mkdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { env } from '../../config/env.js';
import { AppError } from '../../utils/AppError.js';

// Bukti gambar (screenshot) diunggah worker, disimpan sebagai berkas PNG di EVIDENCE_DIR, dan disajikan
// read-only lewat CAPABILITY URL: nama berkas acak tak tertebak. Auth aplikasi memakai Bearer token yang
// tak dapat dikirim tag <img>, sehingga kontrol akses di sini berbasis kepemilikan URL (URL hanya tersimpan
// pada hasil scan yang terlihat oleh pengguna berwenang). Hanya PNG, ukuran dibatasi, path aman dari traversal.

const PNG_MAGIC = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const MAKS_BYTE = 6 * 1024 * 1024; // selaras batas body /internal (10mb base64 ≈ 7mb biner)
const RX_FILE = /^[0-9a-f]{32}\.png$/;

function akarDir() {
  return path.resolve(env.evidenceDir);
}

/** Direktori satu scan, dipastikan berada DI DALAM akar bukti (cegah traversal via scanId). */
function dirScan(scanId) {
  const id = String(scanId);
  if (!/^\d+$/.test(id)) throw AppError.badRequest('ID scan tidak valid');
  const akar = akarDir();
  const dir = path.resolve(akar, id);
  if (dir !== path.join(akar, id)) throw AppError.badRequest('Jalur bukti tidak valid');
  return dir;
}

/** Simpan satu PNG (base64) milik sebuah scan. Return { url, id, bytes }. */
export async function simpanGambar(scanId, gambarBase64) {
  const data = Buffer.from(String(gambarBase64 || ''), 'base64');
  if (data.length === 0) throw AppError.badRequest('Data gambar kosong');
  if (data.length > MAKS_BYTE) throw AppError.badRequest('Gambar melebihi batas ukuran');
  if (!data.subarray(0, 8).equals(PNG_MAGIC)) throw AppError.badRequest('Hanya berkas PNG yang diterima');
  const dir = dirScan(scanId);
  await mkdir(dir, { recursive: true });
  const id = randomBytes(16).toString('hex');
  await writeFile(path.join(dir, `${id}.png`), data);
  // URL relatif same-origin (nginx mem-proxy /api → backend); aman dipakai sebagai <img src>.
  return { url: `/api/v1/evidence/${scanId}/${id}.png`, id, bytes: data.length };
}

/** Jalur berkas bukti yang sudah divalidasi (untuk disajikan). 404 bila nama tak valid / tak ada. */
export async function berkasGambar(scanId, file) {
  if (!RX_FILE.test(String(file || ''))) throw AppError.notFound('Bukti tidak ditemukan');
  const p = path.join(dirScan(scanId), file);
  try {
    const s = await stat(p);
    if (!s.isFile()) throw new Error('bukan berkas');
  } catch {
    throw AppError.notFound('Bukti tidak ditemukan');
  }
  return p;
}

/** Stream berkas bukti ke response (dipakai route publik serve). */
export async function sajikanGambar(scanId, file, res) {
  const p = await berkasGambar(scanId, file);
  res.setHeader('Content-Type', 'image/png');
  res.setHeader('Cache-Control', 'private, max-age=86400');
  createReadStream(p).pipe(res);
}
