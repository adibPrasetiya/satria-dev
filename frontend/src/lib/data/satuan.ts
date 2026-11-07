// Referensi satuan kerja TNI. Sama dengan backend/src/config/satuan.js — ubah keduanya bersamaan.

/** Jenis (tingkatan) satuan; urutan dari puncak hierarki ke bawah, sama dengan urutan di backend. */
export const JENIS_SATUAN = [
	{
		kode: 'MABES',
		label: 'Mabes',
		keterangan: 'Markas Besar — Mabes TNI, Mabesad, Mabesal, Mabesau'
	},
	{
		kode: 'KOTAMA',
		label: 'Kotama',
		keterangan: 'Komando Utama — Kodam, Kostrad, Kopassus, Koarmada, Koopsud, …'
	},
	{
		kode: 'BALAKPUS',
		label: 'Balakpus',
		keterangan: 'Badan Pelaksana Pusat — Bais, Pusinfolahta, Satsiber, …'
	},
	{
		kode: 'KOREM',
		label: 'Korem',
		keterangan: 'Komando Resor Militer / setingkat (Lantamal, Lanud tipe A)'
	},
	{
		kode: 'KODIM',
		label: 'Kodim',
		keterangan: 'Komando Distrik Militer / setingkat (Lanal, Lanud)'
	},
	{ kode: 'KORAMIL', label: 'Koramil', keterangan: 'Komando Rayon Militer / setingkat' },
	{
		kode: 'SATUAN',
		label: 'Satuan lain',
		keterangan: 'Batalyon, detasemen, dinas, staf, laboratorium, …'
	}
] as const;

export type JenisSatuan = (typeof JENIS_SATUAN)[number]['kode'];

export const labelJenis = (kode: string | undefined) =>
	JENIS_SATUAN.find((j) => j.kode === kode)?.label ?? 'Satuan';

/** 38 provinsi; kode wilayah Kemendagri/BPS 2 digit — kunci peta sebaran di dasbor. */
export const PROVINSI: { kode: string; nama: string }[] = [
	['11', 'Aceh'],
	['12', 'Sumatera Utara'],
	['13', 'Sumatera Barat'],
	['14', 'Riau'],
	['15', 'Jambi'],
	['16', 'Sumatera Selatan'],
	['17', 'Bengkulu'],
	['18', 'Lampung'],
	['19', 'Kepulauan Bangka Belitung'],
	['21', 'Kepulauan Riau'],
	['31', 'DKI Jakarta'],
	['32', 'Jawa Barat'],
	['33', 'Jawa Tengah'],
	['34', 'DI Yogyakarta'],
	['35', 'Jawa Timur'],
	['36', 'Banten'],
	['51', 'Bali'],
	['52', 'Nusa Tenggara Barat'],
	['53', 'Nusa Tenggara Timur'],
	['61', 'Kalimantan Barat'],
	['62', 'Kalimantan Tengah'],
	['63', 'Kalimantan Selatan'],
	['64', 'Kalimantan Timur'],
	['65', 'Kalimantan Utara'],
	['71', 'Sulawesi Utara'],
	['72', 'Sulawesi Tengah'],
	['73', 'Sulawesi Selatan'],
	['74', 'Sulawesi Tenggara'],
	['75', 'Gorontalo'],
	['76', 'Sulawesi Barat'],
	['81', 'Maluku'],
	['82', 'Maluku Utara'],
	['91', 'Papua'],
	['92', 'Papua Barat'],
	['93', 'Papua Selatan'],
	['94', 'Papua Tengah'],
	['95', 'Papua Pegunungan'],
	['96', 'Papua Barat Daya']
].map(([kode, nama]) => ({ kode, nama }));

export const namaProvinsi = (kode: string | null | undefined) =>
	PROVINSI.find((p) => p.kode === kode)?.nama ?? null;

/** Batas kotak wilayah Indonesia, sama dengan validasi backend. */
export const BATAS_KOORDINAT = { latMin: -11.5, latMax: 6.5, lngMin: 94.5, lngMax: 141.5 };
