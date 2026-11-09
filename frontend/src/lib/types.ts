import type { DataPenemuan } from '#lib/penemuan/peristiwa.js';
import type { DataUji } from '#lib/pengujian/peristiwa.js';
import type { JenisSatuan } from '#lib/data/satuan.js';

// Tipe data bersama frontend <-> backend Express.
// Bentuk katalog mengikuti controls/bssn_web.yaml.

export type Severity = 'kritis' | 'tinggi' | 'sedang' | 'rendah' | 'info';
export type Verifiabilitas = 'otomatis' | 'sebagian' | 'manual';
export type Jenis = 'otomatis' | 'semi_otomatis' | 'manual';
export type Engine = 'custom' | 'zap' | 'nuclei' | 'sslyze' | 'playwright' | 'manual';
export type Profil = 'aman' | 'intrusif';
export type Agregasi = 'semua_lulus' | 'minimal_satu';
export type JenisBukti = 'request_response' | 'screenshot' | 'dokumen';

/** Status akhir metode/kontrol sesuai katalog. */
export type Status = 'lulus' | 'gagal' | 'tidak_berlaku' | 'tidak_dapat_diverifikasi';
/** Status metode selama scan berjalan. */
export type StatusMetode = Status | 'antre' | 'berjalan';

export interface Metode {
	id: string;
	nama: string;
	titik_uji: string;
	check_id: string;
	jenis: Jenis;
	engine: Engine;
	profil: Profil;
	butuh_autentikasi: boolean;
	bukti: JenisBukti[];
	kriteria_lulus: string;
	efek_samping?: string;
	parameter?: Record<string, unknown>;
	severity: Severity;
	/** false = dinonaktifkan admin: tidak dipakai di pengujian baru (dari backend; katalog statis selalu aktif). */
	aktif?: boolean;
}

/** Data metode yang diisi admin (kode dibuat backend). */
export type MetodeBaru = Omit<Metode, 'id' | 'parameter' | 'aktif' | 'efek_samping'> & {
	efek_samping: string;
	/** null = hapus semua parameter. */
	parameter?: Record<string, unknown> | null;
};

export interface Kontrol {
	id: string;
	nomor_referensi: string;
	uraian: string;
	verifiabilitas: Verifiabilitas;
	severity_default: Severity;
	agregasi: Agregasi;
	referensi_pendukung?: string[];
	parameter?: Record<string, unknown>;
	aktif?: boolean;
	metode_pengujian: Metode[];
}

/** Data kontrol yang diisi admin; kode dibentuk dari fungsi + nomor referensi dan tidak bisa diubah. */
export type KontrolBaru = Pick<Kontrol, 'nomor_referensi' | 'uraian' | 'verifiabilitas' | 'severity_default' | 'agregasi'> & {
	referensi_pendukung: string[];
	/** null = hapus semua parameter. */
	parameter?: Record<string, unknown> | null;
};

export interface Fungsi {
	id: string;
	nomor: number;
	nama: string;
	kontrol: Kontrol[];
}

/**
 * Ketersediaan worker per pemeriksa (check_id): jumlah worker yang mendukungnya dan berapa yang sedang online.
 * Worker mengumumkan engine & daftar check_id yang didukung lewat heartbeat (registri backend menyusul).
 */
export type KetersediaanWorker = Record<string, { siap: number; total: number }>;

export interface TitikUji {
	id: string;
	nama: string;
}

export interface Katalog {
	schema_version: number;
	sumber: { peraturan: string; bagian: string; catatan?: string[] };
	titik_uji: TitikUji[];
	fungsi_keamanan: Fungsi[];
}

// ---------------------------------------------------------------------------
// Pengguna

export type Peran = 'pemilik' | 'asesor' | 'admin';

/** Satuan/instansi dari daftar baku backend (GET /units). */
export interface Satuan {
	id: string;
	nama: string;
	/** Kode jenis satuan (lihat `JENIS_SATUAN` di #lib/data/satuan). */
	jenis?: JenisSatuan;
	/** Nama satuan-satuan induknya dari puncak, mis. "Mabes TNI › Kodam Jaya"; kosong = satuan teratas. */
	jalur?: string;
}

/** Data satuan yang bisa diisi admin (hierarki + lokasi untuk peta sebaran di dasbor). */
export interface SatuanInput {
	nama: string;
	jenis: JenisSatuan;
	/** null = satuan teratas (tanpa induk). */
	induk_id: string | null;
	aktif: boolean;
	alamat: string | null;
	kota: string | null;
	/** Kode provinsi 2 digit (Kemendagri/BPS). */
	provinsi_kode: string | null;
	latitude: number | null;
	longitude: number | null;
}

/** Satuan di halaman admin: hierarki, lokasi, status & jumlah akun/aplikasi/sub-satuan yang merujuknya. */
export interface SatuanAdmin extends Satuan, SatuanInput {
	jenis: JenisSatuan;
	jalur: string;
	/** Leluhur dari puncak ke induk langsung (untuk breadcrumb). */
	leluhur: { id: string; nama: string }[];
	provinsi: string | null;
	/** Nonaktif = hilang dari pilihan pendaftaran; akun yang sudah memakainya tetap sah. */
	aktif: boolean;
	jumlah_pengguna: number;
	jumlah_aplikasi: number;
	jumlah_sub: number;
	dibuat_pada: string;
}

/** Permohonan akun baru; aktif setelah disetujui admin. */
/** Status kepegawaian pendaftar: militer (NRP) atau PNS (NIP 18 digit). */
export type StatusKepegawaian = 'TNI' | 'PNS';

export interface PendaftaranAkun {
	nama: string;
	status_kepegawaian: StatusKepegawaian;
	/** Pangkat (TNI) atau golongan (PNS). */
	pangkat: string;
	/** NRP (TNI) / NIP (PNS). */
	nrp: string;
	/** Id dari daftar satuan (lihat `Satuan`). */
	satuan_id: string;
	email: string;
	password: string;
}

/** pending = menunggu verifikasi admin; verified = terverifikasi & aktif; inactive = dinonaktifkan. */
export type StatusAkun = 'pending' | 'verified' | 'inactive';

export interface Pengguna {
	id: string;
	nama: string;
	/** Null untuk akun lama (pangkat dulu tergabung di `nama`). */
	status_kepegawaian?: StatusKepegawaian | null;
	pangkat?: string | null;
	nrp?: string;
	email: string;
	peran: Peran;
	/** Nama satuan (untuk ditampilkan). */
	satuan: string;
	satuan_id?: string;
	aktif: boolean;
	/** Akun pendaftaran mandiri baru bisa dipakai setelah diverifikasi admin. */
	terverifikasi: boolean;
	status?: StatusAkun;
	dibuat_pada?: string;
	masuk_terakhir?: string | null;
}

// ---------------------------------------------------------------------------
// Aplikasi yang diregistrasikan

export type Lingkungan = 'produksi' | 'staging' | 'pengembangan';
export type KlasifikasiData = 'biasa' | 'terbatas' | 'rahasia';
export type MetodeVerifikasi = 'dns' | 'file';
export type StatusVerifikasi = 'belum' | 'terverifikasi' | 'gagal';
export type StatusIzin = 'tidak_diminta' | 'menunggu' | 'disetujui' | 'ditolak';
export type KunciAkunUji = 'akun_uji_1' | 'akun_uji_2' | 'admin_uji';

export interface PemetaanTitikUji {
	tersedia: boolean;
	url: string;
	metode_http: string;
	catatan?: string;
}

export interface AkunUji {
	kunci: KunciAkunUji;
	username: string;
	/** Hanya dikirim saat menyimpan; backend menyimpan terenkripsi dan tidak pernah mengembalikannya. */
	password?: string;
	terisi: boolean;
}

export interface IzinIntrusif {
	status: StatusIzin;
	dokumen_nama?: string;
	jendela_mulai?: string;
	jendela_selesai?: string;
	diajukan_pada?: string;
	diputuskan_oleh?: string;
	catatan_asesor?: string;
}

export interface Aplikasi {
	id: string;
	nama: string;
	deskripsi: string;
	satuan: string;
	satuan_id?: string;
	pic_nama: string;
	pic_kontak: string;
	url_dasar: string;
	lingkungan: Lingkungan;
	klasifikasi_data: KlasifikasiData;
	teknologi: { frontend: string; backend: string; database: string; server: string };
	// --- Persiapan pengujian (masih mock; akan dipindah ke fitur pengujian, terpisah dari data aset) ---
	verifikasi: {
		metode: MetodeVerifikasi;
		token: string;
		status: StatusVerifikasi;
		diverifikasi_pada?: string;
	};
	titik_uji: Record<string, PemetaanTitikUji>;
	akun_uji: AkunUji[];
	profil_pengujian: Profil;
	izin_intrusif: IzinIntrusif;
	pemilik_id: string;
	dibuat_pada: string;
	diubah_pada?: string;
}

/** Data dasar aset aplikasi yang diisi saat registrasi (tanpa persiapan pengujian). */
export type AsetBaru = Pick<
	Aplikasi,
	'nama' | 'deskripsi' | 'pic_nama' | 'pic_kontak' | 'url_dasar' | 'lingkungan' | 'klasifikasi_data' | 'teknologi'
> & {
	/** Hanya admin yang boleh memilih; pemilik selalu memakai satuannya sendiri. */
	satuan_id?: string;
};

/** Jumlah temuan (metode uji GAGAL) per severity; info tidak dihitung. */
export interface TemuanSeverity {
	kritis: number;
	tinggi: number;
	sedang: number;
	rendah: number;
}

/** Ringkasan pengujian terakhir sebuah aplikasi (dihitung backend saat scan selesai). */
export interface RingkasanPengujian {
	/** Waktu mulai scan terakhir (apa pun statusnya). */
	scan_terakhir_pada: string | null;
	berjalan: boolean;
	/** Scan SELESAI terakhir — sumber putusan, skor, & temuan. */
	scan_selesai_id: string | null;
	selesai_pada: string | null;
	putusan: Putusan | null;
	skor: number | null;
	temuan: TemuanSeverity | null;
}

export type BarisAplikasi = Aplikasi & { pengujian: RingkasanPengujian };

export type UrutAplikasi = 'nama' | 'satuan' | 'lingkungan' | 'klasifikasi' | 'skor' | 'temuan' | 'uji' | 'dibuat';
export type FilterPutusan = Putusan | 'belum';

export interface FilterAplikasi {
	page?: number;
	limit?: 10 | 25 | 50 | 100;
	search?: string;
	lingkungan?: Lingkungan | '';
	klasifikasi?: KlasifikasiData | '';
	satuan_id?: string;
	putusan?: FilterPutusan | '';
	sort?: UrutAplikasi;
	order?: 'asc' | 'desc';
	/** Sertakan jumlah per putusan & opsi satuan. */
	ringkasan?: boolean;
}

export interface HalamanAplikasi {
	items: BarisAplikasi[];
	page: number;
	limit: number;
	total: number;
	totalPages: number;
	/** Jumlah per putusan dengan filter lain tetap berlaku (hanya bila `ringkasan`). */
	ringkasan?: Record<'semua' | FilterPutusan, number>;
	opsi_satuan?: { id: string; nama: string; jumlah: number }[];
}

// ---------------------------------------------------------------------------
// Scan & hasil

export interface Bukti {
	jenis: JenisBukti;
	judul: string;
	isi?: string;
	nama_file?: string;
	diunggah_oleh?: string;
	waktu?: string;
}

export interface Tinjauan {
	asesor: string;
	putusan: Status;
	catatan: string;
	waktu: string;
}

export interface HasilMetode {
	metode_id: string;
	status: StatusMetode;
	ringkasan?: string;
	detail?: string;
	bukti: Bukti[];
	/** true bila metode menunggu bukti/putusan asesor. */
	menunggu_tinjauan?: boolean;
	tinjauan?: Tinjauan;
	durasi_ms?: number;
}

export type StatusScan = 'antre' | 'berjalan' | 'selesai' | 'dibatalkan';

export interface LogScan {
	waktu: string;
	level: 'info' | 'peringatan' | 'galat';
	pesan: string;
	/** Peristiwa terstruktur (fase penemuan / pengujian) untuk visualisasi graf. */
	data?: DataPenemuan | DataUji;
}

export interface AnalisisAi {
	ringkasan_eksekutif: string;
	rekomendasi: { metode_id: string; judul: string; penjelasan: string; langkah: string[] }[];
	model: string;
	dibuat_pada: string;
	disamarkan: boolean;
}

/** Mode pengujian: terarah (data persiapan diisi pengguna) | eksploratif (hanya URL → penemuan otomatis). */
export type ModePengujian = 'terarah' | 'eksploratif';
/** Grey box: dengan akun uji terbatas. Black box: tanpa akun & informasi internal. */
export type PendekatanUji = 'greybox' | 'blackbox';

export interface Scan {
	id: string;
	aplikasi_id: string;
	profil: Profil;
	mode?: ModePengujian;
	pendekatan?: PendekatanUji;
	status: StatusScan;
	dimulai_pada: string;
	selesai_pada?: string;
	hasil: Record<string, HasilMetode>;
	log: LogScan[];
	ai?: AnalisisAi;
	/** Posisi antrean & worker yang mengerjakan (hanya selama berjalan). */
	antrean?: AntreanScan;
}

// ---------------------------------------------------------------------------
// Koordinasi worker (registry + antrean) — GET /workers/status

export interface AntreanScan {
	/** 0 = sedang dikerjakan worker; 1 = berikutnya; dst. */
	posisi: number;
	di_depan: number;
	scan_di_depan: number;
	sedang_dikerjakan: boolean;
	perkiraan_tunggu_detik: number;
	worker_aktif: number;
	worker?: { id: string; tahap: string | null; terakhir_terlihat_detik: number } | null;
}

export interface InfoWorker {
	id: string;
	status: 'siaga' | 'sibuk' | 'berhenti' | 'terputus';
	engines: string[];
	versi?: string | null;
	terakhir_terlihat_detik: number;
	sedang: { scan_id: string | null; aplikasi: string; tahap: string | null } | null;
}

export interface StatusWorker {
	aktif: number;
	sibuk: number;
	siaga: number;
	engines: string[];
	workers: InfoWorker[];
	antrean: { task_antre: number; task_berjalan: number; scan: ({ scan_id: string; aplikasi: string } & AntreanScan)[] };
	/** Perkiraan bila pengujian BARU dimulai sekarang. */
	scan_baru: AntreanScan;
}

export type Putusan = 'laik' | 'laik_bersyarat' | 'tidak_laik';

/** Event progres scan (SSE /api/scans/:id/events). */
export type EventScan =
	| { tipe: 'metode'; hasil: HasilMetode }
	| { tipe: 'log'; log: LogScan }
	| { tipe: 'status'; status: StatusScan; selesai_pada?: string }
	| { tipe: 'worker'; peristiwa: 'diklaim' | 'terputus'; worker_id: string | null; metode_id: string };

// ---------------------------------------------------------------------------
// Antrian asesor & pengaturan

export interface ItemTinjauan {
	scan_id: string;
	aplikasi_id: string;
	aplikasi_nama: string;
	metode_id: string;
	ada_bukti: boolean;
}

export type ProviderAi = 'anthropic' | 'openai_compatible' | 'ollama' | 'vllm';

export interface PengaturanAi {
	provider: ProviderAi;
	endpoint: string;
	model: string;
	api_key_terisi: boolean;
	api_key?: string;
	redaksi: boolean;
	bahasa: 'id' | 'en';
}

// ---------------------------------------------------------------------------
// Persiapan pengujian (per aset, per fungsi keamanan). Isinya informasi yang dibutuhkan worker.

/** Status kesiapan satu metode berdasarkan isian persiapan. */
export type StatusKesiapan = 'siap' | 'perlu_data' | 'dilewati' | 'asesor';

export interface KesiapanMetode {
	status: StatusKesiapan;
	/** Penjelasan singkat, mis. isian yang masih kurang atau alasan dilewati. */
	alasan: string;
}

/** Akun khusus uji. Kata sandi hanya dikirim saat menyimpan; respons cukup `terisi`. */
export interface AkunPersiapan {
	username: string;
	password?: string;
	terisi: boolean;
	/** Secret TOTP (base32) untuk MFA; hanya dikirim saat menyimpan, tidak dikembalikan. */
	totp_secret?: string;
	/** Parameter TOTP dari URI otpauth (QR). Default 6 digit · 30 dtk · SHA1. */
	totp_digits?: number;
	totp_period?: number;
	totp_algoritma?: 'SHA1' | 'SHA256' | 'SHA512';
}

export interface FieldTambahan {
	nama: string;
	nilai: string;
}

/** null = belum dijawab; true/false = fitur ada/tidak ada di aplikasi. */
export type Ketersediaan = boolean | null;

/**
 * Persiapan fungsi Autentikasi (AUTH). Setiap `jalur_*` berisi URL lengkap (http/https); `jalur_aksi`
 * (endpoint backend) boleh berbeda domain/subdomain dari URL dasar aset.
 */
export interface PersiapanAuth {
	login: {
		jalur_halaman: string;
		jalur_aksi: string;
		metode_http: 'POST' | 'GET';
		field_username: string;
		field_password: string;
		penanda_berhasil: string;
		penanda_gagal: string;
		jalur_terbatas: string;
	};
	registrasi: {
		tersedia: Ketersediaan;
		jalur_halaman: string;
		jalur_aksi: string;
		field_identitas: string;
		field_password: string;
		field_konfirmasi: string;
		field_lain: FieldTambahan[];
		catatan_pembersihan: string;
	};
	reset: {
		tersedia: Ketersediaan;
		jalur_halaman: string;
		/** Endpoint API penerima permintaan reset (mis. /auth/forgot-password). */
		jalur_aksi: string;
		field_identitas: string;
		email_akun_uji: string;
	};
	ubah_password: {
		tersedia: Ketersediaan;
		jalur_halaman: string;
		/** Endpoint API penerima ubah kata sandi (mis. /auth/change-password). */
		jalur_aksi: string;
		field_lama: string;
		field_baru: string;
		field_konfirmasi: string;
	};
	akun_uji: { utama: AkunPersiapan; penguncian: AkunPersiapan };
	hambatan: { captcha: boolean; mfa: boolean; waf: boolean; dikecualikan_untuk_worker: boolean };
	intrusif: { izinkan_penguncian: boolean; jendela_mulai: string; jendela_selesai: string };
	/** Nama berkas yang diunggah untuk ditinjau asesor. */
	dokumen: { kebijakan_masa_berlaku: string; bukti_hashing: string };
	diperbarui_pada?: string;
}
