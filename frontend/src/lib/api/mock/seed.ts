// Data contoh untuk mode mock.
import { titikUjiKosong } from '#lib/catalog.js';
import type { Aplikasi, PemetaanTitikUji, Pengguna, PengaturanAi, Satuan, Scan } from '#lib/types.js';
import { analisisTiruan, hasilLengkap } from './simulasi';

export interface StateMock {
	pengguna: Pengguna[];
	aplikasi: Aplikasi[];
	scan: Scan[];
	pengaturanAi: PengaturanAi;
}

/** Sama dengan data contoh di migrasi backend (drizzle/0001_units.sql). Bukan bagian state agar localStorage lama tetap terpakai. */
export const DAFTAR_SATUAN: Satuan[] = [
	'Laboratorium Siber',
	'Pengelola Platform',
	'Satuan Contoh A',
	'Satuan Contoh B',
	'Satuan Contoh C',
	'Tim Asesor Keamanan Siber'
].map((nama, i) => ({ id: String(i + 1), nama }));

export const PENGGUNA_DEMO: Record<Pengguna['peran'], string> = {
	pemilik: 'u-pemilik',
	asesor: 'u-asesor',
	admin: 'u-admin'
};

function peta(
	url: string,
	tersedia = true,
	metode_http = 'GET'
): PemetaanTitikUji {
	return { tersedia, url, metode_http };
}

const jamLalu = (j: number) => new Date(Date.now() - j * 3600_000).toISOString();

export function buatSeed(): StateMock {
	const sipers: Aplikasi = {
		id: 'app-sipers',
		nama: 'SIPERS — Sistem Informasi Personel',
		deskripsi: 'Pengelolaan data personel, mutasi, dan kenaikan pangkat.',
		satuan: 'Satuan Contoh A',
		pic_nama: 'Kapten Czi. Rina Wulandari',
		pic_kontak: 'rina.w@contoh.mil.id',
		url_dasar: 'https://sipers.contoh.mil.id',
		lingkungan: 'staging',
		klasifikasi_data: 'terbatas',
		teknologi: { frontend: 'Vue 3', backend: 'Laravel 10', database: 'MySQL 8', server: 'nginx' },
		verifikasi: {
			metode: 'dns',
			token: 'satya-verify=8f2c1a9d4e',
			status: 'terverifikasi',
			diverifikasi_pada: jamLalu(72)
		},
		titik_uji: {
			...titikUjiKosong(),
			registrasi: peta('/register', false),
			login: peta('/login', true, 'POST'),
			reset_password: peta('/password/reset', true, 'POST'),
			ubah_password: peta('/profil/password', true, 'POST'),
			logout: peta('/logout', true, 'POST'),
			area_terautentikasi: peta('/dashboard'),
			admin: peta('/admin'),
			form_input: peta('/personel/cari'),
			unggah_file: peta('/dokumen/unggah', true, 'POST'),
			unduh_file: peta('/dokumen/unduh/1'),
			api: peta('/api/v1')
		},
		akun_uji: [
			{ kunci: 'akun_uji_1', username: 'uji.satu', terisi: true },
			{ kunci: 'akun_uji_2', username: 'uji.dua', terisi: true },
			{ kunci: 'admin_uji', username: 'uji.admin', terisi: true }
		],
		profil_pengujian: 'aman',
		izin_intrusif: { status: 'tidak_diminta' },
		pemilik_id: 'u-pemilik',
		dibuat_pada: jamLalu(96)
	};

	const latihan: Aplikasi = {
		id: 'app-latihan',
		nama: 'Toko Latihan (OWASP Juice Shop)',
		deskripsi: 'Target latihan yang sengaja rentan untuk demonstrasi pengujian.',
		satuan: 'Laboratorium Siber',
		pic_nama: 'Lettu Inf. Dimas Saputra',
		pic_kontak: 'dimas.s@contoh.mil.id',
		url_dasar: 'http://juiceshop.lab.contoh.mil.id',
		lingkungan: 'pengembangan',
		klasifikasi_data: 'biasa',
		teknologi: { frontend: 'Angular', backend: 'Node.js Express', database: 'SQLite', server: 'Node.js' },
		verifikasi: {
			metode: 'file',
			token: 'satya-verify=31b7e0c55a',
			status: 'terverifikasi',
			diverifikasi_pada: jamLalu(30)
		},
		titik_uji: {
			...titikUjiKosong(),
			registrasi: peta('/#/register', true, 'POST'),
			login: peta('/rest/user/login', true, 'POST'),
			reset_password: peta('/#/forgot-password', true, 'POST'),
			ubah_password: peta('/rest/user/change-password'),
			logout: peta('/#/logout', false),
			area_terautentikasi: peta('/#/basket'),
			admin: peta('/#/administration'),
			form_input: peta('/rest/products/search?q='),
			unggah_file: peta('/file-upload', true, 'POST'),
			unduh_file: peta('/ftp/acquisitions.md'),
			api: peta('/api')
		},
		akun_uji: [
			{ kunci: 'akun_uji_1', username: 'uji1@juice-sh.op', terisi: true },
			{ kunci: 'akun_uji_2', username: 'uji2@juice-sh.op', terisi: true },
			{ kunci: 'admin_uji', username: '', terisi: false }
		],
		profil_pengujian: 'intrusif',
		izin_intrusif: {
			status: 'disetujui',
			dokumen_nama: 'Sprin-Uji-Lab-017.pdf',
			jendela_mulai: jamLalu(28).slice(0, 16),
			jendela_selesai: jamLalu(-48).slice(0, 16),
			diajukan_pada: jamLalu(29),
			diputuskan_oleh: 'Mayor Chb. Budi Santoso',
			catatan_asesor: 'Disetujui untuk lingkungan laboratorium.'
		},
		pemilik_id: 'u-pemilik',
		dibuat_pada: jamLalu(31)
	};

	const logistik: Aplikasi = {
		id: 'app-logistik',
		nama: 'e-Logistik',
		deskripsi: 'Permintaan dan distribusi perbekalan antarsatuan.',
		satuan: 'Satuan Contoh B',
		pic_nama: 'Serka Agus Hidayat',
		pic_kontak: 'agus.h@contoh.mil.id',
		url_dasar: 'https://elogistik.contoh.mil.id',
		lingkungan: 'produksi',
		klasifikasi_data: 'terbatas',
		teknologi: { frontend: 'React', backend: 'Spring Boot', database: 'PostgreSQL', server: 'Apache' },
		verifikasi: { metode: 'dns', token: 'satya-verify=c09a77e1f3', status: 'belum' },
		titik_uji: {
			...titikUjiKosong(),
			login: peta('/login', true, 'POST'),
			area_terautentikasi: peta('/beranda'),
			form_input: peta('/permintaan/baru', true, 'POST'),
			api: peta('/api')
		},
		akun_uji: [
			{ kunci: 'akun_uji_1', username: 'uji.log1', terisi: true },
			{ kunci: 'akun_uji_2', username: '', terisi: false },
			{ kunci: 'admin_uji', username: '', terisi: false }
		],
		profil_pengujian: 'intrusif',
		izin_intrusif: {
			status: 'menunggu',
			dokumen_nama: 'Surat-Permohonan-Uji-eLogistik.pdf',
			jendela_mulai: jamLalu(-24).slice(0, 16),
			jendela_selesai: jamLalu(-72).slice(0, 16),
			diajukan_pada: jamLalu(3)
		},
		pemilik_id: 'u-pemilik-2',
		dibuat_pada: jamLalu(5)
	};

	const model = 'claude-sonnet-5-5';
	const scanSipers: Scan = {
		id: 'scan-sipers-1',
		aplikasi_id: sipers.id,
		profil: 'aman',
		status: 'selesai',
		dimulai_pada: jamLalu(48),
		selesai_pada: jamLalu(47.8),
		hasil: hasilLengkap(sipers),
		log: [{ waktu: jamLalu(48), level: 'info', pesan: 'Pengujian dimulai (profil aman).' }]
	};
	// Contoh bukti dan putusan asesor yang sudah ada.
	const mHash = scanSipers.hasil['AUTH-1.6-T02'];
	mHash.status = 'lulus';
	mHash.menunggu_tinjauan = false;
	mHash.ringkasan = 'Asesor memverifikasi penggunaan bcrypt (cost 12).';
	mHash.bukti = [
		{
			jenis: 'dokumen',
			judul: 'Dokumen desain keamanan',
			nama_file: 'SIPERS-Desain-Keamanan-v2.pdf',
			diunggah_oleh: sipers.pic_nama,
			waktu: jamLalu(40)
		}
	];
	mHash.tinjauan = {
		asesor: 'Mayor Chb. Budi Santoso',
		putusan: 'lulus',
		catatan: 'Konfigurasi hashing sesuai, bukti kode dan konfigurasi memadai.',
		waktu: jamLalu(30)
	};
	scanSipers.hasil['MALC-9.1-T01'].bukti = [
		{
			jenis: 'dokumen',
			judul: 'Laporan SAST',
			nama_file: 'SIPERS-SonarQube-Okt2026.pdf',
			diunggah_oleh: sipers.pic_nama,
			waktu: jamLalu(20)
		}
	];
	scanSipers.ai = analisisTiruan(scanSipers.hasil, model);

	const scanLatihan: Scan = {
		id: 'scan-latihan-1',
		aplikasi_id: latihan.id,
		profil: 'intrusif',
		status: 'selesai',
		dimulai_pada: jamLalu(26),
		selesai_pada: jamLalu(25.5),
		hasil: hasilLengkap(latihan),
		log: [{ waktu: jamLalu(26), level: 'info', pesan: 'Pengujian dimulai (profil intrusif).' }]
	};
	scanLatihan.ai = analisisTiruan(scanLatihan.hasil, model);

	return {
		pengguna: [
			{
				id: 'u-pemilik',
				nama: 'Kapten Czi. Rina Wulandari',
				email: 'rina.w@contoh.mil.id',
				peran: 'pemilik',
				satuan: 'Satuan Contoh A',
				aktif: true,
				terverifikasi: true
			},
			{
				id: 'u-pemilik-2',
				nama: 'Serka Agus Hidayat',
				email: 'agus.h@contoh.mil.id',
				peran: 'pemilik',
				satuan: 'Satuan Contoh B',
				aktif: true,
				terverifikasi: true
			},
			{
				id: 'u-asesor',
				nama: 'Mayor Chb. Budi Santoso',
				email: 'budi.s@contoh.mil.id',
				peran: 'asesor',
				satuan: 'Tim Asesor Keamanan Siber',
				aktif: true,
				terverifikasi: true
			},
			{
				id: 'u-admin',
				nama: 'Admin Sistem',
				email: 'admin@contoh.mil.id',
				peran: 'admin',
				satuan: 'Pengelola Platform',
				aktif: true,
				terverifikasi: true
			},
			{
				id: 'u-pendaftar',
				nama: 'Letda Inf. Bagas Wicaksono',
				nrp: '11200045',
				email: 'bagas.w@contoh.mil.id',
				peran: 'pemilik',
				satuan: 'Satuan Contoh C',
				aktif: true,
				terverifikasi: false,
				dibuat_pada: jamLalu(2)
			}
		],
		aplikasi: [sipers, latihan, logistik],
		scan: [scanSipers, scanLatihan],
		pengaturanAi: {
			provider: 'anthropic',
			endpoint: 'https://api.anthropic.com',
			model,
			api_key_terisi: false,
			redaksi: true,
			bahasa: 'id'
		}
	};
}
