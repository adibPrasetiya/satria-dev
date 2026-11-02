// Menambahkan ekstensi eksplisit pada import '#lib/...' (wajib untuk subpath imports Node).
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const root = 'src';
const lib = 'src/lib';
function* files(d) {
	for (const f of readdirSync(d)) {
		const p = join(d, f);
		if (statSync(p).isDirectory()) yield* files(p);
		else if (/\.(ts|svelte)$/.test(f)) yield p;
	}
}
function resolve(spec) {
	if (existsSync(join(lib, spec.slice(5) + '.ts'))) return spec + '.js';
	if (/\.(js|svelte|json|svg|css)$/.test(spec)) return spec;
	const rel = spec.slice('#lib/'.length);
	if (existsSync(join(lib, rel + '.ts'))) return spec + '.js';
	if (existsSync(join(lib, rel, 'index.ts'))) return spec + '/index.js';
	if (existsSync(join(lib, rel + '.svelte.ts'))) return spec.replace(/\.svelte$/, '') + '.svelte.js';
	return spec;
}
for (const f of files(root)) {
	const src = readFileSync(f, 'utf8');
	const out = src.replace(/(['"])(#lib\/[^'"]+)\1/g, (m, q, spec) => q + resolve(spec) + q);
	if (out !== src) {
		writeFileSync(f, out);
		console.log('fixed', f);
	}
}
