import { logger } from './logger.js';

// Jejak audit keamanan (kontrol BSSN 6.x): siapa melakukan apa, kapan, dari mana, dan hasilnya.
// IP & kode request ikut tercatat otomatis lewat requestContext. Jangan sertakan kata sandi/token.
const PESAN = {
  'auth.daftar': 'Pendaftaran akun baru',
  'auth.daftar.duplikat': 'Pendaftaran dengan email/NRP yang sudah terdaftar diabaikan',
  'auth.cek_ketersediaan': 'Cek ketersediaan NRP/email',
  'auth.login.berhasil': 'Login berhasil',
  'auth.login.gagal': 'Login gagal',
  'auth.akun.dikunci': 'Akun dikunci karena login gagal berturut-turut',
  'auth.refresh.reuse': 'Refresh token lama dipakai ulang; semua sesi user dicabut',
  'auth.logout': 'Logout',
  'auth.lupa_sandi': 'Permintaan atur ulang kata sandi',
  'auth.reset_sandi.berhasil': 'Kata sandi diatur ulang lewat tautan',
  'auth.reset_sandi.gagal': 'Tautan atur ulang kata sandi ditolak',
  'auth.ganti_sandi.berhasil': 'Kata sandi diganti oleh pemilik akun',
  'auth.ganti_sandi.gagal': 'Ganti kata sandi ditolak',
  'pengguna.verifikasi': 'Admin memverifikasi akun',
  'pengguna.tolak': 'Admin menolak pendaftaran',
  'pengguna.status': 'Admin mengubah status akun',
  'satuan.tambah': 'Admin menambah satuan kerja',
  'satuan.ubah': 'Admin mengubah satuan kerja',
  'aplikasi.daftar': 'Aset aplikasi didaftarkan',
  'aplikasi.ubah': 'Data aset aplikasi diubah',
  'katalog.kontrol.tambah': 'Admin menambah kontrol katalog',
  'katalog.kontrol.ubah': 'Admin mengubah kontrol katalog',
  'katalog.metode.tambah': 'Admin menambah metode pengujian',
  'katalog.metode.ubah': 'Admin mengubah metode pengujian',
  'scan.mulai': 'Pengujian (scan) dimulai',
  'scan.batal': 'Pengujian dibatalkan',
  'scan.selesai': 'Pengujian selesai',
  'scan.target.simpan': 'Persiapan pengujian (target) disimpan',
  'akses.ditolak': 'Akses ditolak (peran tidak sesuai)',
  'rate_limit.terlampaui': 'Batas permintaan terlampaui',
};

// Kejadian yang patut dicurigai dicatat sebagai warn; sisanya info.
const WARN = new Set([
  'auth.daftar.duplikat',
  'auth.login.gagal',
  'auth.akun.dikunci',
  'auth.refresh.reuse',
  'auth.reset_sandi.gagal',
  'auth.ganti_sandi.gagal',
  'akses.ditolak',
  'rate_limit.terlampaui',
]);

/** `audit('auth.login.gagal', { email, alasan: 'sandi_salah' })` */
export function audit(event, data = {}, level = WARN.has(event) ? 'warn' : 'info') {
  logger.log(level, PESAN[event] ?? event, { kategori: 'audit', event, ...data });
}
