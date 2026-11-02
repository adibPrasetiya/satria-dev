// Ikon entitas bergaya aplikasi (SVG berwarna, viewBox 64) untuk graf penemuan & daftar aset.
// Satu sumber untuk kanvas (SVG → Image, di-cache) dan HTML ({@html svgEntitas(...)}).
// Glyph generik — bukan logo merek pihak mana pun.

export type JenisIkon =
	| 'situs'
	| 'frontend'
	| 'halaman'
	| 'aset'
	| 'js'
	| 'backend'
	| 'endpoint'
	| 'upload'
	| 'docs'
	| 'sesi'
	| 'zap'
	| 'katana'
	| 'alur'
	| 'titik'
	| 'penguji'
	| 'payload'
	| 'gembok'
	| 'gembok_terbuka';

const tile = (id: string, a: string, b: string) =>
	`<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs>` +
	`<rect x="4" y="4" width="56" height="56" rx="13" fill="url(#${id})"/>` +
	`<rect x="4.5" y="4.5" width="55" height="55" rx="12.5" fill="none" stroke="#fff" stroke-opacity=".18"/>` +
	`<path d="M17 4.5h30a12.5 12.5 0 0 1 12.5 12.5v3C42 26 22 26 4.5 20v-3A12.5 12.5 0 0 1 17 4.5z" fill="#fff" fill-opacity=".1"/>`;

const SVG: Record<Exclude<JenisIkon, 'endpoint'>, string> = {
	// Folder target dengan bola dunia.
	situs:
		`<defs><linearGradient id="gs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7cc4ff"/><stop offset="1" stop-color="#2f80d1"/></linearGradient>` +
		`<linearGradient id="gs2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5aa9ec"/><stop offset="1" stop-color="#1f62a8"/></linearGradient></defs>` +
		`<path d="M6 16a5 5 0 0 1 5-5h14l6 6h22a5 5 0 0 1 5 5v4H6z" fill="url(#gs2)"/>` +
		`<rect x="6" y="22" width="52" height="32" rx="5" fill="url(#gs)"/>` +
		`<circle cx="32" cy="38" r="10" fill="none" stroke="#fff" stroke-width="2.4"/>` +
		`<ellipse cx="32" cy="38" rx="4.5" ry="10" fill="none" stroke="#fff" stroke-width="2"/>` +
		`<path d="M22 38h20M24 33h16M24 43h16" stroke="#fff" stroke-width="1.8"/>`,
	// Jendela web browser: bilah judul + 3 lampu + address bar + konten.
	frontend:
		tile('gf', '#4f9bff', '#1f5fd6') +
		`<rect x="12" y="15" width="40" height="34" rx="4" fill="#f4f8ff"/>` +
		`<path d="M12 19a4 4 0 0 1 4-4h32a4 4 0 0 1 4 4v4H12z" fill="#d6e4fb"/>` +
		`<circle cx="17" cy="19" r="1.7" fill="#ff5f57"/><circle cx="22" cy="19" r="1.7" fill="#febc2e"/><circle cx="27" cy="19" r="1.7" fill="#28c840"/>` +
		`<rect x="31" y="17.2" width="17" height="3.6" rx="1.8" fill="#fff"/>` +
		`<rect x="16" y="27" width="14" height="10" rx="1.5" fill="#bcd3f7"/>` +
		`<path d="M33 28h14M33 32h11M33 36h13M16 41h31M16 44.5h24" stroke="#9db6dd" stroke-width="2" stroke-linecap="round"/>`,
	// Halaman/rute: dokumen web kecil dengan header biru.
	halaman:
		`<rect x="12" y="8" width="40" height="48" rx="5" fill="#eef4ff" stroke="#9cb9e6" stroke-width="1.5"/>` +
		`<path d="M12 13a5 5 0 0 1 5-5h30a5 5 0 0 1 5 5v5H12z" fill="#3d86f0"/>` +
		`<circle cx="18" cy="13" r="1.5" fill="#fff"/><circle cx="23" cy="13" r="1.5" fill="#fff" fill-opacity=".7"/>` +
		`<path d="M19 27h26M19 33h20M19 39h24M19 45h14" stroke="#8eaad6" stroke-width="2.4" stroke-linecap="round"/>`,
	// Tumpukan berkas statis.
	aset:
		tile('ga', '#f9c74f', '#d48806') +
		`<rect x="21" y="12" width="26" height="32" rx="3" fill="#fff" fill-opacity=".55"/>` +
		`<path d="M16 18a3 3 0 0 1 3-3h17l7 7v25a3 3 0 0 1-3 3H19a3 3 0 0 1-3-3z" fill="#fffbea"/>` +
		`<path d="M36 15v7h7" fill="#f3dfa0"/>` +
		`<text x="29.5" y="42" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="12" fill="#b07400">JS</text>`,
	// Berkas JS tunggal.
	js:
		`<path d="M14 10a4 4 0 0 1 4-4h20l12 12v36a4 4 0 0 1-4 4H18a4 4 0 0 1-4-4z" fill="#fff6d6" stroke="#e0b341" stroke-width="1.5"/>` +
		`<path d="M38 6v12h12" fill="#f6dd8a"/>` +
		`<rect x="18" y="30" width="28" height="18" rx="3" fill="#f7c843"/>` +
		`<text x="32" y="44" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="13" fill="#3b2a00">JS</text>`,
	// Rak server dengan LED.
	backend:
		tile('gb', '#7d8ca3', '#3c4a5f') +
		[14, 27, 40]
			.map(
				(y, i) =>
					`<rect x="12" y="${y}" width="40" height="10" rx="2.5" fill="#1d2633" stroke="#a9b6c9" stroke-opacity=".5"/>` +
					`<circle cx="18" cy="${y + 5}" r="1.8" fill="${i === 1 ? '#f5c451' : '#4ade80'}"/>` +
					`<circle cx="23" cy="${y + 5}" r="1.8" fill="#4ade80" fill-opacity=".55"/>` +
					`<path d="M31 ${y + 3.5}h16M31 ${y + 6.5}h16" stroke="#6b7a90" stroke-width="1.4"/>`
			)
			.join(''),
	// Dokumen + panah unggah.
	upload:
		tile('gu', '#ff9a4d', '#d9480f') +
		`<path d="M18 13a3 3 0 0 1 3-3h16l9 9v32a3 3 0 0 1-3 3H21a3 3 0 0 1-3-3z" fill="#fff4ec"/>` +
		`<path d="M37 10v9h9" fill="#ffd2b3"/>` +
		`<circle cx="32" cy="38" r="9" fill="#e8590c"/>` +
		`<path d="M32 43v-10M27.5 37.5 32 33l4.5 4.5" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>`,
	// Dokumen spesifikasi API (kertas putih + kurung kurawal).
	docs:
		`<path d="M13 9a4 4 0 0 1 4-4h22l13 13v38a4 4 0 0 1-4 4H17a4 4 0 0 1-4-4z" fill="#fbfcfe" stroke="#c9d3e0" stroke-width="1.5"/>` +
		`<path d="M39 5v13h13" fill="#e3e9f2"/>` +
		`<path d="M20 26h16M20 31h22M20 36h18" stroke="#b6c2d3" stroke-width="2" stroke-linecap="round"/>` +
		`<text x="32" y="52" text-anchor="middle" font-family="Consolas,Menlo,monospace" font-weight="700" font-size="13" fill="#2f9e44">{ }</text>`,
	// Avatar pengguna + kunci (sesi login).
	sesi:
		`<defs><linearGradient id="gp" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e3e7ee"/><stop offset="1" stop-color="#9aa5b5"/></linearGradient></defs>` +
		`<circle cx="32" cy="32" r="26" fill="url(#gp)"/><circle cx="32" cy="32" r="25.5" fill="none" stroke="#fff" stroke-opacity=".5"/>` +
		`<circle cx="32" cy="25" r="8.5" fill="#5b6678"/>` +
		`<path d="M16.5 49a16 16 0 0 1 31 0A25.6 25.6 0 0 1 32 58a25.6 25.6 0 0 1-15.5-9z" fill="#5b6678"/>` +
		`<circle cx="47" cy="47" r="9" fill="#2f9e44" stroke="#fff" stroke-width="2"/>` +
		`<circle cx="44.5" cy="47" r="2.6" fill="none" stroke="#fff" stroke-width="1.8"/><path d="M47 47h5.5M50.5 47v2.5" stroke="#fff" stroke-width="1.8"/>`,
	// Perisai pemindai (pemindai kerentanan, generik).
	zap:
		tile('gz', '#ff6b6b', '#c92a2a') +
		`<path d="M32 11 47 17v12c0 11-6.6 19-15 23-8.4-4-15-12-15-23V17z" fill="#fff"/>` +
		`<path d="M32 18v24M22 27h20" stroke="#ffc9c9" stroke-width="1.5"/>` +
		`<circle cx="32" cy="30" r="8" fill="none" stroke="#e03131" stroke-width="2"/>` +
		`<path d="M32 30 38 24" stroke="#e03131" stroke-width="2.4" stroke-linecap="round"/><circle cx="32" cy="30" r="2" fill="#e03131"/>`,
	// Crawler (laba-laba di jaring).
	katana:
		tile('gk', '#a78bfa', '#6d28d9') +
		`<path d="M32 12v40M12 32h40M18 18l28 28M46 18 18 46" stroke="#fff" stroke-opacity=".35" stroke-width="1.2"/>` +
		`<circle cx="32" cy="32" r="13" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="1.2"/>` +
		`<circle cx="32" cy="32" r="7" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="1.2"/>` +
		`<ellipse cx="32" cy="34" rx="4.5" ry="6" fill="#fff"/><circle cx="32" cy="26.5" r="3.2" fill="#fff"/>` +
		`<path d="M28 31l-7-4M28 34l-8 0M28 37l-7 5M36 31l7-4M36 34h8M36 37l7 5" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>`,
	// Alur proses bisnis.
	alur:
		tile('gl', '#b197fc', '#7048e8') +
		`<rect x="12" y="16" width="14" height="10" rx="2.5" fill="#fff"/><rect x="38" y="16" width="14" height="10" rx="2.5" fill="#fff"/>` +
		`<rect x="25" y="38" width="14" height="10" rx="2.5" fill="#fff"/>` +
		`<path d="M26 21h12M45 26v6H32v6" stroke="#fff" stroke-width="2.2" fill="none" stroke-linejoin="round"/>`,
	// Agen penguji SATYA (perisai + pemindai).
	penguji:
		tile('gq', '#3fa86b', '#1f6b3f') +
		`<path d="M32 10 49 16.5v13c0 11.5-7.2 19.6-17 24.5-9.8-4.9-17-13-17-24.5v-13z" fill="#0f2a1b" stroke="#c9f7d6" stroke-width="2"/>` +
		`<circle cx="32" cy="31" r="8.5" fill="none" stroke="#9fe08a" stroke-width="2.2"/><circle cx="32" cy="31" r="3" fill="#9fe08a"/>` +
		`<path d="M32 18v5M32 39v5M19 31h5M40 31h5" stroke="#9fe08a" stroke-width="2.2" stroke-linecap="round"/>`,
	// Payload request (amplop berisi data).
	payload:
		tile('gy', '#5c7cfa', '#364fc7') +
		`<rect x="12" y="20" width="40" height="27" rx="3.5" fill="#eef2ff"/>` +
		`<path d="M12.5 21.5 32 35l19.5-13.5" fill="none" stroke="#91a7ff" stroke-width="2.2" stroke-linejoin="round"/>` +
		`<rect x="35" y="12" width="20" height="13" rx="3" fill="#ffd43b" stroke="#fff" stroke-width="1.5"/>` +
		`<text x="45" y="21.5" text-anchor="middle" font-family="Consolas,Menlo,monospace" font-weight="700" font-size="8.5" fill="#5c3c00">{ }</text>`,
	// Gembok tertutup (kanal terenkripsi).
	gembok:
		`<rect x="14" y="28" width="36" height="28" rx="5" fill="#2f9e44" stroke="#d3f9d8" stroke-width="2"/>` +
		`<path d="M21 28v-7a11 11 0 0 1 22 0v7" fill="none" stroke="#d3f9d8" stroke-width="5" stroke-linecap="round"/>` +
		`<circle cx="32" cy="40" r="4" fill="#d3f9d8"/><path d="M32 42v6" stroke="#d3f9d8" stroke-width="3" stroke-linecap="round"/>`,
	// Gembok terbuka (kanal tanpa enkripsi).
	gembok_terbuka:
		`<rect x="14" y="28" width="36" height="28" rx="5" fill="#e03131" stroke="#ffe3e3" stroke-width="2"/>` +
		`<path d="M21 28v-7a11 11 0 0 1 21.6-3" fill="none" stroke="#ffe3e3" stroke-width="5" stroke-linecap="round"/>` +
		`<circle cx="32" cy="40" r="4" fill="#ffe3e3"/><path d="M32 42v6" stroke="#ffe3e3" stroke-width="3" stroke-linecap="round"/>`,
	// Titik uji (crosshair).
	titik:
		`<circle cx="32" cy="32" r="22" fill="#fff4d6" stroke="#f59f00" stroke-width="3"/>` +
		`<circle cx="32" cy="32" r="11" fill="none" stroke="#f59f00" stroke-width="3"/><circle cx="32" cy="32" r="3.5" fill="#f59f00"/>` +
		`<path d="M32 4v12M32 48v12M4 32h12M48 32h12" stroke="#f59f00" stroke-width="3" stroke-linecap="round"/>`
};

/** Warna pita metode HTTP pada ikon endpoint. */
export const WARNA_METODE: Record<string, [string, string]> = {
	GET: ['#38d9a9', '#0ca678'],
	POST: ['#ffd43b', '#f08c00'],
	PUT: ['#b197fc', '#7048e8'],
	PATCH: ['#b197fc', '#7048e8'],
	DELETE: ['#ff8787', '#e03131']
};

// Endpoint API: konektor bertanda metode.
function svgEndpoint(metode: string): string {
	const [a, b] = WARNA_METODE[metode.toUpperCase()] ?? ['#74c0fc', '#1c7ed6'];
	const id = `ge${metode.toUpperCase()}`;
	return (
		tile(id, a, b) +
		`<path d="M20 26h8v12h-8a6 6 0 0 1 0-12z" fill="#fff"/><path d="M14 32h-4" stroke="#fff" stroke-width="3" stroke-linecap="round"/>` +
		`<path d="M44 26h-8v12h8a6 6 0 0 0 0-12z" fill="#fff" fill-opacity=".85"/><path d="M50 32h4M36 29h-4M36 35h-4" stroke="#fff" stroke-width="3" stroke-linecap="round"/>` +
		`<text x="32" y="54" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="9" fill="#fff">${metode.toUpperCase().slice(0, 6)}</text>`
	);
}

/** Markup SVG lengkap sebuah ikon entitas. */
export function svgEntitas(jenis: JenisIkon, opsi: { metode?: string; ukuran?: number } = {}): string {
	const isi = jenis === 'endpoint' ? svgEndpoint(opsi.metode ?? 'GET') : SVG[jenis];
	const u = opsi.ukuran ?? 64;
	return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="${u}" height="${u}">${isi}</svg>`;
}

/** Segitiga peringatan risiko ZAP. */
export const WARNA_RISIKO: Record<string, string> = { High: '#ff4d4f', Medium: '#ffa940', Low: '#fadb14', Informational: '#8c9bab' };

/** Data URL ikon (untuk `<image href>` di dalam SVG). */
export function uriIkon(jenis: JenisIkon, metode?: string): string {
	return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgEntitas(jenis, { metode, ukuran: 128 }));
}

const cache = new Map<string, HTMLImageElement>();

/** Image (tercache) untuk kanvas; mungkin belum termuat pada pemanggilan pertama. */
export function gambarIkon(jenis: JenisIkon, metode?: string): HTMLImageElement {
	const kunci = jenis === 'endpoint' ? `endpoint:${metode ?? 'GET'}` : jenis;
	let img = cache.get(kunci);
	if (!img) {
		img = new Image();
		img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgEntitas(jenis, { metode, ukuran: 128 }));
		cache.set(kunci, img);
	}
	return img;
}
