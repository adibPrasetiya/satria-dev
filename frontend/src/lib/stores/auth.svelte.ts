// Profil pengguna yang sedang masuk (untuk tampilan & guard peran).
// Token sesi backend dikelola terpisah di api/http.ts.
import { api } from '#lib/api/client.js';
import { EVENT_SESI_BERAKHIR } from '#lib/api/http.js';
import { setSesiMock } from '#lib/api/mock/index.js';
import type { Pengguna, Peran } from '#lib/types.js';

const KUNCI = 'satya-sesi';

function muat(): Pengguna | null {
	try {
		const raw = localStorage.getItem(KUNCI);
		return raw ? (JSON.parse(raw) as Pengguna) : null;
	} catch {
		return null;
	}
}

class Auth {
	pengguna = $state<Pengguna | null>(muat());

	constructor() {
		setSesiMock(this.pengguna?.id ?? null);
		// Refresh token ditolak backend (kedaluwarsa/dicabut) → keluar dari tampilan juga.
		if (typeof window !== 'undefined') window.addEventListener(EVENT_SESI_BERAKHIR, () => this.hapusSesi());
	}

	masuk(p: Pengguna) {
		this.pengguna = p;
		setSesiMock(p.id);
		try {
			localStorage.setItem(KUNCI, JSON.stringify(p));
		} catch {
			// abaikan
		}
	}

	keluar() {
		// Cabut sesi di server tanpa menunggu; tampilan langsung keluar.
		api.logout().catch(() => {});
		this.hapusSesi();
	}

	private hapusSesi() {
		this.pengguna = null;
		setSesiMock(null);
		try {
			localStorage.removeItem(KUNCI);
		} catch {
			// abaikan
		}
	}

	punya(...peran: Peran[]) {
		return !!this.pengguna && peran.includes(this.pengguna.peran);
	}

	// Matriks hak akses (selaras dengan requireRole di backend):
	// - pemilik : mendaftarkan/mengubah aplikasi satuannya & melihat hasil pengujian.
	// - asesor  : melakukan pengujian (persiapan, mulai, hentikan) — tanpa mendaftarkan aplikasi.
	// - admin   : semua akses. Peta/dasbor terbuka untuk semua peran.
	get bisaMendaftarkan() {
		return this.punya(...PERAN_PENDAFTAR);
	}

	get bisaMenguji() {
		return this.punya(...PERAN_PENGUJI);
	}
}

export const PERAN_PENDAFTAR: Peran[] = ['pemilik', 'admin'];
export const PERAN_PENGUJI: Peran[] = ['asesor', 'admin'];

export const auth = new Auth();

export const LABEL_PERAN: Record<Peran, string> = {
	pemilik: 'Pemilik Aplikasi',
	asesor: 'Asesor',
	admin: 'Administrator'
};

/** Inisial untuk avatar: buang pangkat & korps di depan nama (mis. "Kapten Czi."), ambil 2 huruf awal. */
export function inisialNama(nama = ''): string {
	return nama
		.replace(/^[A-Za-z]+\.?\s+[A-Za-z]+\.\s+/, '')
		.split(' ')
		.filter(Boolean)
		.slice(0, 2)
		.map((s) => s[0].toUpperCase())
		.join('');
}
