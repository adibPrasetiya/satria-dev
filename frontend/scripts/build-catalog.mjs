// Konversi katalog kontrol BSSN (YAML) menjadi JSON yang dibaca frontend.
// Nantinya backend Express menyajikan JSON yang sama di GET /api/catalog.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load } from 'js-yaml';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../../controls/bssn_web.yaml');
const out = resolve(here, '../src/lib/data/catalog.json');

const katalog = load(readFileSync(src, 'utf8'));
const def = katalog.default_metode ?? {};

let jumlahKontrol = 0;
let jumlahMetode = 0;
for (const fungsi of katalog.fungsi_keamanan) {
	for (const kontrol of fungsi.kontrol) {
		jumlahKontrol++;
		kontrol.metode_pengujian = kontrol.metode_pengujian.map((m) => {
			jumlahMetode++;
			return { ...def, ...m, severity: m.severity ?? kontrol.severity_default };
		});
	}
}

mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(katalog, null, '\t'));
console.log(
	`Katalog: ${katalog.fungsi_keamanan.length} fungsi, ${jumlahKontrol} kontrol, ${jumlahMetode} metode -> ${out}`
);
