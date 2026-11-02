// Urutan peristiwa penemuan contoh (mode demo) — meniru keluaran worker `discovery.py`.
import type { DataPenemuan, EndpointTemuan, ItemCrawl } from '#lib/penemuan/peristiwa.js';
import type { LogScan } from '#lib/types.js';

type Langkah = { jeda: number; level?: LogScan['level']; pesan: string; data?: DataPenemuan };

const SUMBER_DAYA = ['cuti', 'pegawai', 'unit', 'jenis-cuti', 'persetujuan', 'laporan'];
// Prefiks path API — path_template worker selalu path penuh dari URL.
const P = '/api/v1';

function ep(metode: string, path: string, api: string, auth: boolean, fields: string[] = [], titik: string | null = null): EndpointTemuan {
	return {
		id: `${metode} ${P}${path}`,
		metode_http: metode,
		path_template: P + path,
		url: api + path.replace('{id}', '1'),
		origin: new URL(api).origin,
		sumber: auth ? ['openapi', 'browser'] : ['openapi'],
		butuh_autentikasi: auth,
		request_fields: fields.map((nama) => ({ nama, lokasi: metode === 'GET' ? 'query' : 'body', tipe: 'string', wajib: true })),
		response_fields: ['id', 'dibuat_pada'],
		content_type: metode === 'GET' ? null : 'application/json',
		status_terlihat: auth ? [200, 401] : [200],
		titik_uji: titik,
		lapisan: 'api'
	};
}

export function urutanPenemuan(urlDasar: string, terautentikasi: boolean): Langkah[] {
	const situs = new URL(urlDasar);
	const api = `${situs.protocol}//api.${situs.host}/api/v1`;
	const endpoints: EndpointTemuan[] = [
		ep('POST', '/auth/login', api, false, ['email', 'password'], 'login'),
		ep('POST', '/auth/register', api, false, ['nama', 'email', 'password'], 'registrasi'),
		ep('POST', '/auth/forgot-password', api, false, ['email'], 'reset_password'),
		ep('GET', '/auth/me', api, true),
		ep('PUT', '/auth/password', api, true, ['lama', 'baru'], 'ubah_password'),
		...SUMBER_DAYA.flatMap((r) => [
			ep('GET', `/${r}`, api, true, ['page', 'q']),
			ep('POST', `/${r}`, api, true, ['nama', 'keterangan']),
			ep('GET', `/${r}/{id}`, api, true),
			ep('PATCH', `/${r}/{id}`, api, true, ['nama']),
			ep('DELETE', `/${r}/{id}`, api, true)
		]),
		{ ...ep('POST', '/cuti/{id}/lampiran', api, true, ['berkas'], 'unggah_file'), content_type: 'multipart/form-data', sumber: ['openapi', 'browser'] },
		{ ...ep('POST', '/pegawai/{id}/foto', api, true, ['foto']), content_type: 'multipart/form-data', sumber: ['openapi', 'katana'] },
		{ ...ep('GET', '/laporan/ekspor', api, true, ['format']), sumber: ['katana', 'zap'] },
		{ ...ep('GET', '/unit/pohon', api, true), sumber: ['katana'] },
		// Ditemukan dari analisis bundle JS (tak tercantum di OpenAPI).
		{ ...ep('POST', '/cuti/{id}/setujui', api, true, ['catatan']), sumber: ['js'] },
		{ ...ep('POST', '/notifikasi/baca-semua', api, true), sumber: ['js'] }
	];
	// Sebagian endpoint juga terlihat oleh ZAP spider / katana.
	for (const [i, e] of endpoints.entries()) if (e.metode_http === 'GET' && i % 3 === 0) e.sumber = [...new Set([...e.sumber, i % 2 ? 'zap' : 'katana'])];
	const batch: Langkah[] = [];
	for (let i = 0; i < endpoints.length; i += 20) {
		const items = endpoints.slice(i, i + 20);
		batch.push({ jeda: 500, pesan: `  ↳ peta endpoint ${i + 1}–${i + items.length} dari ${endpoints.length}`, data: { v: 1, jenis: 'endpoint', items } });
	}
	const halaman = ['/', '/login', '/daftar', '/lupa-sandi', '/tentang'].map((p) => ({ url: situs.origin + p, status: 200, judul: `Cuti — ${p}`, sumber: 'html' }));
	const rute = ['/beranda', '/cuti', '/cuti/baru', '/cuti/12', '/pegawai', '/pegawai/7', '/laporan', '/profil', '/pengaturan'].map((p) => ({
		url: situs.origin + p,
		status: 200,
		judul: '',
		sumber: 'browser'
	}));
	const js = ['/assets/index-4f2a91.js', '/assets/vendor-react-9c1e.js', '/assets/cuti-form-77b3.js', '/assets/laporan-chart-a08d.js'];
	const itemKatana: ItemCrawl[] = [
		...['/', '/beranda', '/cuti', '/cuti/baru', '/bantuan', '/kebijakan-privasi', '/tentang'].map((p) => ({ url: situs.origin + p, metode_http: 'GET', lapisan: 'frontend' as const, status: 200 })),
		...['/laporan/ekspor', '/unit/pohon', '/cuti', '/pegawai'].map((p) => ({ url: api + p, metode_http: 'GET', lapisan: 'api' as const, status: 200 })),
		...js.map((p) => ({ url: situs.origin + p, metode_http: 'GET', lapisan: 'aset' as const, status: 200 }))
	];
	const itemZap: ItemCrawl[] = [
		...['/', '/login', '/daftar', '/lupa-sandi', '/bantuan', '/sitemap'].map((p) => ({ url: situs.origin + p, lapisan: 'frontend' as const })),
		...['/auth/login', '/laporan/ekspor', '/jenis-cuti'].map((p) => ({ url: api + p, lapisan: 'api' as const })),
		...js.slice(0, 2).map((p) => ({ url: situs.origin + p, lapisan: 'aset' as const }))
	];
	const alertZap = [
		{ url: situs.origin + '/', nama: 'Content Security Policy (CSP) Header Not Set', risk: 'Medium' },
		{ url: situs.origin + '/login', nama: 'Content Security Policy (CSP) Header Not Set', risk: 'Medium' },
		{ url: situs.origin + '/login', nama: 'Cookie without SameSite Attribute', risk: 'Low' },
		{ url: situs.origin + '/daftar', nama: 'Absence of Anti-CSRF Tokens', risk: 'Medium' },
		{ url: api + '/auth/login', nama: 'Cookie without SameSite Attribute', risk: 'Low' },
		{ url: api + '/laporan/ekspor', nama: 'X-Content-Type-Options Header Missing', risk: 'Low' },
		{ url: situs.origin + '/bantuan', nama: 'Information Disclosure - Suspicious Comments', risk: 'Informational' }
	];

	return [
		{ jeda: 400, pesan: `Penemuan dimulai untuk ${urlDasar}`, data: { v: 1, jenis: 'tahap', tahap: 'situs', url: urlDasar } },
		{ jeda: 3400, pesan: 'Mencari spesifikasi OpenAPI/Swagger…', data: { v: 1, jenis: 'tahap', tahap: 'recon', jalur: ['/openapi.json', '/swagger.json', '/api-docs', '/api/openapi.json', '/api/v1/openapi.json', '/docs/', '/swagger-ui/'] } },
		{ jeda: 2600, pesan: `Spec OpenAPI ditemukan: ${api}/openapi.json` },
		{ jeda: 300, pesan: `OpenAPI 'Cuti API' v1.0: ${endpoints.length} endpoint, base API ${api}`, data: { v: 1, jenis: 'docs', url: `${api}/openapi.json`, judul: 'Cuti API', versi: '1.0', jumlah_endpoint: endpoints.length, base_api: api } },
		{ jeda: 1600, pesan: 'Menjelajah (crawl) halaman HTML…', data: { v: 1, jenis: 'tahap', tahap: 'crawl' } },
		{ jeda: 1200, pesan: `Crawl HTML: ${halaman.length} halaman diperiksa.`, data: { v: 1, jenis: 'halaman', items: halaman } },
		{ jeda: 400, pesan: `  • titik 'login_page' ditemukan (tinggi): GET ${situs.origin}/login`, data: { v: 1, jenis: 'titik', titik: 'login_page', url: `${situs.origin}/login`, metode_http: 'GET', keyakinan: 'tinggi' } },
		{ jeda: 900, pesan: 'Menjelajah via browser (SPA) + login terautentikasi…', data: { v: 1, jenis: 'tahap', tahap: 'browser', login: terautentikasi } },
		{ jeda: 1400, pesan: `Browser: ${rute.length} rute frontend terender.`, data: { v: 1, jenis: 'halaman', items: rute } },
		...(terautentikasi
			? [
					{ jeda: 1200, pesan: 'Mencoba login untuk crawl terautentikasi…', data: { v: 1, jenis: 'tahap', tahap: 'login', akun: 'akun_uji_1' } } as Langkah,
					{ jeda: 1800, pesan: "Login berhasil (akun 'akun_uji_1') — menjelajah area terautentikasi.", data: { v: 1, jenis: 'sesi', berhasil: true, akun: 'akun_uji_1' } } as Langkah
				]
			: []),
		{ jeda: 1200, pesan: `ZAP 2.16: menjalankan spider + ajax spider pada ${urlDasar}…`, data: { v: 1, jenis: 'tahap', tahap: 'zap' } },
		{
			jeda: 2200,
			pesan: 'ZAP passive scan: 9 alert (5 jenis); URL: frontend 6, API 3, aset 2.',
			data: {
				v: 1,
				jenis: 'zap',
				jumlah_url: 142,
				ringkas: { frontend: 6, api: 3, aset: 2 },
				items: itemZap,
				alert_url: alertZap,
				temuan: [{ nama: 'Content Security Policy (CSP) Header Not Set', n: 4 }, { nama: 'Cookie without SameSite Attribute', n: 3 }, { nama: 'X-Content-Type-Options Header Missing', n: 2 }]
			}
		},
		{ jeda: 900, pesan: 'Menjalankan katana (crawl + JS parsing)…', data: { v: 1, jenis: 'tahap', tahap: 'katana' } },
		{
			jeda: 1800,
			pesan: `Katana: 88 URL/endpoint ditemukan (frontend 7, API 4, aset ${js.length}).`,
			data: { v: 1, jenis: 'katana', jumlah: 88, ringkas: { frontend: 7, api: 4, aset: js.length }, items: itemKatana }
		},
		{ jeda: 1000, pesan: `Analisis bundle JS: membaca ${js.length} berkas skrip…`, data: { v: 1, jenis: 'tahap', tahap: 'bundle' } },
		{ jeda: 1400, pesan: `Analisis bundle JS: ${js.length} berkas, 2 panggilan API baru (2 non-GET); base backend ${api}.` },
		{ jeda: 1400, pesan: `Inventaris endpoint terpadu: ${endpoints.length} endpoint unik.`, data: { v: 1, jenis: 'tahap', tahap: 'inventaris', jumlah: endpoints.length } },
		...batch,
		{
			jeda: 900,
			pesan: `Alur proses bisnis terpetakan: ${1 + SUMBER_DAYA.length} alur.`,
			data: {
				v: 1,
				jenis: 'alur',
				items: [
					{ nama: 'Autentikasi', sumber: 'heuristik', langkah: [`POST ${P}/auth/register`, `POST ${P}/auth/login`] },
					...SUMBER_DAYA.map((r) => ({ nama: `Kelola ${r}`, sumber: 'heuristik', langkah: [`POST ${P}/${r}`, `GET ${P}/${r}/{id}`, `PATCH ${P}/${r}/{id}`, `DELETE ${P}/${r}/{id}`] }))
				]
			}
		},
		{
			jeda: 700,
			pesan: 'Kandidat uji terpetakan: AUTH×5, SESS×4, INPV×18, ACCS×24',
			data: {
				v: 1,
				jenis: 'kandidat',
				ringkas: { AUTH: 5, SESS: 4, INPV: 18, ACCS: 24 },
				per_endpoint: Object.fromEntries(endpoints.map((e) => [e.id, e.path_template.startsWith(`${P}/auth`) ? ['AUTH', 'SESS'] : e.metode_http === 'GET' ? ['ACCS'] : ['ACCS', 'INPV']]))
			}
		},
		{ jeda: 1200, pesan: 'Analisis AI atas hasil penemuan…', data: { v: 1, jenis: 'tahap', tahap: 'ai' } },
		{ jeda: 1800, pesan: 'Penemuan selesai. Titik uji terdeteksi: login, login_page, registrasi, reset_password, ubah_password', data: { v: 1, jenis: 'tahap', tahap: 'selesai', terautentikasi } }
	];
}
