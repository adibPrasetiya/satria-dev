// Peristiwa penemuan terstruktur yang menumpang pada log scan (`LogScan.data`).
// Kontrak sama dengan worker `satya_worker/peristiwa.py` (v=1). Field berlapis bersifat opsional
// agar log lama (sebelum klasifikasi lapisan) tetap terbaca.

export type KodeTahap =
	| 'situs'
	| 'recon'
	| 'crawl'
	| 'browser'
	| 'login'
	| 'intersep'
	| 'zap'
	| 'katana'
	| 'bundle'
	| 'inventaris'
	| 'ai'
	| 'selesai';

/** Lapisan sebuah URL temuan: halaman/rute frontend, endpoint backend, atau berkas statis. */
export type Lapisan = 'frontend' | 'api' | 'aset';

export interface FieldRequest {
	nama: string;
	lokasi: string;
	tipe?: string;
	wajib?: boolean;
}

export interface EndpointTemuan {
	/** "METODE /path/template" — sama dengan langkah alur & kandidat. */
	id: string;
	metode_http: string;
	path_template: string;
	url: string;
	origin: string;
	sumber: string[];
	butuh_autentikasi: boolean;
	request_fields: FieldRequest[];
	response_fields: string[];
	content_type: string | null;
	status_terlihat: number[];
	titik_uji: string | null;
	lapisan?: Lapisan;
}

/** URL hasil crawl katana/ZAP yang sudah diklasifikasi worker. */
export interface ItemCrawl {
	url: string;
	metode_http?: string;
	lapisan: Lapisan;
	status?: number;
}

export interface AlertUrl {
	url: string;
	nama: string;
	risk: string;
}

export type RingkasLapisan = Record<Lapisan, number>;

/**
 * Keterangan worker diblokir / tak bisa menjangkau target (worker `keterjangkauan.peristiwa_terblokir`).
 * `fatal` = task dihentikan; selain itu peringatan (hasil mungkin tak lengkap). `awal` = terdeteksi saat
 * preflight sebelum task berjalan.
 */
export interface Terblokir {
	fase: 'recon' | 'pengujian';
	lapisan: 'dns' | 'tcp' | 'http';
	alasan: string;
	saran: string;
	fatal: boolean;
	awal?: boolean;
	host?: string;
	status?: number;
	ip_worker?: string;
}

export type DataPenemuan = { v: 1 } & (
	| { jenis: 'tahap'; tahap: KodeTahap; url?: string; jalur?: string[]; login?: boolean; akun?: string; jumlah?: number; terautentikasi?: boolean }
	| { jenis: 'docs'; url: string; judul: string; versi: string; jumlah_endpoint: number; base_api: string }
	| { jenis: 'halaman'; items: { url: string; status: number; judul: string; sumber?: string }[] }
	| { jenis: 'titik'; titik: string; url: string; metode_http: string; keyakinan: string }
	| { jenis: 'sesi'; berhasil: boolean; akun: string }
	| { jenis: 'endpoint'; items: EndpointTemuan[] }
	| { jenis: 'alur'; items: { nama: string; sumber: string; langkah: string[] }[] }
	| { jenis: 'kandidat'; ringkas: Record<string, number>; per_endpoint: Record<string, string[]> }
	| { jenis: 'zap'; jumlah_url: number; temuan: { nama: string; n: number }[]; ringkas?: RingkasLapisan; items?: ItemCrawl[]; alert_url?: AlertUrl[] }
	| { jenis: 'katana'; jumlah: number; ringkas?: RingkasLapisan; items?: ItemCrawl[] }
	| ({ jenis: 'terblokir' } & Terblokir)
);
