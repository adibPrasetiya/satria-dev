import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'mysql://test:test@localhost:3306/test';
process.env.JWT_ACCESS_SECRET = 'test-secret-yang-panjangnya-lebih-dari-32-karakter';

const { sanitasi, susunKonteks, bangunPrompt } = await import('../src/features/laporan/laporan.konteks.js');
const { createLaporanService, rapikanKeluaran } = await import('../src/features/laporan/laporan.service.js');
const { muatProvider, parseJson } = await import('../src/features/laporan/laporan.ai.js');
const { pool } = await import('../src/db/index.js');
await pool.end();

const APLIKASI = {
  id: 7,
  name: 'Sistem Cuti Kodam',
  unit: 'Kodam III/Siliwangi',
  picName: 'Mayor Budi Santoso',
  baseUrl: 'https://cuti.kodam3.mil.id',
  environment: 'produksi',
  dataClassification: 'terbatas',
  techFrontend: 'SvelteKit',
  techBackend: 'Express',
  techDatabase: 'MySQL',
  techServer: '',
};
const SCAN = { id: 12, applicationId: 7, approach: 'greybox', mode: 'eksploratif', profile: 'aman', status: 'selesai', startedAt: '2026-11-09T02:00:00Z', finishedAt: '2026-11-09T02:12:00Z', verdict: 'tidak_laik', score: 60 };
const metode = (code, status, severity, ringkasan, extra = {}) => ({
  methodCode: code,
  status: 'selesai',
  result: { status, ringkasan, detail: extra.detail },
  methodName: `Metode ${code}`,
  severity,
  passCriteria: 'Kriteria lulus contoh',
  testPoint: 'login',
  controlRef: '1.2',
  controlDescription: 'Kontrol contoh',
  functionCode: code.split('-')[0],
  functionName: 'Autentikasi',
});
const METODE = [
  metode('AUTH-1.2-T01', 'gagal', 'tinggi', 'Login https://cuti.kodam3.mil.id/api/login/123 menerima sandi lemah untuk admin_cuti; Cookie: connect.sid=s%3Aabc123def456; token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc', {
    detail: 'Respons dari 10.20.30.40 berisi email budi@kodam3.mil.id dan Authorization: Bearer abcdef0123456789abcdef0123',
  }),
  metode('SESS-2.6-T01', 'gagal', 'sedang', 'Cookie sesi tanpa atribut Secure di Sistem Cuti Kodam (Kodam III/Siliwangi), PIC Mayor Budi Santoso'),
  metode('AUTH-1.1-T01', 'lulus', 'tinggi', 'OK'),
  metode('CONF-13.1-T01', 'tidak_dapat_diverifikasi', 'rendah', ''),
  metode('INFO-1-T01', 'gagal', 'info', 'informasi saja'),
];

describe('laporan: sanitasi', () => {
  it('menyamarkan URL/host, email, IP, JWT, bearer, cookie & nilai sensitif', () => {
    const s = sanitasi(
      'GET https://cuti.kodam3.mil.id/api/pegawai/42?nik=123 dari 192.168.1.10, kirim ke a.b@c.id; password=Rahasia1 token: eyJa.eyJb.cc Bearer xyz.abc',
      { host: 'cuti.kodam3.mil.id' },
    );
    assert.match(s, /\[host\]\/api\/pegawai\/\{id\}/);
    assert.doesNotMatch(s, /kodam3|192\.168|a\.b@c\.id|Rahasia1|eyJa|xyz\.abc/);
    assert.match(s, /password=\[disamarkan\]/);
  });

  it('istilah privat (nama aplikasi, akun uji) diganti placeholder', () => {
    const s = sanitasi('akun admin_cuti di Sistem Cuti Kodam', {
      privat: [
        { kata: 'admin_cuti', ganti: '[akun_uji]' },
        { kata: 'Sistem Cuti Kodam', ganti: '[aplikasi]' },
      ],
    });
    assert.equal(s, 'akun [akun_uji] di [aplikasi]');
  });
});

describe('laporan: konteks & prompt', () => {
  const konteks = susunKonteks({ aplikasi: APLIKASI, scan: SCAN, metode: METODE, akunUji: ['admin_cuti'], acuan: 'Peraturan BSSN' });
  const prompt = bangunPrompt(konteks);

  it('memuat konteks teknis lengkap: teknologi, metode uji, putusan, per fungsi, temuan', () => {
    assert.deepEqual(konteks.aplikasi.teknologi, { frontend: 'SvelteKit', backend: 'Express', basis_data: 'MySQL' });
    assert.match(konteks.pengujian.pendekatan, /Grey Box/);
    assert.equal(konteks.pengujian.durasi_menit, 12);
    assert.equal(konteks.hasil.putusan, 'tidak_laik');
    assert.deepEqual(konteks.temuan.map((t) => t.metode_id), ['AUTH-1.2-T01', 'SESS-2.6-T01'], 'urut severity; info bukan temuan');
    assert.equal(konteks.temuan[0].kriteria_lulus, 'Kriteria lulus contoh');
    assert.deepEqual(konteks.belum_terverifikasi, [{ metode_id: 'CONF-13.1-T01', nama: 'Metode CONF-13.1-T01' }]);
  });

  it('TIDAK memuat informasi sensitif di prompt', () => {
    for (const rahasia of [
      'Sistem Cuti Kodam',
      'Siliwangi',
      'Budi',
      'kodam3',
      'mil.id',
      'admin_cuti',
      '10.20.30.40',
      'abc123def456',
      'eyJhbGciOiJIUzI1NiJ9',
      'abcdef0123456789abcdef0123',
    ]) {
      assert.ok(!prompt.includes(rahasia), `prompt bocor: ${rahasia}`);
    }
    assert.match(prompt, /\[host\]\/api\/login\/\{id\}/);
    assert.match(prompt, /\[aplikasi\]/);
  });
});

describe('laporan: rapikanKeluaran & provider', () => {
  it('hanya rekomendasi untuk temuan yang ada, tanpa duplikat; prioritas tervalidasi', () => {
    const r = rapikanKeluaran(
      {
        ringkasan_eksekutif: '  Ringkas.  ',
        rekomendasi: [
          { metode_id: 'AUTH-1.2-T01', judul: 'Tegakkan kebijakan sandi', prioritas: 'segera', langkah: ['a', '', 'b'] },
          { metode_id: 'AUTH-1.2-T01', judul: 'duplikat' },
          { metode_id: 'KARANGAN-1', judul: 'tidak ada' },
          { metode_id: 'SESS-2.6-T01', judul: 'Set Secure', prioritas: 'darurat' },
        ],
        rekomendasi_umum: ['Uji ulang', 42],
      },
      ['AUTH-1.2-T01', 'SESS-2.6-T01'],
    );
    assert.equal(r.ringkasan_eksekutif, 'Ringkas.');
    assert.deepEqual(r.rekomendasi.map((x) => [x.metode_id, x.prioritas]), [['AUTH-1.2-T01', 'segera'], ['SESS-2.6-T01', 'sedang']]);
    assert.deepEqual(r.rekomendasi[0].langkah, ['a', 'b']);
    assert.deepEqual(r.rekomendasi_umum, ['Uji ulang']);
  });

  it('parseJson toleran pagar kode; muatProvider memilih sesuai konfigurasi', () => {
    assert.deepEqual(parseJson('```json\n{"a":1}\n```'), { a: 1 });
    assert.equal(parseJson('bukan json'), null);
    assert.equal(muatProvider({ provider: '', geminiKey: '', anthropicKey: '' }), null);
    assert.equal(muatProvider({ provider: 'none', geminiKey: 'k', anthropicKey: 'k' }), null);
    assert.equal(muatProvider({ provider: '', geminiKey: 'g', anthropicKey: 'a' }).nama, 'gemini');
    assert.equal(muatProvider({ provider: '', geminiKey: '', anthropicKey: 'a' }).nama, 'anthropic');
    assert.equal(muatProvider({ provider: 'anthropic', geminiKey: 'g', anthropicKey: 'a', model: '' }).model, 'claude-opus-5-5');
  });
});

describe('laporan.service', () => {
  const buat = ({ terakhir = 12, scan = SCAN, ai = true } = {}) => {
    const tersimpan = [];
    let promptTerkirim = '';
    const svc = createLaporanService({
      scans: { get: async () => ({ id: String(scan.id), status: scan.status }) },
      scanRepo: { findScanById: async () => scan },
      apps: { findById: async () => APLIKASI },
      repository: {
        metodeScan: async () => METODE,
        acuan: async () => 'Peraturan BSSN',
        akunUji: async () => ['admin_cuti'],
        scanSelesaiTerakhir: async () => terakhir,
        simpan: async (appId, scanId, data) => tersimpan.push([appId, scanId, data]),
      },
      provider: () =>
        ai
          ? {
              nama: 'gemini',
              model: 'gemini-uji',
              tanyaJson: async (p) => {
                promptTerkirim = p;
                return { ringkasan_eksekutif: 'R', rekomendasi: [{ metode_id: 'AUTH-1.2-T01', judul: 'J', langkah: ['x'] }] };
              },
            }
          : null,
      auditor: () => {},
      sekarang: () => new Date('2026-11-09T03:00:00Z'),
    });
    return { svc, tersimpan, prompt: () => promptTerkirim };
  };

  it('riwayat terakhir: laporan disimpan', async () => {
    const { svc, tersimpan, prompt } = buat();
    const hasil = await svc.generate({ id: '1', peran: 'admin' }, '12');
    assert.equal(hasil.ai.disimpan, true);
    assert.equal(hasil.ai.provider, 'gemini');
    assert.equal(tersimpan.length, 1);
    assert.equal(tersimpan[0][1], 12);
    assert.ok(!prompt().includes('kodam3'));
  });

  it('bukan riwayat terakhir: laporan disusun tetapi TIDAK disimpan', async () => {
    const { svc, tersimpan } = buat({ terakhir: 20 });
    const hasil = await svc.generate({ id: '1', peran: 'admin' }, '12');
    assert.equal(hasil.ai.disimpan, false);
    assert.equal(hasil.ai.rekomendasi.length, 1);
    assert.equal(tersimpan.length, 0);
  });

  it('pengujian dihentikan tidak disimpan; berjalan ditolak; AI tak aktif → 503', async () => {
    const dihentikan = buat({ scan: { ...SCAN, status: 'dibatalkan' } });
    assert.equal((await dihentikan.svc.generate({ id: '1', peran: 'admin' }, '12')).ai.disimpan, false);
    assert.equal(dihentikan.tersimpan.length, 0);
    await assert.rejects(buat({ scan: { ...SCAN, status: 'berjalan' } }).svc.generate({ id: '1' }, '12'), { statusCode: 400 });
    await assert.rejects(buat({ ai: false }).svc.generate({ id: '1' }, '12'), { statusCode: 503 });
  });
});
