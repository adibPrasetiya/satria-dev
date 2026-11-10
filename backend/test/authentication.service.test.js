import assert from 'node:assert/strict';
import { after, beforeEach, describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { createAuthenticationService } = await import('../src/features/authentication/authentication.service.js');
const { availabilitySchema, changePasswordSchema, registerSchema, resetPasswordSchema } = await import('../src/features/authentication/authentication.validation.js');
const { verifyPassword } = await import('../src/utils/password.js');
const { hashToken } = await import('../src/utils/crypto.js');
const { pool } = await import('../src/db/index.js');

after(() => pool.end());

const SANDI = 'Rahasia!123';
const CONFIG = {
  refreshTokenTtlDays: 7,
  passwordResetTtlMinutes: 30,
  emailVerificationTtlHours: 24,
  login: { maxAttempts: 5, lockMinutes: 15 },
  appUrl: 'http://satya.test',
};

/** Repository palsu di memori dengan perilaku sama seperti versi MySQL. */
function createFakeRepository() {
  const state = { users: [], units: [{ id: 1, name: 'Satuan Uji', isActive: true }, { id: 2, name: 'Satuan Lama', isActive: false }], refreshTokens: [], resetTokens: [], verifyTokens: [], seq: 1 };
  return {
    state,
    findUserByEmail: async (email) => state.users.find((u) => u.email === email) ?? null,
    findUserById: async (id) => state.users.find((u) => u.id === id) ?? null,
    findActiveUnitById: async (id) => state.units.find((u) => u.id === id && u.isActive) ?? null,
    isTaken: async ({ email, nrp }) => state.users.some((u) => (email ? u.email === email : u.nrp === nrp)),
    emailOrNrpExists: async (email, nrp) => state.users.some((u) => u.email === email || u.nrp === nrp),
    createUser: async (data) => {
      const user = { id: state.seq++, isActive: true, isVerified: false, failedLoginCount: 0, lockedUntil: null, passwordChangedAt: null, ...data };
      state.users.push(user);
      return user;
    },
    updateUser: async (id, data) => Object.assign(state.users.find((u) => u.id === id), data),
    createRefreshToken: async (data) => state.refreshTokens.push({ id: state.seq++, revokedAt: null, revokedReason: null, ...data }),
    findRefreshTokenByHash: async (hash) => state.refreshTokens.find((t) => t.tokenHash === hash) ?? null,
    revokeRefreshToken: async (id, reason) => {
      const token = state.refreshTokens.find((t) => t.id === id);
      if (token.revokedAt) return false;
      Object.assign(token, { revokedAt: new Date(), revokedReason: reason });
      return true;
    },
    revokeAllRefreshTokensForUser: async (userId, reason) => {
      for (const t of state.refreshTokens) if (t.userId === userId && !t.revokedAt) Object.assign(t, { revokedAt: new Date(), revokedReason: reason });
    },
    createPasswordResetToken: async ({ userId, tokenHash, expiresAt, now }) => {
      for (const t of state.resetTokens) if (t.userId === userId && !t.usedAt) t.usedAt = now;
      state.resetTokens.push({ id: state.seq++, userId, tokenHash, expiresAt, usedAt: null });
    },
    findPasswordResetTokenByHash: async (hash) => state.resetTokens.find((t) => t.tokenHash === hash) ?? null,
    createEmailVerificationToken: async ({ userId, tokenHash, expiresAt, now }) => {
      for (const t of state.verifyTokens) if (t.userId === userId && !t.usedAt) t.usedAt = now;
      state.verifyTokens.push({ id: state.seq++, userId, tokenHash, expiresAt, usedAt: null });
    },
    findEmailVerificationTokenByHash: async (hash) => state.verifyTokens.find((t) => t.tokenHash === hash) ?? null,
    verifyEmail: async ({ userId, tokenId, verifiedAt }) => {
      const token = state.verifyTokens.find((t) => t.id === tokenId);
      if (token.usedAt) return false;
      token.usedAt = verifiedAt;
      const user = state.users.find((u) => u.id === userId);
      if (!user.isVerified) Object.assign(user, { isVerified: true, verifiedAt });
      return true;
    },
    changePassword: async ({ userId, passwordHash, passwordChangedAt }) => {
      Object.assign(state.users.find((u) => u.id === userId), { passwordHash, passwordChangedAt });
      for (const t of state.refreshTokens) if (t.userId === userId && !t.revokedAt) Object.assign(t, { revokedAt: passwordChangedAt, revokedReason: 'password_change' });
    },
    resetPassword: async ({ userId, tokenId, passwordHash, passwordChangedAt }) => {
      const token = state.resetTokens.find((t) => t.id === tokenId);
      if (token.usedAt) return false;
      token.usedAt = passwordChangedAt;
      Object.assign(state.users.find((u) => u.id === userId), { passwordHash, passwordChangedAt, failedLoginCount: 0, lockedUntil: null });
      for (const t of state.refreshTokens) if (t.userId === userId && !t.revokedAt) Object.assign(t, { revokedAt: passwordChangedAt, revokedReason: 'password_change' });
      return true;
    },
  };
}

describe('authentication.service', () => {
  let repo;
  let service;
  let clock;
  let mails;
  let events;
  const eventNames = () => events.map(([e]) => e);

  const daftar = (overrides = {}) =>
    service.register({
      nama: 'Uji Coba',
      status_kepegawaian: 'TNI',
      pangkat: 'Letda',
      nrp: '11080012',
      satuan_id: 1,
      email: 'uji@satuan.mil.id',
      password: SANDI,
      ...overrides,
    });
  const verifikasi = (email = 'uji@satuan.mil.id') => Object.assign(repo.state.users.find((u) => u.email === email), { isVerified: true });
  const tokenDariEmail = () => new URL(mails.at(-1).text.match(/https?:\/\/\S+/)[0]).searchParams.get('token');

  beforeEach(() => {
    repo = createFakeRepository();
    clock = new Date('2026-10-21T08:00:00.000Z');
    mails = [];
    events = [];
    service = createAuthenticationService({
      repository: repo,
      now: () => clock,
      config: CONFIG,
      mailer: async (m) => mails.push(m),
      auditor: (event, data) => events.push([event, data]),
    });
  });

  describe('register', () => {
    it('membuat akun pemilik yang belum terverifikasi dengan kata sandi ter-hash', async () => {
      await daftar();
      const [user] = repo.state.users;
      assert.equal(user.role, 'pemilik');
      assert.equal(user.isVerified, false);
      assert.notEqual(user.passwordHash, SANDI);
      assert.ok(await verifyPassword(SANDI, user.passwordHash));
    });

    it('menyimpan status kepegawaian & pangkat sebagai kolom tersendiri', async () => {
      await daftar();
      const [user] = repo.state.users;
      assert.equal(user.name, 'Uji Coba');
      assert.equal(user.employmentStatus, 'TNI');
      assert.equal(user.rank, 'Letda');
    });

    it('email/NRP yang sudah ada tidak membuat akun kedua dan tidak melempar galat (cegah enumerasi)', async () => {
      await daftar();
      await assert.doesNotReject(daftar({ nrp: '99999999' }));
      await assert.doesNotReject(daftar({ email: 'lain@satuan.mil.id' }));
      assert.equal(repo.state.users.length, 1);
    });

    it('skema menolak kata sandi lemah & NRP bukan angka', () => {
      const base = { nama: 'Nama Uji', status_kepegawaian: 'TNI', pangkat: 'Kapten', nrp: '11080012', satuan_id: 1, email: 'a@b.mil.id', password: SANDI };
      assert.equal(registerSchema.validate(base).error, undefined);
      assert.ok(registerSchema.validate({ ...base, password: 'rahasia123' }).error, 'tanpa huruf besar & simbol');
      assert.ok(registerSchema.validate({ ...base, password: 'Ab!1' }).error, 'terlalu pendek');
      assert.ok(registerSchema.validate({ ...base, nrp: 'ABC123' }).error);
      assert.ok(registerSchema.validate({ ...base, satuan_id: undefined }).error, 'satuan wajib dipilih');
      assert.ok(registerSchema.validate({ ...base, satuan_id: 'Satuan bebas' }).error, 'satuan harus id dari daftar');
    });

    it('skema mewajibkan status & pangkat, dan NIP PNS harus 18 digit', () => {
      const base = { nama: 'Nama Uji', status_kepegawaian: 'TNI', pangkat: 'Kapten', nrp: '11080012', satuan_id: 1, email: 'a@b.mil.id', password: SANDI };
      assert.ok(registerSchema.validate({ ...base, status_kepegawaian: undefined }).error, 'status wajib');
      assert.ok(registerSchema.validate({ ...base, status_kepegawaian: 'POLRI' }).error, 'status hanya TNI/PNS');
      assert.ok(registerSchema.validate({ ...base, pangkat: '' }).error, 'pangkat wajib');
      const pns = { ...base, status_kepegawaian: 'PNS', pangkat: 'Penata (III/c)' };
      assert.ok(registerSchema.validate({ ...pns, nrp: '11080012' }).error, 'NIP PNS tidak boleh 8 digit');
      assert.equal(registerSchema.validate({ ...pns, nrp: '198501012010011001' }).error, undefined);
    });

    it('menolak satuan yang tidak ada atau nonaktif di daftar', async () => {
      await assert.rejects(daftar({ satuan_id: 999 }), { statusCode: 400 });
      await assert.rejects(daftar({ satuan_id: 2 }), { statusCode: 400 });
      assert.equal(repo.state.users.length, 0);
    });
  });

  describe('audit', () => {
    it('mencatat login gagal (dengan alasan), penguncian, dan login berhasil tanpa kata sandi', async () => {
      await daftar();
      verifikasi();
      for (let i = 0; i < CONFIG.login.maxAttempts; i++) {
        await service.login({ email: 'uji@satuan.mil.id', password: 'Salah!123' }).catch(() => {});
      }
      assert.ok(events.some(([e, d]) => e === 'auth.login.gagal' && d.alasan === 'sandi_salah'));
      assert.ok(eventNames().includes('auth.akun.dikunci'));
      await service.login({ email: 'tidak.ada@satuan.mil.id', password: SANDI }).catch(() => {});
      assert.equal(events.at(-1)[1].alasan, 'email_tidak_terdaftar');

      clock = new Date(clock.getTime() + 16 * 60 * 1000);
      await service.login({ email: 'uji@satuan.mil.id', password: SANDI }, { userAgent: 'uji' });
      assert.equal(events.at(-1)[0], 'auth.login.berhasil');
      assert.ok(!JSON.stringify(events).includes(SANDI), 'kata sandi tidak boleh masuk log audit');
    });

    it('mencatat pendaftaran, duplikat, dan cek ketersediaan tanpa nilai yang dicek', async () => {
      await daftar();
      await daftar({ email: 'lain@satuan.mil.id' });
      await service.checkAvailability({ nrp: '55555555' });
      assert.deepEqual(eventNames(), ['auth.daftar', 'auth.daftar.duplikat', 'auth.cek_ketersediaan']);
      assert.deepEqual(events.at(-1)[1], { kolom: 'nrp', tersedia: true });
    });
  });

  describe('changePassword', () => {
    const BARU = 'SandiBaru#789';
    let sesi;
    beforeEach(async () => {
      await daftar();
      verifikasi();
      sesi = await service.login({ email: 'uji@satuan.mil.id', password: SANDI });
    });

    it('kata sandi lama salah ditolak 400 & tercatat audit; hash tidak berubah', async () => {
      const hashLama = repo.state.users[0].passwordHash;
      await assert.rejects(service.changePassword('1', { passwordLama: 'Salah!123', passwordBaru: BARU }), { statusCode: 400 });
      assert.equal(repo.state.users[0].passwordHash, hashLama);
      assert.equal(events.at(-1)[0], 'auth.ganti_sandi.gagal');
    });

    it('menolak kata sandi baru yang sama dengan yang lama', async () => {
      await assert.rejects(service.changePassword('1', { passwordLama: SANDI, passwordBaru: SANDI }), { statusCode: 400 });
    });

    it('berhasil: sandi baru berlaku, sesi lama dicabut, token baru tetap sah', async () => {
      clock = new Date(clock.getTime() + 5000);
      const hasil = await service.changePassword('1', { passwordLama: SANDI, passwordBaru: BARU });
      assert.ok(await verifyPassword(BARU, repo.state.users[0].passwordHash));
      // Refresh token sebelum ganti sandi sudah dicabut, refresh token baru masih bisa dipakai.
      await assert.rejects(service.refresh({ refreshToken: sesi.refreshToken }), { statusCode: 401 });
      await assert.doesNotReject(service.refresh({ refreshToken: hasil.refreshToken }));
      assert.ok(eventNames().includes('auth.ganti_sandi.berhasil'));
    });

    it('skema mewajibkan sandi lama & kebijakan sandi baru', () => {
      assert.equal(changePasswordSchema.validate({ passwordLama: SANDI, passwordBaru: BARU }).error, undefined);
      assert.ok(changePasswordSchema.validate({ passwordLama: '', passwordBaru: BARU }).error);
      assert.ok(changePasswordSchema.validate({ passwordLama: SANDI, passwordBaru: 'lemah' }).error);
    });
  });

  describe('checkAvailability', () => {
    it('melaporkan NRP/email yang sudah dipakai dan yang masih tersedia', async () => {
      await daftar();
      assert.deepEqual(await service.checkAvailability({ nrp: '11080012' }), { tersedia: false });
      assert.deepEqual(await service.checkAvailability({ email: 'uji@satuan.mil.id' }), { tersedia: false });
      assert.deepEqual(await service.checkAvailability({ nrp: '99999999' }), { tersedia: true });
      assert.deepEqual(await service.checkAvailability({ email: 'baru@satuan.mil.id' }), { tersedia: true });
    });

    it('skema meminta tepat satu kolom yang formatnya valid', () => {
      assert.equal(availabilitySchema.validate({ nrp: '11080012' }).error, undefined);
      assert.equal(availabilitySchema.validate({ email: 'A@B.mil.id' }).value.email, 'a@b.mil.id');
      assert.ok(availabilitySchema.validate({}).error);
      assert.ok(availabilitySchema.validate({ nrp: '11080012', email: 'a@b.mil.id' }).error);
      assert.ok(availabilitySchema.validate({ nrp: '12ab' }).error);
    });
  });

  describe('login', () => {
    it('akun belum diverifikasi ditolak dengan ACCOUNT_PENDING setelah kata sandi benar', async () => {
      await daftar();
      await assert.rejects(service.login({ email: 'uji@satuan.mil.id', password: SANDI }), { statusCode: 403, code: 'ACCOUNT_PENDING' });
      // Kata sandi salah tetap "salah", tidak membocorkan status verifikasi.
      await assert.rejects(service.login({ email: 'uji@satuan.mil.id', password: 'Salah!123' }), { statusCode: 401 });
    });

    it('akun terverifikasi bisa masuk; respons berisi token & data publik tanpa hash', async () => {
      await daftar();
      verifikasi();
      const result = await service.login({ email: 'uji@satuan.mil.id', password: SANDI }, { ip: '127.0.0.1' });
      assert.ok(result.accessToken && result.refreshToken);
      assert.deepEqual(Object.keys(result.user).sort(), [
        'aktif', 'email', 'id', 'nama', 'nrp', 'pangkat', 'peran', 'satuan', 'satuan_id', 'status_kepegawaian', 'terverifikasi',
      ]);
      assert.equal(result.user.terverifikasi, true);
      assert.equal(result.user.status_kepegawaian, 'TNI');
      assert.equal(result.user.pangkat, 'Letda');
      assert.equal(repo.state.users[0].lastLoginAt, clock);
    });

    it('email tidak terdaftar & kata sandi salah memberi pesan yang sama', async () => {
      await daftar();
      verifikasi();
      const a = await service.login({ email: 'tidakada@x.mil.id', password: SANDI }).catch((e) => e);
      const b = await service.login({ email: 'uji@satuan.mil.id', password: 'Salah!123' }).catch((e) => e);
      assert.equal(a.message, b.message);
      assert.equal(a.statusCode, 401);
    });

    it('5x salah berturut-turut mengunci akun 15 menit (423), lalu bisa masuk lagi setelah kedaluwarsa', async () => {
      await daftar();
      verifikasi();
      for (let i = 0; i < 4; i++) {
        await assert.rejects(service.login({ email: 'uji@satuan.mil.id', password: 'Salah!123' }), { statusCode: 401 });
      }
      await assert.rejects(service.login({ email: 'uji@satuan.mil.id', password: 'Salah!123' }), { statusCode: 423, code: 'ACCOUNT_LOCKED' });
      // Selama terkunci, kata sandi benar pun ditolak.
      await assert.rejects(service.login({ email: 'uji@satuan.mil.id', password: SANDI }), { statusCode: 423 });

      clock = new Date(clock.getTime() + 16 * 60 * 1000);
      await assert.doesNotReject(service.login({ email: 'uji@satuan.mil.id', password: SANDI }));
      assert.equal(repo.state.users[0].failedLoginCount, 0);
      assert.equal(repo.state.users[0].lockedUntil, null);
    });

    it('login berhasil mereset hitungan gagal', async () => {
      await daftar();
      verifikasi();
      await service.login({ email: 'uji@satuan.mil.id', password: 'Salah!123' }).catch(() => {});
      assert.equal(repo.state.users[0].failedLoginCount, 1);
      await service.login({ email: 'uji@satuan.mil.id', password: SANDI });
      assert.equal(repo.state.users[0].failedLoginCount, 0);
    });

    it('akun nonaktif ditolak', async () => {
      await daftar();
      Object.assign(repo.state.users[0], { isVerified: true, isActive: false });
      await assert.rejects(service.login({ email: 'uji@satuan.mil.id', password: SANDI }), { statusCode: 403, code: 'ACCOUNT_INACTIVE' });
    });
  });

  describe('verifikasi email', () => {
    it('pendaftaran mengirim tautan APP_URL/verifikasi-email; hanya hash token yang disimpan', async () => {
      await daftar();
      assert.equal(mails.length, 1);
      assert.equal(mails[0].to, 'uji@satuan.mil.id');
      assert.match(mails[0].text, /http:\/\/satya\.test\/verifikasi-email\?token=/);
      const token = tokenDariEmail();
      assert.equal(repo.state.verifyTokens[0].tokenHash, hashToken(token));
      assert.ok(!JSON.stringify(repo.state.verifyTokens).includes(token));
    });

    it('pendaftaran duplikat tidak mengirim email', async () => {
      await daftar();
      await daftar({ nrp: '99999999' });
      assert.equal(mails.length, 1);
    });

    it('membuka tautan memverifikasi akun (tanpa admin) sehingga bisa masuk; token sekali pakai', async () => {
      await daftar();
      const token = tokenDariEmail();
      await assert.rejects(service.login({ email: 'uji@satuan.mil.id', password: SANDI }), { code: 'ACCOUNT_PENDING' });
      await service.verifyEmail({ token });
      const [user] = repo.state.users;
      assert.equal(user.isVerified, true);
      assert.equal(user.verifiedBy, undefined, 'bukan diverifikasi admin');
      assert.equal(user.verifiedAt.getMilliseconds(), 0, 'presisi detik');
      assert.ok(await service.login({ email: 'uji@satuan.mil.id', password: SANDI }));
      await assert.rejects(service.verifyEmail({ token }), { statusCode: 400 });
      assert.equal(events.at(-1)[1].alasan, 'sudah_dipakai');
    });

    it('token kedaluwarsa & tak dikenal ditolak', async () => {
      await daftar();
      const token = tokenDariEmail();
      await assert.rejects(service.verifyEmail({ token: 'ngawur' }), { statusCode: 400 });
      clock = new Date(clock.getTime() + 25 * 60 * 60 * 1000);
      await assert.rejects(service.verifyEmail({ token }), { statusCode: 400 });
      assert.equal(repo.state.users[0].isVerified, false);
    });

    it('kirim ulang membatalkan tautan lama; akun terverifikasi / tak terdaftar tidak dikirimi', async () => {
      await daftar();
      const lama = tokenDariEmail();
      await service.resendVerification({ email: 'uji@satuan.mil.id' });
      assert.equal(mails.length, 2);
      const baru = tokenDariEmail();
      await assert.rejects(service.verifyEmail({ token: lama }), { statusCode: 400 });
      await service.verifyEmail({ token: baru });

      await service.resendVerification({ email: 'uji@satuan.mil.id' });
      await service.resendVerification({ email: 'tidakada@x.mil.id' });
      assert.equal(mails.length, 2);
      assert.deepEqual(events.slice(-2).map(([, d]) => d.tautanDikirim), [false, false]);
    });

    it('gagal kirim email tidak menggagalkan pendaftaran', async () => {
      service = createAuthenticationService({
        repository: repo,
        now: () => clock,
        config: CONFIG,
        mailer: async () => {
          throw new Error('SMTP mati');
        },
        auditor: () => {},
      });
      await assert.doesNotReject(daftar());
      assert.equal(repo.state.users.length, 1);
    });
  });

  describe('forgot & reset password', () => {
    beforeEach(async () => {
      await daftar();
      verifikasi();
      mails.length = 0;
    });

    it('email tidak terdaftar / belum terverifikasi tidak mengirim apa pun dan tidak melempar galat', async () => {
      await service.forgotPassword({ email: 'tidakada@x.mil.id' });
      await daftar({ email: 'pending@satuan.mil.id', nrp: '22222222' });
      await service.forgotPassword({ email: 'pending@satuan.mil.id' });
      assert.ok(!mails.some((m) => m.text.includes('/reset-sandi')));
      assert.equal(repo.state.resetTokens.length, 0);
    });

    it('mengirim tautan ke APP_URL/reset-sandi; hanya hash token yang disimpan', async () => {
      await service.forgotPassword({ email: 'uji@satuan.mil.id' });
      assert.equal(mails.length, 1);
      assert.match(mails[0].text, /http:\/\/satya\.test\/reset-sandi\?token=/);
      const token = tokenDariEmail();
      assert.equal(repo.state.resetTokens[0].tokenHash, hashToken(token));
      assert.ok(!JSON.stringify(repo.state.resetTokens).includes(token));
    });

    it('reset mengganti kata sandi, mencabut semua sesi, dan token hanya bisa dipakai sekali', async () => {
      await service.login({ email: 'uji@satuan.mil.id', password: SANDI });
      await service.forgotPassword({ email: 'uji@satuan.mil.id' });
      const token = tokenDariEmail();

      await service.resetPassword({ token, password: 'SandiBaru#456' });
      const user = repo.state.users[0];
      assert.ok(await verifyPassword('SandiBaru#456', user.passwordHash));
      assert.ok(repo.state.refreshTokens.every((t) => t.revokedReason === 'password_change'));

      await assert.rejects(service.resetPassword({ token, password: 'LainLagi#789' }), { statusCode: 400 });
      await assert.doesNotReject(service.login({ email: 'uji@satuan.mil.id', password: 'SandiBaru#456' }));
    });

    it('token kedaluwarsa ditolak', async () => {
      await service.forgotPassword({ email: 'uji@satuan.mil.id' });
      const token = tokenDariEmail();
      clock = new Date(clock.getTime() + 31 * 60 * 1000);
      await assert.rejects(service.resetPassword({ token, password: 'SandiBaru#456' }), { statusCode: 400 });
    });

    it('permintaan baru membatalkan tautan lama', async () => {
      await service.forgotPassword({ email: 'uji@satuan.mil.id' });
      const lama = tokenDariEmail();
      await service.forgotPassword({ email: 'uji@satuan.mil.id' });
      const baru = tokenDariEmail();
      await assert.rejects(service.resetPassword({ token: lama, password: 'SandiBaru#456' }), { statusCode: 400 });
      await assert.doesNotReject(service.resetPassword({ token: baru, password: 'SandiBaru#456' }));
    });

    it('reset membuka penguncian akun', async () => {
      repo.state.users[0].lockedUntil = new Date(clock.getTime() + 10 * 60 * 1000);
      await service.forgotPassword({ email: 'uji@satuan.mil.id' });
      await service.resetPassword({ token: tokenDariEmail(), password: 'SandiBaru#456' });
      assert.equal(repo.state.users[0].lockedUntil, null);
    });

    it('skema reset menerapkan kebijakan kata sandi', () => {
      assert.ok(resetPasswordSchema.validate({ token: 'x', password: 'lemah' }).error);
      assert.equal(resetPasswordSchema.validate({ token: 'x', password: 'SandiBaru#456' }).error, undefined);
    });
  });

  describe('refresh & authenticate', () => {
    beforeEach(async () => {
      await daftar();
      verifikasi();
    });

    it('refresh merotasi token; memakai token lama lagi mencabut semua sesi', async () => {
      const first = await service.login({ email: 'uji@satuan.mil.id', password: SANDI });
      const second = await service.refresh({ refreshToken: first.refreshToken });
      assert.notEqual(second.refreshToken, first.refreshToken);

      await assert.rejects(service.refresh({ refreshToken: first.refreshToken }), { statusCode: 401 });
      await assert.rejects(service.refresh({ refreshToken: second.refreshToken }), { statusCode: 401 }, 'sesi baru ikut dicabut');
    });

    it('authenticate menolak token dari akun yang sudah dinonaktifkan', async () => {
      const { accessToken } = await service.login({ email: 'uji@satuan.mil.id', password: SANDI });
      assert.equal((await service.authenticate(accessToken)).email, 'uji@satuan.mil.id');
      repo.state.users[0].isActive = false;
      await assert.rejects(service.authenticate(accessToken), { statusCode: 401 });
    });

    it('authenticate menolak token yang terbit sebelum kata sandi diubah', async () => {
      const { accessToken } = await service.login({ email: 'uji@satuan.mil.id', password: SANDI });
      repo.state.users[0].passwordChangedAt = new Date(Date.now() + 60_000);
      await assert.rejects(service.authenticate(accessToken), { statusCode: 401 });
    });
  });
});
