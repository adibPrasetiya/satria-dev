<svelte:options namespace="svg" />

<script lang="ts" module>
	// Adegan Manajemen Sesi (berulang): login → server menerbitkan token sesi → logout →
	// memakai ulang token LAMA ke area terautentikasi → mengevaluasi apakah token lama ditolak.
	// Elemen SVG murni; ditempatkan di dalam <svg> induk (VisualisasiUji). Gaya teks diwarisi
	// dari .panggung-uji.
	import type { Babak } from '#lib/pengujian/timeline.js';

	export const babak: Babak[] = [
		{ id: 'login', label: 'Login', teks: 'Masuk dengan akun uji — meminta penerbitan sesi', dur: 2400 },
		{ id: 'token', label: 'Token', teks: 'Server menerbitkan token sesi setelah login berhasil', dur: 2200 },
		{ id: 'logout', label: 'Logout', teks: 'Mengakhiri sesi melalui endpoint logout', dur: 2200 },
		{ id: 'pakai_ulang', label: 'Pakai ulang', teks: 'Memakai ulang token LAMA ke area terautentikasi', dur: 2600 },
		{ id: 'nilai', label: 'Evaluasi', teks: 'Memeriksa apakah token lama ditolak (401/403)', dur: 2400 }
	];
</script>

<script lang="ts">
	import { halus, lerp } from '#lib/pengujian/timeline.js';
	import { WARNA, IKON } from './elemen-uji.js';
	import NodeBackend from './NodeBackend.svelte';

	let { i, p }: { i: number; p: number } = $props();

	// Tata letak tetap (ruang viewBox 1000×520).
	const B = { x: 110, y: 118, w: 340, h: 234 };
	const API = { x: 848, y: 210 };
	const keluar = { x: B.x + B.w, y: 224 };
	const dock = { x: API.x - 75, y: API.y };
	const tengah = { x: (keluar.x + dock.x) / 2, y: (keluar.y + dock.y) / 2 };

	const url = $derived(['/auth/login', '/auth/login', '/auth/logout', '/auth/me', '/auth/me'][i] ?? '/auth/me');
	const adaToken = $derived(i >= 1); // token sesi terbit
	const tokenLama = $derived(i >= 2); // setelah logout token menjadi "lama"
	const adaKanal = $derived(i === 0 || i === 2 || i === 3);

	// Paket pada kanal: browser → API (login/logout/pakai ulang).
	const paket = $derived.by(() => {
		if (!adaKanal) return null;
		const u = halus(p);
		return { x: lerp(keluar.x, dock.x, u), y: lerp(keluar.y, dock.y, u) };
	});
	const metodePaket = $derived(i === 3 ? 'GET' : 'POST');
	const warnaPaket = $derived(i === 3 ? WARNA.kuning : i === 2 ? WARNA.merah : WARNA.hijau);
	const menilai = $derived(i === 4);
</script>

<!-- kanal HTTPS browser ⇄ API -->
{#if adaKanal}
	<line x1={keluar.x} y1={keluar.y} x2={dock.x} y2={dock.y} stroke={WARNA.hijau} stroke-width="2.2" opacity="0.6" />
	<image href={IKON.gembok} x={tengah.x - 13} y={tengah.y - 13} width="26" height="26" />
{/if}

<!-- jendela browser + area sesi -->
<g>
	<rect x={B.x} y={B.y} width={B.w} height={B.h} rx="12" fill="#f4f8ff" />
	<path d="M{B.x} {B.y + 16} a16 16 0 0 1 16-16 h{B.w - 32} a16 16 0 0 1 16 16 v16 h-{B.w} z" fill="#d6e4fb" />
	<circle cx={B.x + 18} cy={B.y + 16} r="3.4" fill="#ff5f57" />
	<circle cx={B.x + 32} cy={B.y + 16} r="3.4" fill="#febc2e" />
	<circle cx={B.x + 46} cy={B.y + 16} r="3.4" fill="#28c840" />
	<rect x={B.x + 70} y={B.y + 9} width={B.w - 160} height="14" rx="7" fill="#fff" />
	<text x={B.x + 82} y={B.y + 19} class="lbl-url-browser">{url}</text>

	<!-- status sesi di dalam jendela -->
	<text x={B.x + 30} y={B.y + 66} class="lbl-form">Status sesi</text>
	{#if i === 0}
		<text x={B.x + 30} y={B.y + 92} class="lbl-form-mono" fill="rgba(90,107,134,0.8)">mengirim kredensial…</text>
	{:else if i === 2}
		<text x={B.x + 30} y={B.y + 92} class="lbl-form-mono" fill={WARNA.merah}>sesi diakhiri (logout)</text>
	{:else}
		<text x={B.x + 30} y={B.y + 92} class="lbl-form-mono" fill={tokenLama ? WARNA.kuning : WARNA.hijau}>{tokenLama ? 'memakai token lama' : 'sesi aktif'}</text>
	{/if}

	<!-- kartu token sesi -->
	{#if adaToken}
		<g transform="translate({B.x + 30}, {B.y + 120})" class="muncul">
			<rect width="280" height="54" rx="8" fill="#0e1317" stroke={tokenLama ? WARNA.kuning : WARNA.hijau} stroke-width="1.3" />
			<image href={IKON.gembok} x="12" y="14" width="24" height="24" />
			<text x="46" y="24" class="lbl-chip" fill={tokenLama ? WARNA.kuning : WARNA.hijau} text-anchor="start">TOKEN SESI {tokenLama ? '(lama)' : ''}</text>
			<text x="46" y="42" class="lbl-form-mono" fill="rgba(255,255,255,0.55)">eyJhbGciOi␣•••••••</text>
			{#if tokenLama}
				<line x1="12" y1="46" x2="268" y2="10" stroke={WARNA.kuning} stroke-width="1.2" opacity="0.5" stroke-dasharray="3 3" />
			{/if}
		</g>
	{/if}
</g>

<!-- node Backend (server sesi) -->
<NodeBackend x={API.x} y={API.y} label="Backend" sub="sesi & token" denyut={menilai} />

<!-- paket pada kanal -->
{#if paket}
	<g transform="translate({paket.x}, {paket.y})">
		<rect x="-82" y="-13" width="164" height="26" rx="8" fill="#0e1317" stroke={warnaPaket} stroke-width="1.6" />
		<rect x="-76" y="-7.5" width="38" height="15" rx="4" fill="rgba(255,255,255,0.08)" />
		<text x="-57" y="4" class="lbl-badge" fill={warnaPaket}>{metodePaket}</text>
		<text x="28" y="4.5" class="lbl-paket" fill={warnaPaket}>{url}{i === 3 ? ' ◇ token lama' : ''}</text>
	</g>
{/if}

<!-- evaluasi: token lama ditolak -->
{#if menilai}
	<g transform="translate({API.x}, {API.y - 82})" class="muncul">
		<rect x="-92" y="-14" width="184" height="26" rx="7" fill="rgba(255,123,107,0.12)" stroke={WARNA.merah} />
		<text y="4" class="lbl-chip" fill={WARNA.merah}>401 · token lama ditolak</text>
	</g>
{/if}
