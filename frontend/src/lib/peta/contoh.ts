// DATA CONTOH untuk peta sebaran di dasbor (mode demo) — bukan data nyata; nama satuan FIKTIF, sama
// dengan seed backend (backend/src/db/seed/satuan.js). Koordinat = perkiraan pusat kota;
// nilai kekuatan dibangkitkan acak-deterministik. Diganti data agregat backend (satuan + hasil asesmen)
// setelah endpoint sebaran tersedia.
import type { JenisSatuan } from '#lib/data/satuan.js';
import type {
	DataPeta,
	RincianProvinsi,
	SebaranTingkat,
	Kotama as KotamaDasar,
	TemuanKerentanan,
	Tingkat,
	TitikSebaran
} from '#lib/peta/tipe.js';

export type { TitikSebaran, TemuanKerentanan, Tingkat };

/** Kotama contoh: `unggulan` hanya dipakai data contoh. */
export interface Kotama extends KotamaDasar {
	provinsi_kode: string;
	unggulan?: boolean;
}

export type Rentang = '24j' | '7h' | '30h';

const KOTAMA: Kotama[] = [
	{
		id: 'im',
		nama: 'Kodam Alfa',
		sebutan: 'Rajawali',
		lat: 5.55,
		lng: 95.32,
		provinsi_kode: '11',
		unggulan: true
	},
	{
		id: 'i',
		nama: 'Kodam Bravo',
		sebutan: 'Bentala',
		lat: 3.59,
		lng: 98.67,
		provinsi_kode: '12'
	},
	{
		id: 'ii',
		nama: 'Kodam Charlie',
		sebutan: 'Cakrawala',
		lat: -2.98,
		lng: 104.75,
		provinsi_kode: '16'
	},
	{
		id: 'jaya',
		nama: 'Kodam Delta',
		sebutan: 'Nusa Indah',
		lat: -6.2,
		lng: 106.85,
		provinsi_kode: '31'
	},
	{
		id: 'iii',
		nama: 'Kodam Echo',
		sebutan: 'Kencana',
		lat: -6.91,
		lng: 107.61,
		provinsi_kode: '32',
		unggulan: true
	},
	{
		id: 'iv',
		nama: 'Kodam Foxtrot',
		sebutan: 'Bayu Seta',
		lat: -6.99,
		lng: 110.42,
		provinsi_kode: '33'
	},
	{
		id: 'v',
		nama: 'Kodam Golf',
		sebutan: 'Arga Dipa',
		lat: -7.25,
		lng: 112.75,
		provinsi_kode: '35'
	},
	{
		id: 'ix',
		nama: 'Kodam Hotel',
		sebutan: 'Lembayung',
		lat: -8.65,
		lng: 115.22,
		provinsi_kode: '51'
	},
	{
		id: 'xii',
		nama: 'Kodam India',
		sebutan: 'Candra Kirana',
		lat: -0.03,
		lng: 109.33,
		provinsi_kode: '61',
		unggulan: true
	},
	{
		id: 'vi',
		nama: 'Kodam Juliet',
		sebutan: 'Tirta Wening',
		lat: -1.24,
		lng: 116.85,
		provinsi_kode: '64'
	},
	{
		id: 'xiii',
		nama: 'Kodam Kilo',
		sebutan: 'Gema Nusa',
		lat: 1.47,
		lng: 124.84,
		provinsi_kode: '71'
	},
	{
		id: 'xiv',
		nama: 'Kodam Lima',
		sebutan: 'Wira Bhumi',
		lat: -5.14,
		lng: 119.42,
		provinsi_kode: '73',
		unggulan: true
	},
	{
		id: 'xvi',
		nama: 'Kodam Mike',
		sebutan: 'Sangkala',
		lat: -3.7,
		lng: 128.18,
		provinsi_kode: '81'
	},
	{
		id: 'xviii',
		nama: 'Kodam November',
		sebutan: 'Nara Bhakti',
		lat: -0.86,
		lng: 134.06,
		provinsi_kode: '92'
	},
	{
		id: 'xvii',
		nama: 'Kodam Oscar',
		sebutan: 'Bhumi Cendana',
		lat: -2.53,
		lng: 140.72,
		provinsi_kode: '91',
		unggulan: true
	}
];

// Kota satuan bawahan per Kotama: [nama, lat, lng, provinsi, jenis].
type Kota = [string, number, number, string, JenisSatuan];
const SATUAN: Record<string, Kota[]> = {
	im: [
		['Lhokseumawe', 5.18, 97.15, '11', 'KOREM'],
		['Meulaboh', 4.14, 96.13, '11', 'KODIM'],
		['Takengon', 4.63, 96.84, '11', 'KODIM'],
		['Langsa', 4.47, 97.97, '11', 'KODIM']
	],
	i: [
		['Pematangsiantar', 2.96, 99.06, '12', 'KOREM'],
		['Padang Sidempuan', 1.38, 99.27, '12', 'KODIM'],
		['Pekanbaru', 0.51, 101.45, '14', 'KOREM'],
		['Padang', -0.95, 100.35, '13', 'KOREM'],
		['Bukittinggi', -0.3, 100.37, '13', 'KODIM'],
		['Batam', 1.08, 104.03, '21', 'KODIM'],
		['Dumai', 1.67, 101.45, '14', 'KODIM'],
		['Sibolga', 1.74, 98.78, '12', 'KODIM']
	],
	ii: [
		['Jambi', -1.61, 103.61, '15', 'KOREM'],
		['Bengkulu', -3.8, 102.26, '17', 'KOREM'],
		['Bandar Lampung', -5.43, 105.26, '18', 'KOREM'],
		['Pangkalpinang', -2.13, 106.11, '19', 'KODIM'],
		['Lubuklinggau', -3.29, 102.86, '16', 'KODIM'],
		['Metro', -5.11, 105.31, '18', 'KODIM'],
		['Baturaja', -4.13, 104.17, '16', 'KODIM']
	],
	jaya: [
		['Tangerang', -6.18, 106.63, '36', 'KODIM'],
		['Bekasi', -6.24, 106.99, '32', 'KODIM'],
		['Depok', -6.4, 106.82, '32', 'KODIM'],
		['Serang', -6.12, 106.15, '36', 'KOREM']
	],
	iii: [
		['Bogor', -6.6, 106.8, '32', 'KOREM'],
		['Cirebon', -6.73, 108.55, '32', 'KOREM'],
		['Tasikmalaya', -7.33, 108.22, '32', 'KOREM'],
		['Sukabumi', -6.92, 106.93, '32', 'KODIM'],
		['Garut', -7.21, 107.9, '32', 'KODIM'],
		['Purwakarta', -6.55, 107.44, '32', 'KODIM']
	],
	iv: [
		['Yogyakarta', -7.8, 110.36, '34', 'KOREM'],
		['Surakarta', -7.57, 110.82, '33', 'KOREM'],
		['Purwokerto', -7.42, 109.23, '33', 'KOREM'],
		['Magelang', -7.47, 110.22, '33', 'KODIM'],
		['Pekalongan', -6.89, 109.67, '33', 'KODIM'],
		['Tegal', -6.87, 109.14, '33', 'KODIM']
	],
	v: [
		['Malang', -7.98, 112.63, '35', 'KOREM'],
		['Madiun', -7.63, 111.52, '35', 'KOREM'],
		['Kediri', -7.82, 112.01, '35', 'KODIM'],
		['Jember', -8.17, 113.7, '35', 'KODIM'],
		['Banyuwangi', -8.22, 114.37, '35', 'KODIM'],
		['Pamekasan', -7.16, 113.48, '35', 'KODIM']
	],
	ix: [
		['Mataram', -8.58, 116.12, '52', 'KOREM'],
		['Kupang', -10.18, 123.6, '53', 'KOREM'],
		['Bima', -8.46, 118.73, '52', 'KODIM'],
		['Ende', -8.84, 121.66, '53', 'KODIM'],
		['Atambua', -9.11, 124.89, '53', 'KODIM'],
		['Singaraja', -8.11, 115.09, '51', 'KODIM']
	],
	xii: [
		['Singkawang', 0.91, 108.98, '61', 'KODIM'],
		['Ketapang', -1.85, 109.98, '61', 'KODIM'],
		['Sintang', 0.07, 111.5, '61', 'KODIM'],
		['Palangka Raya', -2.21, 113.92, '62', 'KOREM'],
		['Sampit', -2.53, 112.95, '62', 'KODIM'],
		['Putussibau', 0.84, 112.93, '61', 'KODIM']
	],
	vi: [
		['Samarinda', -0.5, 117.15, '64', 'KOREM'],
		['Banjarmasin', -3.32, 114.59, '63', 'KOREM'],
		['Tarakan', 3.3, 117.63, '65', 'KOREM'],
		['Bontang', 0.13, 117.5, '64', 'KODIM'],
		['Tanjung Selor', 2.84, 117.37, '65', 'KODIM'],
		['Kotabaru', -3.24, 116.21, '63', 'KODIM']
	],
	xiii: [
		['Gorontalo', 0.54, 123.06, '75', 'KOREM'],
		['Palu', -0.9, 119.87, '72', 'KOREM'],
		['Bitung', 1.44, 125.19, '71', 'KODIM'],
		['Luwuk', -0.95, 122.79, '72', 'KODIM'],
		['Tolitoli', 1.04, 120.82, '72', 'KODIM']
	],
	xiv: [
		['Kendari', -3.97, 122.51, '74', 'KOREM'],
		['Mamuju', -2.68, 118.89, '76', 'KODIM'],
		['Parepare', -4.01, 119.62, '73', 'KOREM'],
		['Palopo', -3.0, 120.2, '73', 'KODIM'],
		['Bau-Bau', -5.47, 122.6, '74', 'KODIM'],
		['Bone', -4.54, 120.33, '73', 'KODIM']
	],
	xvi: [
		['Ternate', 0.79, 127.38, '82', 'KOREM'],
		['Tual', -5.64, 132.75, '81', 'KODIM'],
		['Masohi', -3.3, 128.96, '81', 'KODIM'],
		['Saumlaki', -7.98, 131.3, '81', 'KODIM'],
		['Tobelo', 1.73, 128.0, '82', 'KODIM']
	],
	xviii: [
		['Sorong', -0.88, 131.26, '92', 'KOREM'],
		['Fakfak', -2.93, 132.3, '92', 'KODIM'],
		['Kaimana', -3.65, 133.75, '92', 'KODIM'],
		['Teluk Bintuni', -2.1, 133.53, '92', 'KODIM']
	],
	xvii: [
		['Merauke', -8.49, 140.4, '91', 'KOREM'],
		['Timika', -4.55, 136.89, '91', 'KOREM'],
		['Wamena', -4.1, 138.95, '91', 'KODIM'],
		['Nabire', -3.37, 135.5, '91', 'KODIM'],
		['Biak', -1.18, 136.08, '91', 'KODIM'],
		['Sarmi', -1.86, 138.74, '91', 'KODIM']
	]
};

// Kecenderungan kekuatan per Kotama agar peta contoh punya pola (bukan derau acak): rendah = rawan.
const KECENDERUNGAN: Record<string, number> = {
	im: 55,
	i: 62,
	ii: 70,
	jaya: 45,
	iii: 30,
	iv: 58,
	v: 66,
	ix: 74,
	xii: 68,
	vi: 72,
	xiii: 63,
	xiv: 50,
	xvi: 70,
	xviii: 60,
	xvii: 35
};

/** PRNG kecil (mulberry32) agar data contoh sama setiap dimuat. */
function acak(benih: number) {
	return () => {
		benih = (benih + 0x6d2b79f5) | 0;
		let t = Math.imul(benih ^ (benih >>> 15), 1 | benih);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

const BENIH: Record<Rentang, number> = { '24j': 24, '7h': 7, '30h': 30 };
/** Rentang lebih panjang = rata-rata lebih stabil (simpangan acak lebih kecil). */
const SIMPANGAN: Record<Rentang, number> = { '24j': 26, '7h': 18, '30h': 12 };

// Kerentanan umum aplikasi web (selaras fungsi keamanan Per-BSSN 4/2021); bobot = peluang muncul.
const KERENTANAN: { kode: string; nama: string; tingkat: Tingkat; bobot: number }[] = [
	{ kode: 'INPV-SQLI', nama: 'Injeksi SQL', tingkat: 'kritis', bobot: 0.5 },
	{ kode: 'ATHZ-IDOR', nama: 'Kontrol akses rusak (IDOR)', tingkat: 'kritis', bobot: 0.6 },
	{ kode: 'CONF-CVE', nama: 'Komponen usang ber-CVE', tingkat: 'kritis', bobot: 0.7 },
	{ kode: 'INPV-XSS', nama: 'Cross-Site Scripting (XSS)', tingkat: 'tinggi', bobot: 0.9 },
	{ kode: 'SESS-FIX', nama: 'Manajemen sesi lemah', tingkat: 'tinggi', bobot: 0.8 },
	{ kode: 'ATHN-MFA', nama: 'Autentikasi tanpa MFA', tingkat: 'tinggi', bobot: 1 },
	{ kode: 'FILE-UPL', nama: 'Unggah berkas tanpa validasi', tingkat: 'tinggi', bobot: 0.5 },
	{ kode: 'COMM-TLS', nama: 'Konfigurasi TLS lemah', tingkat: 'sedang', bobot: 1.1 },
	{ kode: 'CONF-HDR', nama: 'Header keamanan tidak lengkap', tingkat: 'sedang', bobot: 1.4 },
	{ kode: 'ERRH-INF', nama: 'Kebocoran informasi pada galat', tingkat: 'sedang', bobot: 1 }
];

/** Satuan makin rawan → makin banyak & makin parah kerentanannya. */
function bangkitkanKerentanan(
	r: () => number,
	kekuatan: number,
	aplikasi: number
): TemuanKerentanan[] {
	const rawan = 1 - kekuatan / 100;
	return KERENTANAN.flatMap((k) => {
		const faktor =
			k.tingkat === 'kritis'
				? rawan * rawan * 1.4
				: k.tingkat === 'tinggi'
					? rawan * 1.1
					: 0.35 + rawan * 0.6;
		if (r() > Math.min(0.95, faktor * k.bobot)) return [];
		const terdampak = Math.max(1, Math.round(aplikasi * (0.2 + r() * 0.6) * (0.5 + rawan)));
		return [
			{ kode: k.kode, nama: k.nama, tingkat: k.tingkat, aplikasi: Math.min(aplikasi, terdampak) }
		];
	});
}

/** Lama satu siklus pembaruan data (dasbor memuat ulang tiap siklus). */
export const SIKLUS_MS = 10 * 60_000;

/**
 * @param siklus nomor siklus pembaruan (mis. floor(waktu / SIKLUS_MS)); tiap siklus nilai bergeser sedikit
 *   agar terasa seperti data yang diperbarui, tetapi tetap sama bila dimuat ulang pada siklus yang sama.
 */
type TitikContoh = TitikSebaran & { kerentanan: TemuanKerentanan[] };

/** Titik contoh lengkap (internal; berisi daftar kerentanan untuk menurunkan sebaran). */
function titikContoh(rentang: Rentang, siklus: number): TitikContoh[] {
	const r = acak(BENIH[rentang]);
	const g = acak(BENIH[rentang] * 7919 + siklus);
	const batasi = (n: number) => Math.round(Math.max(3, Math.min(98, n)));
	const titik: TitikContoh[] = [];
	const tambah = (t: Omit<TitikSebaran, 'kekuatan'>, dasar: number) => {
		// Nilai dasar tetap per rentang; geseran kecil per siklus pembaruan.
		const kekuatan = batasi(dasar + (g() - 0.5) * 6);
		titik.push({
			...t,
			kekuatan,
			kerentanan: bangkitkanKerentanan(g, kekuatan, t.jumlah_aplikasi)
		});
	};
	for (const k of KOTAMA) {
		const dasar = KECENDERUNGAN[k.id];
		const kodeKodam = k.nama.replace('Kodam ', '');
		let korem = 0;
		let kodim = 0;
		tambah(
			{
				id: `${k.id}-mk`,
				nama: `${k.nama}/${k.sebutan}`,
				jenis: 'KOTAMA',
				kotama: k.id,
				lat: k.lat,
				lng: k.lng,
				provinsi_kode: k.provinsi_kode,
				jumlah_aplikasi: 8 + Math.floor(r() * 18)
			},
			dasar + (r() - 0.5) * SIMPANGAN[rentang]
		);
		for (const [nama, lat, lng, prov, jenis] of SATUAN[k.id] ?? []) {
			tambah(
				{
					id: `${k.id}-${nama.toLowerCase().replace(/\W+/g, '-')}`,
					// Pola nama sama dengan seed backend: "Korem Alfa-1/Kota", "Kodim Alfa-01/Kota".
					nama:
						jenis === 'KOREM'
							? `Korem ${kodeKodam}-${(korem += 1)}/${nama}`
							: `Kodim ${kodeKodam}-${String((kodim += 1)).padStart(2, '0')}/${nama}`,
					jenis,
					kotama: k.id,
					lat,
					lng,
					provinsi_kode: prov,
					jumlah_aplikasi: 1 + Math.floor(r() * (jenis === 'KOREM' ? 9 : 5))
				},
				dasar + (r() - 0.5) * SIMPANGAN[rentang] * 1.6
			);
		}
	}
	return titik;
}

/** Sebaran temuan per tingkat = jumlah (jenis kerentanan × sistem informasi terdampak). */
function sebaranDari(titik: TitikContoh[]): SebaranTingkat {
	const n: SebaranTingkat = { kritis: 0, tinggi: 0, sedang: 0, rendah: 0 };
	for (const t of titik) for (const k of t.kerentanan) n[k.tingkat] += k.aplikasi;
	return n;
}

/** Data peta ringkas (bentuk sama dengan GET /dashboard/peta). */
export function dataContoh(rentang: Rentang = '24j', siklus = 0): DataPeta {
	const lengkap = titikContoh(rentang, siklus);
	const titik = lengkap.map(({ kerentanan: _k, ...t }) => t);
	return {
		kotama: KOTAMA,
		titik,
		nasional: { sebaran: sebaranDari(lengkap) },
		versi: `contoh-${rentang}-${siklus}`,
		ringkasan: {
			aplikasi_terpetakan: titik.reduce((s, t) => s + t.jumlah_aplikasi, 0),
			aplikasi_belum_terpetakan: 0,
			aplikasi_belum_diuji: 0
		},
		// Cap waktu awal siklus (bukan waktu sekarang) agar sama bila dimuat ulang dalam siklus yang sama.
		diperbarui: new Date(siklus * SIKLUS_MS).toISOString()
	};
}

/** Rincian satu provinsi (bentuk sama dengan GET /dashboard/peta/provinsi/:kode). */
export function rincianProvinsiContoh(kode: string, rentang: Rentang = '24j', siklus = 0): RincianProvinsi {
	const anggota = titikContoh(rentang, siklus).filter((t) => t.provinsi_kode === kode);
	const bobot = anggota.reduce((s, t) => s + t.jumlah_aplikasi, 0);
	return {
		kode,
		satuan: anggota.length,
		aplikasi: bobot,
		indeks: bobot ? Math.round((anggota.reduce((s, t) => s + t.kekuatan * t.jumlah_aplikasi, 0) / bobot) * 10) / 10 : null,
		sebaran: sebaranDari(anggota),
		versi: `contoh-${rentang}-${siklus}`
	};
}
