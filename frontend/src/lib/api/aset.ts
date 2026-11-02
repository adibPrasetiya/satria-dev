import type { Aplikasi } from '#lib/types.js';

/**
 * Bagian persiapan pengujian untuk aset yang belum disiapkan. Aset di backend hanya menyimpan data dasar;
 * halaman pengujian (masih mock) tetap membaca field ini sampai fitur pengujian dibuat.
 */
export function bagianUjiKosong(): Pick<
	Aplikasi,
	'verifikasi' | 'titik_uji' | 'akun_uji' | 'profil_pengujian' | 'izin_intrusif'
> {
	return {
		verifikasi: { metode: 'dns', token: '', status: 'belum' },
		titik_uji: {},
		akun_uji: [],
		profil_pengujian: 'aman',
		izin_intrusif: { status: 'tidak_diminta' }
	};
}
