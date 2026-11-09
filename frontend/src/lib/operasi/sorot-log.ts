// Pewarnaan sintaks baris log operasi: ID metode, metode HTTP, URL, status HTTP, kata kunci
// verdict, dan durasi. Dipakai panel log halaman operasi.
import type { LogScan } from '#lib/types.js';

export type Level = LogScan['level'];

export const LEVEL: { k: Level; label: string; kelas: string }[] = [
	{ k: 'info', label: 'INFO', kelas: 'text-[#62a0ea]' },
	{ k: 'peringatan', label: 'WARN', kelas: 'text-[#f6d32d]' },
	{ k: 'galat', label: 'ERROR', kelas: 'text-[#f66151]' }
];
export const LABEL_LEVEL = Object.fromEntries(LEVEL.map((l) => [l.k, l])) as Record<
	Level,
	(typeof LEVEL)[number]
>;

export type Token = { t: string; k?: string };

const RX =
	/(▶|■|→|←|•|↳)|(\b[A-Z]{3,5}-\d+\.\d+-T\d+\b)|(\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b)|(https?:\/\/[^\s·,)]+)|(\bHTTP \d{3}\b)|(\b(?:GAGAL|gagal|FAILED)\b)|(\b(?:Lulus|lulus|LULUS|berhasil)\b)|(\b(?:menunggu tinjauan asesor|Belum Terverifikasi|tidak_dapat_diverifikasi)\b)|(\d+(?:[.,]\d+)?\s?(?:ms|s|detik))/g;
const KELAS = [
	'',
	'text-[#c0bfbc]',
	'font-bold text-[#5bc8af]',
	'text-[#dc8add]',
	'text-[#62a0ea] underline decoration-[#62a0ea]/40 underline-offset-2',
	'',
	'font-bold text-[#f66151]',
	'text-[#8ff0a4]',
	'text-[#f6d32d]',
	'text-[#9a9996]'
];

function warnaStatus(teks: string): string {
	const n = Number(teks.slice(5));
	return n < 300
		? 'text-[#8ff0a4]'
		: n < 400
			? 'text-[#f6d32d]'
			: n < 500
				? 'text-[#ffa348]'
				: 'text-[#f66151]';
}

export function tokenisasi(s: string): Token[] {
	const out: Token[] = [];
	let i = 0;
	for (const m of s.matchAll(RX)) {
		if (m.index! > i) out.push({ t: s.slice(i, m.index) });
		const g = m.slice(1).findIndex((x) => x !== undefined) + 1;
		out.push({ t: m[0], k: g === 5 ? warnaStatus(m[0]) : KELAS[g] });
		i = m.index! + m[0].length;
	}
	if (i < s.length) out.push({ t: s.slice(i) });
	return out;
}

export const jamLog = (w: string) => new Date(w).toLocaleTimeString('id-ID', { hour12: false });

/** Baris rekapitulasi/pemisah ditebalkan. */
export const barisTebal = (p: string) =>
	/^(─|═|-{3,})|REKAPITULASI|Total metode diuji/.test(p.trim());
