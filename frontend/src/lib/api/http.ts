// Implementasi Api terhadap backend Express (lihat backend/README.md).
// Respons backend: { success, message, data }; galat: { success: false, message, code?, errors? }.
// Sesi: access token JWT (Authorization: Bearer) + refresh token berotasi.
import type { Api } from '#lib/api/types.js';
import type {
	Aplikasi,
	AsetBaru,
	EventScan,
	HalamanAplikasi,
	Pengguna,
	RingkasanPengujian,
	SatuanAdmin,
	SatuanInput,
	StatusWorker
} from '#lib/types.js';
import { bagianUjiKosong } from '#lib/api/aset.js';

const BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';
const KUNCI_TOKEN = 'satya-token';

/** Dipancarkan bila sesi tidak bisa diperpanjang; store auth mendengarkannya untuk keluar. */
export const EVENT_SESI_BERAKHIR = 'satya:sesi-berakhir';

interface Token {
	accessToken: string;
	refreshToken: string;
}

let token: Token | null = (() => {
	try {
		return JSON.parse(localStorage.getItem(KUNCI_TOKEN) ?? 'null');
	} catch {
		return null;
	}
})();

function simpanToken(t: Token | null) {
	token = t;
	try {
		if (t) localStorage.setItem(KUNCI_TOKEN, JSON.stringify(t));
		else localStorage.removeItem(KUNCI_TOKEN);
	} catch {
		// localStorage tidak tersedia; token tetap di memori.
	}
}

export class GalatApi extends Error {
	constructor(
		message: string,
		readonly status: number,
		readonly code?: string,
		readonly errors?: { field: string; message: string }[],
		/** Rincian galat berbentuk objek (mis. 409 SCAN_AKTIF → { scan_id }). */
		readonly detail?: Record<string, unknown>
	) {
		super(message);
	}
}

async function kirim(path: string, init: RequestInit & { json?: unknown }): Promise<Response> {
	const { json, ...rest } = init;
	return fetch(`${BASE}${path}`, {
		...rest,
		headers: {
			...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
			...(token ? { Authorization: `Bearer ${token.accessToken}` } : {}),
			...rest.headers
		},
		body: json !== undefined ? JSON.stringify(json) : rest.body
	});
}

/**
 * Baca aliran SSE lewat fetch (bukan EventSource) agar bisa membawa header Authorization.
 * Selesai saat aliran ditutup; melempar galat bila koneksi gagal/ditolak.
 */
async function bacaSse<T>(path: string, cb: (data: T) => void, signal: AbortSignal): Promise<void> {
	let res = await kirim(path, { signal });
	// Token akses kedaluwarsa: perpanjang sekali lalu buka ulang.
	if (res.status === 401 && (await perpanjangSesi())) res = await kirim(path, { signal });
	if (!res.ok || !res.body) throw new GalatApi(`Aliran ${path} gagal dibuka`, res.status);
	const pembaca = res.body.pipeThrough(new TextDecoderStream()).getReader();
	let sisa = '';
	for (;;) {
		const { value, done } = await pembaca.read();
		if (done) return;
		sisa += value;
		const blok = sisa.split('\n\n');
		sisa = blok.pop() ?? '';
		for (const b of blok) {
			const data = b
				.split('\n')
				.filter((l) => l.startsWith('data:'))
				.map((l) => l.slice(5).trim())
				.join('');
			if (data) cb(JSON.parse(data) as T);
		}
	}
}

// Satu proses refresh untuk banyak request yang gagal bersamaan.
let refreshBerjalan: Promise<boolean> | null = null;
function perpanjangSesi(): Promise<boolean> {
	if (!token) return Promise.resolve(false);
	refreshBerjalan ??= (async () => {
		try {
			const res = await fetch(`${BASE}/auth/refresh`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ refreshToken: token!.refreshToken })
			});
			if (!res.ok) return false;
			const { data } = await res.json();
			simpanToken({ accessToken: data.accessToken, refreshToken: data.refreshToken });
			return true;
		} catch {
			return false;
		} finally {
			refreshBerjalan = null;
		}
	})();
	return refreshBerjalan;
}

async function req<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
	let res = await kirim(path, init);
	// Access token kedaluwarsa → perpanjang sekali lalu ulangi; bila gagal, sesi berakhir.
	if (res.status === 401 && token && !path.startsWith('/auth/')) {
		if (await perpanjangSesi()) res = await kirim(path, init);
		else {
			simpanToken(null);
			window.dispatchEvent(new Event(EVENT_SESI_BERAKHIR));
		}
	}
	const body = await res.json().catch(() => null);
	if (!res.ok || body?.success === false) {
		const e = body?.errors;
		throw new GalatApi(body?.message ?? `Galat ${res.status}`, res.status, body?.code, Array.isArray(e) ? e : undefined, e && !Array.isArray(e) ? e : undefined);
	}
	return body?.data as T;
}

// Aset dari backend hanya berisi data dasar; bagian persiapan uji diisi bawaan (lihat api/aset.ts).
type AsetDto = Omit<Aplikasi, keyof ReturnType<typeof bagianUjiKosong> | 'pemilik_id'> & { pemilik_id: string | null };
const keAplikasi = (a: AsetDto): Aplikasi => ({ ...a, ...bagianUjiKosong(), pemilik_id: a.pemilik_id ?? '' });
// Backend memakai id numerik untuk induk.
const kirimSatuan = ({ induk_id, ...data }: Partial<SatuanInput>) => ({
	...data,
	...(induk_id !== undefined ? { induk_id: induk_id === null ? null : Number(induk_id) } : {})
});
const kirimAset = ({ satuan_id, ...data }: Partial<AsetBaru>) => ({
	...data,
	...(satuan_id ? { satuan_id: Number(satuan_id) } : {})
});

export const httpApi: Api = {
	async login(email, password) {
		const data = await req<Token & { user: Pengguna }>('/auth/login', { method: 'POST', json: { email, password } });
		simpanToken({ accessToken: data.accessToken, refreshToken: data.refreshToken });
		return data.user;
	},
	async loginDemo() {
		throw new GalatApi('Akun demo hanya tersedia di mode mock', 400);
	},
	async logout() {
		if (!token) return;
		const refreshToken = token.refreshToken;
		try {
			await req('/auth/logout', { method: 'POST', json: { refreshToken } });
		} finally {
			simpanToken(null);
		}
	},
	async gantiSandi(lama, baru) {
		const data = await req<Token>('/auth/change-password', {
			method: 'POST',
			json: { passwordLama: lama, passwordBaru: baru }
		});
		// Backend mencabut semua sesi lama dan memberi token baru untuk sesi ini.
		simpanToken({ accessToken: data.accessToken, refreshToken: data.refreshToken });
	},
	daftar: (data) => req('/auth/register', { method: 'POST', json: { ...data, satuan_id: Number(data.satuan_id) } }),
	cariSatuan: (kata) => req(`/units?${new URLSearchParams({ search: kata.trim() })}`),
	async cekKetersediaan(data) {
		const { tersedia } = await req<{ tersedia: boolean }>('/auth/check-availability', { method: 'POST', json: data });
		return tersedia;
	},
	lupaSandi: (email) => req('/auth/forgot-password', { method: 'POST', json: { email } }),
	resetSandi: (resetToken, password) =>
		req('/auth/reset-password', { method: 'POST', json: { token: resetToken, password } }),
	verifikasiEmail: (verifToken) => req('/auth/verify-email', { method: 'POST', json: { token: verifToken } }),
	kirimUlangVerifikasi: (email) => req('/auth/resend-verification', { method: 'POST', json: { email } }),

	async listPengguna(filter = {}) {
		const q = new URLSearchParams({ limit: '100', status: filter.status ?? '', search: filter.search ?? '' });
		const data = await req<{ items: Pengguna[] }>(`/users?${q}`);
		return data.items;
	},
	verifikasiPengguna: (id, peran) => req(`/users/${id}/verify`, { method: 'PATCH', json: { peran } }),
	tolakPendaftaran: (id) => req(`/users/${id}`, { method: 'DELETE' }),
	ubahStatusPengguna: (id, aktif) => req(`/users/${id}/status`, { method: 'PATCH', json: { aktif } }),
	ubahPeranPengguna: (id, peran) => req(`/users/${id}/role`, { method: 'PATCH', json: { peran } }),
	async listSatuanAdmin({ search = '', status = '', jenis = '', provinsi = '', induk = '', page = 1, limit = 50 }) {
		const q = new URLSearchParams({ search, status, jenis, provinsi, induk, page: String(page), limit: String(limit) });
		const data = await req<{ items: SatuanAdmin[]; meta: { total: number; totalPages: number; limit: number } }>(
			`/admin/units?${q}`
		);
		return { items: data.items, ...data.meta };
	},
	getSatuanAdmin: (id) => req(`/admin/units/${id}`),
	tambahSatuan: (data) => req('/admin/units', { method: 'POST', json: kirimSatuan(data) }),
	ubahSatuan: (id, data) => req(`/admin/units/${id}`, { method: 'PATCH', json: kirimSatuan(data) }),

	// --- Fitur di bawah ini belum tersedia di backend (lihat client.ts: sementara memakai mock).
	getKatalog: () => req('/catalog'),
	// TODO backend: GET /workers/availability setelah registri worker (register + heartbeat) dibuat.
	getKetersediaanWorker: async () => ({}),
	// TODO backend: GET/PUT /applications/:id/preparation/AUTH (kata sandi akun uji disimpan terenkripsi).
	getPersiapanAuth: async () => null,
	simpanPersiapanAuth: async (_id, data) => data,
	// Persiapan (subset yang dibutuhkan worker) dikirim ke scan_targets backend.
	simpanTargetUji: (id, data) => req(`/apps/${id}/scan-target`, { method: 'PUT', json: data }),
	getTargetUji: (id) => req(`/apps/${id}/scan-target`),
	tambahKontrol: (kodeFungsi, data) => req(`/catalog/functions/${kodeFungsi}/controls`, { method: 'POST', json: data }),
	ubahKontrol: (kode, data) => req(`/catalog/controls/${kode}`, { method: 'PATCH', json: data }),
	tambahMetode: (kodeKontrol, data) => req(`/catalog/controls/${kodeKontrol}/methods`, { method: 'POST', json: data }),
	ubahMetode: (kode, data) => req(`/catalog/methods/${kode}`, { method: 'PATCH', json: data }),

	async listAplikasi() {
		const data = await req<{ items: AsetDto[] }>('/applications?limit=100');
		return data.items.map(keAplikasi);
	},
	async cariAplikasi(filter) {
		const q = new URLSearchParams();
		for (const [k, v] of Object.entries(filter)) if (v !== undefined && v !== '') q.set(k, String(v));
		const data = await req<{
			items: (AsetDto & { pengujian: RingkasanPengujian })[];
			meta: Omit<HalamanAplikasi, 'items'>;
		}>(`/applications?${q}`);
		return { ...data.meta, items: data.items.map((a) => ({ ...keAplikasi(a), pengujian: a.pengujian })) };
	},
	getAplikasi: async (id) => keAplikasi(await req<AsetDto>(`/applications/${id}`)),
	buatAplikasi: async (data) =>
		keAplikasi(await req<AsetDto>('/applications', { method: 'POST', json: kirimAset(data) })),
	ubahAplikasi: async (id, data) =>
		keAplikasi(await req<AsetDto>(`/applications/${id}`, { method: 'PATCH', json: kirimAset(data) })),
	verifikasiKepemilikan: (id) => req(`/apps/${id}/verify-ownership`, { method: 'POST' }),
	ajukanIzinIntrusif: (id, izin) => req(`/apps/${id}/intrusive-permit`, { method: 'POST', json: izin }),
	putuskanIzinIntrusif: (id, disetujui, catatan) =>
		req(`/approvals/${id}`, { method: 'POST', json: { disetujui, catatan } }),

	listScan: (aplikasiId) => req(aplikasiId ? `/scans?app=${encodeURIComponent(aplikasiId)}` : '/scans'),
	getScan: (id) => req(`/scans/${id}`),
	statusWorker: () => req('/workers/status'),
	getPeta: () => req('/dashboard/peta'),
	getPetaProvinsi: (kode) => req(`/dashboard/peta/provinsi/${encodeURIComponent(kode)}`),
	mulaiScan: (aplikasiId, opsi) =>
		req(`/apps/${aplikasiId}/scans`, {
			method: 'POST',
			json: {
				mode: opsi?.mode ?? 'terarah',
				...(opsi?.pendekatan ? { pendekatan: opsi.pendekatan } : {}),
				...(opsi?.persetujuan ? { persetujuan: true } : {}),
				...(opsi?.accounts ? { accounts: opsi.accounts } : {}),
				...(opsi?.options ? { options: opsi.options } : {}),
				...(opsi?.pakai_discovery ? { pakai_discovery: true } : {}),
				...(opsi?.persetujuan_sk ? { persetujuan_sk: opsi.persetujuan_sk } : {})
			}
		}),
	batalkanScan: (id) => req(`/scans/${id}/cancel`, { method: 'POST' }),
	// SSE lewat fetch (bukan EventSource) agar bisa membawa header Authorization.
	pantauScan(id, cb) {
		const kendali = new AbortController();
		bacaSse<EventScan>(`/scans/${id}/events`, cb, kendali.signal).catch(() => {});
		return () => kendali.abort();
	},
	// Status worker didorong server hanya saat berubah (pengganti polling). `putus` dipanggil bila aliran
	// berakhir/gagal — store yang memutuskan kapan menyambung ulang.
	pantauStatusWorker(cb, putus) {
		const kendali = new AbortController();
		bacaSse<StatusWorker>('/workers/status/stream', cb, kendali.signal)
			.catch(() => {})
			.finally(() => {
				if (!kendali.signal.aborted) putus?.();
			});
		return () => kendali.abort();
	},

	unggahBukti: (scanId, metodeId, bukti) =>
		req(`/scans/${scanId}/evidence`, { method: 'POST', json: { metode_id: metodeId, ...bukti } }),
	tinjauMetode: (scanId, metodeId, putusan, catatan) =>
		req(`/scans/${scanId}/reviews`, { method: 'POST', json: { metode_id: metodeId, putusan, catatan } }),
	antrianTinjauan: () => req('/reviews/queue'),

	analisisAi: (scanId) => req(`/scans/${scanId}/ai`, { method: 'POST' }),

	getPengaturanAi: () => req('/settings/ai'),
	simpanPengaturanAi: (p) => req('/settings/ai', { method: 'PUT', json: p })
};
