// Membangkitkan pola loreng (SVG ubin mulus) bernuansa palet loreng TNI AD:
// dasar hijau daun, bercak cokelat tanah, hijau tua, hitam, dan sorot khaki.
// Pola dibuat prosedural (bukan salinan pola resmi). Hasil: static/loreng.svg
import { writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const UKURAN = 480;

// PRNG deterministik agar pola stabil antar build.
let benih = 20211005;
const acak = () => {
	benih = (benih * 1664525 + 1013904223) >>> 0;
	return benih / 4294967296;
};
const antara = (a, b) => a + acak() * (b - a);

const WARNA = {
	dasar: '#6e7a44',
	khaki: '#9c9467',
	cokelat: '#5f4129',
	hijauTua: '#2c3f26',
	hitam: '#1b1d18'
};

/** Bercak organik: titik keliling acak, dihaluskan Catmull-Rom menjadi kurva Bezier tertutup. */
function bercak(cx, cy, rx, ry, sudut, titik = 9, kasar = 0.35) {
	const pts = [];
	for (let i = 0; i < titik; i++) {
		const t = (i / titik) * Math.PI * 2 + antara(-0.25, 0.25);
		const r = 1 + antara(-kasar, kasar);
		const x = Math.cos(t) * rx * r;
		const y = Math.sin(t) * ry * r;
		pts.push([
			cx + x * Math.cos(sudut) - y * Math.sin(sudut),
			cy + x * Math.sin(sudut) + y * Math.cos(sudut)
		]);
	}
	const n = pts.length;
	const f = (v) => v.toFixed(1);
	let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
	for (let i = 0; i < n; i++) {
		const p0 = pts[(i - 1 + n) % n];
		const p1 = pts[i];
		const p2 = pts[(i + 1) % n];
		const p3 = pts[(i + 2) % n];
		const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
		const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
		d += `C${f(c1[0])} ${f(c1[1])} ${f(c2[0])} ${f(c2[1])} ${f(p2[0])} ${f(p2[1])}`;
	}
	return d + 'Z';
}

/** Gambar bercak di sembilan posisi geser agar ubin tersambung mulus di semua sisi. */
function mulus(d0) {
	return (cx, cy, rx, ...arg) => {
		const out = [];
		const d = d0(cx, cy, rx, ...arg);
		const jangkau = rx * 1.5;
		const geser = (v) => [0, ...(v < jangkau ? [UKURAN] : []), ...(v > UKURAN - jangkau ? [-UKURAN] : [])];
		for (const dx of geser(cx))
			for (const dy of geser(cy))
				out.push(dx || dy ? `<path transform="translate(${dx} ${dy})" d="${d}"/>` : `<path d="${d}"/>`);
		return out.join('');
	};
}
const blob = mulus(bercak);

function lapisan(warna, jumlah, [rMin, rMax], opsi = {}) {
	const { pipih = 0.55, kasar = 0.38, sudutMaks = 0.5 } = opsi;
	let isi = '';
	for (let i = 0; i < jumlah; i++) {
		const rx = antara(rMin, rMax);
		isi += blob(
			antara(0, UKURAN),
			antara(0, UKURAN),
			rx,
			rx * antara(pipih * 0.7, pipih * 1.3),
			antara(-sudutMaks, sudutMaks),
			Math.round(antara(9, 14)),
			kasar
		);
	}
	return `<g fill="${warna}">${isi}</g>`;
}

const svg = [
	`<svg xmlns="http://www.w3.org/2000/svg" width="${UKURAN}" height="${UKURAN}" viewBox="0 0 ${UKURAN} ${UKURAN}">`,
	`<rect width="${UKURAN}" height="${UKURAN}" fill="${WARNA.dasar}"/>`,
	lapisan(WARNA.khaki, 12, [22, 42], { pipih: 0.5, kasar: 0.45 }),
	lapisan(WARNA.cokelat, 22, [40, 78], { pipih: 0.5, kasar: 0.45 }),
	lapisan(WARNA.hijauTua, 24, [36, 68], { pipih: 0.55, kasar: 0.45 }),
	lapisan(WARNA.hitam, 18, [16, 36], { pipih: 0.42, kasar: 0.5 }),
	// Serpihan kecil untuk tekstur.
	lapisan(WARNA.cokelat, 26, [5, 12], { kasar: 0.55 }),
	lapisan(WARNA.hijauTua, 26, [5, 12], { kasar: 0.55 }),
	lapisan(WARNA.hitam, 22, [3, 8], { kasar: 0.55 }),
	lapisan(WARNA.khaki, 18, [3, 8], { kasar: 0.55 }),
	'</svg>'
].join('');

const out = resolve(here, '../static/loreng.svg');
writeFileSync(out, svg);
console.log(`Loreng: ${(svg.length / 1024).toFixed(1)} KB -> ${out}`);
