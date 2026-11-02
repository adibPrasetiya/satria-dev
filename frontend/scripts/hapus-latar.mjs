// Proses terpisah: background removal (jangan dimuat bersama sharp milik proyek — konflik libvips).
// Pemakaian: node scripts/hapus-latar.mjs <masukan.png> <keluaran.png>
import { readFileSync, writeFileSync } from 'node:fs';
import { removeBackground } from '@imgly/background-removal-node';

const [, , masuk, keluar] = process.argv;
const blob = await removeBackground(new Blob([readFileSync(masuk)], { type: 'image/png' }), {
	model: 'medium',
	output: { format: 'image/png' }
});
writeFileSync(keluar, Buffer.from(await blob.arrayBuffer()));
