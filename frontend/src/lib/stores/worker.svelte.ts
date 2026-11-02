// Status worker pengujian & antrean (GET /workers/status), dipoll berkala selama ada pemakai.
// Polling berhenti saat tab tersembunyi dan langsung disegarkan saat tab kembali terlihat.
import { api } from '#lib/api/client.js';
import type { StatusWorker } from '#lib/types.js';

const INTERVAL_MS = 10_000;

class StoreWorker {
	status = $state<StatusWorker | null>(null);
	/** true = endpoint status gagal (backend tak terjangkau / galat). */
	galat = $state(false);
	memuat = $state(false);

	#pemakai = 0;
	#timer: ReturnType<typeof setInterval> | null = null;

	readonly #saatTerlihat = () => {
		if (document.visibilityState === 'visible') void this.segarkan();
	};

	/** Daftarkan pemakai; return fungsi pelepas (pakai di $effect / onMount). */
	pakai(): () => void {
		this.#pemakai += 1;
		if (this.#pemakai === 1) {
			void this.segarkan();
			this.#timer = setInterval(() => {
				if (document.visibilityState === 'visible') void this.segarkan();
			}, INTERVAL_MS);
			document.addEventListener('visibilitychange', this.#saatTerlihat);
		}
		return () => {
			this.#pemakai -= 1;
			if (this.#pemakai === 0 && this.#timer) {
				clearInterval(this.#timer);
				this.#timer = null;
				document.removeEventListener('visibilitychange', this.#saatTerlihat);
			}
		};
	}

	async segarkan() {
		if (this.memuat) return;
		this.memuat = true;
		try {
			this.status = await api.statusWorker();
			this.galat = false;
		} catch {
			this.galat = true;
		} finally {
			this.memuat = false;
		}
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
