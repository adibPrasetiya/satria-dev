<svelte:options namespace="svg" />

<script lang="ts" module>
	// Adegan Kontrol Akses (berulang): dua akun (A biasa & B) login → akun A mencoba membaca objek
	// milik akun B (IDOR / akses horizontal) → akun A mencoba fungsi admin (akses vertikal) →
	// mengevaluasi apakah server menolak (403). Elemen SVG murni; gaya teks diwarisi dari .panggung-uji.
	import type { Babak } from '#lib/pengujian/timeline.js';

	export const babak: Babak[] = [
		{ id: 'peran', label: 'Dua akun', teks: 'Masuk dengan dua akun uji (A biasa & B)', dur: 2400 },
		{ id: 'objek', label: 'IDOR', teks: 'Akun A meminta objek milik akun B (akses horizontal)', dur: 2800 },
		{ id: 'admin', label: 'Admin', teks: 'Akun A mencoba fungsi administrator (akses vertikal)', dur: 2600 },
		{ id: 'nilai', label: 'Evaluasi', teks: 'Memeriksa apakah server menolak akses tak berhak (403)', dur: 2400 }
	];
</script>

<script lang="ts">
	import { halus, lerp } from '#lib/pengujian/timeline.js';
	import { WARNA, IKON } from './elemen-uji.js';
	import NodeBackend from './NodeBackend.svelte';

	let { i, p }: { i: number; p: number } = $props();

	// Tata letak tetap (ruang viewBox 1000×520). Dua kartu pengguna di kiri, API di kanan.
	const CA = { x: 96, y: 70, w: 252, h: 150 };
	const CB = { x: 96, y: 300, w: 252, h: 150 };
	const API = { x: 840, y: 250 };
	const keluarA = { x: CA.x + CA.w, y: CA.y + CA.h / 2 };
	const dock = { x: API.x - 75, y: API.y };

	const aktifA = $derived(i === 0 || i >= 1); // A selalu pelaku
	const aktifB = $derived(i === 0); // B hanya pemilik objek (login di babak peran)
	const adaKanal = $derived(i === 1 || i === 2);

	// Paket dari A → API (percobaan akses tak berhak).
	const paket = $derived.by(() => {
		if (!adaKanal) return null;
		const u = halus(p);
		return { x: lerp(keluarA.x, dock.x, u), y: lerp(keluarA.y, dock.y, u) };
	});
	const jalurPaket = $derived(i === 1 ? 'GET /orders/‹B›' : 'GET /admin');
	const menilai = $derived(i === 3);
</script>

<!-- kanal percobaan akses A → API -->
{#if adaKanal}
	<line x1={keluarA.x} y1={keluarA.y} x2={dock.x} y2={dock.y} stroke={WARNA.kuning} stroke-width="1.8" stroke-dasharray="6 5" opacity="0.6" />
{/if}

<!-- kartu akun A (pelaku) -->
<g opacity={aktifA ? 1 : 0.5}>
	<rect x={CA.x} y={CA.y} width={CA.w} height={CA.h} rx="12" fill="#f4f8ff" stroke={i >= 1 ? WARNA.kuning : '#c3d6f0'} stroke-width={i >= 1 ? 2 : 1.3} />
	<path d="M{CA.x} {CA.y + 15} a15 15 0 0 1 15-15 h{CA.w - 30} a15 15 0 0 1 15 15 v14 h-{CA.w} z" fill="#d6e4fb" />
	<text x={CA.x + 16} y={CA.y + 19} class="lbl-win-judul" fill="#5f7696">Akun A — pengguna biasa</text>
	<circle cx={CA.x + 34} cy={CA.y + 64} r="16" fill="#e4edfb" stroke="#b9cdee" />
	<path d="M{CA.x + 34} {CA.y + 58} m-6 10 a6 6 0 0 1 12 0" fill="#9db6dd" /><circle cx={CA.x + 34} cy={CA.y + 60} r="4.5" fill="#9db6dd" />
	<text x={CA.x + 62} y={CA.y + 60} class="lbl-form" fill="#3a4a66">sesi A aktif</text>
	<text x={CA.x + 62} y={CA.y + 80} class="lbl-form-mono" fill="rgba(90,107,134,0.75)">id objek: A</text>
	{#if i >= 1}
		<text x={CA.x + 16} y={CA.y + CA.h - 14} class="lbl-kecil" fill={WARNA.kuning}>{i === 1 ? 'mencoba objek milik B' : 'mencoba fungsi admin'}</text>
	{/if}
</g>

<!-- kartu akun B (pemilik objek) -->
<g opacity={aktifB ? 1 : 0.65}>
	<rect x={CB.x} y={CB.y} width={CB.w} height={CB.h} rx="12" fill="#f4f8ff" stroke={i === 1 ? WARNA.sian : '#c3d6f0'} stroke-width={i === 1 ? 2 : 1.3} />
	<path d="M{CB.x} {CB.y + 15} a15 15 0 0 1 15-15 h{CB.w - 30} a15 15 0 0 1 15 15 v14 h-{CB.w} z" fill="#d6e4fb" />
	<text x={CB.x + 16} y={CB.y + 19} class="lbl-win-judul" fill="#5f7696">Akun B — pemilik objek</text>
	<rect x={CB.x + 18} y={CB.y + 44} width={CB.w - 36} height="40" rx="8" fill="#eef4fe" stroke={i === 1 ? WARNA.sian : '#cadcf6'} stroke-width="1.2" />
	<image href={IKON.gembok} x={CB.x + 28} y={CB.y + 52} width="22" height="22" />
	<text x={CB.x + 58} y={CB.y + 60} class="lbl-form" fill="#3a4a66">objek /orders/‹B›</text>
	<text x={CB.x + 58} y={CB.y + 78} class="lbl-form-mono" fill="rgba(90,107,134,0.75)">rahasia milik B</text>
</g>

<!-- node Backend (API) -->
<NodeBackend x={API.x} y={API.y} label="Backend" sub={i === 2 ? 'fungsi admin' : 'otorisasi objek'} denyut={menilai} />

<!-- paket percobaan akses -->
{#if paket}
	<g transform="translate({paket.x}, {paket.y})">
		<rect x="-88" y="-13" width="176" height="26" rx="8" fill="#0e1317" stroke={WARNA.kuning} stroke-width="1.6" />
		<rect x="-82" y="-7.5" width="34" height="15" rx="4" fill="rgba(245,196,81,0.15)" />
		<text x="-65" y="4" class="lbl-badge" fill={WARNA.kuning}>GET</text>
		<text x="26" y="4.5" class="lbl-paket" fill={WARNA.kuning}>{i === 1 ? '/orders/‹B›' : '/admin'}</text>
	</g>
{/if}

<!-- evaluasi: akses tak berhak ditolak -->
{#if menilai}
	<g transform="translate({API.x}, {API.y - 86})" class="muncul">
		<rect x="-98" y="-14" width="196" height="26" rx="7" fill="rgba(159,224,138,0.12)" stroke={WARNA.hijau} />
		<text y="4" class="lbl-chip" fill={WARNA.hijau}>403 · akses tak berhak ditolak</text>
	</g>
{/if}
