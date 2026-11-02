// Timeline adegan uji berulang: daftar babak bertempo tetap yang diputar melingkar (loop).
// Adegan menerima indeks babak `i` & progres `p` (0..1) lalu menurunkan posisi elemennya.

export interface Babak {
	id: string;
	/** Label pendek untuk stepper HUD. */
	label: string;
	/** Keterangan naratif di bilah bawah. */
	teks: string;
	/** Durasi babak (ms). */
	dur: number;
}

export interface Posisi {
	i: number;
	p: number;
}

export const totalDurasi = (babak: Babak[]) => babak.reduce((s, b) => s + b.dur, 0);

/** Posisi pada timeline untuk waktu `ms` sejak mulai (melingkar). */
export function posisi(babak: Babak[], ms: number): Posisi {
	const total = totalDurasi(babak);
	// Normalisasi ke [0, total): JS `%` bisa negatif (mis. frame rAF pertama sedikit sebelum mulai).
	let sisa = (((ms % total) + total) % total) || 0;
	for (let i = 0; i < babak.length; i++) {
		if (sisa < babak[i].dur) return { i, p: sisa / babak[i].dur };
		sisa -= babak[i].dur;
	}
	return { i: babak.length - 1, p: 1 };
}

export const jepit = (u: number) => Math.max(0, Math.min(1, u));
/** Smoothstep. */
export const halus = (u: number) => {
	const v = jepit(u);
	return v * v * (3 - 2 * v);
};
/** Progres sub-rentang [a, b] dari progres babak. */
export const antara = (p: number, a: number, b: number) => jepit((p - a) / (b - a));
export const lerp = (a: number, b: number, u: number) => a + (b - a) * u;

/** Titik pada kurva kuadrat Bézier. */
export function kuadrat(a: { x: number; y: number }, k: { x: number; y: number }, b: { x: number; y: number }, u: number) {
	const v = 1 - u;
	return { x: v * v * a.x + 2 * v * u * k.x + u * u * b.x, y: v * v * a.y + 2 * v * u * k.y + u * u * b.y };
}

/** Titik pada polyline (bagian sama panjang per segmen). */
export function sepanjang(titik: { x: number; y: number }[], u: number) {
	const n = titik.length - 1;
	const s = Math.min(n - 1, Math.floor(jepit(u) * n));
	const e = halus(jepit(u) * n - s);
	return { x: lerp(titik[s].x, titik[s + 1].x, e), y: lerp(titik[s].y, titik[s + 1].y, e) };
}
