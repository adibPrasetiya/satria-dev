// Status worker pengujian & antrean. Satu aliran SSE (GET /workers/status/stream) dibagi semua pemakai di
// tab ini; server hanya mengirim saat status berubah, jadi tidak ada polling berkala.
// - Aliran dibuka saat ada pemakai pertama, ditutup saat pemakai terakhir pergi.
// - Tab tersembunyi > 1 menit: aliran ditutup (hemat koneksi); dibuka lagi saat tab terlihat.
// - Aliran putus: sambung ulang dengan jeda bertahap (2 dtk → … → 60 dtk), bukan dibanjiri percobaan.
import { untrack } from 'svelte';
import { api } from '#lib/api/client.js';
import type { StatusWorker } from '#lib/types.js';

const JEDA_SAMBUNG_MS = [2_000, 5_000, 10_000, 30_000, 60_000];
const TUTUP_SAAT_TERSEMBUNYI_MS = 60_000;

class StoreWorker {
	status = $state<StatusWorker | null>(null);
	/** true = aliran/endpoint status gagal (backend tak terjangkau / galat). */
	galat = $state(false);
	/** Waktu (ms epoch) status terakhir diterima — untuk menghitung umur heartbeat yang ditampilkan. */
	diterimaPada = $state(0);

	#pemakai = 0;
	#tutupAliran: (() => void) | null = null;
	#tersambung = false;
	#percobaan = 0;
	#timerSambung: ReturnType<typeof setTimeout> | null = null;
	#timerSembunyi: ReturnType<typeof setTimeout> | null = null;
	#memuat = false;

	readonly #saatVisibilitas = () => {
		if (document.visibilityState === 'visible') {
			if (this.#timerSembunyi) clearTimeout(this.#timerSembunyi);
			this.#timerSembunyi = null;
			if (!this.#tutupAliran && !this.#timerSambung) this.#buka();
		} else if (!this.#timerSembunyi) {
			this.#timerSembunyi = setTimeout(() => {
				this.#timerSembunyi = null;
				this.#tutup();
			}, TUTUP_SAAT_TERSEMBUNYI_MS);
		}
	};

	/**
	 * Daftarkan pemakai; return fungsi pelepas (pakai di $effect / onMount).
	 * Dibungkus `untrack`: tanpa itu $effect pemanggil ikut melacak state store (mis. status) sehingga
	 * effect dibongkar-pasang setiap kali data datang → membuka permintaan baru tanpa henti.
	 */
	pakai(): () => void {
		return untrack(() => {
			this.#pemakai += 1;
			if (this.#pemakai === 1) {
				document.addEventListener('visibilitychange', this.#saatVisibilitas);
				if (document.visibilityState === 'visible') this.#buka();
			}
			let dilepas = false;
			return () => {
				if (dilepas) return;
				dilepas = true;
				this.#pemakai -= 1;
				if (this.#pemakai > 0) return;
				document.removeEventListener('visibilitychange', this.#saatVisibilitas);
				if (this.#timerSembunyi) clearTimeout(this.#timerSembunyi);
				this.#timerSembunyi = null;
				this.#tutup();
			};
		});
	}

	/**
	 * Minta status terbaru sekali. Saat aliran tersambung tidak perlu (server sudah mendorong perubahan),
	 * jadi hanya dipakai bila aliran sedang putus.
	 */
	async segarkan() {
		if (this.#tersambung || this.#memuat) return;
		this.#memuat = true;
		try {
			this.#terima(await api.statusWorker());
		} catch {
			this.galat = true;
		} finally {
			this.#memuat = false;
		}
	}

	#terima(s: StatusWorker) {
		this.status = s;
		this.galat = false;
		this.diterimaPada = Date.now();
	}

	#buka() {
		if (this.#tutupAliran) return;
		this.#tutupAliran = api.pantauStatusWorker(
			(s) => {
				this.#tersambung = true;
				this.#percobaan = 0;
				this.#terima(s);
			},
			() => this.#putus()
		);
	}

	#tutup() {
		if (this.#timerSambung) clearTimeout(this.#timerSambung);
		this.#timerSambung = null;
		this.#tutupAliran?.();
		this.#tutupAliran = null;
		this.#tersambung = false;
	}

	#putus() {
		this.#tutupAliran = null;
		this.#tersambung = false;
		if (!this.#pemakai || document.visibilityState !== 'visible') return;
		// Percobaan pertama gagal belum tentu backend mati (mis. restart); tandai galat setelah gagal berulang.
		if (this.#percobaan >= 1) this.galat = true;
		const jeda = JEDA_SAMBUNG_MS[Math.min(this.#percobaan, JEDA_SAMBUNG_MS.length - 1)];
		this.#percobaan += 1;
		this.#timerSambung = setTimeout(() => {
			this.#timerSambung = null;
			this.#buka();
		}, jeda);
	}
}

export const storeWorker = new StoreWorker();

/** "±3 menit" / "±40 detik" untuk perkiraan tunggu. */
export function teksPerkiraan(detik: number): string {
	if (detik <= 0) return 'segera';
	if (detik < 60) return `±${Math.max(5, Math.round(detik / 5) * 5)} detik`;
	const menit = Math.round(detik / 60);
	return menit < 60 ? `±${menit} menit` : `±${Math.floor(menit / 60)} jam ${menit % 60} menit`;
}
