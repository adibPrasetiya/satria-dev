// Logika turunan katalog: penerapan metode per aplikasi, agregasi kontrol,
// skor per fungsi, dan putusan kelaikan. Murni (tanpa I/O) agar bisa dipakai
// ulang oleh mock maupun saat data datang dari backend.
// Catatan: halaman Katalog membaca & mengedit katalog dari backend (api.getKatalog). Konstanta `katalog` di sini
// (catalog.json statis dari controls/bssn_web.yaml) masih dipakai simulasi pengujian mock sampai fitur pengujian
// tersambung ke backend.
import data from '#lib/data/catalog.json';
import type {
	Aplikasi,
	Fungsi,
	HasilMetode,
	Katalog,
	Kontrol,
	Metode,
	PemetaanTitikUji,
	Putusan,
	Severity,
	Status
} from '#lib/types.js';

export const katalog = data as unknown as Katalog;

export interface MetodeLengkap {
	metode: Metode;
	kontrol: Kontrol;
	fungsi: Fungsi;
}

export const semuaMetode: MetodeLengkap[] = katalog.fungsi_keamanan.flatMap((fungsi) =>
	fungsi.kontrol.flatMap((kontrol) =>
		kontrol.metode_pengujian.map((metode) => ({ metode, kontrol, fungsi }))
	)
);

export const indeksMetode = new Map(semuaMetode.map((m) => [m.metode.id, m]));
export const indeksKontrol = new Map(
	katalog.fungsi_keamanan.flatMap((f) => f.kontrol.map((k) => [k.id, { kontrol: k, fungsi: f }]))
);
export const namaTitikUji = new Map(katalog.titik_uji.map((t) => [t.id, t.nama]));

/** Titik uji yang selalu berlaku dan tidak perlu dipetakan pengguna. */
export const TITIK_UJI_TETAP = ['global', 'dokumen'];

/** Pemetaan awal: semua titik uji yang perlu dipetakan dalam keadaan tidak tersedia. */
export function titikUjiKosong(): Record<string, PemetaanTitikUji> {
	return Object.fromEntries(
		katalog.titik_uji
			.filter((t) => !TITIK_UJI_TETAP.includes(t.id))
			.map((t) => [t.id, { tersedia: false, url: '', metode_http: 'GET' }])
	);
}

export const URUTAN_SEVERITY: Severity[] = ['kritis', 'tinggi', 'sedang', 'rendah', 'info'];

// ---------------------------------------------------------------------------
// Penerapan metode terhadap aplikasi

export type Penerapan =
	| { jalan: true }
	| { jalan: false; status: 'tidak_berlaku' | 'tidak_dapat_diverifikasi'; alasan: string };

export function penerapanMetode(app: Pick<Aplikasi, 'titik_uji' | 'akun_uji' | 'profil_pengujian' | 'izin_intrusif'>, metode: Metode): Penerapan {
	if (!TITIK_UJI_TETAP.includes(metode.titik_uji) && !app.titik_uji[metode.titik_uji]?.tersedia) {
		return {
			jalan: false,
			status: 'tidak_berlaku',
			alasan: `Titik uji "${namaTitikUji.get(metode.titik_uji) ?? metode.titik_uji}" tidak tersedia pada aplikasi.`
		};
	}
	if (metode.butuh_autentikasi && !app.akun_uji.some((a) => a.terisi)) {
		return {
			jalan: false,
			status: 'tidak_dapat_diverifikasi',
			alasan: 'Membutuhkan akun uji, tetapi akun uji belum diisi.'
		};
	}
	if (metode.profil === 'intrusif') {
		if (app.profil_pengujian !== 'intrusif') {
			return {
				jalan: false,
				status: 'tidak_dapat_diverifikasi',
				alasan: 'Metode intrusif tidak dipilih pada profil pengujian.'
			};
		}
		if (app.izin_intrusif.status !== 'disetujui') {
			return {
				jalan: false,
				status: 'tidak_dapat_diverifikasi',
				alasan: 'Izin pengujian intrusif belum disetujui asesor.'
			};
		}
	}
	return { jalan: true };
}

export interface RingkasanRencana {
	total: number;
	otomatis: number;
	semi_otomatis: number;
	manual: number;
	tidak_berlaku: number;
	dilewati: number;
	intrusif: number;
	butuh_dokumen: number;
}

export function ringkasanRencana(app: Parameters<typeof penerapanMetode>[0]): RingkasanRencana {
	const r: RingkasanRencana = {
		total: semuaMetode.length,
		otomatis: 0,
		semi_otomatis: 0,
		manual: 0,
		tidak_berlaku: 0,
		dilewati: 0,
		intrusif: 0,
		butuh_dokumen: 0
	};
	for (const { metode } of semuaMetode) {
		const p = penerapanMetode(app, metode);
		if (!p.jalan) {
			if (p.status === 'tidak_berlaku') r.tidak_berlaku++;
			else r.dilewati++;
			continue;
		}
		r[metode.jenis]++;
		if (metode.profil === 'intrusif') r.intrusif++;
		if (metode.bukti.includes('dokumen')) r.butuh_dokumen++;
	}
	return r;
}

/** Jumlah metode yang bergantung pada tiap titik uji. */
export const jumlahMetodePerTitik: Record<string, number> = semuaMetode.reduce(
	(acc, { metode }) => {
		acc[metode.titik_uji] = (acc[metode.titik_uji] ?? 0) + 1;
		return acc;
	},
	{} as Record<string, number>
);

// ---------------------------------------------------------------------------
// Agregasi hasil

function statusAkhir(h: HasilMetode | undefined): Status {
	if (!h || h.status === 'antre' || h.status === 'berjalan') return 'tidak_dapat_diverifikasi';
	return h.status;
}

/** Status kontrol dari hasil metodenya sesuai aturan `agregasi` di katalog. */
export function statusKontrol(kontrol: Kontrol, hasil: Record<string, HasilMetode>): Status {
	// Metode bertingkat severity "info" hanya informasi dan tidak memengaruhi status.
	const status = kontrol.metode_pengujian
		.filter((m) => m.severity !== 'info')
		.map((m) => statusAkhir(hasil[m.id]))
		.filter((s) => s !== 'tidak_berlaku');

	if (status.length === 0) return 'tidak_berlaku';
	if (kontrol.agregasi === 'minimal_satu') {
		if (status.includes('lulus')) return 'lulus';
		if (status.includes('tidak_dapat_diverifikasi')) return 'tidak_dapat_diverifikasi';
		return 'gagal';
	}
	if (status.includes('gagal')) return 'gagal';
	if (status.includes('tidak_dapat_diverifikasi')) return 'tidak_dapat_diverifikasi';
	return 'lulus';
}

export type Hitungan = Record<Status, number>;

export function hitunganKosong(): Hitungan {
	return { lulus: 0, gagal: 0, tidak_berlaku: 0, tidak_dapat_diverifikasi: 0 };
}

export interface SkorFungsi {
	fungsi: Fungsi;
	hitungan: Hitungan;
	/** Persentase kontrol lulus dari kontrol yang sudah teruji (lulus+gagal); null bila belum ada. */
	skor: number | null;
}

export function skorFungsi(fungsi: Fungsi, hasil: Record<string, HasilMetode>): SkorFungsi {
	const hitungan = hitunganKosong();
	for (const k of fungsi.kontrol) hitungan[statusKontrol(k, hasil)]++;
	const teruji = hitungan.lulus + hitungan.gagal;
	return { fungsi, hitungan, skor: teruji ? Math.round((hitungan.lulus / teruji) * 100) : null };
}

export interface Penilaian {
	putusan: Putusan;
	/** Kepatuhan: kontrol lulus / kontrol teruji (lulus+gagal). */
	skor: number;
	/** Cakupan: kontrol teruji / kontrol berlaku; sisanya menunggu bukti/asesor. */
	cakupan: number;
	hitungan: Hitungan;
	perFungsi: SkorFungsi[];
	gagalKritisTinggi: Kontrol[];
	alasan: string[];
}

/** Aturan putusan kelaikan; ubah di sini bila kebijakan instansi berbeda. */
export const ATURAN_PUTUSAN = {
	/** Kontrol gagal dengan severity ini membuat aplikasi Tidak Laik. */
	severityPenggagal: ['kritis', 'tinggi'] as Severity[],
	/** Skor minimum agar dapat dinyatakan Laik. */
	skorMinimumLaik: 100
};

export function nilaiKelaikan(hasil: Record<string, HasilMetode>): Penilaian {
	const perFungsi = katalog.fungsi_keamanan.map((f) => skorFungsi(f, hasil));
	const hitungan = hitunganKosong();
	const gagalKritisTinggi: Kontrol[] = [];
	for (const f of katalog.fungsi_keamanan) {
		for (const k of f.kontrol) {
			const s = statusKontrol(k, hasil);
			hitungan[s]++;
			if (s === 'gagal' && ATURAN_PUTUSAN.severityPenggagal.includes(k.severity_default)) {
				gagalKritisTinggi.push(k);
			}
		}
	}
	const berlaku = hitungan.lulus + hitungan.gagal + hitungan.tidak_dapat_diverifikasi;
	const teruji = hitungan.lulus + hitungan.gagal;
	const skor = teruji ? Math.round((hitungan.lulus / teruji) * 100) : 0;
	const cakupan = berlaku ? Math.round((teruji / berlaku) * 100) : 0;

	const alasan: string[] = [];
	let putusan: Putusan;
	if (gagalKritisTinggi.length > 0) {
		putusan = 'tidak_laik';
		alasan.push(`${gagalKritisTinggi.length} kontrol berseverity kritis/tinggi tidak terpenuhi.`);
	} else if (hitungan.gagal > 0 || hitungan.tidak_dapat_diverifikasi > 0 || skor < ATURAN_PUTUSAN.skorMinimumLaik) {
		putusan = 'laik_bersyarat';
		if (hitungan.gagal > 0) alasan.push(`${hitungan.gagal} kontrol berseverity sedang/rendah tidak terpenuhi.`);
		if (hitungan.tidak_dapat_diverifikasi > 0)
			alasan.push(`${hitungan.tidak_dapat_diverifikasi} kontrol belum dapat diverifikasi (menunggu bukti/asesor).`);
	} else {
		putusan = 'laik';
		alasan.push('Seluruh kontrol yang berlaku terpenuhi.');
	}
	return { putusan, skor, cakupan, hitungan, perFungsi, gagalKritisTinggi, alasan };
}

// ---------------------------------------------------------------------------
// Label tampilan

export const LABEL_STATUS: Record<Status | 'antre' | 'berjalan', string> = {
	lulus: 'Lulus',
	gagal: 'Gagal',
	tidak_berlaku: 'Tidak Berlaku',
	tidak_dapat_diverifikasi: 'Belum Terverifikasi',
	antre: 'Antre',
	berjalan: 'Berjalan'
};

export const LABEL_PUTUSAN: Record<Putusan, string> = {
	laik: 'Laik',
	laik_bersyarat: 'Laik Bersyarat',
	tidak_laik: 'Tidak Laik'
};

export const LABEL_JENIS: Record<Metode['jenis'], string> = {
	otomatis: 'Otomatis',
	semi_otomatis: 'Semi-otomatis',
	manual: 'Manual'
};

export const LABEL_ENGINE: Record<Metode['engine'], string> = {
	custom: 'Pemeriksa bawaan',
	zap: 'OWASP ZAP',
	nuclei: 'Nuclei',
	sslyze: 'SSLyze',
	playwright: 'Playwright',
	manual: 'Asesor'
};
