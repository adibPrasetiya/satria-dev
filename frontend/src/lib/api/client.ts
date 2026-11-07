import type { Api } from '#lib/api/types.js';
import { httpApi } from '#lib/api/http.js';
import { mockApi } from '#lib/api/mock/index.js';
import { USE_MOCK } from '#lib/api/mode.js';

export { USE_MOCK };

// Fitur yang sudah tersedia di backend. Sisanya (aplikasi, scan, laporan, AI) sementara tetap
// memakai mock sampai endpoint-nya dibuat; hapus daftar ini bila backend sudah lengkap.
const DI_BACKEND = [
	'login',
	'logout',
	'gantiSandi',
	'daftar',
	'cariSatuan',
	'getKatalog',
	'tambahKontrol',
	'ubahKontrol',
	'tambahMetode',
	'ubahMetode',
	'listAplikasi',
	'getAplikasi',
	'buatAplikasi',
	'ubahAplikasi',
	'simpanTargetUji',
	'getTargetUji',
	'listScan',
	'getScan',
	'mulaiScan',
	'batalkanScan',
	'pantauScan',
	'statusWorker',
	'pantauStatusWorker',
	'getPeta',
	'cekKetersediaan',
	'lupaSandi',
	'resetSandi',
	'listPengguna',
	'verifikasiPengguna',
	'tolakPendaftaran',
	'ubahStatusPengguna',
	'listSatuanAdmin',
	'getSatuanAdmin',
	'tambahSatuan',
	'ubahSatuan'
] as const satisfies readonly (keyof Api)[];

export const api: Api = USE_MOCK
	? mockApi
	: { ...mockApi, ...Object.fromEntries(DI_BACKEND.map((k) => [k, httpApi[k]])) };
