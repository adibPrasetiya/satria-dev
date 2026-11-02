// Mengolah foto latar halaman publik (di root proyek) menjadi, per adegan:
//   static/login/<latar>     — foto penuh terkompresi
//   static/login/<prajurit>  — potongan prajurit beralpha, kanvas sama persis dengan latar
// Foto sumber yang tidak ada di root dilewati (asetnya dianggap sudah dibangun sebelumnya).
// Jalankan: npm run login-assets
import { existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const ADEGAN = [
	{ sumber: 'Soldier Radio Watch at Military Base.png', latar: 'latar.webp', prajurit: 'prajurit.webp' },
	{ sumber: 'Kopassus.png', latar: 'latar-daftar.webp', prajurit: 'prajurit-daftar.webp' }
];

const here = dirname(fileURLToPath(import.meta.url));
const keluar = resolve(here, '../static/login');
mkdirSync(keluar, { recursive: true });

for (const adegan of ADEGAN) {
	const sumber = resolve(here, '../..', adegan.sumber);
	if (!existsSync(sumber)) {
		console.log(`Lewati "${adegan.sumber}" (tidak ada di root proyek).`);
		continue;
	}
	const { width, height } = await sharp(sumber).metadata();

	await sharp(sumber).webp({ quality: 82 }).toFile(resolve(keluar, adegan.latar));

	console.log(`Memisahkan prajurit dari "${adegan.sumber}" (model ONNX, unduhan pertama butuh waktu)…`);
	const sementara = resolve(tmpdir(), 'satya-potongan.png');
	execFileSync(process.execPath, [resolve(here, 'hapus-latar.mjs'), sumber, sementara], { stdio: 'inherit' });
	const potongan = readFileSync(sementara);
	rmSync(sementara);

	// Gabungkan RGB asli (lebih tajam dari keluaran model) dengan alpha model yang sedikit dihaluskan.
	const alpha = await sharp(potongan).resize(width, height).extractChannel('alpha').blur(0.8).raw().toBuffer();
	const rgb = await sharp(sumber).removeAlpha().raw().toBuffer();
	const rgba = Buffer.alloc(width * height * 4);
	for (let i = 0; i < width * height; i++) {
		rgba[i * 4] = rgb[i * 3];
		rgba[i * 4 + 1] = rgb[i * 3 + 1];
		rgba[i * 4 + 2] = rgb[i * 3 + 2];
		rgba[i * 4 + 3] = alpha[i];
	}
	await sharp(rgba, { raw: { width, height, channels: 4 } })
		.webp({ quality: 85, alphaQuality: 90 })
		.toFile(resolve(keluar, adegan.prajurit));

	console.log(`Selesai: ${width}x${height} -> ${adegan.latar}, ${adegan.prajurit}`);
}
