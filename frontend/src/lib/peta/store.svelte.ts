// Penyimpanan sementara data dasbor di frontend (memori, bertahan selama aplikasi terbuka — termasuk
// saat berpindah halaman):
// - Ringkasan peta disimpan & hanya diambil ulang bila sudah lebih dari 10 menit (siklus pembaruan).
// - Rincian provinsi diambil per provinsi saat disorot, lalu disimpan per `versi` data; bila pembaruan
//   10 menit membawa versi baru, seluruh rincian lama dibuang & diambil ulang saat dibutuhkan.
import { api } from '#lib/api/client.js';
import type { DataPeta, RincianProvinsi } from '#lib/peta/tipe.js';

export const SIKLUS_PEMBARUAN_MS = 10 * 60_000;

let peta = $state<DataPeta | null>(null);
let galat = $state<string | null>(null);
let dimuatPada = 0;
let muatPeta: Promise<void> | null = null;

let rincian = $state<Record<string, RincianProvinsi>>({});
const sedangDimuat = new Map<string, Promise<void>>();

function setelPeta(data: DataPeta) {
	if (peta?.versi !== data.versi) {
		rincian = {}; // data berubah → rincian provinsi lama usang
		sedangDimuat.clear();
	}
	peta = data;
}

export const storePeta = {
	get data() {
		return peta;
	},
	get galat() {
		return galat;
	},

	/** Muat ringkasan peta; memakai data tersimpan bila belum lewat siklus (kecuali `paksa`). */
	muat(paksa = false): Promise<void> {
		if (!paksa && peta && Date.now() - dimuatPada < SIKLUS_PEMBARUAN_MS) return Promise.resolve();
		if (muatPeta) return muatPeta;
		muatPeta = api
			.getPeta()
			.then((d) => {
				setelPeta(d);
				dimuatPada = Date.now();
				galat = null;
			})
			.catch((e) => {
				// Data lama tetap ditampilkan bila pemuatan ulang gagal.
				galat = (e as Error).message;
			})
			.finally(() => (muatPeta = null));
		return muatPeta;
	},

	/** Rincian provinsi tersimpan (undefined = belum dimuat). */
	rincian(kode: string): RincianProvinsi | undefined {
		return rincian[kode];
	},

	/** Ambil rincian provinsi sekali per versi data. */
	muatRincian(kode: string): Promise<void> {
		if (rincian[kode] || !peta) return Promise.resolve();
		const berjalan = sedangDimuat.get(kode);
		if (berjalan) return berjalan;
		const versi = peta.versi;
		const p = api
			.getPetaProvinsi(kode)
			.then((r) => {
				// Abaikan jawaban dari versi data lama (peta sempat diperbarui saat permintaan berjalan).
				if (peta?.versi === versi) rincian = { ...rincian, [kode]: r };
			})
			.catch(() => {
				/* kartu tetap menampilkan ringkasan; dicoba lagi saat disorot berikutnya */
			})
			.finally(() => sedangDimuat.delete(kode));
		sedangDimuat.set(kode, p);
		return p;
	}
};
