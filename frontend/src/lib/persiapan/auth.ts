// Kesiapan metode fungsi Autentikasi berdasarkan isian persiapan pengujian.
// Murni (tanpa I/O): dipakai panel "Kesiapan metode" sekarang, dan dapat dipakai backend/worker nanti
// untuk memutuskan metode mana yang dijalankan, dilewati, atau diserahkan ke asesor.
import type { KesiapanMetode, Metode, PersiapanAuth } from '#lib/types.js';

export function persiapanAuthKosong(): PersiapanAuth {
	return {
		login: {
			jalur_halaman: '',
			jalur_aksi: '',
			metode_http: 'POST',
			field_username: '',
			field_password: '',
			penanda_berhasil: '',
			penanda_gagal: '',
			jalur_terbatas: ''
		},
		registrasi: {
			tersedia: null,
			jalur_halaman: '',
			jalur_aksi: '',
			field_identitas: '',
			field_password: '',
			field_konfirmasi: '',
			field_lain: [],
			catatan_pembersihan: ''
		},
		reset: { tersedia: null, jalur_halaman: '', jalur_aksi: '', field_identitas: '', email_akun_uji: '' },
		ubah_password: { tersedia: null, jalur_halaman: '', jalur_aksi: '', field_lama: '', field_baru: '', field_konfirmasi: '' },
		akun_uji: { utama: { username: '', terisi: false }, penguncian: { username: '', terisi: false } },
		hambatan: { captcha: false, mfa: false, waf: false, dikecualikan_untuk_worker: false },
		intrusif: { izinkan_penguncian: false, jendela_mulai: '', jendela_selesai: '' },
		dokumen: { kebijakan_masa_berlaku: '', bukti_hashing: '' }
	};
}

const isi = (s: string) => s.trim().length > 0;
export const akunAda = (a: { username: string; terisi: boolean; password?: string }) =>
	isi(a.username) && (a.terisi || !!a.password);

/** Label isian yang masih kosong dari pasangan [label, nilai]. */
const kurang = (pasangan: [string, string][]) => pasangan.filter(([, v]) => !isi(v)).map(([l]) => l);

export const kurangLogin = (p: PersiapanAuth) =>
	kurang([
		['alamat halaman login', p.login.jalur_halaman],
		['alamat penerima data login', p.login.jalur_aksi],
		['kolom username', p.login.field_username],
		['kolom kata sandi', p.login.field_password]
	]);

export const kurangRegistrasi = (p: PersiapanAuth) =>
	kurang([
		['alamat halaman pendaftaran', p.registrasi.jalur_halaman],
		['alamat penerima data pendaftaran', p.registrasi.jalur_aksi],
		['kolom username/email', p.registrasi.field_identitas],
		['kolom kata sandi', p.registrasi.field_password]
	]);

export const kurangReset = (p: PersiapanAuth) =>
	kurang([
		['alamat halaman lupa kata sandi', p.reset.jalur_halaman],
		['alamat penerima data reset', p.reset.jalur_aksi],
		['kolom username/email', p.reset.field_identitas],
		['email akun uji', p.reset.email_akun_uji]
	]);

export const kurangUbah = (p: PersiapanAuth) =>
	kurang([
		['alamat halaman ubah kata sandi', p.ubah_password.jalur_halaman],
		['alamat penerima data ubah sandi', p.ubah_password.jalur_aksi],
		['kolom kata sandi lama', p.ubah_password.field_lama],
		['kolom kata sandi baru', p.ubah_password.field_baru]
	]);

const perluData = (daftar: string[]): KesiapanMetode => ({ status: 'perlu_data', alasan: `Lengkapi ${daftar.join(', ')}` });

/** Kesiapan satu metode AUTH dari isian persiapan. */
export function kesiapanMetodeAuth(p: PersiapanAuth, m: Metode): KesiapanMetode {
	// Metode dokumen: diperiksa asesor dari dokumen yang diunggah.
	if (m.titik_uji === 'dokumen') {
		const berkas = m.check_id === 'manual.password_hashing' ? p.dokumen.bukti_hashing : p.dokumen.kebijakan_masa_berlaku;
		return isi(berkas)
			? { status: 'asesor', alasan: 'Dokumen siap ditinjau asesor' }
			: { status: 'perlu_data', alasan: 'Unggah dokumen untuk asesor' };
	}

	// Fitur yang tidak ada di aplikasi → metode tidak berlaku.
	const fitur: Record<string, { tersedia: boolean | null }> = {
		registrasi: p.registrasi,
		reset_password: p.reset,
		ubah_password: p.ubah_password
	};
	const f = fitur[m.titik_uji];
	if (f?.tersedia === false) return { status: 'dilewati', alasan: 'Fitur tidak ada di aplikasi' };
	if (f?.tersedia === null) return { status: 'perlu_data', alasan: 'Jawab apakah fitur ini ada di aplikasi' };

	const butuh: string[] = [];
	if (['login', 'area_terautentikasi', 'ubah_password'].includes(m.titik_uji) || m.butuh_autentikasi) butuh.push(...kurangLogin(p));
	if (m.titik_uji === 'registrasi') butuh.push(...kurangRegistrasi(p));
	if (m.titik_uji === 'reset_password') butuh.push(...kurangReset(p));
	if (m.titik_uji === 'ubah_password') butuh.push(...kurangUbah(p));
	if ((m.check_id === 'auth.login_required' || m.titik_uji === 'area_terautentikasi') && !isi(p.login.jalur_terbatas)) {
		butuh.push('halaman khusus pengguna terdaftar');
	}
	if (m.butuh_autentikasi && !akunAda(p.akun_uji.utama)) butuh.push('akun uji utama');

	// Uji intrusif penguncian akun: butuh izin dan akun yang boleh terkunci.
	if (m.profil === 'intrusif') {
		if (!p.intrusif.izinkan_penguncian) return { status: 'dilewati', alasan: 'Izin uji berisiko belum diberikan' };
		if (!akunAda(p.akun_uji.penguncian)) butuh.push('akun uji cadangan');
	}
	if (butuh.length) return perluData([...new Set(butuh)]);

	// Hambatan otomasi menggagalkan uji otomatis bila tidak dikecualikan untuk worker.
	const h = p.hambatan;
	if ((h.captcha || h.mfa || h.waf) && !h.dikecualikan_untuk_worker && m.engine !== 'manual') {
		return { status: 'perlu_data', alasan: 'Izinkan alamat IP mesin uji pada pengaman tambahan' };
	}
	if (m.engine === 'manual' || m.jenis === 'manual') return { status: 'asesor', alasan: 'Diperiksa asesor saat pengujian' };
	return {
		status: 'siap',
		alasan: m.jenis === 'semi_otomatis' ? 'Siap; sebagian langkah dikonfirmasi asesor' : 'Siap dijalankan mesin uji'
	};
}

/** Kelengkapan per bagian formulir (untuk indikator di navigasi). */
export function kelengkapanAuth(p: PersiapanAuth): { selesai: number; total: number } {
	const fitur = (f: { tersedia: boolean | null }, kurangFn: () => string[]) =>
		f.tersedia === false || (f.tersedia === true && !kurangFn().length);
	const bagian = [
		!kurangLogin(p).length && isi(p.login.jalur_terbatas),
		fitur(p.registrasi, () => kurangRegistrasi(p)),
		fitur(p.reset, () => kurangReset(p)),
		fitur(p.ubah_password, () => kurangUbah(p)),
		akunAda(p.akun_uji.utama),
		isi(p.dokumen.kebijakan_masa_berlaku) && isi(p.dokumen.bukti_hashing)
	];
	return { selesai: bagian.filter(Boolean).length, total: bagian.length };
}
