// Implementasi Api tiruan: state di memori + localStorage, scan disimulasikan dengan timer.
import { urutanPenemuan } from './penemuan.js';
import { indeksMetode, katalog, LABEL_ENGINE, LABEL_STATUS, nilaiKelaikan, semuaMetode, penerapanMetode } from '#lib/catalog.js';
import type { Api } from '#lib/api/types.js';
import { USE_MOCK } from '#lib/api/mode.js';
import { bagianUjiKosong } from '#lib/api/aset.js';
import type {
	AntreanScan,
	AkunPersiapan,
	Aplikasi,
	BarisAplikasi,
	EventScan,
	HalamanAplikasi,
	HasilMetode,
	Kontrol,
	LogScan,
	Metode,
	Pengguna,
	PersiapanAuth,
	SatuanAdmin,
	SatuanInput,
	Scan,
	StatusAkun,
	StatusWorker
} from '#lib/types.js';
import { buatSeed, DAFTAR_SATUAN, PENGGUNA_DEMO, type StateMock } from './seed';
import { analisisTiruan, hasilMetode } from './simulasi';
import { peristiwaUji } from './uji';
import { GalatApi } from '#lib/api/http.js';
import { JENIS_SATUAN, namaProvinsi } from '#lib/data/satuan.js';
import { dataContoh, SIKLUS_MS } from '#lib/peta/contoh.js';

const KUNCI = 'satya-mock-v2';
// Persiapan pengujian disimpan terpisah dari state mock agar juga berlaku untuk aset dari backend (mode hibrida).
const KUNCI_PERSIAPAN = 'satya-persiapan-mock';
function persiapanMock(): Record<string, PersiapanAuth> {
	try {
		return JSON.parse(localStorage.getItem(KUNCI_PERSIAPAN) ?? '{}');
	} catch {
		return {};
	}
}

function muat(): StateMock {
	try {
		const raw = localStorage.getItem(KUNCI);
		if (raw) return JSON.parse(raw) as StateMock;
	} catch {
		// localStorage tidak tersedia; pakai seed di memori.
	}
	return buatSeed();
}

let state = muat();

function simpan() {
	try {
		localStorage.setItem(KUNCI, JSON.stringify(state));
	} catch {
		// abaikan
	}
}

export function resetMock() {
	state = buatSeed();
	simpan();
}

const salin = <T>(v: T): T => structuredClone(v);
// Jeda tiruan jaringan hanya untuk mode demo penuh. Saat backend dipakai (mode hibrida), fitur yang masih
// mock langsung menjawab agar perpindahan halaman tidak tertahan.
const jeda = (ms = 150 + Math.random() * 200) =>
	USE_MOCK ? new Promise((r) => setTimeout(r, ms)) : Promise.resolve();
const idBaru = (awalan: string) => `${awalan}-${Math.random().toString(36).slice(2, 9)}`;
const sekarang = () => new Date().toISOString();

function cariApp(id: string): Aplikasi {
	const a = state.aplikasi.find((x) => x.id === id);
	if (!a) throw new Error('Aplikasi tidak ditemukan');
	return a;
}

// Satuan kerja tiruan (hanya di memori; kembali ke daftar awal saat halaman dimuat ulang).
type SatuanMock = SatuanInput & { id: string; dibuat_pada: string };
const satuanMock: SatuanMock[] = DAFTAR_SATUAN.map((s) => ({
	...s,
	aktif: true,
	dibuat_pada: new Date().toISOString()
}));
const MAKS_KEDALAMAN_SATUAN = 8;
function leluhurSatuan(id: string | null) {
	const hasil: { id: string; nama: string }[] = [];
	for (
		let u = satuanMock.find((x) => x.id === id);
		u && hasil.length < MAKS_KEDALAMAN_SATUAN;
		u = satuanMock.find((x) => x.id === u!.induk_id)
	)
		hasil.unshift({ id: u.id, nama: u.nama });
	return hasil;
}
const tinggiSatuan = (id: string): number =>
	Math.max(0, ...satuanMock.filter((x) => x.induk_id === id).map((x) => 1 + tinggiSatuan(x.id)));
const jalurSatuan = (s: SatuanMock) =>
	leluhurSatuan(s.induk_id)
		.map((l) => l.nama)
		.join(' › ');
const denganJumlah = (s: SatuanMock): SatuanAdmin => ({
	...s,
	jalur: jalurSatuan(s),
	leluhur: leluhurSatuan(s.induk_id),
	provinsi: namaProvinsi(s.provinsi_kode),
	jumlah_pengguna: state.pengguna.filter((u) => u.satuan === s.nama).length,
	jumlah_aplikasi: state.aplikasi.filter((a) => a.satuan === s.nama).length,
	jumlah_sub: satuanMock.filter((x) => x.induk_id === s.id).length
});
function cekNamaSatuan(nama: string, kecuali?: string) {
	if (satuanMock.some((s) => s.id !== kecuali && s.nama.toLowerCase() === nama.toLowerCase()))
		throw new Error('Satuan dengan nama ini sudah ada');
}
function cekIndukSatuan(indukId: string | null, id?: string) {
	if (!indukId) return;
	if (indukId === id) throw new Error('Satuan tidak bisa menjadi induk bagi dirinya sendiri');
	if (!satuanMock.some((x) => x.id === indukId)) throw new Error('Satuan induk tidak ditemukan');
	const leluhur = leluhurSatuan(indukId);
	if (id && leluhur.some((l) => l.id === id))
		throw new Error('Satuan induk tidak boleh berasal dari sub-satuannya sendiri');
	if (leluhur.length + (id ? tinggiSatuan(id) : 0) >= MAKS_KEDALAMAN_SATUAN)
		throw new Error(`Hierarki satuan maksimal ${MAKS_KEDALAMAN_SATUAN} tingkat`);
}
function cekKoordinat(s: Pick<SatuanInput, 'latitude' | 'longitude'>) {
	if ((s.latitude === null) !== (s.longitude === null))
		throw new Error('Isi latitude dan longitude berpasangan, atau kosongkan keduanya');
}
const kosongkan = <T>(v: T) => (v === '' ? null : v);
const rapikanSatuan = (data: Partial<SatuanInput>) =>
	Object.fromEntries(
		Object.entries(data).map(([k, v]) => [k, kosongkan(v)])
	) as Partial<SatuanInput>;

// Salinan katalog yang bisa diubah admin di mode demo (hanya di memori).
const katalogMock = salin(katalog);
// parameter: null (atau objek kosong) = hapus parameter, sama seperti backend.
function terapkanParameter<T extends { parameter?: Record<string, unknown> }>(
	target: T,
	{ parameter, ...data }: { parameter?: Record<string, unknown> | null } & Record<string, unknown>
) {
	Object.assign(target, salin(data));
	if (parameter === null || (parameter && !Object.keys(parameter).length)) delete target.parameter;
	else if (parameter) target.parameter = salin(parameter);
	return target;
}
const cariKontrolMock = (kode: string) =>
	katalogMock.fungsi_keamanan.flatMap((f) => f.kontrol).find((k) => k.id === kode);

function cariPengguna(id: string): Pengguna {
	const u = state.pengguna.find((x) => x.id === id);
	if (!u) throw new Error('Pengguna tidak ditemukan');
	return u;
}

const statusAkun = (u: Pengguna): StatusAkun =>
	u.terverifikasi === false ? 'pending' : u.aktif ? 'verified' : 'inactive';

function cariScan(id: string): Scan {
	const s = state.scan.find((x) => x.id === id);
	if (!s) throw new Error('Pengujian tidak ditemukan');
	return s;
}

// ---------------------------------------------------------------------------
// Simulasi scan

const pelanggan = new Map<string, Set<(e: EventScan) => void>>();
const berjalan = new Map<string, ReturnType<typeof setTimeout>>();

function siarkan(scanId: string, e: EventScan) {
	pelanggan.get(scanId)?.forEach((cb) => cb(e));
}

function catat(scan: Scan, level: LogScan['level'], pesan: string, data?: LogScan['data']) {
	const log: LogScan = { waktu: sekarang(), level, pesan, ...(data ? { data } : {}) };
	scan.log.push(log);
	siarkan(scan.id, { tipe: 'log', log });
}

function jalankan(scanId: string) {
	const scan = cariScan(scanId);
	const app = cariApp(scan.aplikasi_id);
	const antrean = semuaMetode.filter(({ metode }) => scan.hasil[metode.id]?.status === 'antre');

	const langkah = () => {
		if (scan.status !== 'berjalan') return;
		const item = antrean.shift();
		if (!item) {
			scan.status = 'selesai';
			scan.selesai_pada = sekarang();
			catat(scan, 'info', 'Pengujian selesai.');
			siarkan(scan.id, { tipe: 'status', status: 'selesai', selesai_pada: scan.selesai_pada });
			berjalan.delete(scanId);
			simpan();
			return;
		}
		const { metode } = item;
		const mulai: HasilMetode = { metode_id: metode.id, status: 'berjalan', bukti: [] };
		scan.hasil[metode.id] = mulai;
		siarkan(scan.id, { tipe: 'metode', hasil: mulai });
		catat(scan, 'info', `[${LABEL_ENGINE[metode.engine]}] ${metode.id} — ${metode.nama}`);

		const durasi = metode.jenis === 'manual' ? 60 : 120 + Math.random() * 380;
		// Metode AUTH: pancarkan peristiwa uji (langkah + request) secepat worker; UI mengantrekannya.
		const hAuth = metode.id.startsWith('AUTH-') ? hasilMetode(app, metode) : null;
		if (hAuth) for (const l of peristiwaUji(app, metode, hAuth)) catat(scan, 'info', l.pesan, l.data);
		berjalan.set(
			scanId,
			setTimeout(() => {
				if (scan.status !== 'berjalan') return;
				const h = hAuth ?? hasilMetode(app, metode);
				scan.hasil[metode.id] = h;
				siarkan(scan.id, { tipe: 'metode', hasil: h });
				if (h.status === 'gagal') catat(scan, 'peringatan', `${metode.id}: GAGAL — ${h.ringkasan}`);
				else if (h.menunggu_tinjauan) catat(scan, 'info', `${metode.id}: menunggu tinjauan asesor`);
				else catat(scan, 'info', `${metode.id}: ${LABEL_STATUS[h.status]}`);
				simpan();
				berjalan.set(scanId, setTimeout(langkah, 40));
			}, durasi)
		);
	};
	langkah();
}

// ---------------------------------------------------------------------------
// Worker tiruan (mode demo). Satu worker "worker-demo" yang aktif; set
// localStorage 'satya.mock.worker' = 'mati' untuk mensimulasikan tak ada worker aktif.

function workerMockMati(): boolean {
	try {
		return localStorage.getItem('satya.mock.worker') === 'mati';
	} catch {
		return false;
	}
}

/** Antrean tiruan: scan berjalan diurut waktu mulai; yang pertama "sedang dikerjakan". */
function antreanMock(scanId: string | null): AntreanScan {
	const aktif = state.scan.filter((s) => s.status === 'berjalan').sort((a, b) => a.dimulai_pada.localeCompare(b.dimulai_pada));
	const nAktif = workerMockMati() ? 0 : 1;
	const sisa = (s: Scan) => Object.values(s.hasil).filter((h) => h.status === 'antre' || h.status === 'berjalan').length;
	const idx = scanId ? aktif.findIndex((s) => s.id === scanId) : aktif.length;
	const depan = aktif.slice(0, Math.max(0, idx));
	const sedang = idx === 0 && nAktif > 0;
	return {
		posisi: sedang ? 0 : depan.length + 1,
		di_depan: depan.reduce((n, s) => n + sisa(s), 0),
		scan_di_depan: depan.length,
		sedang_dikerjakan: sedang,
		perkiraan_tunggu_detik: sedang ? 0 : depan.reduce((n, s) => n + sisa(s), 0) * 3,
		worker_aktif: nAktif,
		worker: sedang ? { id: 'worker-demo', tahap: tahapMock(aktif[0]), terakhir_terlihat_detik: 2 } : null
	};
}

function tahapMock(s: Scan | undefined): string | null {
	if (!s) return null;
	const jalan = Object.values(s.hasil).find((h) => h.status === 'berjalan');
	return jalan ? jalan.metode_id : 'penemuan';
}

function statusWorkerMock(): StatusWorker {
	const mati = workerMockMati();
	const aktif = state.scan.filter((s) => s.status === 'berjalan').sort((a, b) => a.dimulai_pada.localeCompare(b.dimulai_pada));
	const sibuk = !mati && aktif.length > 0;
	return {
		aktif: mati ? 0 : 1,
		sibuk: sibuk ? 1 : 0,
		siaga: !mati && !sibuk ? 1 : 0,
		engines: mati ? [] : ['custom', 'discovery', 'zap', 'playwright'],
		workers: [
			{
				id: 'worker-demo',
				status: mati ? 'terputus' : sibuk ? 'sibuk' : 'siaga',
				engines: ['custom', 'discovery', 'zap', 'playwright'],
				versi: 'satya-worker 0.2 (demo)',
				terakhir_terlihat_detik: mati ? 900 : 2,
				sedang: sibuk ? { scan_id: aktif[0].id, aplikasi: cariApp(aktif[0].aplikasi_id).nama, tahap: tahapMock(aktif[0]) } : null
			}
		],
		antrean: {
			task_antre: aktif.reduce((n, s) => n + Object.values(s.hasil).filter((h) => h.status === 'antre').length, 0),
			task_berjalan: sibuk ? 1 : 0,
			scan: aktif.map((s) => ({ scan_id: s.id, aplikasi: cariApp(s.aplikasi_id).nama, ...antreanMock(s.id) }))
		},
		scan_baru: antreanMock(null)
	};
}

// Lanjutkan scan yang terputus karena halaman dimuat ulang.
for (const s of state.scan) if (s.status === 'berjalan') setTimeout(() => jalankan(s.id), 500);

// ---------------------------------------------------------------------------

export const mockApi: Api = {
	// Mock tidak memeriksa kata sandi; pesan & urutan pemeriksaan mengikuti backend.
	async login(email) {
		await jeda();
		const p = state.pengguna.find((u) => u.email.toLowerCase() === email.toLowerCase());
		if (!p) throw new Error('Email atau kata sandi salah');
		// Data lama di localStorage belum punya field ini; anggap terverifikasi.
		if (p.terverifikasi === false)
			throw new Error('Akun Anda belum diverifikasi administrator. Silakan tunggu persetujuan.');
		if (!p.aktif) throw new Error('Akun Anda dinonaktifkan. Hubungi administrator.');
		return salin(p);
	},

	async logout() {},

	// Mode demo tidak menyimpan kata sandi; cukup tolak bila sama dengan yang lama.
	async gantiSandi(lama, baru) {
		await jeda(500);
		if (lama === baru) throw new Error('Kata sandi baru harus berbeda dari yang lama');
	},

	async loginDemo(peran) {
		await jeda();
		return salin(state.pengguna.find((u) => u.id === PENGGUNA_DEMO[peran])!);
	},

	async daftar(data) {
		await jeda(700);
		const satuan = satuanMock.find((s) => s.id === data.satuan_id && s.aktif);
		if (!satuan) throw new Error('Satuan tidak ditemukan di daftar');
		if (!state.pengguna.some((u) => u.email.toLowerCase() === data.email.toLowerCase())) {
			state.pengguna.push({
				id: idBaru('u'),
				nama: data.nama,
				status_kepegawaian: data.status_kepegawaian,
				pangkat: data.pangkat,
				nrp: data.nrp,
				email: data.email,
				satuan: satuan.nama,
				satuan_id: satuan.id,
				peran: 'pemilik',
				aktif: true,
				terverifikasi: false,
				dibuat_pada: sekarang()
			});
			simpan();
		}
	},

	async cekKetersediaan(data) {
		await jeda(400);
		return !state.pengguna.some((u) =>
			'nrp' in data ? u.nrp === data.nrp : u.email.toLowerCase() === data.email.toLowerCase()
		);
	},

	async cariSatuan(kata) {
		await jeda();
		const q = kata.trim().toLowerCase();
		return satuanMock
			.filter((s) => s.aktif && s.nama.toLowerCase().includes(q))
			.slice(0, 20)
			.map(({ id, nama }) => ({ id, nama }));
	},

	async lupaSandi() {
		await jeda(700);
	},

	// Mode demo tidak mengirim email; token apa pun diterima kecuali "kedaluwarsa".
	async resetSandi(token) {
		await jeda(600);
		if (!token || token === 'kedaluwarsa')
			throw new Error('Tautan atur ulang kata sandi tidak valid atau sudah kedaluwarsa');
	},

	async getKatalog() {
		await jeda();
		return salin(katalogMock);
	},

	async getPersiapanAuth(aplikasiId) {
		await jeda();
		return salin(persiapanMock()[aplikasiId] ?? null);
	},

	// Kata sandi akun uji tidak pernah disimpan di browser; cukup tanda `terisi`.
	async simpanPersiapanAuth(aplikasiId, data) {
		await jeda(400);
		const tanpaSandi = (a: AkunPersiapan): AkunPersiapan => ({ username: a.username, terisi: a.terisi || !!a.password });
		const simpanan: PersiapanAuth = {
			...salin(data),
			akun_uji: { utama: tanpaSandi(data.akun_uji.utama), penguncian: tanpaSandi(data.akun_uji.penguncian) },
			diperbarui_pada: sekarang()
		};
		const semua = persiapanMock();
		semua[aplikasiId] = simpanan;
		try {
			localStorage.setItem(KUNCI_PERSIAPAN, JSON.stringify(semua));
		} catch {
			// abaikan
		}
		return salin(simpanan);
	},

	// Mode demo tidak punya backend: terima saja (scan_targets hanya dipakai worker nyata).
	async simpanTargetUji(aplikasiId, data) {
		await jeda(200);
		return { aplikasi_id: aplikasiId, ...salin(data) };
	},
	async getTargetUji(aplikasiId) {
		await jeda(100);
		return { aplikasi_id: aplikasiId, akun: [], discovery: null };
	},

	// Simulasi registri worker: ketersediaan ditentukan engine metode (data contoh).
	async getKetersediaanWorker() {
		await jeda();
		const perEngine: Record<string, { siap: number; total: number }> = {
			custom: { siap: 2, total: 2 },
			sslyze: { siap: 1, total: 1 },
			playwright: { siap: 1, total: 2 },
			zap: { siap: 1, total: 1 },
			nuclei: { siap: 0, total: 1 }
		};
		const hasil: Record<string, { siap: number; total: number }> = {};
		for (const m of katalogMock.fungsi_keamanan.flatMap((f) => f.kontrol.flatMap((k) => k.metode_pengujian))) {
			if (perEngine[m.engine]) hasil[m.check_id] = { ...perEngine[m.engine] };
		}
		return hasil;
	},

	async tambahKontrol(kodeFungsi, data) {
		await jeda();
		const fungsi = katalogMock.fungsi_keamanan.find((f) => f.id === kodeFungsi);
		if (!fungsi) throw new Error(`Fungsi keamanan ${kodeFungsi} tidak ditemukan`);
		const id = `${kodeFungsi}-${data.nomor_referensi}`;
		if (cariKontrolMock(id)) throw new Error(`Kontrol ${id} sudah ada`);
		const k = terapkanParameter({ id, aktif: true, metode_pengujian: [] } as unknown as Kontrol, data);
		fungsi.kontrol.push(k);
		return salin(k);
	},

	async ubahKontrol(kode, data) {
		await jeda();
		const k = cariKontrolMock(kode);
		if (!k) throw new Error(`Kontrol ${kode} tidak ditemukan`);
		terapkanParameter(k, data);
		return salin(k);
	},

	async tambahMetode(kodeKontrol, data) {
		await jeda();
		const k = cariKontrolMock(kodeKontrol);
		if (!k) throw new Error(`Kontrol ${kodeKontrol} tidak ditemukan`);
		const nomor = Math.max(0, ...k.metode_pengujian.map((m) => Number(m.id.match(/-T(d+)$/)?.[1] ?? 0))) + 1;
		const m = terapkanParameter({ id: `${kodeKontrol}-T${String(nomor).padStart(2, '0')}`, aktif: true } as unknown as Metode, data);
		k.metode_pengujian.push(m);
		return salin(m);
	},

	async ubahMetode(kode, data) {
		await jeda();
		const m = katalogMock.fungsi_keamanan.flatMap((f) => f.kontrol.flatMap((k) => k.metode_pengujian)).find((x) => x.id === kode);
		if (!m) throw new Error(`Metode ${kode} tidak ditemukan`);
		terapkanParameter(m, data);
		return salin(m);
	},

	async listAplikasi() {
		await jeda();
		const u = state.pengguna.find((x) => x.id === sesiId);
		return salin(u?.peran === 'pemilik' ? state.aplikasi.filter((a) => a.satuan === u.satuan) : state.aplikasi);
	},

	async cariAplikasi({
		page = 1,
		limit = 25,
		search = '',
		lingkungan = '',
		klasifikasi = '',
		satuan_id = '',
		putusan = '',
		sort = 'dibuat',
		order = 'desc',
		ringkasan = false
	}) {
		await jeda();
		const u = state.pengguna.find((x) => x.id === sesiId);
		const cakupan =
			u?.peran === 'pemilik' ? state.aplikasi.filter((a) => a.satuan === u.satuan) : state.aplikasi;
		const idSatuan = (a: Aplikasi) => a.satuan_id ?? a.satuan;

		// Ringkasan pengujian seperti yang dihitung backend saat scan selesai.
		const baris: BarisAplikasi[] = cakupan.map((app) => {
			const milik = state.scan
				.filter((s) => s.aplikasi_id === app.id)
				.sort((a, b) => b.dimulai_pada.localeCompare(a.dimulai_pada));
			const selesai = milik.find((s) => s.status === 'selesai');
			const n = selesai ? nilaiKelaikan(selesai.hasil) : null;
			const temuan = { kritis: 0, tinggi: 0, sedang: 0, rendah: 0 };
			for (const h of Object.values(selesai?.hasil ?? {})) {
				const sev = indeksMetode.get(h.metode_id)?.metode.severity;
				if (h.status === 'gagal' && sev && sev in temuan) temuan[sev as keyof typeof temuan]++;
			}
			return {
				...salin(app),
				pengujian: {
					scan_terakhir_pada: milik[0]?.dimulai_pada ?? null,
					berjalan: milik.some((s) => s.status === 'berjalan'),
					scan_selesai_id: selesai?.id ?? null,
					selesai_pada: selesai?.selesai_pada ?? null,
					putusan: n?.putusan ?? null,
					skor: n?.skor ?? null,
					temuan: n ? temuan : null
				}
			};
		});

		const q = search.trim().toLowerCase();
		const cocokTanpaPutusan = baris.filter(
			(a) =>
				(!q ||
					[a.nama, a.satuan, a.url_dasar, a.pic_nama].some((s) => s?.toLowerCase().includes(q))) &&
				(!lingkungan || a.lingkungan === lingkungan) &&
				(!klasifikasi || a.klasifikasi_data === klasifikasi) &&
				(!satuan_id || idSatuan(a) === satuan_id)
		);
		const status = (a: BarisAplikasi) => a.pengujian.putusan ?? 'belum';
		const cocok = cocokTanpaPutusan.filter((a) => !putusan || status(a) === putusan);

		const URUT_KLAS = { biasa: 0, terbatas: 1, rahasia: 2 };
		const URUT_LING = { produksi: 0, staging: 1, pengembangan: 2 };
		const kunci = (a: BarisAplikasi): (string | number)[] | null => {
			const t = a.pengujian.temuan;
			switch (sort) {
				case 'nama':
					return [a.nama.toLowerCase()];
				case 'satuan':
					return [a.satuan.toLowerCase(), a.nama.toLowerCase()];
				case 'lingkungan':
					return [URUT_LING[a.lingkungan]];
				case 'klasifikasi':
					return [URUT_KLAS[a.klasifikasi_data]];
				case 'skor':
					return a.pengujian.skor === null ? null : [a.pengujian.skor];
				case 'temuan':
					return t ? [t.kritis, t.tinggi, t.sedang, t.rendah] : null;
				case 'uji':
					return a.pengujian.scan_terakhir_pada ? [a.pengujian.scan_terakhir_pada] : null;
				default:
					return [a.dibuat_pada];
			}
		};
		const k = order === 'asc' ? 1 : -1;
		cocok.sort((x, y) => {
			const a = kunci(x);
			const b = kunci(y);
			if (!a || !b) return a === b ? 0 : a ? -1 : 1; // kosong di akhir
			for (let i = 0; i < a.length; i++) {
				const d =
					typeof a[i] === 'number'
						? (a[i] as number) - (b[i] as number)
						: String(a[i]).localeCompare(String(b[i]));
				if (d) return d * k;
			}
			return 0;
		});

		const hasil: HalamanAplikasi = {
			items: cocok.slice((page - 1) * limit, page * limit),
			page,
			limit,
			total: cocok.length,
			totalPages: Math.max(1, Math.ceil(cocok.length / limit))
		};
		if (ringkasan) {
			const j = { semua: 0, laik: 0, laik_bersyarat: 0, tidak_laik: 0, belum: 0 };
			for (const a of cocokTanpaPutusan) {
				j.semua++;
				j[status(a)]++;
			}
			const perSatuan = new Map<string, { id: string; nama: string; jumlah: number }>();
			for (const a of cakupan) {
				const s = perSatuan.get(idSatuan(a)) ?? { id: idSatuan(a), nama: a.satuan, jumlah: 0 };
				s.jumlah++;
				perSatuan.set(s.id, s);
			}
			hasil.ringkasan = j;
			hasil.opsi_satuan = [...perSatuan.values()].sort((a, b) => a.nama.localeCompare(b.nama));
		}
		return hasil;
	},

	async getAplikasi(id) {
		await jeda();
		return salin(cariApp(id));
	},

	async buatAplikasi(data) {
		await jeda();
		if (state.aplikasi.some((x) => x.url_dasar === data.url_dasar))
			throw new Error('URL dasar ini sudah terdaftar sebagai aset lain');
		const pengguna = state.pengguna.find((u) => u.id === sesiId);
		const satuan = satuanMock.find((x) => x.id === data.satuan_id)?.nama ?? pengguna?.satuan ?? '';
		const { satuan_id: _, ...dasar } = salin(data);
		const app: Aplikasi = {
			...dasar,
			...bagianUjiKosong(),
			satuan,
			id: idBaru('app'),
			pemilik_id: sesiId ?? 'u-pemilik',
			dibuat_pada: sekarang()
		};
		state.aplikasi.unshift(app);
		simpan();
		return salin(app);
	},

	async ubahAplikasi(id, data) {
		await jeda();
		const app = cariApp(id);
		const { satuan_id, ...dasar } = salin(data);
		if (satuan_id) app.satuan = satuanMock.find((x) => x.id === satuan_id)?.nama ?? app.satuan;
		Object.assign(app, dasar, { diubah_pada: sekarang() });
		simpan();
		return salin(app);
	},

	async verifikasiKepemilikan(id) {
		await jeda(900);
		const app = cariApp(id);
		app.verifikasi.status = 'terverifikasi';
		app.verifikasi.diverifikasi_pada = sekarang();
		simpan();
		return salin(app);
	},

	async ajukanIzinIntrusif(id, izin) {
		await jeda();
		const app = cariApp(id);
		app.profil_pengujian = 'intrusif';
		app.izin_intrusif = { ...izin, status: 'menunggu', diajukan_pada: sekarang() };
		simpan();
		return salin(app);
	},

	async putuskanIzinIntrusif(id, disetujui, catatan) {
		await jeda();
		const app = cariApp(id);
		app.izin_intrusif.status = disetujui ? 'disetujui' : 'ditolak';
		app.izin_intrusif.catatan_asesor = catatan;
		app.izin_intrusif.diputuskan_oleh = state.pengguna.find((u) => u.id === sesiId)?.nama;
		simpan();
		return salin(app);
	},

	async listScan(aplikasiId) {
		await jeda();
		return salin(
			state.scan
				.filter((s) => !aplikasiId || s.aplikasi_id === aplikasiId)
				.sort((a, b) => b.dimulai_pada.localeCompare(a.dimulai_pada))
		);
	},

	async getScan(id) {
		await jeda();
		const s = salin(cariScan(id));
		if (s.status === 'berjalan') s.antrean = antreanMock(id);
		return s;
	},

	async statusWorker() {
		await jeda(80);
		return statusWorkerMock();
	},

	// Mode demo: peta memakai data contoh yang bergeser tiap siklus pembaruan.
	async getPeta() {
		await jeda();
		return dataContoh('24j', Math.floor(Date.now() / SIKLUS_MS));
	},

	// Mode demo: tanpa jaringan; status tiruan dibaca ulang dari memori berkala.
	pantauStatusWorker(cb) {
		cb(statusWorkerMock());
		const t = setInterval(() => cb(statusWorkerMock()), 10_000);
		return () => clearInterval(t);
	},

	async mulaiScan(aplikasiId, opsi) {
		await jeda();
		const app = cariApp(aplikasiId);
		const mode = opsi?.mode ?? 'terarah';
		if (mode === 'eksploratif' && !opsi?.persetujuan)
			throw new Error('Persetujuan pemindaian aktif wajib untuk mode eksploratif.');
		if (app.verifikasi.status !== 'terverifikasi')
			throw new Error('Kepemilikan aplikasi belum terverifikasi.');
		const aktifApp = state.scan.find((s) => s.aplikasi_id === aplikasiId && s.status === 'berjalan');
		if (aktifApp)
			throw new GalatApi('Aplikasi ini masih memiliki pengujian yang berjalan atau mengantre.', 409, 'SCAN_AKTIF', undefined, { scan_id: aktifApp.id });
		if (workerMockMati())
			throw new GalatApi('Tidak ada worker pengujian yang aktif. Nyalakan worker lalu coba lagi.', 409, 'WORKER_TIDAK_AKTIF', undefined, { worker_aktif: 0 });

		const hasil: Record<string, HasilMetode> = {};
		for (const { metode } of semuaMetode) {
			const p = penerapanMetode(app, metode);
			hasil[metode.id] = p.jalan
				? { metode_id: metode.id, status: 'antre', bukti: [] }
				: { metode_id: metode.id, status: p.status, ringkasan: p.alasan, bukti: [] };
		}
		const scan: Scan = {
			id: idBaru('scan'),
			aplikasi_id: aplikasiId,
			profil: app.izin_intrusif.status === 'disetujui' ? app.profil_pengujian : 'aman',
			mode,
			status: 'berjalan',
			dimulai_pada: sekarang(),
			hasil,
			log: []
		};
		state.scan.unshift(scan);
		catat(
			scan,
			'info',
			mode === 'eksploratif'
				? `Pengujian eksploratif dimulai; fase penemuan terhadap ${app.url_dasar}.`
				: `Pengujian dimulai terhadap ${app.url_dasar} (profil ${scan.profil}).`
		);
		const nAkun = opsi?.accounts?.daftar?.filter((a) => a.username && a.password).length ?? 0;
		if (mode === 'eksploratif' && nAkun) catat(scan, 'info', `${nAkun} akun uji disertakan untuk penemuan terautentikasi.`);
		simpan();
		if (mode === 'eksploratif' && !opsi?.pakai_discovery) {
			// Fase penemuan simulasi: peristiwa terstruktur untuk visualisasi, lalu semai pengujian.
			const semai = scan.hasil;
			scan.hasil = { _discovery: { metode_id: '_discovery', status: 'berjalan', bukti: [] } };
			const urutan = urutanPenemuan(app.url_dasar, nAkun >= 1);
			const lanjut = () => {
				if (scan.status !== 'berjalan') return;
				const l = urutan.shift();
				if (!l) {
					scan.hasil = { ...semai, _discovery: { metode_id: '_discovery', status: 'lulus', ringkasan: 'Penemuan selesai.', bukti: [] } };
					for (const h of Object.values(scan.hasil)) siarkan(scan.id, { tipe: 'metode', hasil: h });
					simpan();
					setTimeout(() => jalankan(scan.id), 600);
					return;
				}
				berjalan.set(scan.id, setTimeout(() => {
					catat(scan, l.level ?? 'info', l.pesan, l.data);
					lanjut();
				}, l.jeda));
			};
			lanjut();
		} else setTimeout(() => jalankan(scan.id), 300);
		return salin(scan);
	},

	async batalkanScan(id) {
		await jeda();
		const scan = cariScan(id);
		clearTimeout(berjalan.get(id));
		berjalan.delete(id);
		scan.status = 'dibatalkan';
		scan.selesai_pada = sekarang();
		for (const h of Object.values(scan.hasil))
			if (h.status === 'antre' || h.status === 'berjalan') {
				h.status = 'tidak_dapat_diverifikasi';
				h.ringkasan = 'Pengujian dibatalkan sebelum metode ini dijalankan.';
			}
		catat(scan, 'peringatan', 'Pengujian dibatalkan oleh pengguna.');
		siarkan(id, { tipe: 'status', status: 'dibatalkan', selesai_pada: scan.selesai_pada });
		simpan();
		return salin(scan);
	},

	pantauScan(id, cb) {
		if (!pelanggan.has(id)) pelanggan.set(id, new Set());
		pelanggan.get(id)!.add(cb);
		return () => pelanggan.get(id)?.delete(cb);
	},

	async unggahBukti(scanId, metodeId, bukti) {
		await jeda(500);
		const scan = cariScan(scanId);
		const h = scan.hasil[metodeId];
		h.bukti.push({
			...bukti,
			waktu: sekarang(),
			diunggah_oleh: state.pengguna.find((u) => u.id === sesiId)?.nama
		});
		h.menunggu_tinjauan = true;
		simpan();
		return salin(scan);
	},

	async tinjauMetode(scanId, metodeId, putusan, catatan) {
		await jeda();
		const scan = cariScan(scanId);
		const h = scan.hasil[metodeId];
		h.status = putusan;
		h.menunggu_tinjauan = false;
		h.tinjauan = {
			asesor: state.pengguna.find((u) => u.id === sesiId)?.nama ?? 'Asesor',
			putusan,
			catatan,
			waktu: sekarang()
		};
		h.ringkasan = catatan || `Diputuskan ${LABEL_STATUS[putusan].toLowerCase()} oleh asesor.`;
		simpan();
		return salin(scan);
	},

	async antrianTinjauan() {
		await jeda();
		return state.scan
			.filter((s) => s.status === 'selesai')
			.flatMap((s) => {
				const app = state.aplikasi.find((a) => a.id === s.aplikasi_id);
				return Object.values(s.hasil)
					.filter((h) => h.menunggu_tinjauan && indeksMetode.has(h.metode_id))
					.map((h) => ({
						scan_id: s.id,
						aplikasi_id: s.aplikasi_id,
						aplikasi_nama: app?.nama ?? s.aplikasi_id,
						metode_id: h.metode_id,
						ada_bukti: h.bukti.some((b) => b.jenis !== 'request_response')
					}));
			});
	},

	async analisisAi(scanId) {
		await jeda(1800);
		const scan = cariScan(scanId);
		scan.ai = analisisTiruan(scan.hasil, state.pengaturanAi.model);
		simpan();
		return salin(scan);
	},

	async listPengguna(filter = {}) {
		await jeda();
		const q = filter.search?.toLowerCase() ?? '';
		return salin(
			state.pengguna
				.map((u) => ({ ...u, status: statusAkun(u) }))
				.filter((u) => !filter.status || u.status === filter.status)
				.filter((u) => !q || [u.nama, u.email, u.satuan, u.nrp ?? ''].some((s) => s.toLowerCase().includes(q)))
		);
	},

	async verifikasiPengguna(id, peran) {
		await jeda();
		const u = cariPengguna(id);
		if (u.terverifikasi !== false) throw new Error('Akun ini sudah diverifikasi');
		Object.assign(u, { terverifikasi: true, peran, aktif: true });
		simpan();
		return salin({ ...u, status: statusAkun(u) });
	},

	async tolakPendaftaran(id) {
		await jeda();
		const u = cariPengguna(id);
		if (u.terverifikasi !== false)
			throw new Error('Akun yang sudah diverifikasi tidak bisa ditolak; nonaktifkan saja');
		state.pengguna = state.pengguna.filter((x) => x.id !== id);
		simpan();
	},

	async listSatuanAdmin({
		search = '',
		status = '',
		jenis = '',
		provinsi = '',
		induk,
		page = 1,
		limit = 50
	}) {
		await jeda();
		const q = search.trim().toLowerCase();
		const urutJenis = (j: string) => JENIS_SATUAN.findIndex((x) => x.kode === j);
		const cocok = satuanMock
			.filter((s) => s.nama.toLowerCase().includes(q))
			.filter((s) => (status === 'aktif' ? s.aktif : status === 'nonaktif' ? !s.aktif : true))
			.filter((s) => !jenis || s.jenis === jenis)
			.filter((s) => !provinsi || s.provinsi_kode === provinsi)
			.filter((s) => !induk || (induk === 'akar' ? !s.induk_id : s.induk_id === induk))
			.sort((a, b) => urutJenis(a.jenis) - urutJenis(b.jenis) || a.nama.localeCompare(b.nama));
		return {
			items: cocok.slice((page - 1) * limit, page * limit).map(denganJumlah),
			total: cocok.length,
			totalPages: Math.max(1, Math.ceil(cocok.length / limit)),
			limit
		};
	},

	async getSatuanAdmin(id) {
		await jeda();
		const s = satuanMock.find((x) => x.id === id);
		if (!s) throw new Error('Satuan tidak ditemukan');
		return denganJumlah(s);
	},

	async tambahSatuan(input) {
		await jeda();
		const data = rapikanSatuan(input);
		const s: SatuanMock = {
			id: idBaru('s'),
			nama: input.nama,
			jenis: data.jenis ?? 'SATUAN',
			induk_id: data.induk_id ?? null,
			aktif: data.aktif ?? true,
			alamat: data.alamat ?? null,
			kota: data.kota ?? null,
			provinsi_kode: data.provinsi_kode ?? null,
			latitude: data.latitude ?? null,
			longitude: data.longitude ?? null,
			dibuat_pada: sekarang()
		};
		cekNamaSatuan(s.nama);
		cekKoordinat(s);
		cekIndukSatuan(s.induk_id);
		satuanMock.push(s);
		return denganJumlah(s);
	},

	async ubahSatuan(id, input) {
		await jeda();
		const s = satuanMock.find((x) => x.id === id);
		if (!s) throw new Error('Satuan tidak ditemukan');
		const data = rapikanSatuan(input);
		if (data.nama !== undefined) cekNamaSatuan(data.nama, id);
		if (data.induk_id !== undefined) cekIndukSatuan(data.induk_id, id);
		cekKoordinat({
			latitude: data.latitude !== undefined ? data.latitude : s.latitude,
			longitude: data.longitude !== undefined ? data.longitude : s.longitude
		});
		if (data.nama !== undefined && data.nama !== s.nama) {
			// Akun & aplikasi yang memakai satuan ini ikut menampilkan nama baru (seperti relasi di backend).
			for (const u of state.pengguna) if (u.satuan === s.nama) u.satuan = data.nama;
			for (const a of state.aplikasi) if (a.satuan === s.nama) a.satuan = data.nama;
			simpan();
		}
		Object.assign(s, data);
		return denganJumlah(s);
	},

	async ubahStatusPengguna(id, aktif) {
		await jeda();
		if (id === sesiId) throw new Error('Anda tidak dapat mengubah akun Anda sendiri');
		const u = cariPengguna(id);
		if (u.terverifikasi === false) throw new Error('Verifikasi akun terlebih dahulu');
		u.aktif = aktif;
		simpan();
		return salin({ ...u, status: statusAkun(u) });
	},

	async getPengaturanAi() {
		await jeda();
		return salin(state.pengaturanAi);
	},

	async simpanPengaturanAi(p) {
		await jeda();
		const { api_key, ...sisa } = p;
		state.pengaturanAi = { ...sisa, api_key_terisi: p.api_key_terisi || !!api_key };
		simpan();
		return salin(state.pengaturanAi);
	}
};

/** ID pengguna yang sedang masuk; diset oleh store auth agar mock tahu "siapa" yang bertindak. */
let sesiId: string | null = null;
export function setSesiMock(id: string | null) {
	sesiId = id;
}
