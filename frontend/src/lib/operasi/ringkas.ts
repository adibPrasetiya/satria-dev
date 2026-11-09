// Turunan data halaman operasi dari hasil scan: baris rincian per metode & daftar temuan.
// Murni (tanpa I/O).
import { indeksMetode, URUTAN_SEVERITY } from '#lib/catalog.js';
import type { HasilMetode, Scan, Severity, StatusMetode } from '#lib/types.js';

export interface BarisMetode {
	id: string;
	nama: string;
	fungsi: string;
	namaFungsi: string;
	kontrol: string;
	severity: Severity;
	status: StatusMetode;
	ringkasan: string;
	durasi_ms?: number;
	menunggu_tinjauan: boolean;
	kriteria: string;
}

/** Semua metode pengujian pada scan (tanpa task penemuan), urut sesuai katalog. */
export function barisMetode(scan: Scan): BarisMetode[] {
	const out: BarisMetode[] = [];
	for (const [id, h] of Object.entries(scan.hasil) as [string, HasilMetode][]) {
		if (id.startsWith('_')) continue;
		const m = indeksMetode.get(id);
		out.push({
			id,
			nama: m?.metode.nama ?? id,
			fungsi: m?.fungsi.id ?? id.split('-')[0],
			namaFungsi: m?.fungsi.nama ?? '',
			kontrol: m?.kontrol.id ?? '',
			severity: m?.metode.severity ?? 'info',
			status: h.status,
			ringkasan: h.ringkasan ?? '',
			durasi_ms: h.durasi_ms,
			menunggu_tinjauan: !!h.menunggu_tinjauan,
			kriteria: m?.metode.kriteria_lulus ?? ''
		});
	}
	const urutan = new Map([...indeksMetode.keys()].map((k, i) => [k, i]));
	return out.sort((a, b) => (urutan.get(a.id) ?? 1e9) - (urutan.get(b.id) ?? 1e9));
}

/** Temuan = metode GAGAL, diurutkan dari severity tertinggi (info tidak dianggap temuan). */
export function daftarTemuan(baris: BarisMetode[]): BarisMetode[] {
	return baris
		.filter((b) => b.status === 'gagal' && b.severity !== 'info')
		.sort((a, b) => URUTAN_SEVERITY.indexOf(a.severity) - URUTAN_SEVERITY.indexOf(b.severity));
}

export const WARNA_STATUS: Record<string, string> = {
	lulus: '#9fe08a',
	gagal: '#ff7b6b',
	tidak_dapat_diverifikasi: '#f5c451',
	tidak_berlaku: '#8c9bab',
	luar_cakupan: '#6b7785',
	antre: 'rgba(255,255,255,0.35)',
	berjalan: '#7fe9d8'
};

// Skala severity (ordinal). Divalidasi di permukaan gelap: pasangan bersebelahan lolos CVD (ΔE ≥ 12)
// & batas penglihatan normal (ΔE ≥ 16). Info memakai abu-abu netral.
export const WARNA_SEVERITY: Record<Severity, string> = {
	kritis: '#d93f45',
	tinggi: '#f08a24',
	sedang: '#e9cf53',
	rendah: '#3f88de',
	info: '#8c9bab'
};
