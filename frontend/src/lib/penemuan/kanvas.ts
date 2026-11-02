// Palet & primitif kanvas bergaya SOC yang dipakai visualisasi operasi & graf penemuan.

export const HIJAU = '#9fe08a';
export const AMBER = '#f5c451';
export const MERAH = '#ff7b6b';
export const SIAN = '#7fe9d8';
export const UNGU = '#c39bff';
export const BIRU = '#7fb2ff';
export const EMAS = '#e8c467';

export function hexA(hex: string, a: number): string {
	const n = parseInt(hex.slice(1), 16);
	return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

export function drawHex(ctx: CanvasRenderingContext2D, r: number, c: string, lw: number) {
	ctx.beginPath();
	for (let i = 0; i < 6; i++) {
		const a = (Math.PI / 3) * i - Math.PI / 2;
		const x = Math.cos(a) * r, y = Math.sin(a) * r;
		i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
	}
	ctx.closePath(); ctx.strokeStyle = c; ctx.lineWidth = lw; ctx.stroke();
}

export function drawGrid(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, red: boolean, sp = 42) {
	ctx.strokeStyle = 'rgba(159,224,138,0.05)';
	ctx.lineWidth = 1;
	const off = red ? 0 : (t * 0.4) % sp;
	ctx.beginPath();
	for (let x = -sp + off; x < w + sp; x += sp) { ctx.moveTo(x, 0); ctx.lineTo(x, h); }
	for (let y = -sp + off; y < h + sp; y += sp) { ctx.moveTo(0, y); ctx.lineTo(w, y); }
	ctx.stroke();
}

/** Warna per metode HTTP. */
export function warnaMetode(m: string): string {
	switch (m.toUpperCase()) {
		case 'GET': return SIAN;
		case 'POST': return AMBER;
		case 'PUT':
		case 'PATCH': return UNGU;
		case 'DELETE': return MERAH;
		default: return HIJAU;
	}
}
