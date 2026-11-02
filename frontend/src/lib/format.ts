const fmtTanggal = new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium', timeStyle: 'short' });
const fmtRelatif = new Intl.RelativeTimeFormat('id-ID', { numeric: 'auto' });

export function tanggal(iso?: string): string {
	return iso ? fmtTanggal.format(new Date(iso)) : '—';
}

export function relatif(iso?: string): string {
	if (!iso) return '—';
	const detik = (new Date(iso).getTime() - Date.now()) / 1000;
	const skala: [Intl.RelativeTimeFormatUnit, number][] = [
		['day', 86400],
		['hour', 3600],
		['minute', 60]
	];
	for (const [unit, s] of skala) if (Math.abs(detik) >= s) return fmtRelatif.format(Math.round(detik / s), unit);
	return 'baru saja';
}

export function durasi(mulai?: string, selesai?: string, sekarang = Date.now()): string {
	if (!mulai) return '—';
	const ms = (selesai ? new Date(selesai).getTime() : sekarang) - new Date(mulai).getTime();
	const d = Math.round(ms / 1000);
	return d < 60 ? `${d} dtk` : `${Math.floor(d / 60)} mnt ${d % 60} dtk`;
}
