import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { after, before, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const DIR = mkdtempSync(path.join(tmpdir(), 'satya-ev-'));
process.env.EVIDENCE_DIR = DIR;

const { simpanGambar, berkasGambar } = await import('../src/features/evidence/evidence.service.js');

// PNG 1x1 minimal (magic + IHDR) cukup untuk lolos pemeriksaan magic byte.
const PNG = Buffer.from(
  '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000002000154a24f5f0000000049454e44ae426082',
  'hex',
);

after(() => rmSync(DIR, { recursive: true, force: true }));

describe('evidence.service', () => {
  it('simpan PNG → URL capability & berkas tertulis', async () => {
    const { url, id, bytes } = await simpanGambar('42', PNG.toString('base64'));
    assert.match(url, /^\/api\/v1\/evidence\/42\/[0-9a-f]{32}\.png$/);
    assert.match(id, /^[0-9a-f]{32}$/);
    assert.equal(bytes, PNG.length);
    const p = await berkasGambar('42', `${id}.png`);
    assert.deepEqual(readFileSync(p), PNG);
  });

  it('tolak non-PNG', async () => {
    await assert.rejects(() => simpanGambar('42', Buffer.from('bukan png').toString('base64')), /PNG/);
  });

  it('tolak data kosong', async () => {
    await assert.rejects(() => simpanGambar('42', ''), /kosong/);
  });

  it('scanId non-numerik ditolak (anti-traversal)', async () => {
    await assert.rejects(() => simpanGambar('../rahasia', PNG.toString('base64')), /tidak valid/);
  });

  it('nama berkas tak valid → 404 (tak melayani path sembarang)', async () => {
    await assert.rejects(() => berkasGambar('42', '../../etc/passwd'), /tidak ditemukan/);
    await assert.rejects(() => berkasGambar('42', 'bukan-hex.png'), /tidak ditemukan/);
  });
});
