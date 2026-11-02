// Ringkasan status aplikasi dari daftar aplikasi & scan (dipakai dasbor dan daftar aplikasi).
import { nilaiKelaikan, type Penilaian } from '#lib/catalog.js';
import type { Aplikasi, Scan } from '#lib/types.js';

export interface RingkasanAplikasi {
	app: Aplikasi;
	scanTerakhir?: Scan;
	/** Penilaian dari scan selesai terakhir. */
	penilaian?: Penilaian;
	berjalan: boolean;
}

export function ringkasAplikasi(apps: Aplikasi[], scans: Scan[]): RingkasanAplikasi[] {
	return apps.map((app) => {
		const milik = scans
			.filter((s) => s.aplikasi_id === app.id)
			.sort((a, b) => b.dimulai_pada.localeCompare(a.dimulai_pada));
		const selesai = milik.find((s) => s.status === 'selesai');
		return {
			app,
			scanTerakhir: milik[0],
			penilaian: selesai ? nilaiKelaikan(selesai.hasil) : undefined,
			berjalan: milik.some((s) => s.status === 'berjalan')
		};
	});
}
