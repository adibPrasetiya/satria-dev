// Agregasi indeks ketahanan dari titik satuan: per provinsi & nasional.
// Bobot = jumlah sistem informasi (satuan dengan lebih banyak aplikasi lebih berpengaruh).
import { namaProvinsi } from '#lib/data/satuan.js';
import type { TitikSebaran } from '#lib/peta/tipe.js';

export interface RingkasProvinsi {
	kode: string;
	nama: string;
	/** Indeks ketahanan 0..100 (1 desimal). */
	indeks: number;
	satuan: number;
	aplikasi: number;
	/** Pusat titik-titik satuan (lng, lat) untuk penanda sorotan di peta. */
	pusat: [number, number];
}

const satuDesimal = (n: number) => Math.round(n * 10) / 10;

export function indeksTertimbang(titik: TitikSebaran[]): number | null {
	const bobot = titik.reduce((s, t) => s + t.jumlah_aplikasi, 0);
	return bobot
		? satuDesimal(titik.reduce((s, t) => s + t.kekuatan * t.jumlah_aplikasi, 0) / bobot)
		: null;
}

/** Ringkasan per provinsi, urut dari indeks terendah (paling rawan) — urutan sorotan di dasbor. */
export function ringkasProvinsi(titik: TitikSebaran[]): RingkasProvinsi[] {
	const grup = new Map<string, TitikSebaran[]>();
	for (const t of titik) {
		if (!t.provinsi_kode) continue; // satuan berlokasi tanpa provinsi: tetap tampil di peta, tak masuk ringkasan provinsi
		grup.set(t.provinsi_kode, [...(grup.get(t.provinsi_kode) ?? []), t]);
	}
	return [...grup.entries()]
		.map(([kode, anggota]) => {
			return {
				kode,
				nama: namaProvinsi(kode) ?? kode,
				indeks: indeksTertimbang(anggota) ?? 0,
				satuan: anggota.length,
				aplikasi: anggota.reduce((s, t) => s + t.jumlah_aplikasi, 0),
				pusat: [
					anggota.reduce((s, t) => s + t.lng, 0) / anggota.length,
					anggota.reduce((s, t) => s + t.lat, 0) / anggota.length
				] as [number, number]
			};
		})
		.sort((a, b) => a.indeks - b.indeks);
}
