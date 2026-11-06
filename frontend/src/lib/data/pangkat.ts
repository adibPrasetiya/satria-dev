// Pilihan pangkat (TNI) & golongan (PNS) untuk langkah "Pangkat" di pendaftaran.
// Disimpan backend apa adanya di kolom `pangkat` (varchar 60).
import type { StatusKepegawaian } from '#lib/types.js';

const TNI = [
	// Tamtama
	'Prada',
	'Pratu',
	'Praka',
	'Kopda',
	'Koptu',
	'Kopka',
	'Kelasi Dua',
	'Kelasi Satu',
	'Kelasi Kepala',
	// Bintara
	'Serda',
	'Sertu',
	'Serka',
	'Serma',
	'Pelda',
	'Peltu',
	// Perwira pertama & menengah
	'Letda',
	'Lettu',
	'Kapten',
	'Mayor',
	'Letkol',
	'Kolonel',
	// Perwira tinggi (AD / AL / AU)
	'Brigjen TNI',
	'Mayjen TNI',
	'Letjen TNI',
	'Jenderal TNI',
	'Laksma TNI',
	'Laksda TNI',
	'Laksdya TNI',
	'Laksamana TNI',
	'Marsma TNI',
	'Marsda TNI',
	'Marsdya TNI',
	'Marsekal TNI'
];

const PNS = [
	'Juru Muda (I/a)',
	'Juru Muda Tk. I (I/b)',
	'Juru (I/c)',
	'Juru Tk. I (I/d)',
	'Pengatur Muda (II/a)',
	'Pengatur Muda Tk. I (II/b)',
	'Pengatur (II/c)',
	'Pengatur Tk. I (II/d)',
	'Penata Muda (III/a)',
	'Penata Muda Tk. I (III/b)',
	'Penata (III/c)',
	'Penata Tk. I (III/d)',
	'Pembina (IV/a)',
	'Pembina Tk. I (IV/b)',
	'Pembina Utama Muda (IV/c)',
	'Pembina Utama Madya (IV/d)',
	'Pembina Utama (IV/e)'
];

export const PANGKAT: Record<StatusKepegawaian, readonly string[]> = { TNI, PNS };

/** Cari pangkat/golongan yang cocok (tanpa beda huruf besar-kecil); kosong = semua. */
export function cariPangkat(status: StatusKepegawaian, kata: string) {
	const k = kata.trim().toLowerCase();
	return PANGKAT[status]
		.filter((p) => !k || p.toLowerCase().includes(k))
		.map((p) => ({ value: p, label: p }));
}
