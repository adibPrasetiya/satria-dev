// Reducer murni: log scan (dengan `data` peristiwa penemuan) → model graf entitas.
// Dipakai untuk live (SSE) maupun rekonstruksi setelah refresh — idempoten terhadap urutan log.
//
// Struktur: target (situs) → hub Frontend (URL halaman/rute) → hub Aset (berkas JS);
// target → hub Backend per origin → endpoint API; plus Upload, Docs, Sesi. Hasil katana &
// ZAP TIDAK berdiri sendiri: tiap URL masuk ke klaster frontend/backend/aset sesuai lapisannya,
// sedangkan node Katana/ZAP menjadi entitas *sumber* yang ditautkan (berlabel jumlah) ke klaster
// yang ia perkaya; alert ZAP ditempel ke URL terkait dan ditautkan merah.
import type { LogScan } from '#lib/types.js';
import type { AlertUrl, EndpointTemuan, ItemCrawl, KodeTahap, Lapisan } from './peristiwa.js';

export type JenisNode =
	| 'situs'
	| 'frontend'
	| 'aset'
	| 'backend'
	| 'upload'
	| 'docs'
	| 'sesi'
	| 'zap'
	| 'katana'
	| 'halaman'
	| 'js'
	| 'endpoint'
	| 'titik'
	| 'alur';

/** Node hub (entitas besar berlabel); selebihnya daun. */
export const JENIS_HUB: ReadonlySet<JenisNode> = new Set(['situs', 'frontend', 'aset', 'backend', 'upload', 'docs', 'sesi', 'zap', 'katana']);

export type Risiko = 'High' | 'Medium' | 'Low' | 'Informational';
export const PERINGKAT_RISIKO: Record<string, number> = { High: 3, Medium: 2, Low: 1, Informational: 0 };

export interface NodeGraf {
	id: string;
	jenis: JenisNode;
	label: string;
	/** Teks kecil di bawah label (mis. jumlah, host). */
	sub?: string;
	/** Node induk (posisi awal & klaster). */
	induk?: string;
	/** Urutan kemunculan (index peristiwa) — dipakai animasi pop berurutan. */
	urutan: number;
	endpoint?: EndpointTemuan;
	/** Sumber temuan: openapi, html, browser, browser-intersep, js, katana, zap. */
	sumber?: string[];
	kategori?: string[];
	titik?: string[];
	/** Endpoint menerima unggahan berkas. */
	upload?: boolean;
	/** Alert pasif ZAP pada URL ini. */
	alert?: { nama: string; risk: string }[];
	info?: Record<string, unknown>;
}

export interface EdgeGraf {
	dari: string;
	ke: string;
	jenis: 'utama' | 'alur' | 'sesi' | 'upload' | 'sumber' | 'alert';
	/** Label teks di sepanjang garis. */
	label?: string;
}

export interface TahapTercatat {
	tahap: KodeTahap;
	waktu: string;
	pesan: string;
	jalur?: string[];
}

export interface Graf {
	nodes: NodeGraf[];
	edges: EdgeGraf[];
	tahap: TahapTercatat[];
	hitung: {
		docs: number;
		backend: number;
		endpoint: number;
		halaman: number;
		aset: number;
		titik: number;
		alur: number;
		upload: number;
		zapUrl: number;
		zapAlert: number;
		katana: number;
	};
	terautentikasi: boolean | null;
	selesai: boolean;
	/** Jumlah peristiwa penemuan (0 = scan tanpa data visual). */
	peristiwa: number;
}

const MAKS_HALAMAN = 80;
const MAKS_JS = 30;

export function originDari(url: string): string {
	try {
		return new URL(url).origin;
	} catch {
		return '';
	}
}

function gabungUrl(rel: string, dasar: string): string {
	try {
		return new URL(rel, dasar).href;
	} catch {
		return '';
	}
}

function hostDari(url: string): string {
	try {
		return new URL(url).host;
	} catch {
		return url;
	}
}

function pathDari(url: string): string {
	try {
		return new URL(url).pathname || '/';
	} catch {
		return url.split('?')[0];
	}
}

const RX_ID = /^(\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{16,})$/i;

/** Path dengan segmen identifier → {id} (sama dengan worker `endpoint_map.path_template`). */
export function templatPath(url: string): string {
	return pathDari(url)
		.split('/')
		.map((s) => (RX_ID.test(s) ? '{id}' : s))
		.join('/') || '/';
}

const EKS_ASET = /\.(js|mjs|cjs|css|map|png|jpe?g|gif|svg|ico|webp|avif|bmp|woff2?|ttf|otf|eot|mp4|webm|mp3|pdf)$/i;
const CT_ASET = /javascript|ecmascript|text\/css|^image\/|^font\/|^video\/|^audio\/|application\/pdf/i;
const CT_API = /json|xml|graphql|event-stream|protobuf|msgpack/i;
const PATH_API = /\/(api|rest|graphql|gql|rpc|oauth2?|v\d+)(\/|$)|\.json$/i;
const SUMBER_API = new Set(['openapi', 'browser', 'browser-intersep', 'js']);
// Berkas build/metadata framework frontend (SvelteKit _app/version.json, Next _next/…) — bukan backend.
const PATH_BUILD = /^\/(_app|_next|_nuxt|__nextjs[^/]*|_astro|_expo)\/|\/(manifest|site|asset-manifest|build-manifest)\.(json|webmanifest)$|\.webmanifest$/i;

/** Port aturan worker `klasifikasi_lapisan` — fallback untuk log lama tanpa `lapisan`. */
export function lapisanDari(metode: string, url: string, opsi: { situs?: string; sumber?: string[]; contentType?: string | null } = {}): Lapisan {
	const path = pathDari(url).toLowerCase();
	const ct = (opsi.contentType ?? '').split(';')[0].trim();
	if (EKS_ASET.test(path) || (ct && CT_ASET.test(ct)) || PATH_BUILD.test(path)) return 'aset';
	if (opsi.sumber?.some((s) => SUMBER_API.has(s))) return 'api';
	if (!['GET', 'HEAD'].includes(metode.toUpperCase())) return 'api';
	if (ct && CT_API.test(ct)) return 'api';
	if (PATH_API.test(path)) return 'api';
	if (opsi.situs && originDari(url) && originDari(url) !== originDari(opsi.situs)) return 'api';
	return 'frontend';
}

/** Endpoint penerima unggahan berkas — selaras heuristik worker `kandidat.py`. */
export function apakahUpload(ep: EndpointTemuan): boolean {
	if (ep.titik_uji === 'unggah_file') return true;
	if ((ep.content_type ?? '').includes('multipart/form-data')) return true;
	if (ep.request_fields.some((f) => (f.tipe ?? '').toLowerCase() === 'file')) return true;
	return ['POST', 'PUT', 'PATCH'].includes(ep.metode_http.toUpperCase()) && /\/(upload|unggah|berkas|lampiran|attachment)/i.test(ep.path_template);
}

/** Endpoint minimal dari URL crawl (katana/ZAP) — dilengkapi bila inventaris worker tiba. */
function endpointDariUrl(metode: string, url: string, sumber: string): EndpointTemuan {
	const tmpl = templatPath(url);
	return {
		id: `${metode} ${tmpl}`,
		metode_http: metode,
		path_template: tmpl,
		url: url.split('?')[0],
		origin: originDari(url),
		sumber: [sumber],
		butuh_autentikasi: false,
		request_fields: [],
		response_fields: [],
		content_type: null,
		status_terlihat: [],
		titik_uji: null,
		lapisan: 'api'
	};
}

const LABEL_SUMBER: Record<string, string> = {
	openapi: 'OpenAPI',
	html: 'Crawl HTML',
	browser: 'Browser',
	'browser-intersep': 'Intersep',
	js: 'Bundle JS',
	katana: 'Katana',
	zap: 'ZAP'
};
export const labelSumber = (s: string) => LABEL_SUMBER[s] ?? s;

export function bangunGraf(logs: LogScan[], urlSitus?: string): Graf {
	const nodes = new Map<string, NodeGraf>();
	const edges = new Map<string, EdgeGraf>();
	const tahap: TahapTercatat[] = [];
	const titikTertunda: { titik: string; url: string; metode: string }[] = [];
	const alertTertunda: AlertUrl[] = [];
	let peristiwa = 0;
	let terautentikasi: boolean | null = null;
	let selesai = false;
	let urutan = 0;
	let halamanLebih = 0;
	let jsLebih = 0;

	const tambahNode = (n: Omit<NodeGraf, 'urutan'>) => {
		const ada = nodes.get(n.id);
		if (ada) {
			const sumber = [...new Set([...(ada.sumber ?? []), ...(n.sumber ?? [])])];
			return Object.assign(ada, { ...n, urutan: ada.urutan, sumber, upload: n.upload ?? ada.upload });
		}
		const baru = { ...n, urutan: urutan++ };
		nodes.set(n.id, baru);
		return baru;
	};
	const tautkan = (dari: string, ke: string, jenis: EdgeGraf['jenis'] = 'utama', label?: string) => {
		if (dari === ke || !nodes.has(dari) || !nodes.has(ke)) return;
		const k = `${dari}>${ke}`;
		const lama = edges.get(k);
		// Tautan struktural tak tertimpa tautan sekunder (mis. upload/alert ke daun yang sama).
		if (lama && lama.jenis === 'utama' && jenis !== 'utama') return;
		edges.set(k, { dari, ke, jenis, label: label ?? lama?.label });
	};
	const tambahSumber = (id: string, s: string) => {
		const n = nodes.get(id);
		if (n && !n.sumber?.includes(s)) n.sumber = [...(n.sumber ?? []), s];
		if (n?.endpoint && !n.endpoint.sumber.includes(s)) n.endpoint = { ...n.endpoint, sumber: [...n.endpoint.sumber, s] };
	};

	let idSitus = '';
	let originSitus = '';
	const pastikanSitus = (url: string) => {
		if (idSitus) return idSitus;
		originSitus = originDari(url);
		idSitus = `situs:${originSitus || url}`;
		tambahNode({ id: idSitus, jenis: 'situs', label: hostDari(url), sub: 'Target', info: { url } });
		return idSitus;
	};
	if (urlSitus) pastikanSitus(urlSitus);

	// Hub kategori: dibuat saat anak pertama muncul (hub kosong tak ditampilkan).
	const pastikanHub = (id: string, jenis: JenisNode, label: string, induk = idSitus) => {
		if (!nodes.has(id)) {
			tambahNode({ id, jenis, label, induk });
			tautkan(induk, id);
		}
		return id;
	};
	const hubFrontend = () => pastikanHub('hub:frontend', 'frontend', 'Frontend');
	const hubAset = () => pastikanHub('hub:aset', 'aset', 'Aset statis', hubFrontend());

	const pastikanBackend = (origin: string, dari?: string) => {
		const id = `be:${origin}`;
		if (!nodes.has(id)) {
			const sama = origin === originSitus;
			tambahNode({
				id,
				jenis: 'backend',
				label: sama ? 'Backend (same-origin)' : 'Backend API',
				sub: hostDari(origin),
				induk: dari ?? idSitus,
				info: { origin, same_origin: sama }
			});
			tautkan(idSitus, id);
		}
		return id;
	};

	const tambahHalaman = (url: string, sumber: string, info: Record<string, unknown> = {}) => {
		if (!idSitus) pastikanSitus(url);
		const tmpl = templatPath(url);
		const id = `hal:${tmpl}`;
		if (!nodes.has(id) && [...nodes.values()].filter((n) => n.jenis === 'halaman').length >= MAKS_HALAMAN) {
			halamanLebih++;
			return null;
		}
		const hub = hubFrontend();
		tambahNode({ id, jenis: 'halaman', label: tmpl, induk: hub, sumber: [sumber], info: { url: url.split('?')[0], ...info } });
		tautkan(hub, id);
		return id;
	};
	const tambahJs = (url: string, sumber: string) => {
		if (!/\.m?js$/i.test(pathDari(url))) return null;
		const id = `js:${pathDari(url)}`;
		if (!nodes.has(id) && [...nodes.values()].filter((n) => n.jenis === 'js').length >= MAKS_JS) {
			jsLebih++;
			return null;
		}
		const hub = hubAset();
		tambahNode({ id, jenis: 'js', label: pathDari(url).split('/').pop() || pathDari(url), sub: pathDari(url), induk: hub, sumber: [sumber], info: { url } });
		tautkan(hub, id);
		return id;
	};
	const tambahEndpoint = (ep: EndpointTemuan) => {
		const origin = ep.origin || originDari(ep.url) || originSitus;
		const be = pastikanBackend(origin);
		const id = `ep:${ep.id}`;
		const lama = nodes.get(id)?.endpoint;
		// Endpoint lengkap dari inventaris menggantikan versi minimal dari URL crawl (dan sebaliknya
		// versi lengkap tak tertimpa versi minimal); daftar sumber selalu digabung.
		const kaya = (e: EndpointTemuan) => e.request_fields.length * 10 + e.sumber.length;
		const dasar = lama && kaya(lama) > kaya(ep) ? lama : ep;
		const pakai = { ...dasar, sumber: [...new Set([...(lama?.sumber ?? []), ...ep.sumber])] };
		const upload = apakahUpload(pakai);
		tambahNode({ id, jenis: 'endpoint', label: ep.id, sub: ep.url, induk: be, endpoint: pakai, upload, sumber: pakai.sumber });
		tautkan(be, id);
		if (upload) tautkan(pastikanHub('hub:upload', 'upload', 'Upload berkas'), id, 'upload');
		return id;
	};
	const tambahItemCrawl = (it: ItemCrawl, sumber: 'katana' | 'zap') => {
		if (it.lapisan === 'aset') return tambahJs(it.url, sumber);
		if (it.lapisan === 'frontend') return tambahHalaman(it.url, sumber, it.status ? { status: it.status } : {});
		const m = (it.metode_http ?? 'GET').toUpperCase();
		const id = `ep:${m} ${templatPath(it.url)}`;
		if (nodes.has(id)) {
			tambahSumber(id, sumber);
			return id;
		}
		return tambahEndpoint(endpointDariUrl(m, it.url, sumber));
	};

	for (const l of logs) {
		const d = l.data;
		// Peristiwa uji (fase pengujian) bukan bagian graf penemuan.
		if (!d || d.v !== 1 || d.jenis === 'uji') continue;
		peristiwa++;
		switch (d.jenis) {
			case 'tahap':
				tahap.push({ tahap: d.tahap, waktu: l.waktu, pesan: l.pesan, jalur: d.jalur });
				if (d.tahap === 'situs' && d.url) pastikanSitus(d.url);
				if (d.tahap === 'selesai') {
					selesai = true;
					if (d.terautentikasi !== undefined) terautentikasi = d.terautentikasi;
				}
				break;
			case 'docs': {
				pastikanSitus(d.url);
				const id = `docs:${d.url}`;
				tambahNode({ id, jenis: 'docs', label: d.judul || 'API Docs', sub: `OpenAPI ${d.versi || ''}`.trim(), induk: idSitus, info: { ...d } });
				tautkan(idSitus, id, 'utama', 'spesifikasi');
				const base = d.base_api ? originDari(d.base_api) || originDari(gabungUrl(d.base_api, d.url)) : '';
				if (base) tautkan(id, pastikanBackend(base, id), 'sumber', `${d.jumlah_endpoint} endpoint`);
				break;
			}
			case 'halaman':
				for (const h of d.items) tambahHalaman(h.url, h.sumber ?? 'html', { status: h.status, judul: h.judul });
				break;
			case 'titik':
				titikTertunda.push({ titik: d.titik, url: d.url, metode: d.metode_http });
				break;
			case 'sesi': {
				tambahNode({ id: 'sesi', jenis: 'sesi', label: d.berhasil ? 'Sesi terautentikasi' : 'Login gagal', sub: `akun ${d.akun}`, induk: idSitus, info: { ...d } });
				tautkan(idSitus, 'sesi', 'sesi', d.berhasil ? 'login' : 'login gagal');
				terautentikasi = d.berhasil;
				break;
			}
			case 'endpoint':
				for (const ep of d.items) {
					const lp = ep.lapisan ?? lapisanDari(ep.metode_http, ep.url, { situs: originSitus, sumber: ep.sumber, contentType: ep.content_type });
					if (lp === 'frontend') {
						const id = tambahHalaman(ep.url, ep.sumber[0] ?? 'html');
						if (id) for (const s of ep.sumber) tambahSumber(id, s);
					} else if (lp === 'aset') {
						tambahJs(ep.url, ep.sumber[0] ?? 'katana');
					} else {
						tambahEndpoint(ep);
					}
				}
				break;
			case 'alur':
				for (const a of d.items) {
					const anggota = a.langkah.map((k) => `ep:${k}`).filter((k) => nodes.has(k));
					if (anggota.length < 2) continue;
					const id = `alur:${a.nama}`;
					tambahNode({ id, jenis: 'alur', label: a.nama, sub: `${anggota.length} langkah · ${a.sumber}`, induk: anggota[0], info: { ...a } });
					for (const k of anggota) tautkan(id, k, 'alur');
				}
				break;
			case 'kandidat':
				for (const [k, kat] of Object.entries(d.per_endpoint)) {
					const n = nodes.get(`ep:${k}`);
					if (n) n.kategori = kat;
				}
				break;
			case 'zap': {
				const alert = d.temuan.reduce((s, t) => s + t.n, 0);
				tambahNode({ id: 'zap', jenis: 'zap', label: 'OWASP ZAP', sub: `${d.jumlah_url} URL · ${alert} alert`, induk: idSitus, info: { ...d, alert } });
				tautkan(idSitus, 'zap', 'sumber');
				for (const it of d.items ?? []) tambahItemCrawl(it, 'zap');
				alertTertunda.push(...(d.alert_url ?? []));
				break;
			}
			case 'katana':
				tambahNode({ id: 'katana', jenis: 'katana', label: 'Katana', sub: `${d.jumlah} URL`, induk: idSitus, info: { ...d } });
				tautkan(idSitus, 'katana', 'sumber');
				for (const it of d.items ?? []) tambahItemCrawl(it, 'katana');
				break;
		}
	}

	// Cari daun (halaman/endpoint) ber-URL sama: cocokkan path template (+ metode bila ada).
	const cariDaun = (url: string, metode?: string): NodeGraf | undefined => {
		const tmpl = templatPath(url);
		const origin = originDari(url);
		if (metode) {
			const ep = nodes.get(`ep:${metode.toUpperCase()} ${tmpl}`);
			if (ep && (!origin || ep.endpoint?.origin === origin)) return ep;
		}
		return (
			nodes.get(`hal:${tmpl}`) ??
			[...nodes.values()].find((n) => n.jenis === 'endpoint' && n.endpoint?.path_template === tmpl && (!origin || n.endpoint.origin === origin))
		);
	};

	// Titik uji: tempel sebagai penanda pada daun ber-URL sama; bila tak ada → node sendiri.
	const titikUnik = new Set<string>();
	for (const t of titikTertunda) {
		titikUnik.add(t.titik);
		const cocok = cariDaun(t.url, t.metode);
		if (cocok) {
			cocok.titik = [...new Set([...(cocok.titik ?? []), t.titik])];
			continue;
		}
		const id = `titik:${t.titik}`;
		if (nodes.has(id)) continue;
		const induk = nodes.get(`be:${originDari(t.url)}`)?.id ?? idSitus;
		tambahNode({ id, jenis: 'titik', label: t.titik, sub: `${t.metode} ${t.url}`, induk, info: { ...t } });
		tautkan(induk, id);
	}

	// Alert ZAP → daun terkait + tautan merah dari node ZAP.
	for (const a of alertTertunda) {
		const daun = cariDaun(a.url);
		if (!daun) continue;
		if (!daun.alert?.some((x) => x.nama === a.nama)) daun.alert = [...(daun.alert ?? []), { nama: a.nama, risk: a.risk }];
		tautkan('zap', daun.id, 'alert');
	}
	for (const n of nodes.values()) {
		if (!n.alert?.length) continue;
		n.alert.sort((a, b) => (PERINGKAT_RISIKO[b.risk] ?? 0) - (PERINGKAT_RISIKO[a.risk] ?? 0));
		const e = edges.get(`zap>${n.id}`);
		if (e && e.jenis === 'alert') e.label = n.alert[0].risk;
	}

	const daftar = [...nodes.values()];
	const endpoints = daftar.filter((n) => n.jenis === 'endpoint');
	const nHalaman = daftar.filter((n) => n.jenis === 'halaman').length + halamanLebih;
	const nJs = daftar.filter((n) => n.jenis === 'js').length + jsLebih;
	const nUpload = endpoints.filter((n) => n.upload).length;
	const zapInfo = nodes.get('zap')?.info as { jumlah_url?: number; alert?: number } | undefined;
	const nAlertTertaut = daftar.filter((n) => n.alert?.length).length;

	// Ringkasan hub + label tautan berisi jumlah.
	const label = (dari: string, ke: string, teks: string) => {
		const e = edges.get(`${dari}>${ke}`);
		if (e) e.label = teks;
	};
	for (const n of daftar) {
		switch (n.jenis) {
			case 'frontend':
				n.sub = `${nHalaman} URL`;
				n.info = { ...n.info, jumlah_url: nHalaman, halaman_lain: halamanLebih };
				label(idSitus, n.id, `${nHalaman} URL`);
				break;
			case 'aset':
				n.sub = `${nJs} berkas JS`;
				n.info = { ...n.info, jumlah: nJs, lain: jsLebih };
				label('hub:frontend', n.id, `${nJs} JS`);
				break;
			case 'backend': {
				const k = endpoints.filter((e) => e.induk === n.id).length;
				n.sub = `${hostDari(String(n.info?.origin ?? ''))} · ${k} endpoint`;
				n.info = { ...n.info, jumlah_endpoint: k };
				label(idSitus, n.id, `${k} endpoint`);
				break;
			}
			case 'upload':
				n.sub = `${nUpload} endpoint`;
				label(idSitus, n.id, `${nUpload} upload`);
				break;
			case 'zap':
			case 'katana': {
				// Kontribusi sumber per klaster: tautan berlabel ke Frontend/Aset/Backend.
				const kontribusi: Record<string, number> = {};
				for (const d of daftar) {
					if (!d.sumber?.includes(n.jenis) || JENIS_HUB.has(d.jenis)) continue;
					const klaster = d.jenis === 'halaman' ? 'hub:frontend' : d.jenis === 'js' ? 'hub:aset' : d.induk ?? '';
					if (klaster) kontribusi[klaster] = (kontribusi[klaster] ?? 0) + 1;
				}
				for (const [klaster, jumlah] of Object.entries(kontribusi)) {
					const jenisKlaster = nodes.get(klaster)?.jenis;
					tautkan(n.id, klaster, 'sumber', `${jumlah} ${jenisKlaster === 'frontend' ? 'URL' : jenisKlaster === 'aset' ? 'JS' : 'endpoint'}`);
				}
				n.info = { ...n.info, kontribusi, total_kontribusi: Object.values(kontribusi).reduce((a, b) => a + b, 0) };
				if (n.jenis === 'zap') label(idSitus, n.id, `${zapInfo?.alert ?? 0} alert`);
				else label(idSitus, n.id, `${n.info?.jumlah ?? 0} URL`);
				break;
			}
		}
	}

	return {
		nodes: daftar,
		edges: [...edges.values()],
		tahap,
		hitung: {
			docs: daftar.filter((n) => n.jenis === 'docs').length,
			backend: daftar.filter((n) => n.jenis === 'backend').length,
			endpoint: endpoints.length,
			halaman: nHalaman,
			aset: nJs,
			titik: titikUnik.size,
			alur: daftar.filter((n) => n.jenis === 'alur').length,
			upload: nUpload,
			zapUrl: Number(zapInfo?.jumlah_url ?? 0),
			zapAlert: Number(zapInfo?.alert ?? nAlertTertaut),
			katana: Number(nodes.get('katana')?.info?.jumlah ?? 0)
		},
		terautentikasi,
		selesai,
		peristiwa
	};
}

/** Relasi untuk panel detail. */
export function tetangga(graf: Graf, id: string): NodeGraf[] {
	const ids = new Set<string>();
	for (const e of graf.edges) {
		if (e.dari === id) ids.add(e.ke);
		if (e.ke === id) ids.add(e.dari);
	}
	return graf.nodes.filter((n) => ids.has(n.id));
}
