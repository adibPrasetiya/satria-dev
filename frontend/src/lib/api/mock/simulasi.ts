// Pembangkit hasil uji & analisis AI tiruan untuk demo tanpa backend.
// Hasil bersifat deterministik per (aplikasi, metode) agar demo konsisten.
import { indeksMetode, nilaiKelaikan, LABEL_PUTUSAN, semuaMetode, penerapanMetode } from '#lib/catalog.js';
import type { AnalisisAi, Aplikasi, Bukti, HasilMetode, Metode, Status } from '#lib/types.js';

function hash(s: string): number {
	let h = 2166136261;
	for (let i = 0; i < s.length; i++) {
		h ^= s.charCodeAt(i);
		h = Math.imul(h, 16777619);
	}
	return (h >>> 0) / 4294967295;
}

/** Skenario demo: check_id yang sengaja gagal untuk aplikasi contoh. */
const SKENARIO_GAGAL: Record<string, string[]> = {
	'app-sipers': [
		'headers.server_banner',
		'headers.permissions_policy',
		'integrity.sri',
		'time.server_clock_drift'
	],
	'app-latihan': [
		'tls.http_redirect',
		'tls.https_enforced',
		'headers.hsts',
		'headers.csp',
		'headers.security_baseline',
		'headers.server_banner',
		'session.cookie_flags',
		'auth.password_policy.min_length',
		'auth.password_policy.complexity',
		'auth.lockout_threshold',
		'auth.reset.no_user_enumeration',
		'error.verbose_messages',
		'error.generic_login_message',
		'zap.active.sqli_policy',
		'zap.active.xss_policy',
		'zap.active.injection_policy',
		'access.horizontal',
		'access.rate_limit',
		'exposure.api_docs_debug',
		'exposure.backup_files',
		'api.cors_policy',
		'deps.vulnerable_js_libraries',
		'integrity.sri',
		'file.content_type_validation',
		'file.filename_sanitization'
	]
};

/** Temuan spesifik yang lebih realistis untuk check_id tertentu. */
const TEMUAN: Record<string, { gagal: string; lulus: string; respons?: string }> = {
	'headers.server_banner': {
		gagal: 'Header Server mengungkap produk dan versi: "nginx/1.18.0 (Ubuntu)"; X-Powered-By: "Express".',
		lulus: 'Header Server tidak menampilkan versi; X-Powered-By tidak ada.',
		respons: 'HTTP/1.1 200 OK\nServer: nginx/1.18.0 (Ubuntu)\nX-Powered-By: Express\nContent-Type: text/html; charset=utf-8'
	},
	'headers.hsts': {
		gagal: 'Header Strict-Transport-Security tidak ditemukan pada respons HTTPS.',
		lulus: 'Strict-Transport-Security: max-age=31536000; includeSubDomains.'
	},
	'headers.csp': {
		gagal: "Header Content-Security-Policy tidak ada; skrip inline dapat dieksekusi.",
		lulus: "Content-Security-Policy: default-src 'self'; script-src 'self'; frame-ancestors 'none'."
	},
	'headers.permissions_policy': {
		gagal: 'Header Permissions-Policy tidak ada; kamera, mikrofon, dan geolokasi tidak dibatasi.',
		lulus: 'Permissions-Policy: camera=(), microphone=(), geolocation=().'
	},
	'session.cookie_flags': {
		gagal: 'Cookie sesi "connect.sid" tanpa atribut Secure dan SameSite.',
		lulus: 'Cookie sesi memiliki Secure; HttpOnly; SameSite=Strict.',
		respons: 'HTTP/1.1 302 Found\nSet-Cookie: connect.sid=s%3A9f...; Path=/; HttpOnly\nLocation: /dashboard'
	},
	'integrity.sri': {
		gagal: '3 skrip dari cdn.jsdelivr.net dimuat tanpa atribut integrity.',
		lulus: 'Seluruh aset eksternal memiliki atribut integrity yang valid.'
	},
	'time.server_clock_drift': {
		gagal: 'Header Date server berselisih 214 detik dari sumber waktu acuan (toleransi 60 detik).',
		lulus: 'Selisih waktu server 2 detik, dalam batas toleransi.'
	},
	'tls.protocol_versions': {
		gagal: 'TLS 1.0 dan TLS 1.1 masih aktif.',
		lulus: 'Hanya TLS 1.2 dan TLS 1.3 yang aktif.'
	},
	'tls.http_redirect': {
		gagal: 'Akses http:// ke halaman login dilayani 200 OK tanpa pengalihan ke HTTPS.',
		lulus: 'http:// dialihkan dengan 301 ke https://.'
	},
	'tls.certificate_validity': {
		gagal: 'Sertifikat kedaluwarsa 12 hari lalu.',
		lulus: 'Sertifikat valid hingga 14 bulan ke depan, nama host cocok, rantai lengkap.'
	},
	'zap.active.sqli_policy': {
		gagal: "Injeksi SQL berbasis error pada parameter 'q' di /rest/products/search (risiko Tinggi).",
		lulus: 'Tidak ada temuan injeksi basis data.',
		respons: "HTTP/1.1 500 Internal Server Error\n\n{\"error\":\"SQLITE_ERROR: near \\\"'\\\": syntax error\"}"
	},
	'zap.active.xss_policy': {
		gagal: "Reflected XSS pada parameter 'q' di /#/search (payload <iframe src=javascript:alert(1)>).",
		lulus: 'Tidak ada temuan XSS.'
	},
	'exposure.api_docs_debug': {
		gagal: 'Dokumentasi Swagger terbuka publik di /api-docs.',
		lulus: 'Tidak ada dokumentasi API/endpoint debug yang terbuka.'
	},
	'exposure.config_vcs_files': {
		gagal: 'Berkas /.git/config dapat diunduh.',
		lulus: 'Berkas .env, .git, dan konfigurasi tidak dapat diakses.'
	},
	'api.cors_policy': {
		gagal: 'Access-Control-Allow-Origin: * dikombinasikan dengan Allow-Credentials: true.',
		lulus: 'CORS hanya mengizinkan origin aplikasi sendiri.'
	},
	'access.horizontal': {
		gagal: 'Akun uji 1 dapat membaca keranjang milik akun uji 2 melalui /rest/basket/{id}.',
		lulus: 'Akses objek milik akun lain ditolak (403).'
	},
	'error.verbose_messages': {
		gagal: 'Halaman 500 menampilkan stack trace beserta path berkas server.',
		lulus: 'Halaman error generik tanpa detail teknis.'
	}
};

function buktiRequest(app: Aplikasi, metode: Metode, status: Status): Bukti {
	const peta = app.titik_uji[metode.titik_uji];
	const url = new URL(peta?.url || '/', app.url_dasar || 'https://contoh.mil.id');
	const respons =
		TEMUAN[metode.check_id]?.respons ??
		(status === 'lulus'
			? 'HTTP/1.1 200 OK\nContent-Type: text/html; charset=utf-8\nX-Content-Type-Options: nosniff'
			: 'HTTP/1.1 200 OK\nContent-Type: text/html');
	return {
		jenis: 'request_response',
		judul: `${peta?.metode_http ?? 'GET'} ${url.pathname}`,
		isi: `${peta?.metode_http ?? 'GET'} ${url.pathname} HTTP/1.1\nHost: ${url.host}\nUser-Agent: SATYA-Scanner/0.1\n\n---\n${respons}`
	};
}

/** Hasil akhir suatu metode yang dijalankan (tanpa status antre/berjalan). */
export function hasilMetode(app: Aplikasi, metode: Metode): HasilMetode {
	const p = penerapanMetode(app, metode);
	if (!p.jalan) return { metode_id: metode.id, status: p.status, ringkasan: p.alasan, bukti: [] };

	if (metode.jenis === 'manual' || metode.engine === 'manual') {
		return {
			metode_id: metode.id,
			status: 'tidak_dapat_diverifikasi',
			ringkasan: 'Menunggu bukti dari pemilik aplikasi dan putusan asesor.',
			bukti: [],
			menunggu_tinjauan: true
		};
	}

	const r = hash(`${app.id}:${metode.id}`);
	const skenario = SKENARIO_GAGAL[app.id];
	let status: Status;
	if (skenario) status = skenario.includes(metode.check_id) ? 'gagal' : 'lulus';
	else status = r < (metode.jenis === 'semi_otomatis' ? 0.25 : 0.15) ? 'gagal' : 'lulus';

	// Sebagian semi-otomatis butuh konfirmasi asesor.
	const perluTinjauan = metode.jenis === 'semi_otomatis' && status === 'lulus' && r > 0.75;
	if (perluTinjauan) {
		return {
			metode_id: metode.id,
			status: 'tidak_dapat_diverifikasi',
			ringkasan: 'Hasil otomatis belum konklusif; perlu konfirmasi asesor.',
			bukti: [buktiRequest(app, metode, 'lulus')],
			menunggu_tinjauan: true,
			durasi_ms: Math.round(400 + r * 3000)
		};
	}

	const temuan = TEMUAN[metode.check_id];
	return {
		metode_id: metode.id,
		status,
		ringkasan:
			(status === 'lulus' ? temuan?.lulus : temuan?.gagal) ??
			(status === 'lulus'
				? `Kriteria terpenuhi: ${metode.kriteria_lulus}`
				: `Kriteria tidak terpenuhi: ${metode.kriteria_lulus}`),
		bukti: metode.bukti.includes('request_response') ? [buktiRequest(app, metode, status)] : [],
		durasi_ms: Math.round(300 + r * 4000)
	};
}

export function hasilLengkap(app: Aplikasi): Record<string, HasilMetode> {
	return Object.fromEntries(semuaMetode.map(({ metode }) => [metode.id, hasilMetode(app, metode)]));
}

// ---------------------------------------------------------------------------
// Analisis AI tiruan

const REKOMENDASI: { awalan: string; langkah: string[] }[] = [
	{
		awalan: 'headers.',
		langkah: [
			'Tambahkan header keamanan pada konfigurasi reverse proxy (nginx/Apache) atau middleware aplikasi (mis. helmet untuk Express).',
			'Uji ulang dengan curl -I untuk memastikan header muncul di seluruh respons.'
		]
	},
	{
		awalan: 'tls.',
		langkah: [
			'Aktifkan pengalihan permanen HTTP ke HTTPS (301/308) di server web.',
			'Nonaktifkan TLS 1.0/1.1 dan cipher lemah; gunakan profil konfigurasi "intermediate" atau "modern".'
		]
	},
	{
		awalan: 'session.',
		langkah: [
			'Set atribut cookie sesi Secure, HttpOnly, dan SameSite=Lax/Strict.',
			'Regenerasi session ID setelah login dan invalidasi saat logout.'
		]
	},
	{
		awalan: 'zap.active.',
		langkah: [
			'Gunakan parameterized query / ORM untuk seluruh akses basis data.',
			'Lakukan output encoding sesuai konteks dan terapkan Content-Security-Policy.',
			'Validasi input di sisi server dengan allowlist.'
		]
	},
	{
		awalan: 'exposure.',
		langkah: [
			'Hapus berkas sensitif dari web root dan blokir akses pola berkas tersebut di server web.',
			'Batasi dokumentasi API hanya untuk jaringan internal atau pengguna terautentikasi.'
		]
	},
	{
		awalan: 'auth.',
		langkah: [
			'Tegakkan kebijakan kata sandi (panjang dan kompleksitas) di sisi server untuk registrasi, reset, dan ubah kata sandi.',
			'Terapkan penguncian sementara atau CAPTCHA setelah percobaan login gagal berulang.'
		]
	},
	{
		awalan: 'access.',
		langkah: [
			'Periksa kepemilikan objek pada setiap request di sisi server (jangan hanya mengandalkan ID dari klien).',
			'Terapkan rate limiting pada fungsi sensitif.'
		]
	},
	{
		awalan: 'integrity.',
		langkah: [
			'Tambahkan atribut integrity dan crossorigin pada skrip/stylesheet eksternal, atau host sendiri pustaka tersebut.'
		]
	},
	{
		awalan: 'error.',
		langkah: [
			'Nonaktifkan mode debug di produksi dan tampilkan halaman error generik.',
			'Samakan pesan gagal login untuk username dan kata sandi salah.'
		]
	},
	{
		awalan: 'api.',
		langkah: [
			'Batasi CORS ke origin yang diizinkan secara eksplisit; jangan gabungkan wildcard dengan credentials.',
			'Validasi skema payload dan Content-Type sebelum diproses.'
		]
	},
	{
		awalan: 'time.',
		langkah: ['Sinkronkan jam server dengan NTP internal yang tepercaya dan pantau selisihnya.']
	}
];

export function analisisTiruan(hasil: Record<string, HasilMetode>, model: string): AnalisisAi {
	const penilaian = nilaiKelaikan(hasil);
	const gagal = Object.values(hasil)
		.filter((h) => h.status === 'gagal')
		.map((h) => indeksMetode.get(h.metode_id)!)
		.filter(Boolean);
	const terberat = [...gagal].sort(
		(a, b) =>
			['kritis', 'tinggi', 'sedang', 'rendah', 'info'].indexOf(a.metode.severity) -
			['kritis', 'tinggi', 'sedang', 'rendah', 'info'].indexOf(b.metode.severity)
	);

	const ringkasan = [
		`Berdasarkan pengujian terhadap ${penilaian.hitungan.lulus + penilaian.hitungan.gagal + penilaian.hitungan.tidak_dapat_diverifikasi} kontrol yang berlaku dari Peraturan BSSN Nomor 4 Tahun 2021, aplikasi dinilai **${LABEL_PUTUSAN[penilaian.putusan]}** dengan skor kepatuhan ${penilaian.skor}%.`,
		gagal.length
			? `Ditemukan ${gagal.length} metode uji yang gagal. Prioritas perbaikan: ${terberat
					.slice(0, 3)
					.map((g) => `${g.kontrol.nomor_referensi} ${g.fungsi.nama} (${g.metode.nama.toLowerCase()})`)
					.join('; ')}.`
			: 'Tidak ditemukan metode uji otomatis yang gagal.',
		penilaian.hitungan.tidak_dapat_diverifikasi
			? `${penilaian.hitungan.tidak_dapat_diverifikasi} kontrol masih memerlukan bukti dokumen atau putusan asesor sebelum penilaian final.`
			: ''
	]
		.filter(Boolean)
		.join('\n\n');

	return {
		ringkasan_eksekutif: ringkasan,
		rekomendasi: terberat.map(({ metode, kontrol }) => ({
			metode_id: metode.id,
			judul: `${kontrol.nomor_referensi} — ${metode.nama}`,
			penjelasan: `Kontrol "${kontrol.uraian}" belum terpenuhi. ${hasil[metode.id]?.ringkasan ?? ''} Kondisi ini dapat dimanfaatkan penyerang bila tidak diperbaiki (severity ${metode.severity}).`,
			langkah: REKOMENDASI.find((r) => metode.check_id.startsWith(r.awalan))?.langkah ?? [
				`Perbaiki implementasi agar memenuhi kriteria: ${metode.kriteria_lulus}`,
				'Jalankan ulang pengujian untuk memverifikasi perbaikan.'
			]
		})),
		model,
		dibuat_pada: new Date().toISOString(),
		disamarkan: true
	};
}
