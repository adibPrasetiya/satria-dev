import { test } from 'node:test';
import assert from 'node:assert/strict';
import { akunUtamaAda, penerapanMetode } from '../src/features/scans/applicability.js';

const metodeButuhAkun = { testPoint: 'login', kind: 'otomatis', engine: 'custom', requiresAuth: true, profile: 'aman' };
const titik = { login: { tersedia: true } };

test('akun uji dari wizard (accounts.daftar) dikenali', () => {
  const target = { testPoints: titik, accounts: { daftar: [{ username: 'pegawai', password: 'rahasia' }] } };
  assert.equal(akunUtamaAda(target), true);
  assert.deepEqual(penerapanMetode(target, metodeButuhAkun), { jalan: true });
});

test('akun uji manual (accounts.utama) tetap dikenali', () => {
  assert.equal(akunUtamaAda({ accounts: { utama: { username: 'u', password: 'p' } } }), true);
});

test('tanpa akun ber-sandi → metode butuh autentikasi tak dijalankan', () => {
  const target = { testPoints: titik, accounts: { daftar: [{ username: 'pegawai', password: '' }] } };
  assert.equal(akunUtamaAda(target), false);
  assert.equal(penerapanMetode(target, metodeButuhAkun).jalan, false);
});

const metodeInpv = (testPoint) => ({ testPoint, kind: 'otomatis', engine: 'custom', requiresAuth: false, profile: 'aman' });

test('titik api/form_input diturunkan dari inventaris penemuan lama', () => {
  const target = {
    testPoints: {},
    discovery: {
      endpoints_lengkap: [
        { lapisan: 'frontend', request_fields: [{ nama: 'q', lokasi: 'query' }] },
        { lapisan: 'api', request_fields: [{ nama: 'email', lokasi: 'body' }] },
      ],
    },
  };
  assert.deepEqual(penerapanMetode(target, metodeInpv('api')), { jalan: true });
  assert.deepEqual(penerapanMetode(target, metodeInpv('form_input')), { jalan: true });
});

test('tanpa endpoint API ber-field → form_input tetap tidak berlaku', () => {
  const target = { testPoints: {}, discovery: { endpoints_lengkap: [{ lapisan: 'api', request_fields: [] }] } };
  assert.equal(penerapanMetode(target, metodeInpv('api')).jalan, true);
  assert.equal(penerapanMetode(target, metodeInpv('form_input')).status, 'tidak_berlaku');
});

test('out of scope: metode manual, engine tak didukung, dan (black box) yang butuh login', () => {
  const target = { testPoints: { login: { tersedia: true } }, accounts: { daftar: [{ username: 'a', password: 'b' }] } };
  const dasar = { testPoint: 'login', kind: 'otomatis', engine: 'custom', requiresAuth: false, profile: 'aman' };
  assert.equal(penerapanMetode(target, { ...dasar, kind: 'manual', engine: 'manual' }).status, 'luar_cakupan');
  assert.equal(penerapanMetode(target, { ...dasar, engine: 'burp' }).status, 'luar_cakupan');
  const butuhLogin = { ...dasar, requiresAuth: true };
  assert.deepEqual(penerapanMetode(target, butuhLogin), { jalan: true }, 'grey box dengan akun → dijalankan');
  assert.equal(penerapanMetode(target, butuhLogin, { pendekatan: 'blackbox' }).status, 'luar_cakupan');
  // Akun belum diisi (grey box) bukan out of scope — masih bisa diuji bila akun dilengkapi.
  assert.equal(penerapanMetode({ ...target, accounts: null }, butuhLogin).status, 'tidak_dapat_diverifikasi');
});
