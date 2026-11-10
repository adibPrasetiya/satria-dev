// Keterangan "worker diblokir / target tak terjangkau" dari peristiwa `terblokir` di log scan
// (worker `keterjangkauan.peristiwa_terblokir`). Dipakai banner di halaman scan.

import type { LogScan } from '#lib/types.js';
import type { Terblokir } from './peristiwa.js';

export type KeteranganBlokir = Terblokir & { waktu: string; jumlah: number };

/**
 * Keterangan blokir terpenting dalam log: peristiwa fatal diutamakan (tak tergantikan peringatan
 * sesudahnya), selain itu yang terbaru. `jumlah` = banyaknya peristiwa blokir (mis. beberapa task
 * metode yang sama-sama gagal preflight). null bila tak ada.
 */
export function cariTerblokir(logs: LogScan[]): KeteranganBlokir | null {
	let pilih: KeteranganBlokir | null = null;
	let jumlah = 0;
	for (const l of logs) {
		const d = l.data;
		if (!d || d.v !== 1 || d.jenis !== 'terblokir') continue;
		jumlah++;
		const { v: _v, jenis: _j, ...isi } = d;
		if (!pilih || !pilih.fatal || isi.fatal) pilih = { ...isi, waktu: l.waktu, jumlah: 0 };
	}
	return pilih ? { ...pilih, jumlah } : null;
}

const LAPISAN: Record<Terblokir['lapisan'], string> = {
	dns: 'DNS tak ter-resolve',
	tcp: 'Koneksi diblokir',
	http: 'Ditolak WAF / rate-limit'
};

export function judulBlokir(k: Terblokir): string {
	const fase = k.fase === 'recon' ? 'Recon' : 'Pengujian';
	if (k.fatal) return `${fase} ${k.awal ? 'tidak dapat dimulai' : 'dihentikan'} — ${LAPISAN[k.lapisan].toLowerCase()}`;
	return `${fase} mungkin tidak lengkap — ${LAPISAN[k.lapisan].toLowerCase()}`;
}
