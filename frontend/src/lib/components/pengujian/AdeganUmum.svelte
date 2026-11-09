<svelte:options namespace="svg" />

<script lang="ts" module>
	// Adegan UMUM metode uji (berulang), sama untuk semua fungsi keamanan: SATRIA menyiapkan kasus
	// uji → mengirim permintaan ke target → target merespons → SATRIA mengevaluasi respons terhadap
	// kriteria lulus. Bila worker sudah melaporkan request nyata, metode HTTP, path, dan status
	// respons ditampilkan pada paket. Elemen SVG murni; gaya teks diwarisi dari .panggung-uji.
	import type { Babak } from '#lib/pengujian/timeline.js';

	export const babak: Babak[] = [
		{
			id: 'siapkan',
			label: 'Siapkan',
			teks: 'Menyiapkan kasus uji & payload sesuai metode',
			dur: 2000
		},
		{ id: 'kirim', label: 'Kirim', teks: 'Mengirim permintaan uji ke aplikasi target', dur: 2400 },
		{
			id: 'respons',
			label: 'Respons',
			teks: 'Aplikasi target merespons permintaan uji',
			dur: 2200
		},
		{
			id: 'evaluasi',
			label: 'Evaluasi',
			teks: 'Mengevaluasi respons terhadap kriteria lulus',
			dur: 2400
		}
	];
</script>

<script lang="ts">
	import { halus, lerp } from '#lib/pengujian/timeline.js';
	import type { RequestUji } from '#lib/pengujian/peristiwa.js';
	import { WARNA, IKON } from './elemen-uji.js';
	import NodeSatya from './NodeSatya.svelte';
	import NodeBackend from './NodeBackend.svelte';

	let {
		i,
		p,
		req = null,
		host = ''
	}: { i: number; p: number; req?: RequestUji | null; host?: string } = $props();

	// Tata letak tetap (ruang viewBox 1000×520).
	const S = { x: 220, y: 250 };
	const T = { x: 780, y: 250 };
	const keluar = { x: S.x + 88, y: S.y };
	const dock = { x: T.x - 75, y: T.y };
	const tengah = { x: (keluar.x + dock.x) / 2, y: keluar.y };

	const metode = $derived(req?.metode_http ?? 'GET');
	const path = $derived.by(() => {
		if (!req?.url) return '/…';
		try {
			const u = new URL(req.url);
			const s = u.pathname + (u.search ? '?…' : '');
			return s.length > 22 ? `${s.slice(0, 21)}…` : s;
		} catch {
			return '/…';
		}
	});
	const status = $derived(req?.status ?? null);
	const warnaStatus = $derived(
		status === null
			? WARNA.sian
			: status < 300
				? WARNA.hijau
				: status < 400
					? WARNA.kuning
					: WARNA.merah
	);
	const namaTarget = $derived(host.replace(/^https?:\/\//, '').replace(/\/.*$/, '') || 'Target');

	// Paket: kirim (S → T) atau respons (T → S).
	const paket = $derived.by(() => {
		if (i !== 1 && i !== 2) return null;
		const u = halus(p);
		return i === 1
			? { x: lerp(keluar.x, dock.x, u), y: keluar.y }
			: { x: lerp(dock.x, keluar.x, u), y: keluar.y };
	});
</script>

<!-- kanal HTTPS SATRIA ⇄ target -->
<line
	x1={keluar.x}
	y1={keluar.y}
	x2={dock.x}
	y2={dock.y}
	stroke={WARNA.hijau}
	stroke-width="2"
	opacity={i === 1 || i === 2 ? 0.6 : 0.25}
/>
<image
	href={IKON.gembok}
	x={tengah.x - 12}
	y={tengah.y - 40}
	width="24"
	height="24"
	opacity="0.8"
/>
<text
	x={tengah.x}
	y={tengah.y + 30}
	class="lbl-kecil"
	fill="rgba(255,255,255,0.4)"
	text-anchor="middle">HTTPS</text
>

<NodeSatya x={S.x} y={S.y} judul="satria ▸ uji" />
<NodeBackend x={T.x} y={T.y} label={namaTarget} sub="aplikasi target" denyut={i === 2} />

<!-- siapkan: payload kasus uji -->
{#if i === 0}
	<g transform="translate({S.x}, {S.y - 104})" class="muncul">
		<rect
			x="-92"
			y="-15"
			width="184"
			height="30"
			rx="8"
			fill="rgba(127,233,216,0.1)"
			stroke={WARNA.sian}
		/>
		<image href={IKON.payload} x="-82" y="-10" width="20" height="20" />
		<text x="10" y="4.5" class="lbl-chip" fill={WARNA.sian}>menyusun kasus uji</text>
	</g>
{/if}

<!-- paket permintaan / respons -->
{#if paket}
	<g transform="translate({paket.x}, {paket.y})">
		{#if i === 1}
			<rect
				x="-92"
				y="-14"
				width="184"
				height="28"
				rx="8"
				fill="#0e1317"
				stroke={WARNA.sian}
				stroke-width="1.6"
			/>
			<rect x="-86" y="-8" width="44" height="16" rx="4" fill="rgba(127,233,216,0.15)" />
			<text x="-64" y="4" class="lbl-badge" fill={WARNA.sian}>{metode}</text>
			<text x="22" y="4.5" class="lbl-paket" fill="rgba(236,240,245,0.9)">{path}</text>
		{:else}
			<rect
				x="-64"
				y="-14"
				width="128"
				height="28"
				rx="8"
				fill="#0e1317"
				stroke={warnaStatus}
				stroke-width="1.6"
			/>
			<text y="4.5" class="lbl-paket" fill={warnaStatus}
				>{status === null ? 'respons' : `HTTP ${status}`}</text
			>
		{/if}
	</g>
{/if}

<!-- evaluasi: respons dicocokkan dengan kriteria lulus -->
{#if i === 3}
	<g transform="translate({S.x}, {S.y - 104})" class="muncul">
		<rect
			x="-104"
			y="-15"
			width="208"
			height="30"
			rx="8"
			fill="rgba(159,224,138,0.1)"
			stroke={WARNA.hijau}
		/>
		<path
			d="M-88 0 l5 5 l10 -11"
			fill="none"
			stroke={WARNA.hijau}
			stroke-width="2.2"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
		<text x="10" y="4.5" class="lbl-chip" fill={WARNA.hijau}>cocokkan kriteria lulus</text>
	</g>
{/if}
