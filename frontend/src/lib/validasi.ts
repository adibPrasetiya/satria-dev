// Validasi form halaman publik. Kebijakan kata sandi mengikuti parameter kontrol BSSN 1.3
// di katalog (panjang minimum 8; huruf besar, huruf kecil, angka, simbol).
const POLA_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function galatEmail(email: string): string | null {
	if (!email.trim()) return 'Email dinas wajib diisi.';
	if (!POLA_EMAIL.test(email.trim())) return 'Format email belum benar.';
	return null;
}

export function bukanEmailDinas(email: string): boolean {
	return !galatEmail(email) && !/\.(mil|go)\.id$/i.test(email.trim());
}

export const SYARAT_SANDI: { label: string; cek: (s: string) => boolean }[] = [
	{ label: 'Minimal 8 karakter', cek: (s) => s.length >= 8 },
	{ label: 'Huruf besar & kecil', cek: (s) => /[A-Z]/.test(s) && /[a-z]/.test(s) },
	{ label: 'Angka', cek: (s) => /\d/.test(s) },
	{ label: 'Simbol', cek: (s) => /[^A-Za-z0-9]/.test(s) }
];
