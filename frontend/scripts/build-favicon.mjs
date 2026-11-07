// Bangun favicon SATRIA dari lambang (static/satria-lambang.png, potret) menjadi ikon persegi:
//   static/favicon-32.png        — tab browser (latar transparan)
//   static/favicon-192.png       — ikon resolusi tinggi / pintasan Android (latar transparan)
//   static/apple-touch-icon.png  — 180×180 berlatar gelap (iOS tidak mendukung transparansi)
// Jalankan: node scripts/build-favicon.mjs  (ulang bila lambang berubah)
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const statis = resolve(dirname(fileURLToPath(import.meta.url)), '../static');
const lambang = resolve(statis, 'satria-lambang.png');
const TRANSPARAN = { r: 0, g: 0, b: 0, alpha: 0 };
const GELAP = { r: 11, g: 15, b: 12, alpha: 1 };

async function ikon(ukuran, nama, { latar = TRANSPARAN, isi = 0.92 } = {}) {
	// Lambang dimuat setinggi `isi` × kanvas, dipusatkan pada kanvas persegi.
	const tinggi = Math.round(ukuran * isi);
	const gambar = await sharp(lambang).resize({ height: tinggi, fit: 'inside' }).toBuffer();
	await sharp({ create: { width: ukuran, height: ukuran, channels: 4, background: latar } })
		.composite([{ input: gambar, gravity: 'center' }])
		.png({ compressionLevel: 9 })
		.toFile(resolve(statis, nama));
	console.log(`${nama} ${ukuran}×${ukuran}`);
}

await ikon(32, 'favicon-32.png', { isi: 1 });
await ikon(192, 'favicon-192.png');
await ikon(180, 'apple-touch-icon.png', { latar: GELAP, isi: 0.74 });
