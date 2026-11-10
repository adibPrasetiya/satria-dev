import type {
	StatusWorker,
	Aplikasi,
	AsetBaru,
	FilterAplikasi,
	HalamanAplikasi,
	Bukti,
	EventScan,
	IzinIntrusif,
	ItemTinjauan,
	Katalog,
	KetersediaanWorker,
	Kontrol,
	KontrolBaru,
	Metode,
	MetodeBaru,
	ModePengujian,
	PendekatanUji,
	Pengguna,
	PengaturanAi,
	PendaftaranAkun,
	Peran,
	PersiapanAuth,
	Satuan,
	SatuanAdmin,
	SatuanInput,
	Scan,
	Status,
	StatusAkun
} from '#lib/types.js';
import type { AkunTarget, TargetUji } from '#lib/persiapan/target.js';
import type { DataPeta, RincianProvinsi } from '#lib/peta/tipe.js';

/** Opsi mulai scan. Jalur otomatis (eksploratif) menyertakan akun uji + opsi yang disimpan
 *  ke scan_targets sebelum fase penemuan, sehingga discovery dapat login. */
export interface OpsiMulaiScan {
	mode?: ModePengujian;
	/** Grey box (bawaan): memakai akun uji. Black box: tanpa akun — akun tersimpan pun tidak dipakai. */
	pendekatan?: PendekatanUji;
	persetujuan?: boolean;
	accounts?: { daftar: AkunTarget[] };
	options?: Partial<TargetUji['options']>;
	/** Uji ulang: pakai hasil penemuan tersimpan (lewati fase penemuan). Tanpa `accounts` = pakai akun tersimpan. */
	pakai_discovery?: boolean;
	/** Versi dokumen Syarat & Ketentuan yang disetujui pengguna (dicatat di log pengujian). */
	persetujuan_sk?: string;
}

/** Persiapan tersimpan untuk uji ulang (GET /apps/:id/scan-target). Sandi & seed TOTP tidak pernah dikembalikan. */
export interface TargetTersimpan {
	aplikasi_id: string;
	akun: { username: string; ada_sandi: boolean; ada_totp: boolean }[];
	discovery: {
		waktu: string | null;
		scan_id: string | null;
		jumlah_halaman: number;
		jumlah_endpoint_unik: number;
		jumlah_alur: number;
		titik_ditemukan: string[];
		terautentikasi: boolean;
		openapi: { judul: string; jumlah_endpoint: number } | null;
		kandidat: Record<string, number>;
		contoh_endpoint: { metode_http: string; path: string; butuh_autentikasi: boolean }[];
	} | null;
}

/** Kontrak API yang diimplementasikan mock maupun backend Express (lihat API_CONTRACT.md). */
export interface Api {
	login(email: string, password: string): Promise<Pengguna>;
	/** Khusus demo: masuk sebagai akun contoh untuk suatu peran. */
	loginDemo(peran: Peran): Promise<Pengguna>;
	/** Respons selalu sama, baik email sudah terdaftar atau belum (cegah enumerasi akun). */
	daftar(data: PendaftaranAkun): Promise<void>;
	/** true bila NRP/NIP atau email (salah satu) belum terdaftar; dipakai stepper pendaftaran. */
	cekKetersediaan(data: { nrp: string } | { email: string }): Promise<boolean>;
	/** Cari satuan/instansi untuk pendaftaran (publik); hasil dibatasi (bawaan 20), bukan seluruh daftar. */
	cariSatuan(kata: string): Promise<Satuan[]>;
	/** Respons selalu sama, baik email terdaftar atau tidak (kontrol BSSN 1.5). */
	lupaSandi(email: string): Promise<void>;
	/** Set kata sandi baru dari tautan email (token sekali pakai). */
	resetSandi(token: string, password: string): Promise<void>;
	/** Buka tautan verifikasi email pendaftaran (token sekali pakai); akun langsung bisa dipakai masuk. */
	verifikasiEmail(token: string): Promise<void>;
	/** Kirim ulang tautan verifikasi; respons selalu sama, terdaftar atau tidak (cegah enumerasi akun). */
	kirimUlangVerifikasi(email: string): Promise<void>;
	/** Cabut sesi di server (refresh token). */
	logout(): Promise<void>;
	/** Ganti kata sandi akun yang sedang masuk; sesi di perangkat lain dicabut, sesi ini tetap berjalan. */
	gantiSandi(lama: string, baru: string): Promise<void>;

	/** Katalog lengkap, termasuk butir nonaktif (`aktif: false`). */
	getKatalog(): Promise<Katalog>;
	/** Worker yang mendukung tiap check_id (siap = online). Belum ada di backend: sementara selalu dari mock. */
	getKetersediaanWorker(): Promise<KetersediaanWorker>;
	/** Persiapan pengujian fungsi Autentikasi untuk satu aset (null = belum pernah diisi). Kata sandi tidak dikembalikan. */
	getPersiapanAuth(aplikasiId: string): Promise<PersiapanAuth | null>;
	simpanPersiapanAuth(aplikasiId: string, data: PersiapanAuth): Promise<PersiapanAuth>;
	/** Kirim persiapan (yang relevan) ke scan_targets backend agar dipakai worker. PUT /apps/:id/scan-target. */
	simpanTargetUji(aplikasiId: string, data: TargetUji): Promise<{ aplikasi_id: string } & TargetUji>;
	/** Akun uji (tanpa sandi) + ringkasan penemuan terakhir untuk uji ulang. */
	getTargetUji(aplikasiId: string): Promise<TargetTersimpan>;
	/** Khusus admin. Galat 409 bila kode kontrol (fungsi + nomor) sudah ada. */
	tambahKontrol(kodeFungsi: string, data: KontrolBaru): Promise<Kontrol>;
	ubahKontrol(kode: string, data: Partial<Omit<KontrolBaru, 'nomor_referensi'>> & { aktif?: boolean }): Promise<Kontrol>;
	tambahMetode(kodeKontrol: string, data: MetodeBaru): Promise<Metode>;
	ubahMetode(kode: string, data: Partial<MetodeBaru> & { aktif?: boolean }): Promise<Metode>;

	listAplikasi(): Promise<Aplikasi[]>;
	/** Daftar aplikasi berhalaman (filter, urut, paginasi di server) beserta ringkasan pengujian terakhir. */
	cariAplikasi(filter: FilterAplikasi): Promise<HalamanAplikasi>;
	getAplikasi(id: string): Promise<Aplikasi>;
	/** Registrasi aset (data dasar saja). Galat 409 bila URL dasar sudah terdaftar. */
	buatAplikasi(data: AsetBaru): Promise<Aplikasi>;
	ubahAplikasi(id: string, data: Partial<AsetBaru>): Promise<Aplikasi>;
	verifikasiKepemilikan(id: string): Promise<Aplikasi>;
	ajukanIzinIntrusif(id: string, izin: Omit<IzinIntrusif, 'status'>): Promise<Aplikasi>;
	putuskanIzinIntrusif(id: string, disetujui: boolean, catatan: string): Promise<Aplikasi>;

	listScan(aplikasiId?: string): Promise<Scan[]>;
	/** Status worker pengujian & antrean (indikator header, penjaga tombol Mulai). */
	statusWorker(): Promise<StatusWorker>;
	/** Peta Indeks Ketahanan Keamanan Siber (agregat per satuan berlokasi); dasbor memuat ulang tiap 10 menit. */
	getPeta(): Promise<DataPeta>;
	/** Rincian satu provinsi (diambil per provinsi saat disorot; di-cache per versi data). */
	getPetaProvinsi(kode: string): Promise<RincianProvinsi>;
	/**
	 * Aliran status worker: `cb` dipanggil saat tersambung dan setiap kali status berubah (bukan berkala).
	 * `putus` dipanggil bila aliran berakhir/gagal. Mengembalikan fungsi penutup aliran.
	 */
	pantauStatusWorker(cb: (s: StatusWorker) => void, putus?: () => void): () => void;
	getScan(id: string): Promise<Scan>;
	mulaiScan(aplikasiId: string, opsi?: OpsiMulaiScan): Promise<Scan>;
	batalkanScan(id: string): Promise<Scan>;
	/** Berlangganan progres scan; mengembalikan fungsi untuk berhenti. */
	pantauScan(id: string, cb: (e: EventScan) => void): () => void;

	unggahBukti(scanId: string, metodeId: string, bukti: Bukti): Promise<Scan>;
	tinjauMetode(scanId: string, metodeId: string, putusan: Status, catatan: string): Promise<Scan>;
	antrianTinjauan(): Promise<ItemTinjauan[]>;

	analisisAi(scanId: string): Promise<Scan>;

	listPengguna(filter?: { status?: StatusAkun | ''; search?: string }): Promise<Pengguna[]>;
	/** Verifikasi manual oleh admin (cadangan bila email verifikasi tidak sampai) sekaligus tetapkan peran. */
	verifikasiPengguna(id: string, peran: Peran): Promise<Pengguna>;
	/** Tolak pendaftaran (hanya akun yang belum diverifikasi; datanya dihapus). */
	tolakPendaftaran(id: string): Promise<void>;
	ubahStatusPengguna(id: string, aktif: boolean): Promise<Pengguna>;
	/** Ubah peran akun terverifikasi; sesi pengguna itu dicabut agar ia masuk ulang dengan peran baru. */
	ubahPeranPengguna(id: string, peran: Peran): Promise<Pengguna>;

	/**
	 * Daftar satuan kerja untuk admin (termasuk nonaktif), dengan pencarian & paginasi di server.
	 * `induk`: 'akar' = satuan teratas, id = sub-satuan langsung, tidak diisi = semua tingkat (pencarian).
	 */
	listSatuanAdmin(filter: {
		search?: string;
		status?: 'aktif' | 'nonaktif' | '';
		jenis?: string;
		provinsi?: string;
		induk?: string;
		page?: number;
		limit?: number;
	}): Promise<{ items: SatuanAdmin[]; total: number; totalPages: number; limit: number }>;
	getSatuanAdmin(id: string): Promise<SatuanAdmin>;
	/** Galat 409 bila nama sudah ada; 400 bila induk membuat siklus / melampaui batas kedalaman. */
	tambahSatuan(data: Partial<SatuanInput> & { nama: string }): Promise<SatuanAdmin>;
	ubahSatuan(id: string, data: Partial<SatuanInput>): Promise<SatuanAdmin>;

	getPengaturanAi(): Promise<PengaturanAi>;
	simpanPengaturanAi(p: PengaturanAi): Promise<PengaturanAi>;
}
