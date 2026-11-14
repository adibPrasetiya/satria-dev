// Mock inventaris komponen & intel kerentanan untuk mode demo. Data contoh dibentuk dari aplikasi mock
// (tidak disimpan di localStorage — cukup untuk mencoba alur UI).
import type { Api } from '#lib/api/types.js';
import { GalatApi } from '#lib/api/http.js';
import type {
	Aplikasi,
	InventarisKomponen,
	KategoriKomponen,
	KerentananAset,
	KomponenAset,
	RingkasanKerentanan,
	StatusSinkronIntel
} from '#lib/types.js';

type MetodeKerentanan =
	| 'getKomponen'
	| 'tambahKomponen'
	| 'hapusKomponen'
	| 'cariKerentanan'
	| 'ringkasanKerentanan'
	| 'ubahStatusKerentanan'
	| 'statusSinkronIntel'
	| 'mulaiSinkronIntel';

const jeda = () => new Promise((r) => setTimeout(r, 150 + Math.random() * 150));
const salin = <T>(v: T): T => structuredClone(v);
const sekarang = () => new Date().toISOString();

const CONTOH_CVE = [
	{
		id: 'CVE-2023-44487',
		ringkasan: 'The HTTP/2 protocol allows a denial of service (server resource consumption) because request cancellation can reset many streams quickly ("Rapid Reset").',
		cvss: 7.5,
		severitas: 'tinggi' as const,
		kev: true,
		epss: 0.94,
		komponen: { vendor: 'f5', produk: 'nginx', nama: 'nginx', versi: '1.18.0' },
		rentang: '≥ 1.9.5 dan ≤ 1.25.2'
	},
	{
		id: 'CVE-2021-23017',
		ringkasan: 'A security issue in nginx resolver was identified, which might allow an attacker to cause 1-byte memory overwrite.',
		cvss: 7.7,
		severitas: 'tinggi' as const,
		kev: false,
		epss: 0.53,
		komponen: { vendor: 'f5', produk: 'nginx', nama: 'nginx', versi: '1.18.0' },
		rentang: '≥ 0.6.18 dan < 1.20.1'
	},
	{
		id: 'CVE-2020-11022',
		ringkasan: 'In jQuery versions >= 1.2 and < 3.5.0, passing HTML from untrusted sources to manipulation methods may execute untrusted code.',
		cvss: 6.1,
		severitas: 'sedang' as const,
		kev: false,
		epss: 0.22,
		komponen: { vendor: 'jquery', produk: 'jquery', nama: 'jQuery', versi: '3.4.1' },
		rentang: '≥ 1.2 dan < 3.5.0'
	}
];

export function buatMockKerentanan(daftarAplikasi: () => Aplikasi[]): Pick<Api, MetodeKerentanan> {
	const komponen = new Map<string, KomponenAset[]>();
	let kerentanan: KerentananAset[] | null = null;
	let urut = 1;

	function komponenAwal(app: Aplikasi): KomponenAset[] {
		const dari = (kategori: KategoriKomponen, teks: string): KomponenAset | null => {
			if (!teks.trim()) return null;
			const m = /(\d+(?:\.\d+)*)/.exec(teks);
			const nama = teks.replace(/\s*v?\d+(\.\d+)*.*/, '').trim() || teks;
			return {
				id: String(urut++),
				kategori,
				vendor: nama.toLowerCase(),
				produk: nama.toLowerCase().replace(/\s+/g, '_'),
				nama,
				versi: m?.[1] ?? null,
				cpe: null,
				purl: null,
				sumber: 'formulir',
				keyakinan: 'tinggi',
				bukti: teks,
				scan_id: null,
				terakhir_terlihat: sekarang(),
				dikenali: true,
				dipakai: true
			};
		};
		const t = app.teknologi ?? { frontend: '', backend: '', database: '', server: '' };
		return [
			dari('frontend', t.frontend),
			dari('backend', t.backend),
			dari('database', t.database),
			dari('server', t.server),
			{ ...dari('server', 'nginx/1.18.0')!, sumber: 'banner' as const, bukti: 'Server: nginx/1.18.0' },
			{ ...dari('library', 'jQuery 3.4.1')!, sumber: 'bundle_js' as const, bukti: 'vendor.js: /*! jQuery v3.4.1' }
		].filter((k): k is KomponenAset => !!k);
	}

	function inventaris(appId: string): InventarisKomponen {
		const app = daftarAplikasi().find((a) => a.id === appId);
		if (!app) throw new GalatApi('Aplikasi tidak ditemukan', 404);
		if (!komponen.has(appId)) komponen.set(appId, komponenAwal(app));
		const items = komponen.get(appId)!;
		const dipakai = items.filter((k) => k.dipakai);
		return {
			items: salin(items),
			ringkasan: { produk: dipakai.length, dikenali: dipakai.filter((k) => k.dikenali).length, berversi: dipakai.filter((k) => k.versi).length }
		};
	}

	function semuaKerentanan(): KerentananAset[] {
		if (kerentanan) return kerentanan;
		kerentanan = daftarAplikasi()
			.filter((a) => !a.diarsipkan_pada)
			.slice(0, 3)
			.flatMap((a, i) =>
				CONTOH_CVE.slice(0, 3 - i).map((c, j): KerentananAset => {
					const prioritas = Math.min(100, (c.kev ? 40 : 0) + Math.round(c.epss * 30) + Math.round(c.cvss * 2.5) + (a.lingkungan === 'produksi' ? 5 : 0));
					return {
						id: `${a.id}-${j}`,
						aplikasi: { id: a.id, nama: a.nama, satuan: a.satuan, lingkungan: a.lingkungan },
						komponen: { ...c.komponen, sumber: c.komponen.produk === 'jquery' ? 'bundle_js' : 'banner' },
						cve: {
							id: c.id,
							ringkasan: c.ringkasan,
							dipublikasi_pada: '2023-10-10T14:15:10.000Z',
							diubah_pada: sekarang(),
							cvss: c.cvss,
							cvss_vektor: null,
							severitas: c.severitas,
							cwe: [],
							referensi: [],
							status_analisis: 'dianalisis',
							kev: c.kev,
							kev_ditambahkan: c.kev ? '2023-10-10' : null,
							kev_tenggat: c.kev ? '2023-10-31' : null,
							kev_ransomware: false,
							epss: c.epss,
							epss_persentil: 0.99,
							sumber: 'nvd',
							tautan: `https://nvd.nist.gov/vuln/detail/${c.id}`
						},
						status: 'terdampak',
						alasan: `${c.komponen.nama} ${c.komponen.versi} (sumber: banner) berada dalam rentang rentan ${c.rentang}.`,
						prioritas,
						tingkat: c.kev || prioritas >= 70 ? 'segera' : prioritas >= 45 ? 'tinggi' : prioritas >= 25 ? 'sedang' : 'rendah',
						catatan: null,
						ditangani_oleh: null,
						ditangani_pada: null,
						pertama_ditemukan: sekarang(),
						terakhir_dievaluasi: sekarang()
					};
				})
			);
		return kerentanan;
	}

	function ringkas(rows: KerentananAset[]): RingkasanKerentanan {
		const aktif = rows.filter((r) => r.status === 'terdampak' || r.status === 'kemungkinan');
		return {
			terdampak: rows.filter((r) => r.status === 'terdampak').length,
			kemungkinan: rows.filter((r) => r.status === 'kemungkinan').length,
			ditangani: rows.filter((r) => r.status === 'ditangani').length,
			dikecualikan: rows.filter((r) => r.status === 'dikecualikan').length,
			kev: aktif.filter((r) => r.cve.kev).length,
			kritis: aktif.filter((r) => r.cve.severitas === 'kritis').length,
			baru7hari: aktif.length,
			aplikasi: new Set(aktif.map((r) => r.aplikasi.id)).size
		};
	}

	const statusSinkron: StatusSinkronIntel = {
		aktif: true,
		kunci_nvd: false,
		osv: true,
		global: { status: 'berhasil', pesan: '3 kecocokan baru · 42 dtk (data contoh)', kursor: sekarang(), diperbarui: sekarang() },
		nvd: { status: 'berhasil', pesan: '12 CVE diperbarui', kursor: sekarang(), diperbarui: sekarang() },
		kev: { status: 'berhasil', pesan: '1.400 entri katalog, 1 relevan', kursor: sekarang(), diperbarui: sekarang() },
		epss: { status: 'berhasil', pesan: '3 skor', kursor: sekarang(), diperbarui: sekarang() },
		produk: []
	};

	return {
		async getKomponen(appId) {
			await jeda();
			return inventaris(appId);
		},
		async tambahKomponen(appId, { kategori, teks }) {
			await jeda();
			const inv = inventaris(appId);
			const m = /(\d+(?:\.\d+)*)/.exec(teks);
			const nama = teks.replace(/[\s/]*v?\d+(\.\d+)*.*/, '').trim();
			if (!nama) throw new GalatApi('Data yang dikirim tidak valid', 400, undefined, [{ field: 'teks', message: 'Nama komponen tidak dikenali, contoh: "nginx 1.18.0"' }]);
			const produk = nama.toLowerCase().replace(/\s+/g, '_');
			const items = inv.items.filter((k) => !(k.sumber === 'manual' && k.produk === produk)).map((k) => (k.produk === produk ? { ...k, dipakai: false } : k));
			items.push({
				id: String(urut++),
				kategori,
				vendor: produk,
				produk,
				nama,
				versi: m?.[1] ?? null,
				cpe: null,
				purl: null,
				sumber: 'manual',
				keyakinan: 'tinggi',
				bukti: teks,
				scan_id: null,
				terakhir_terlihat: sekarang(),
				dikenali: true,
				dipakai: true
			});
			komponen.set(appId, items);
			return inventaris(appId);
		},
		async hapusKomponen(appId, komponenId) {
			await jeda();
			const inv = inventaris(appId);
			const k = inv.items.find((x) => x.id === komponenId);
			if (!k) throw new GalatApi('Komponen tidak ditemukan', 404);
			if (k.sumber !== 'manual') throw new GalatApi('Komponen dari formulir atau hasil recon tidak dapat dihapus langsung.', 409);
			komponen.set(
				appId,
				inv.items.filter((x) => x.id !== komponenId).map((x) => (x.produk === k.produk ? { ...x, dipakai: true } : x))
			);
			return inventaris(appId);
		},
		async cariKerentanan(f) {
			await jeda();
			const status = f.status ? f.status.split(',') : ['terdampak', 'kemungkinan'];
			const kata = (f.search ?? '').toLowerCase();
			const semua = semuaKerentanan();
			const cakupan = semua.filter((r) => !f.aplikasi_id || r.aplikasi.id === f.aplikasi_id);
			let rows = cakupan.filter(
				(r) =>
					status.includes(r.status) &&
					(!f.kev || r.cve.kev) &&
					(!f.severitas || r.cve.severitas === f.severitas) &&
					(!kata || [r.cve.id, r.komponen.nama, r.aplikasi.nama, r.cve.ringkasan ?? ''].some((s) => s.toLowerCase().includes(kata)))
			);
			rows = [...rows].sort((a, b) => b.prioritas - a.prioritas);
			const limit = f.limit ?? 25;
			const page = f.page ?? 1;
			return {
				items: salin(rows.slice((page - 1) * limit, page * limit)),
				meta: { page, limit, total: rows.length, totalPages: Math.max(1, Math.ceil(rows.length / limit)), ringkasan: ringkas(cakupan) }
			};
		},
		async ringkasanKerentanan() {
			await jeda();
			return ringkas(semuaKerentanan());
		},
		async ubahStatusKerentanan(id, { status, catatan }) {
			await jeda();
			const r = semuaKerentanan().find((x) => x.id === id);
			if (!r) throw new GalatApi('Kerentanan tidak ditemukan', 404);
			r.status = status === 'buka' ? 'terdampak' : status;
			r.catatan = status === 'buka' ? null : (catatan ?? null);
			r.ditangani_oleh = status === 'buka' ? null : 'Pengguna demo';
			r.ditangani_pada = status === 'buka' ? null : sekarang();
			return salin(r);
		},
		async statusSinkronIntel() {
			await jeda();
			return salin(statusSinkron);
		},
		async mulaiSinkronIntel() {
			await jeda();
			statusSinkron.global = { status: 'berhasil', pesan: '0 kecocokan baru · 1 dtk (data contoh)', kursor: sekarang(), diperbarui: sekarang() };
		}
	};
}
