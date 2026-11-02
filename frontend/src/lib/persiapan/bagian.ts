// Metadata bagian persiapan fungsi Autentikasi — satu sumber kebenaran untuk hub,
// daftar bagian, dan form fokus. Status dihitung dari helper murni di auth.ts.
import type { PersiapanAuth } from '#lib/types.js';
import { akunAda, kurangLogin, kurangRegistrasi, kurangReset, kurangUbah } from '#lib/persiapan/auth.js';

export type IdBagian = 'login' | 'registrasi' | 'reset' | 'ubah' | 'akun' | 'pengaman' | 'izin' | 'dokumen';
export type StatusBagian = 'lengkap' | 'belum' | 'opsional';

export interface MetaBagian {
	id: IdBagian;
	nomor: number;
	judul: string;
	ket: string;
	wajib: boolean;
	/** Kode metode ringkas yang memakai isian bagian ini (mis. "1.1-T01"). */
	metode: string[];
	/** Bagian dengan pertanyaan "Ada / Tidak ada"; isian hanya tampil saat "Ada". */
	pertanyaan?: string;
}

export const BAGIAN_AUTH: MetaBagian[] = [
	{
		id: 'login',
		nomor: 1,
		judul: 'Halaman login',
		ket: 'Mesin uji membuka halaman login aplikasi dan mencoba masuk seperti pengguna biasa.',
		wajib: true,
		metode: ['1.1-T01', '1.1-T02', '1.2-T01', '1.4-T01', '1.7-T01', '1.7-T02']
	},
	{
		id: 'registrasi',
		nomor: 2,
		judul: 'Pendaftaran akun',
		ket: 'Mesin uji mencoba mendaftar dengan kata sandi lemah untuk memastikan server menolaknya.',
		wajib: false,
		metode: ['1.2-T02', '1.3-T01', '1.3-T02'],
		pertanyaan: 'Apakah pengguna bisa mendaftar akun sendiri di aplikasi ini?'
	},
	{
		id: 'reset',
		nomor: 3,
		judul: 'Lupa kata sandi',
		ket: 'Memeriksa agar fitur lupa kata sandi tidak membocorkan akun dan tautan pemulihannya hanya bisa dipakai sekali.',
		wajib: false,
		metode: ['1.3-T03', '1.5-T01', '1.5-T02', '1.5-T03'],
		pertanyaan: 'Apakah aplikasi punya fitur lupa kata sandi?'
	},
	{
		id: 'ubah',
		nomor: 4,
		judul: 'Ubah kata sandi',
		ket: 'Mesin uji masuk dengan akun uji lalu mencoba mengganti kata sandi menjadi lemah.',
		wajib: false,
		metode: ['1.3-T04'],
		pertanyaan: 'Apakah pengguna dapat mengubah kata sandinya sendiri?'
	},
	{
		id: 'akun',
		nomor: 5,
		judul: 'Akun uji',
		ket: 'Akun khusus pengujian, bukan akun pengguna nyata. Kata sandi disimpan terenkripsi dan tidak ditampilkan lagi.',
		wajib: true,
		metode: ['1.3-T04', '1.4-T01', '1.6-T01']
	},
	{
		id: 'pengaman',
		nomor: 6,
		judul: 'Pengaman tambahan',
		ket: 'Pengaman yang bisa menghalangi mesin uji (CAPTCHA, OTP, firewall). Bila ada, izinkan alamat IP mesin uji.',
		wajib: false,
		metode: []
	},
	{
		id: 'izin',
		nomor: 7,
		judul: 'Izin uji berisiko',
		ket: 'Uji penguncian akun memasukkan kata sandi salah berulang kali, sehingga akun uji cadangan bisa terkunci.',
		wajib: false,
		metode: ['1.4-T01']
	},
	{
		id: 'dokumen',
		nomor: 8,
		judul: 'Dokumen pendukung',
		ket: 'Hal yang tidak bisa diperiksa dari luar aplikasi dinilai asesor melalui dokumen.',
		wajib: true,
		metode: ['1.3-T05', '1.6-T02']
	}
];

export const META_BAGIAN: Record<IdBagian, MetaBagian> = Object.fromEntries(
	BAGIAN_AUTH.map((b) => [b.id, b])
) as Record<IdBagian, MetaBagian>;

export const ID_BAGIAN = BAGIAN_AUTH.map((b) => b.id);
export const adalahBagian = (v: string): v is IdBagian => ID_BAGIAN.includes(v as IdBagian);

const isi = (s: string) => s.trim().length > 0;

/** Status keterpenuhan data satu bagian. `opsional` = tidak diperhitungkan dalam ringkasan. */
export function statusBagian(p: PersiapanAuth, id: IdBagian): StatusBagian {
	switch (id) {
		case 'login':
			return !kurangLogin(p).length && isi(p.login.jalur_terbatas) ? 'lengkap' : 'belum';
		case 'registrasi':
			return p.registrasi.tersedia === false || (p.registrasi.tersedia === true && !kurangRegistrasi(p).length)
				? 'lengkap'
				: 'belum';
		case 'reset':
			return p.reset.tersedia === false || (p.reset.tersedia === true && !kurangReset(p).length) ? 'lengkap' : 'belum';
		case 'ubah':
			return p.ubah_password.tersedia === false || (p.ubah_password.tersedia === true && !kurangUbah(p).length)
				? 'lengkap'
				: 'belum';
		case 'akun':
			return akunAda(p.akun_uji.utama) ? 'lengkap' : 'belum';
		case 'dokumen':
			return isi(p.dokumen.kebijakan_masa_berlaku) && isi(p.dokumen.bukti_hashing) ? 'lengkap' : 'belum';
		case 'pengaman':
		case 'izin':
			return 'opsional';
	}
}

/** Ringkasan untuk hub: berapa bagian wajib/berstatus yang sudah lengkap. */
export function ringkasBagianAuth(p: PersiapanAuth): { selesai: number; total: number } {
	const berstatus = BAGIAN_AUTH.filter((b) => statusBagian(p, b.id) !== 'opsional');
	return { selesai: berstatus.filter((b) => statusBagian(p, b.id) === 'lengkap').length, total: berstatus.length };
}

/** Validasi ringan alamat: harus URL lengkap http(s); boleh beda domain dari URL dasar. */
export const alamatSalah = (v: string) => !!v && !/^https?:\/\/[^\s/?#]+([/?#]\S*)?$/.test(v);
