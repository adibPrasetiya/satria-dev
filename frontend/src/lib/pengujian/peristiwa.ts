// Peristiwa uji terstruktur (fase pengujian) yang menumpang pada log scan (`LogScan.data`).
// Kontrak sama dengan worker `satya_worker/peristiwa_uji.py` (v=1, jenis "uji").

export type SkenarioUji =
	| 'payload_server'
	| 'kanal_https'
	| 'redirect_http'
	| 'kebijakan_sandi'
	| 'lockout'
	| 'enumerasi_reset'
	| 'akses_terproteksi'
	| 'field_sandi'
	| 'echo_sandi'
	| 'validasi_input'
	| 'versi_runtime'
	| 'header_keamanan'
	| 'pemindaian_aktif'
	| 'generik';

/** Metadata satu request yang dikirim check (tanpa nilai body/respons). */
export interface RequestUji {
	no: number;
	metode_http: string;
	url: string;
	skema: string;
	host: string;
	lapisan: 'frontend' | 'api' | 'aset';
	field: string[];
	status: number | null;
	alasan?: string;
	lokasi?: string;
	content_type?: string;
	galat?: string;
	durasi_ms: number;
}

export type DataUji = { v: 1; jenis: 'uji'; metode_id: string } & (
	| { fase: 'mulai'; check_id: string; fungsi: string; judul: string; titik_uji: string; skenario: SkenarioUji }
	| { fase: 'langkah'; langkah: string; label: string; detail: Record<string, unknown> }
	| ({ fase: 'request' } & RequestUji)
	| { fase: 'hasil'; status: string; ringkasan: string }
);
