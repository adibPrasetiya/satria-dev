// Kontrak data peta Indeks Ketahanan Keamanan Siber (GET /dashboard/peta; data contoh mengikuti bentuk sama).
import type { JenisSatuan } from '#lib/data/satuan.js';

export type Tingkat = 'kritis' | 'tinggi' | 'sedang' | 'rendah';

export interface TemuanKerentanan {
	kode: string;
	nama: string;
	tingkat: Tingkat;
	/** Jumlah sistem informasi terdampak. */
	aplikasi: number;
}

/** Satu satuan berlokasi yang punya sistem informasi teruji. */
export interface TitikSebaran {
	id: string;
	nama: string;
	jenis: JenisSatuan;
	/** Kotama induk (untuk label); null bila satuan tidak berada di bawah Kotama. */
	kotama: string | null;
	lat: number;
	lng: number;
	provinsi_kode: string | null;
	/** Indeks ketahanan 0 (rawan) .. 100 (tangguh). */
	kekuatan: number;
	jumlah_aplikasi: number;
	kerentanan: TemuanKerentanan[];
}

export interface Kotama {
	id: string;
	/** Nama pendek untuk label, mis. "Kodam III". */
	nama: string;
	/** Nama kehormatan, mis. "Siliwangi" (boleh kosong). */
	sebutan: string;
	lat: number;
	lng: number;
	provinsi_kode: string | null;
}

export interface DataPeta {
	titik: TitikSebaran[];
	kotama: Kotama[];
	ringkasan: {
		aplikasi_terpetakan: number;
		/** Aplikasi teruji yang satuannya (dan induk-induknya) belum punya lokasi. */
		aplikasi_belum_terpetakan: number;
		aplikasi_belum_diuji: number;
	};
	diperbarui: string;
}
