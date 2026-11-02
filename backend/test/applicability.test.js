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
