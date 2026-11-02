// Peristiwa uji contoh (mode demo) untuk metode AUTH — meniru keluaran worker `peristiwa_uji.py`
// (langkah check + request otomatis dari KlienScan), konsisten dengan status hasil simulasi.
import type { DataUji, RequestUji, SkenarioUji } from '#lib/pengujian/peristiwa.js';
import type { Aplikasi, HasilMetode, Metode } from '#lib/types.js';

type Langkah = { pesan: string; data: DataUji };

const SKENARIO: Record<string, SkenarioUji> = {
	'auth.login_required': 'akses_terproteksi',
	'auth.password_field_masked': 'field_sandi',
	'auth.server_side_validation': 'payload_server',
	'auth.password_policy.server_side': 'kebijakan_sandi',
	'auth.password_policy.min_length': 'kebijakan_sandi',
	'auth.password_policy.complexity': 'kebijakan_sandi',
	'auth.password_policy.min_length+complexity': 'kebijakan_sandi',
	'auth.lockout_threshold': 'lockout',
	'auth.reset.no_user_enumeration': 'enumerasi_reset',
	'auth.password_not_echoed': 'echo_sandi',
	'auth.login_over_https': 'kanal_https',
	'tls.http_redirect': 'redirect_http'
};

export function peristiwaUji(app: Aplikasi, metode: Metode, h: HasilMetode): Langkah[] {
	const situs = new URL(app.url_dasar);
	const api = `${situs.origin}/api/v1`;
	const lulus = h.status === 'lulus';
	const out: Langkah[] = [];
	let no = 0;
	const dasar = { v: 1 as const, jenis: 'uji' as const, metode_id: metode.id };
	const langkah = (l: string, label: string, detail: Record<string, unknown> = {}) =>
		out.push({ pesan: `  ${label}`, data: { ...dasar, fase: 'langkah', langkah: l, label, detail } });
	const request = (metode_http: string, url: string, status: number | null, ekstra: Partial<RequestUji> = {}) => {
		const u = new URL(url);
		const req: RequestUji = {
			no: ++no,
			metode_http,
			url,
			skema: u.protocol.replace(':', ''),
			host: u.hostname,
			lapisan: u.pathname.startsWith('/api/') ? 'api' : 'frontend',
			field: [],
			status,
			durasi_ms: 60 + Math.round(Math.random() * 180),
			...ekstra
		};
		out.push({ pesan: `  → ${metode_http} ${url} · ${status === null ? 'gagal' : `HTTP ${status}`} (${req.durasi_ms} ms)`, data: { ...dasar, fase: 'request', ...req } });
	};

	out.push({
		pesan: `▶ ${metode.id} — ${metode.nama} (titik: ${metode.titik_uji})`,
		data: { ...dasar, fase: 'mulai', check_id: metode.check_id, fungsi: 'AUTH', judul: metode.nama, titik_uji: metode.titik_uji, skenario: SKENARIO[metode.check_id] ?? 'generik' }
	});

	const konklusif = h.status === 'lulus' || h.status === 'gagal';
	if (konklusif) {
		switch (metode.check_id) {
			case 'auth.server_side_validation':
				langkah('siapkan_payload', 'Menyusun payload login berkredensial acak (validasi JavaScript klien dilewati)', {
					payload: { email: 'satya-uji-3f9a@contoh.go.id', password: '[disamarkan]' },
					tipe_body: 'json'
				});
				langkah('kirim', `Mengirim langsung ke endpoint POST ${api}/auth/login`);
				request('POST', `${api}/auth/login`, lulus ? 401 : 200, { field: ['email', 'password'], alasan: lulus ? 'Unauthorized' : 'OK' });
				langkah('evaluasi', lulus ? 'Server menolak kredensial acak' : 'Server tidak menolak kredensial acak', { hasil: lulus ? 'ditolak' : 'diterima' });
				break;
			case 'auth.login_over_https':
				langkah('periksa_skema', 'Halaman login (frontend): HTTPS', { skema: 'https', lapisan: 'frontend' });
				langkah('periksa_skema', 'Endpoint login (backend): HTTPS', { skema: 'https', lapisan: 'api' });
				langkah('ubah_skema', 'Mengganti kanal ke HTTP (tanpa enkripsi) untuk payload login', { ke: `http://${situs.host}/api/v1/auth/login` });
				langkah('siapkan_payload', 'Payload login berkredensial acak (bukan akun uji)', { payload: { email: 'satya-uji-81c2@contoh.go.id', password: '[disamarkan]' }, tipe_body: 'json' });
				request('POST', `http://${situs.host}/api/v1/auth/login`, lulus ? 301 : 401, lulus ? { lokasi: `${api}/auth/login`, alasan: 'Moved Permanently' } : { alasan: 'Unauthorized' });
				langkah('evaluasi', lulus ? 'Kanal HTTP dialihkan ke HTTPS (HTTP 301) — payload tidak diproses' : 'Endpoint login MEMPROSES payload lewat HTTP (HTTP 401)', { hasil: lulus ? 'dialihkan' : 'diterima' });
				break;
			case 'tls.http_redirect':
				langkah('ubah_skema', 'Membuka halaman login lewat HTTP (tanpa enkripsi)', { ke: `http://${situs.host}/login` });
				request('GET', `http://${situs.host}/login`, lulus ? 301 : 200, lulus ? { lokasi: `${situs.origin}/login`, alasan: 'Moved Permanently' } : { alasan: 'OK' });
				langkah('evaluasi', lulus ? 'Dialihkan permanen ke HTTPS (HTTP 301)' : 'Tidak dialihkan ke HTTPS (HTTP 200)', { hasil: lulus ? 'dialihkan' : 'diterima' });
				break;
			case 'auth.password_policy.server_side':
			case 'auth.password_policy.min_length':
			case 'auth.password_policy.complexity':
			case 'auth.password_policy.min_length+complexity': {
				const sandi = metode.check_id.endsWith('complexity') && !metode.check_id.includes('+') ? 'aaaaaaaaaa' : 'ab';
				langkah('siapkan_payload', `Payload registrasi dengan kata sandi lemah (${sandi === 'ab' ? 'pendek & tanpa kombinasi' : 'tanpa kombinasi jenis karakter'})`, {
					payload: { nama: 'uji', email: 'uji-5d1e@contoh.go.id', password: sandi },
					tipe_body: 'json'
				});
				langkah('kirim', `Mengirim langsung ke POST ${api}/auth/register (validasi klien dilewati)`);
				request('POST', `${api}/auth/register`, lulus ? 400 : 201, { field: ['nama', 'email', 'password'], alasan: lulus ? 'Bad Request' : 'Created' });
				langkah('evaluasi', lulus ? 'Sandi lemah ditolak server' : 'Sandi lemah DITERIMA server', { hasil: lulus ? 'ditolak' : 'diterima' });
				break;
			}
			case 'auth.lockout_threshold':
				langkah('siapkan_payload', "Menyiapkan 6 percobaan login dengan kata sandi salah untuk akun 'akun_uji_2'", {
					payload: { email: 'uji2@contoh.go.id', password: '[disamarkan]' },
					percobaan: 6
				});
				for (let i = 1; i <= (lulus ? 5 : 6); i++) request('POST', `${api}/auth/login`, lulus && i === 5 ? 429 : 401, { field: ['email', 'password'] });
				langkah('evaluasi', lulus ? 'Penguncian/pembatasan terpicu pada percobaan ke-5' : '6 percobaan selesai tanpa penguncian', { hasil: lulus ? 'terkunci' : 'tanpa_penguncian' });
				break;
			case 'auth.reset.no_user_enumeration':
				langkah('siapkan_payload', 'Dua payload reset: akun terdaftar vs akun fiktif', {
					payload: { email: 'uji1@contoh.go.id' },
					pembanding: { email: 'satya-tiada-9b0c@contoh.go.id' }
				});
				request('POST', `${api}/auth/forgot-password`, 202, { field: ['email'] });
				request('POST', `${api}/auth/forgot-password`, lulus ? 202 : 404, { field: ['email'] });
				langkah('bandingkan', 'Membandingkan dua respons (status, isi, panjang)', { hasil: lulus ? 'aman' : 'bocor' });
				break;
			case 'auth.login_required':
				langkah('akses_tanpa_sesi', 'Mengakses area terbatas TANPA sesi login');
				request('GET', `${api}/auth/me`, lulus ? 401 : 200, { alasan: lulus ? 'Unauthorized' : 'OK' });
				langkah('evaluasi', lulus ? 'Akses ditolak / dialihkan ke login' : 'Area merespons HTTP 200 tanpa sesi', { hasil: lulus ? 'ditolak' : 'diterima' });
				break;
			case 'auth.password_field_masked':
				langkah('ambil_halaman', 'Mengambil HTML halaman login (frontend)');
				request('GET', `${situs.origin}/login`, 200, { alasan: 'OK' });
				langkah('periksa_input', lulus ? 'Input kata sandi bertipe password' : 'Input kata sandi BUKAN tipe password', { hasil: lulus ? 'tersamar' : 'terbuka' });
				break;
			case 'auth.password_not_echoed':
				langkah('login', "Login akun uji 'akun_uji_1', lalu periksa apakah kata sandi dikembalikan server");
				request('POST', `${api}/auth/login`, 200, { field: ['email', 'password'] });
				request('GET', `${api}/auth/me`, 200);
				langkah('evaluasi', lulus ? 'Kata sandi tidak dikembalikan di respons' : 'Kata sandi MUNCUL di respons profil', { hasil: lulus ? 'aman' : 'bocor' });
				break;
		}
	}
	out.push({ pesan: '', data: { ...dasar, fase: 'hasil', status: h.status, ringkasan: h.ringkasan ?? '' } });
	return out;
}
