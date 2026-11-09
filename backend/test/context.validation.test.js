import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { buildContext } = await import('../src/features/scans/context.js');
const { mulaiScanSchema, saveTargetSchema } = await import('../src/features/scans/scans.validation.js');

const scan = { id: 7 };
const application = { id: 3, baseUrl: 'https://contoh.go.id' };

describe('buildContext → buildAkunUji', () => {
  it('memetakan accounts.daftar (N akun) ke akun_uji_1..N + totp_secret', () => {
    const target = {
      accounts: {
        daftar: [
          { username: 'admin', password: 'Admin@123', totp_secret: 'JBSWY3DPEHPK3PXP' },
          { username: 'user2', password: 'User@123' },
          { username: 'kosong', password: '' }, // dilewati (tak lengkap)
        ],
      },
    };
    const ctx = buildContext({ scan, application, target });
    assert.equal(ctx.akun_uji.length, 2);
    assert.deepEqual(
      ctx.akun_uji.map((a) => a.kunci),
      ['akun_uji_1', 'akun_uji_2'],
    );
    assert.equal(ctx.akun_uji[0].totp_secret, 'JBSWY3DPEHPK3PXP');
    assert.equal(ctx.akun_uji[1].totp_secret, null);
  });

  it('scan black box tidak membawa akun uji walau akun tersimpan', () => {
    const target = { accounts: { daftar: [{ username: 'admin', password: 'Admin@123' }] } };
    assert.deepEqual(buildContext({ scan: { id: 8, approach: 'blackbox' }, application, target }).akun_uji, []);
    assert.equal(buildContext({ scan: { id: 8, approach: 'greybox' }, application, target }).akun_uji.length, 1);
  });

  it('tetap mendukung bentuk lama { utama, penguncian }', () => {
    const target = {
      accounts: {
        utama: { username: 'u', password: 'p', totp_secret: 'AAAA' },
        penguncian: { username: 'k', password: 'q' },
      },
    };
    const ctx = buildContext({ scan, application, target });
    assert.deepEqual(
      ctx.akun_uji.map((a) => a.kunci),
      ['akun_uji_1', 'akun_uji_2'],
    );
    assert.equal(ctx.akun_uji[0].totp_secret, 'AAAA');
  });

  it('meneruskan inventaris discovery (endpoints/flows/kandidat) ke konteks', () => {
    const target = { discovery: { endpoints_lengkap: [{ x: 1 }], flows: [], kandidat_uji: { per_endpoint: [] } } };
    const ctx = buildContext({ scan, application, target });
    assert.equal(ctx.endpoints.length, 1);
    assert.ok(ctx.kandidat_uji);
  });
});

describe('validasi: totp_secret tidak lagi terbuang', () => {
  it('mulaiScanSchema menerima accounts.daftar + totp_secret', () => {
    const { value, error } = mulaiScanSchema.validate(
      {
        mode: 'eksploratif',
        persetujuan: true,
        accounts: { daftar: [{ username: 'a', password: 'b', totp_secret: 'SEED' }] },
        options: { izinkan_penguncian: true },
      },
      { stripUnknown: true },
    );
    assert.equal(error, undefined);
    assert.equal(value.accounts.daftar[0].totp_secret, 'SEED');
  });

  it('mempertahankan parameter TOTP non-standar & meneruskannya ke konteks', () => {
    const { value, error } = mulaiScanSchema.validate(
      {
        mode: 'eksploratif',
        persetujuan: true,
        accounts: { daftar: [{ username: 'a', password: 'b', totp_secret: 'SEED', totp_digits: 8, totp_period: 60, totp_algoritma: 'sha256' }] },
      },
      { stripUnknown: true },
    );
    assert.equal(error, undefined);
    const a = value.accounts.daftar[0];
    assert.deepEqual([a.totp_digits, a.totp_period, a.totp_algoritma], [8, 60, 'SHA256']);
    const ctx = buildContext({ scan, application, target: { accounts: value.accounts } });
    assert.deepEqual(
      [ctx.akun_uji[0].totp_digits, ctx.akun_uji[0].totp_period, ctx.akun_uji[0].totp_algoritma],
      [8, 60, 'SHA256'],
    );
  });

  it('menolak parameter TOTP tak valid', () => {
    const { error } = mulaiScanSchema.validate({
      mode: 'eksploratif',
      persetujuan: true,
      accounts: { daftar: [{ username: 'a', password: 'b', totp_algoritma: 'MD5' }] },
    });
    assert.ok(error);
  });

  it('saveTargetSchema mempertahankan totp_secret (bentuk lama & daftar)', () => {
    const { value, error } = saveTargetSchema.validate(
      {
        test_points: {},
        accounts: { utama: { username: 'u', password: 'p', totp_secret: 'X' }, daftar: [{ username: 'a', password: 'b', totp_secret: 'Y' }] },
      },
      { stripUnknown: true },
    );
    assert.equal(error, undefined);
    assert.equal(value.accounts.utama.totp_secret, 'X');
    assert.equal(value.accounts.daftar[0].totp_secret, 'Y');
  });
});
