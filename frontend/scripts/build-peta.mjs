// Bangun data peta Indonesia (src/lib/data/peta-indonesia.json) dari GeoJSON batas provinsi.
//
//   node scripts/build-peta.mjs <adm1.geojson>
//
// Sumber saat ini: geoBoundaries gbOpen IDN ADM1 (simplified) — data © OpenStreetMap contributors,
// lisensi ODbL 1.0 (atribusi wajib tampil di peta). 34 provinsi (2017); bila tersedia data resmi BIG
// 38 provinsi, cukup jalankan ulang skrip ini dengan file tersebut (sesuaikan ISO_KE_BPS bila perlu).
//
// Hasil: path SVG yang sudah diproyeksikan (Mercator) ke kotak 1000 × TINGGI, disederhanakan
// (Douglas–Peucker) dan tanpa pulau yang terlalu kecil untuk terlihat. Proyeksi yang sama diulang di
// src/lib/peta/proyeksi.ts untuk menempatkan titik satuan — ubah keduanya bersamaan.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const BATAS = { lngMin: 94.5, lngMax: 141.5, latMin: -11.5, latMax: 6.5 };
const LEBAR = 1000;
const TOLERANSI = 0.12; // satuan kotak (±0,6 km): cukup halus untuk zoom 4×
const LUAS_MIN = 0.015; // pulau lebih kecil dari ini (satuan²) dibuang
const DESIMAL = 2;

// shapeISO (ISO 3166-2:ID) → kode wilayah Kemendagri/BPS (sama dengan PROVINSI di #lib/data/satuan).
const ISO_KE_BPS = {
	'ID-AC': '11', 'ID-SU': '12', 'ID-SB': '13', 'ID-RI': '14', 'ID-JA': '15', 'ID-SS': '16', 'ID-BE': '17',
	'ID-LA': '18', 'ID-BB': '19', 'ID-KR': '21', 'ID-JK': '31', 'ID-JB': '32', 'ID-JT': '33', 'ID-YO': '34',
	'ID-JI': '35', 'ID-BT': '36', 'ID-BA': '51', 'ID-NB': '52', 'ID-NT': '53', 'ID-KB': '61', 'ID-KT': '62',
	'ID-KS': '63', 'ID-KI': '64', 'ID-KU': '65', 'ID-SA': '71', 'ID-ST': '72', 'ID-SN': '73', 'ID-SG': '74',
	'ID-GO': '75', 'ID-SR': '76', 'ID-MA': '81', 'ID-MU': '82', 'ID-PA': '91', 'ID-PB': '92'
};

const rad = (d) => (d * Math.PI) / 180;
const mercY = (lat) => (Math.log(Math.tan(Math.PI / 4 + rad(lat) / 2)) * 180) / Math.PI;
const K = LEBAR / (BATAS.lngMax - BATAS.lngMin);
const ATAS = mercY(BATAS.latMax);
const TINGGI = Math.round((ATAS - mercY(BATAS.latMin)) * K);
const proyeksi = ([lng, lat]) => [(lng - BATAS.lngMin) * K, (ATAS - mercY(lat)) * K];

function jarakKeGaris([x, y], [x1, y1], [x2, y2]) {
	const dx = x2 - x1;
	const dy = y2 - y1;
	const d2 = dx * dx + dy * dy;
	const t = d2 ? Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / d2)) : 0;
	return Math.hypot(x - (x1 + t * dx), y - (y1 + t * dy));
}

/** Douglas–Peucker iteratif (cincin bisa ribuan titik; rekursi dalam bisa melimpah). */
function sederhanakan(titik, tol) {
	if (titik.length < 4) return titik;
	const simpan = new Uint8Array(titik.length);
	simpan[0] = simpan[titik.length - 1] = 1;
	const tumpuk = [[0, titik.length - 1]];
	while (tumpuk.length) {
		const [a, b] = tumpuk.pop();
		let maks = 0;
		let idx = -1;
		for (let i = a + 1; i < b; i++) {
			const d = jarakKeGaris(titik[i], titik[a], titik[b]);
			if (d > maks) [maks, idx] = [d, i];
		}
		if (maks > tol) {
			simpan[idx] = 1;
			tumpuk.push([a, idx], [idx, b]);
		}
	}
	return titik.filter((_, i) => simpan[i]);
}

const luas = (r) => Math.abs(r.reduce((s, [x, y], i) => { const [x2, y2] = r[(i + 1) % r.length]; return s + x * y2 - x2 * y; }, 0)) / 2;
const f = (n) => Number(n.toFixed(DESIMAL));

function keJalur(rings) {
	return rings
		.map((r) => {
			const [awal, ...sisa] = r;
			// Koordinat relatif (huruf kecil `l`) memangkas ukuran berkas ±40%. Selisih dihitung dari titik
			// sebelumnya yang SUDAH dibulatkan agar galat pembulatan tidak menumpuk sepanjang garis.
			let px = f(awal[0]);
			let py = f(awal[1]);
			const seg = sisa.map(([x, y]) => {
				const [rx, ry] = [f(x), f(y)];
				const s = `${f(rx - px)} ${f(ry - py)}`;
				[px, py] = [rx, ry];
				return s;
			});
			return `M${f(awal[0])} ${f(awal[1])}l${seg.join(' ')}z`;
		})
		.join('');
}

const masukan = process.argv[2];
if (!masukan) {
	console.error('Pakai: node scripts/build-peta.mjs <adm1.geojson>');
	process.exit(1);
}
const geo = JSON.parse(readFileSync(masukan, 'utf8'));
let jumlahTitik = 0;
const provinsi = geo.features.map((fitur) => {
	const iso = fitur.properties.shapeISO;
	const kode = ISO_KE_BPS[iso];
	if (!kode) throw new Error(`ISO tidak dikenal: ${iso}`);
	const poligon = fitur.geometry.type === 'Polygon' ? [fitur.geometry.coordinates] : fitur.geometry.coordinates;
	// Hanya cincin luar (lubang/danau diabaikan pada skala ini).
	const cincin = poligon
		.map((p) => sederhanakan(p[0].map(proyeksi), TOLERANSI))
		.filter((r) => r.length >= 4 && luas(r) >= LUAS_MIN);
	jumlahTitik += cincin.reduce((s, r) => s + r.length, 0);
	return { kode, iso, d: keJalur(cincin) };
}).sort((a, b) => a.kode.localeCompare(b.kode));

const keluaran = {
	sumber: 'geoBoundaries gbOpen IDN ADM1 — © OpenStreetMap contributors (ODbL 1.0)',
	batas: BATAS,
	lebar: LEBAR,
	tinggi: TINGGI,
	provinsi
};
const tujuan = fileURLToPath(new URL('../src/lib/data/peta-indonesia.json', import.meta.url));
writeFileSync(tujuan, JSON.stringify(keluaran));
console.log(`${provinsi.length} provinsi, ${jumlahTitik} titik, ${Math.round(JSON.stringify(keluaran).length / 1024)} KB → ${tujuan}`);
