// Utilitas TOTP (RFC 6238) di browser: parse URI otpauth dari QR, validasi seed base32,
// dan pembangkit kode untuk pratinjau. Selaras dengan worker/satya_worker/mfa.py
// (normalisasi & regex base32 yang sama) agar kode pratinjau = kode yang dipakai mesin uji.

export type AlgoritmaTotp = 'SHA1' | 'SHA256' | 'SHA512';

export interface ParameterTotp {
	digits: number;
	period: number;
	algoritma: AlgoritmaTotp;
}

export interface HasilOtpauth extends ParameterTotp {
	secret: string;
	issuer: string;
	label: string;
}

export const TOTP_DEFAULT: ParameterTotp = { digits: 6, period: 30, algoritma: 'SHA1' };

const BASE32 = /^[A-Z2-7]+=*$/;
const ALFABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

/** Buang spasi/strip & jadikan huruf besar (format QR/aplikasi sering berspasi). */
export function normalisasiSecret(s: string | undefined | null): string {
	return (s ?? '').replace(/[\s-]/g, '').toUpperCase();
}

export function secretValid(s: string | undefined | null): boolean {
	const n = normalisasiSecret(s);
	return n.length > 0 && BASE32.test(n);
}

export function parameterStandar(p: Partial<ParameterTotp>): boolean {
	return (
		(p.digits ?? 6) === 6 && (p.period ?? 30) === 30 && (p.algoritma ?? 'SHA1') === 'SHA1'
	);
}

/** Parse `otpauth://totp/Label?secret=…&issuer=…&digits=…&period=…&algorithm=…`.
 *  Mengembalikan null bila bukan URI TOTP yang valid (HOTP ditolak). */
export function parseOtpauth(teks: string): HasilOtpauth | null {
	const t = teks.trim();
	if (!/^otpauth:\/\//i.test(t)) return null;
	let url: URL;
	try {
		url = new URL(t);
	} catch {
		return null;
	}
	if (url.hostname.toLowerCase() !== 'totp') return null;
	const q = url.searchParams;
	const secret = normalisasiSecret(q.get('secret'));
	if (!secretValid(secret)) return null;
	const digits = Number(q.get('digits') ?? 6);
	const period = Number(q.get('period') ?? 30);
	const alg = (q.get('algorithm') ?? 'SHA1').toUpperCase();
	if (![6, 7, 8].includes(digits) || !(period >= 15 && period <= 120)) return null;
	if (alg !== 'SHA1' && alg !== 'SHA256' && alg !== 'SHA512') return null;
	const label = decodeURIComponent(url.pathname.replace(/^\/+/, ''));
	return {
		secret,
		digits,
		period,
		algoritma: alg,
		issuer: q.get('issuer') ?? (label.includes(':') ? label.split(':')[0] : ''),
		label
	};
}

function decodeBase32(s: string): Uint8Array<ArrayBuffer> {
	const n = normalisasiSecret(s).replace(/=+$/, '');
	let bits = 0;
	let nilai = 0;
	const out: number[] = [];
	for (const c of n) {
		const i = ALFABET.indexOf(c);
		if (i < 0) throw new Error('Seed bukan base32');
		nilai = (nilai << 5) | i;
		bits += 5;
		if (bits >= 8) {
			out.push((nilai >>> (bits - 8)) & 0xff);
			bits -= 8;
		}
	}
	return new Uint8Array(out);
}

const HASH = { SHA1: 'SHA-1', SHA256: 'SHA-256', SHA512: 'SHA-512' } as const;

/** Kode TOTP pada waktu `ms` (default sekarang) + sisa detik jendela berjalan. */
export async function kodeTotp(
	secret: string,
	p: ParameterTotp = TOTP_DEFAULT,
	ms: number = Date.now()
): Promise<{ kode: string; sisaDetik: number }> {
	const detik = Math.floor(ms / 1000);
	const counter = Math.floor(detik / p.period);
	const pesan = new ArrayBuffer(8);
	const v = new DataView(pesan);
	v.setUint32(0, Math.floor(counter / 2 ** 32));
	v.setUint32(4, counter >>> 0);
	const kunci = await crypto.subtle.importKey(
		'raw',
		decodeBase32(secret),
		{ name: 'HMAC', hash: HASH[p.algoritma] },
		false,
		['sign']
	);
	const h = new Uint8Array(await crypto.subtle.sign('HMAC', kunci, pesan));
	const off = h[h.length - 1] & 0x0f;
	const bin = ((h[off] & 0x7f) << 24) | (h[off + 1] << 16) | (h[off + 2] << 8) | h[off + 3];
	const kode = String(bin % 10 ** p.digits).padStart(p.digits, '0');
	return { kode, sisaDetik: p.period - (detik % p.period) };
}
