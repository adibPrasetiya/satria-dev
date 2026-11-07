// Skala warna indeks ketahanan: 0 (rawan, merah) → 55 (waspada, kuning) → 100 (tangguh, hijau).
const SKALA: [number, [number, number, number]][] = [
	[0, [255, 45, 45]],
	[35, [255, 120, 30]],
	[55, [255, 200, 40]],
	[75, [170, 230, 60]],
	[100, [70, 225, 110]]
];

export function warnaIndeks(n: number, alfa = 1): string {
	const i = Math.max(
		1,
		SKALA.findIndex(([b]) => n <= b)
	);
	const [b0, c0] = SKALA[i - 1];
	const [b1, c1] = SKALA[i] ?? SKALA[SKALA.length - 1];
	const t = b1 === b0 ? 0 : (n - b0) / (b1 - b0);
	const c = c0.map((v, j) => Math.round(v + (c1[j] - v) * t));
	return `rgb(${c[0]} ${c[1]} ${c[2]} / ${alfa})`;
}

/** Kategori indeks; ambang sama di panel, legenda, dan pusat indeks. */
export const statusIndeks = (n: number) => (n >= 75 ? 'Tangguh' : n >= 55 ? 'Waspada' : 'Rawan');
