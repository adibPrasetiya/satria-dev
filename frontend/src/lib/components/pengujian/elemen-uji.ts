// Palet & ikon bersama adegan uji (AdeganUmum). Warna mengikuti bahasa
// desain web; ikon memakai glyph generik dari penemuan (bukan logo merek pihak mana pun).
import { uriIkon } from '#lib/penemuan/ikon-entitas.js';

export const WARNA = {
	hijau: '#9fe08a',
	sian: '#7fe9d8',
	merah: '#ff7b6b',
	kuning: '#f5c451',
	biru: '#748ffc',
	redup: 'rgba(255,255,255,0.18)'
} as const;

export const IKON = {
	penguji: uriIkon('penguji'),
	backend: uriIkon('backend'),
	frontend: uriIkon('frontend'),
	payload: uriIkon('payload'),
	gembok: uriIkon('gembok'),
	gembokBuka: uriIkon('gembok_terbuka')
} as const;
