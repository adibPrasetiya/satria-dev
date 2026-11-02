// Reducer murni: log scan (dengan peristiwa `jenis: "uji"`) → daftar metode uji beserta
// "ketukan" (langkah & request berurutan) yang diputar animasi. Idempoten terhadap urutan log.
import type { LogScan } from '#lib/types.js';
import type { RequestUji, SkenarioUji } from './peristiwa.js';

export type Ketukan =
	| { tipe: 'langkah'; langkah: string; label: string; detail: Record<string, unknown> }
	| { tipe: 'request'; req: RequestUji };

export interface MetodeUji {
	id: string;
	judul: string;
	fungsi: string;
	check_id: string;
	titik_uji: string;
	skenario: SkenarioUji;
	ketukan: Ketukan[];
	/** Verdict dari worker (null = masih berjalan). */
	status: string | null;
	ringkasan: string;
	waktu: string;
}

export interface Uji {
	daftar: MetodeUji[];
	per: Map<string, MetodeUji>;
}

export function bangunUji(logs: LogScan[]): Uji {
	const per = new Map<string, MetodeUji>();
	const daftar: MetodeUji[] = [];
	for (const l of logs) {
		const d = l.data;
		if (!d || d.v !== 1 || d.jenis !== 'uji') continue;
		let m = per.get(d.metode_id);
		if (d.fase === 'mulai') {
			// Metode dijalankan ulang (mis. task diambil ulang) → mulai dari awal.
			m = { id: d.metode_id, judul: d.judul, fungsi: d.fungsi, check_id: d.check_id, titik_uji: d.titik_uji, skenario: d.skenario, ketukan: [], status: null, ringkasan: '', waktu: l.waktu };
			if (!per.has(d.metode_id)) daftar.push(m);
			else daftar[daftar.findIndex((x) => x.id === d.metode_id)] = m;
			per.set(d.metode_id, m);
			continue;
		}
		if (!m) continue;
		if (d.fase === 'langkah') m.ketukan.push({ tipe: 'langkah', langkah: d.langkah, label: d.label, detail: d.detail ?? {} });
		else if (d.fase === 'request') {
			const { v: _v, jenis: _j, fase: _f, metode_id: _m, ...req } = d;
			// Nomor urut per metode dihitung di sini: nomor dari worker bisa berulang bila satu uji
			// memakai beberapa klien HTTP (dipakai sebagai kunci {#each} → wajib unik).
			const no = m.ketukan.filter((k) => k.tipe === 'request').length + 1;
			m.ketukan.push({ tipe: 'request', req: { ...req, no } });
		} else if (d.fase === 'hasil') {
			m.status = d.status;
			m.ringkasan = d.ringkasan;
		}
	}
	return { daftar, per };
}

/** Warna & arti hasil evaluasi langkah (detail.hasil dari worker). */
export const HASIL_AMAN = new Set(['ditolak', 'dialihkan', 'terkunci', 'tertunda', 'tersamar', 'aman']);
export const HASIL_RENTAN = new Set(['diterima', 'bocor', 'terbuka', 'tanpa_penguncian', 'tidak_aman']);
