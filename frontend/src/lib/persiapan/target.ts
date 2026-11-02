// Pemetaan persiapan pengujian (PersiapanAuth) → bentuk scan_targets backend
// ({ test_points, forms, accounts, options }) yang dibaca worker. Murni, tanpa I/O.
//
// Worker menguji ENDPOINT PENERIMA DATA (backend): registrasi/login/reset/ubah memakai
// `jalur_aksi` (endpoint API), bukan `jalur_halaman` (halaman frontend). Halaman login
// (login_page) & area terautentikasi dipakai untuk cek HTML/HTTPS/akses.
import type { PersiapanAuth } from '#lib/types.js';
import { normalisasiSecret } from '#lib/totp.js';

export interface PemetaanTitikTarget {
	tersedia: boolean;
	url: string;
	metode_http: string;
}

export interface FormTarget {
	// registrasi
	field_dasar?: Record<string, unknown>;
	field_sandi?: string;
	field_unik?: string[];
	tipe_body?: 'json' | 'form';
	status_sukses?: number[];
	// login
	field_username?: string;
	field_password?: string;
	penanda_berhasil?: string;
	penanda_gagal?: string;
	// ubah
	field_lama?: string;
	field_baru?: string;
	// reset
	field_identitas?: string;
	email?: string;
}

export interface AkunTarget {
	username: string;
	password: string;
	/** Secret TOTP (base32) opsional untuk MFA; worker membangkitkan kode OTP sendiri. */
	totp_secret?: string;
	/** Parameter TOTP dari URI otpauth (QR); dikirim hanya bila non-standar. */
	totp_digits?: number;
	totp_period?: number;
	totp_algoritma?: 'SHA1' | 'SHA256' | 'SHA512';
}

export interface TargetUji {
	test_points: Record<string, PemetaanTitikTarget>;
	forms: Record<string, FormTarget>;
	accounts: { utama: AkunTarget; penguncian: AkunTarget };
	options: { izinkan_penguncian: boolean; jendela_mulai: string; jendela_selesai: string };
}

const ada = (s: string | undefined | null) => !!s && s.trim().length > 0;

export interface AkunTotpSumber {
	totp_secret?: string;
	totp_digits?: number;
	totp_period?: number;
	totp_algoritma?: 'SHA1' | 'SHA256' | 'SHA512';
}

/** Field TOTP untuk payload: seed (dinormalisasi) + parameter hanya bila non-standar. */
export function totpUntukKirim(a: AkunTotpSumber): Partial<AkunTarget> {
	if (!ada(a.totp_secret)) return {};
	const out: Partial<AkunTarget> = { totp_secret: normalisasiSecret(a.totp_secret) };
	if (a.totp_digits && a.totp_digits !== 6) out.totp_digits = a.totp_digits;
	if (a.totp_period && a.totp_period !== 30) out.totp_period = a.totp_period;
	if (a.totp_algoritma && a.totp_algoritma !== 'SHA1') out.totp_algoritma = a.totp_algoritma;
	return out;
}
const CONTOH_IDENTITAS = 'uji.satya@contoh.go.id';

export function petakanKeScanTarget(p: PersiapanAuth): TargetUji {
	const test_points: Record<string, PemetaanTitikTarget> = {
		registrasi: {
			tersedia: p.registrasi.tersedia === true && ada(p.registrasi.jalur_aksi),
			url: p.registrasi.jalur_aksi ?? '',
			metode_http: 'POST',
		},
		login: {
			tersedia: ada(p.login.jalur_aksi),
			url: p.login.jalur_aksi ?? '',
			metode_http: p.login.metode_http || 'POST',
		},
		login_page: {
			tersedia: ada(p.login.jalur_halaman),
			url: p.login.jalur_halaman ?? '',
			metode_http: 'GET',
		},
		area_terautentikasi: {
			tersedia: ada(p.login.jalur_terbatas),
			url: p.login.jalur_terbatas ?? '',
			metode_http: 'GET',
		},
		reset_password: {
			tersedia: p.reset.tersedia === true && ada(p.reset.jalur_aksi),
			url: p.reset.jalur_aksi ?? '',
			metode_http: 'POST',
		},
		ubah_password: {
			tersedia: p.ubah_password.tersedia === true && ada(p.ubah_password.jalur_aksi),
			url: p.ubah_password.jalur_aksi ?? '',
			metode_http: 'POST',
		},
	};

	const forms: Record<string, FormTarget> = {};
	if (test_points.registrasi.tersedia && ada(p.registrasi.field_identitas) && ada(p.registrasi.field_password)) {
		const field_dasar: Record<string, unknown> = { [p.registrasi.field_identitas]: CONTOH_IDENTITAS };
		for (const f of p.registrasi.field_lain) if (ada(f.nama)) field_dasar[f.nama] = f.nilai;
		forms.registrasi = {
			field_dasar,
			field_sandi: p.registrasi.field_password,
			field_unik: [p.registrasi.field_identitas],
			tipe_body: 'json',
			status_sukses: [200, 201, 202],
		};
	}
	if (test_points.login.tersedia) {
		forms.login = {
			field_username: p.login.field_username || 'email',
			field_password: p.login.field_password || 'password',
			penanda_berhasil: p.login.penanda_berhasil ?? '',
			penanda_gagal: p.login.penanda_gagal ?? '',
			tipe_body: 'json',
		};
	}
	if (test_points.ubah_password.tersedia) {
		forms.ubah_password = {
			field_lama: p.ubah_password.field_lama || 'current_password',
			field_baru: p.ubah_password.field_baru || 'new_password',
			tipe_body: 'json',
		};
	}
	if (test_points.reset_password.tersedia) {
		forms.reset_password = {
			field_identitas: p.reset.field_identitas || 'email',
			email: p.reset.email_akun_uji ?? '',
			tipe_body: 'json',
		};
	}

	const akun = (a: AkunTotpSumber & { username: string; password?: string }): AkunTarget => ({
		username: a.username ?? '',
		password: a.password ?? '',
		...totpUntukKirim(a),
	});

	return {
		test_points,
		forms,
		accounts: { utama: akun(p.akun_uji.utama), penguncian: akun(p.akun_uji.penguncian) },
		options: {
			izinkan_penguncian: p.intrusif.izinkan_penguncian,
			jendela_mulai: p.intrusif.jendela_mulai ?? '',
			jendela_selesai: p.intrusif.jendela_selesai ?? '',
		},
	};
}
