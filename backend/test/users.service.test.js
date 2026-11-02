import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createUsersService } = await import('../src/features/users/users.service.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

const NOW = new Date('2026-10-21T08:00:00.700Z');

describe('users.service', () => {
  let rows;
  let service;
  let events;
  const admin = { id: '1', peran: 'admin' };

  beforeEach(() => {
    rows = [
      { id: 1, name: 'Admin', nrp: '1000001', unitId: 1, unit: 'Pusat', email: 'admin@x.mil.id', role: 'admin', isVerified: true, isActive: true, createdAt: NOW },
      { id: 2, name: 'Pendaftar', nrp: '2000002', unitId: 2, unit: 'Satuan A', email: 'baru@x.mil.id', role: 'pemilik', isVerified: false, isActive: true, createdAt: NOW },
      { id: 3, name: 'Asesor', nrp: '3000003', unitId: 3, unit: 'Satuan B', email: 'asesor@x.mil.id', role: 'asesor', isVerified: true, isActive: true, createdAt: NOW },
    ];
    events = [];
    service = createUsersService({
      now: () => NOW,
      auditor: (event, data) => events.push([event, data]),
      repository: {
        list: async ({ status }) => {
          const filtered = rows.filter((r) =>
            status === 'pending' ? !r.isVerified : status === 'verified' ? r.isVerified && r.isActive : status === 'inactive' ? r.isVerified && !r.isActive : true,
          );
          return { rows: filtered, total: filtered.length };
        },
        findById: async (id) => rows.find((r) => r.id === id) ?? null,
        countActiveAdmins: async () => rows.filter((r) => r.role === 'admin' && r.isActive && r.isVerified).length,
        verify: async (id, { role, verifiedBy, verifiedAt }) => Object.assign(rows.find((r) => r.id === id), { isVerified: true, role, verifiedBy, verifiedAt }),
        removePending: async (id) => (rows = rows.filter((r) => r.id !== id || r.isVerified)),
        setActive: async (id, isActive) => Object.assign(rows.find((r) => r.id === id), { isActive }),
      },
    });
  });

  it('tindakan admin tercatat di audit beserta akun targetnya', async () => {
    await service.verify(admin, 2, { peran: 'asesor' });
    await service.setStatus(admin, 3, { aktif: false });
    assert.deepEqual(events.map(([e, d]) => [e, d.targetUserId]), [['pengguna.verifikasi', 2], ['pengguna.status', 3]]);
  });

  it('list memfilter status pending & menandai status tiap akun', async () => {
    const { items, meta } = await service.list({ page: 1, limit: 25, search: '', status: 'pending' });
    assert.deepEqual(items.map((u) => u.email), ['baru@x.mil.id']);
    assert.equal(items[0].status, 'pending');
    assert.equal(items[0].terverifikasi, false);
    assert.equal(meta.total, 1);
  });

  it('verify mengubah flag, mencatat admin & waktu, dan menetapkan peran', async () => {
    const user = await service.verify(admin, 2, { peran: 'asesor' });
    assert.equal(user.terverifikasi, true);
    assert.equal(user.peran, 'asesor');
    assert.equal(user.status, 'verified');
    assert.equal(rows[1].verifiedBy, 1);
    assert.equal(rows[1].verifiedAt.getMilliseconds(), 0, 'presisi detik');
    await assert.rejects(service.verify(admin, 2, { peran: 'pemilik' }), { statusCode: 409 });
    await assert.rejects(service.verify(admin, 99, { peran: 'pemilik' }), { statusCode: 404 });
  });

  it('reject hanya untuk akun yang belum diverifikasi', async () => {
    await assert.rejects(service.reject(admin, 3), { statusCode: 400 });
    await service.reject(admin, 2);
    assert.ok(!rows.some((r) => r.id === 2));
  });

  it('setStatus: akun pending harus diverifikasi dulu, admin tidak bisa mengubah dirinya, admin aktif terakhir dipertahankan', async () => {
    await assert.rejects(service.setStatus(admin, 2, { aktif: false }), { statusCode: 400 });
    await assert.rejects(service.setStatus(admin, 1, { aktif: false }), { statusCode: 400 });

    const nonaktif = await service.setStatus(admin, 3, { aktif: false });
    assert.equal(nonaktif.aktif, false);
    assert.equal(nonaktif.status, 'inactive');

    // Admin lain mencoba menonaktifkan satu-satunya admin aktif.
    await assert.rejects(service.setStatus({ id: '3', peran: 'admin' }, 1, { aktif: false }), { statusCode: 400 });
  });
});
