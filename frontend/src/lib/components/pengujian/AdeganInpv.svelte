<svelte:options namespace="svg" />

<script lang="ts" module>
	// Adegan validasi input (berulang): memetakan field formulir & parameter API, menyorot titik
	// masukan, menyusun varian masukan uji, menahan permintaan di proxy untuk mengganti nilai field,
	// mengirim langsung ke API melewati validasi klien, lalu mengevaluasi penanganan masukan.
	import type { Babak } from '#lib/pengujian/timeline.js';

	export const babak: Babak[] = [
		{ id: 'petakan', label: 'Petakan', teks: 'Memetakan field formulir & parameter API', dur: 2600 },
		{ id: 'pilih', label: 'Titik uji', teks: 'Menyorot titik masukan yang akan diuji', dur: 2200 },
		{ id: 'susun', label: 'Susun varian', teks: 'Menyusun varian masukan: panjang, tipe, karakter khusus, pola injeksi', dur: 2800 },
		{ id: 'intersep', label: 'Intersep', teks: 'Menahan permintaan — mengganti nilai field dengan varian', dur: 2400 },
		{ id: 'langsung', label: 'Langsung ke API', teks: 'Mengirim langsung ke API, melewati validasi sisi klien', dur: 2600 },
		{ id: 'nilai', label: 'Evaluasi', teks: 'Mengevaluasi penanganan masukan oleh API', dur: 2600 }
	];
</script>

<script lang="ts">
	import { antara, halus, lerp, kuadrat, sepanjang, jepit } from '#lib/pengujian/timeline.js';
	import { WARNA, IKON } from './elemen-uji.js';
	import NodeSatya from './NodeSatya.svelte';
	import NodeBackend from './NodeBackend.svelte';

	let { i, p }: { i: number; p: number } = $props();

	const B = { x: 110, y: 96, w: 340, h: 268 };
	const fields = [
		{ nama: 'Nama', y: 152, h: 28 },
		{ nama: 'Email', y: 200, h: 28 },
		{ nama: 'Komentar', y: 248, h: 54 }
	];
	const PARAM = ['q', 'id', 'sort'];
	const VARIAN = ['string panjang', 'tipe tak sesuai', 'karakter khusus', 'pola injeksi'];
	const PROXY = { x: 512, y: 424 };
	const API = { x: 848, y: 196 };
	const keluarBrowser = { x: B.x + B.w, y: 230 };
	const dockBackend = { x: API.x - 75, y: API.y };
	const dockSatya = { x: PROXY.x, y: PROXY.y - 52 };
	const tengahKanal = { x: (keluarBrowser.x + dockBackend.x) / 2, y: (keluarBrowser.y + dockBackend.y) / 2 };

	// Pusat tiap field — titik yang disapu kaca pembesar.
	const titikKaca = fields.map((f) => ({ x: B.x + 170, y: f.y + f.h / 2 }));
	/** Indeks elemen dari progres babak (0..1), selalu dalam rentang [0, n-1]. */
	const indeks = (prog: number, n: number) => Math.min(n - 1, Math.max(0, Math.floor(jepit(prog) * n)));

	// Kaca pembesar menyapu ketiga field (babak petakan).
	const kaca = $derived(i === 0 ? sepanjang(titikKaca, p) : null);

	// Field tersorot (babak pilih) & parameter tersorot bergilir.
	const sorotField = $derived(i === 1 ? indeks(p, fields.length) : i >= 2 && i <= 4 ? 2 : -1);
	const sorotParam = $derived(i === 0 && p > 0.3 ? indeks(antara(p, 0.3, 1), PARAM.length) : -1);

	const idxVarian = $derived(i === 2 ? indeks(p, VARIAN.length) : i >= 3 ? VARIAN.length - 1 : -1);
	const adaKanal = $derived(i === 4);

	const paketTarik = $derived.by(() => {
		if (i !== 3 || p >= 0.5) return null;
		const u = halus(antara(p, 0, 0.5));
		return { x: lerp(tengahKanal.x, dockSatya.x, u), y: lerp(tengahKanal.y, dockSatya.y, u) };
	});
	const panelBuka = $derived(i === 3 && p >= 0.4);

	const paketLangsung = $derived.by(() => {
		if (i !== 4) return null;
		const u = halus(p);
		return kuadrat(dockSatya, { x: 620, y: 118 }, dockBackend, u);
	});
	const lewatiKlien = $derived(i === 4 || i === 5);
	const menilai = $derived(i === 5);
</script>

{#if adaKanal}
	<line x1={keluarBrowser.x} y1={keluarBrowser.y} x2={dockBackend.x} y2={dockBackend.y} stroke={WARNA.hijau} stroke-width="2.2" opacity="0.6" />
	<image href={IKON.gembok} x={tengahKanal.x - 13} y={tengahKanal.y - 13} width="26" height="26" />
{/if}

{#if lewatiKlien}
	<text x={B.x + 60} y={B.y + B.h + 54} class="lbl-kecil" fill="rgba(255,255,255,0.45)">validasi sisi klien dilewati</text>
	<line x1={B.x + 36} y1={B.y + B.h + 48} x2={B.x + 54} y2={B.y + B.h + 64} stroke={WARNA.merah} stroke-width="2.2" opacity="0.85" />
	<line x1={B.x + 54} y1={B.y + B.h + 48} x2={B.x + 36} y2={B.y + B.h + 64} stroke={WARNA.merah} stroke-width="2.2" opacity="0.85" />
{/if}

<!-- jendela browser + formulir -->
<g>
	<rect x={B.x} y={B.y} width={B.w} height={B.h} rx="12" fill="#f4f8ff" />
	<path d="M{B.x} {B.y + 16} a16 16 0 0 1 16-16 h{B.w - 32} a16 16 0 0 1 16 16 v16 h-{B.w} z" fill="#d6e4fb" />
	<circle cx={B.x + 18} cy={B.y + 16} r="3.4" fill="#ff5f57" />
	<circle cx={B.x + 32} cy={B.y + 16} r="3.4" fill="#febc2e" />
	<circle cx={B.x + 46} cy={B.y + 16} r="3.4" fill="#28c840" />
	<rect x={B.x + 70} y={B.y + 9} width={B.w - 160} height="14" rx="7" fill="#fff" />
	<text x={B.x + 82} y={B.y + 19} class="lbl-url-browser">/api/items</text>

	{#each fields as f, idx (f.nama)}
		<text x={B.x + 30} y={f.y - 7} class="lbl-form">{f.nama}</text>
		<rect
			x={B.x + 30}
			y={f.y}
			width="280"
			height={f.h}
			rx="6"
			fill="#fff"
			stroke={sorotField === idx ? WARNA.kuning : '#b9cdee'}
			stroke-width={sorotField === idx ? 2.4 : 1.4}
		/>
	{/each}
</g>

<!-- strip parameter API -->
<g transform="translate({B.x + 30}, {B.y + B.h + 2})">
	<text x="0" y="-4" class="lbl-kecil" fill="rgba(255,255,255,0.4)">GET /api/items</text>
	{#each PARAM as prm, idx (prm)}
		<g transform="translate({idx * 58}, 6)">
			<rect width="52" height="20" rx="5" fill={sorotParam === idx ? 'rgba(245,196,81,0.14)' : '#141a20'} stroke={sorotParam === idx ? WARNA.kuning : 'rgba(255,255,255,0.14)'} />
			<text x="26" y="14" class="lbl-chip" fill={sorotParam === idx ? WARNA.kuning : 'rgba(255,255,255,0.6)'}>{prm}</text>
		</g>
	{/each}
</g>

<!-- kaca pembesar -->
{#if kaca}
	<g transform="translate({kaca.x}, {kaca.y})">
		<circle r="26" fill="rgba(127,233,216,0.08)" stroke={WARNA.sian} stroke-width="3" />
		<line x1="19" y1="19" x2="40" y2="40" stroke={WARNA.sian} stroke-width="5" stroke-linecap="round" />
		<circle r="26" fill="none" stroke={WARNA.sian} stroke-width="1" opacity="0.4" class="denyut-svg" />
	</g>
{/if}

<!-- node SATYA (proxy uji) & Backend (API) -->
<NodeSatya x={PROXY.x} y={PROXY.y} />
<NodeBackend x={API.x} y={API.y} sub="validasi masukan" denyut={menilai} />

<!-- generator varian -->
{#if i === 2}
	<g transform="translate({PROXY.x + 100}, {PROXY.y - 70})" class="muncul">
		<rect width="192" height="124" rx="8" fill="#0e1317" stroke={WARNA.kuning} stroke-width="1.2" opacity="0.98" />
		<text x="12" y="22" class="lbl-chip" fill={WARNA.kuning} text-anchor="start">GENERATOR VARIAN</text>
		{#each VARIAN as v, idx (v)}
			<g transform="translate(14, {44 + idx * 20})">
				<circle cx="4" cy="-4" r="3" fill={idxVarian === idx ? WARNA.kuning : 'rgba(255,255,255,0.25)'} />
				<text x="16" y="0" class="lbl-form-mono" fill={idxVarian === idx ? WARNA.kuning : 'rgba(255,255,255,0.5)'}>{v}</text>
			</g>
		{/each}
	</g>
{/if}

<!-- paket ditarik ke proxy (intersep) -->
{#if paketTarik}
	<line x1={tengahKanal.x} y1={tengahKanal.y} x2={paketTarik.x} y2={paketTarik.y} stroke={WARNA.kuning} stroke-width="1.4" stroke-dasharray="4 4" opacity="0.7" />
	<g transform="translate({paketTarik.x}, {paketTarik.y})">
		<rect x="-72" y="-13" width="144" height="26" rx="8" fill="#0e1317" stroke={WARNA.kuning} stroke-width="1.6" />
		<rect x="-66" y="-7.5" width="34" height="15" rx="4" fill="rgba(245,196,81,0.15)" />
		<text x="-49" y="4" class="lbl-badge" fill={WARNA.kuning}>GET</text>
		<text x="30" y="4.5" class="lbl-paket" fill={WARNA.kuning}>/api/items</text>
	</g>
{/if}

<!-- panel badan permintaan di proxy -->
{#if panelBuka}
	<g transform="translate({PROXY.x + 100}, {PROXY.y - 48})" class="muncul">
		<rect width="236" height="64" rx="8" fill="#0e1317" stroke={WARNA.biru} stroke-width="1.3" opacity="0.98" />
		<text x="12" y="26" class="lbl-form-mono" fill="rgba(255,255,255,0.55)">comment:</text>
		<text x="12" y="46" class="lbl-form-mono" fill={WARNA.kuning}>‹{VARIAN[idxVarian] ?? 'varian'}›</text>
	</g>
{/if}

<!-- kirim langsung proxy → API -->
{#if i === 4}
	<path d="M{dockSatya.x} {dockSatya.y} Q 620 118 {dockBackend.x} {dockBackend.y}" fill="none" stroke={WARNA.kuning} stroke-width="1.8" stroke-dasharray="6 5" opacity="0.75" />
{/if}
{#if paketLangsung}
	<g transform="translate({paketLangsung.x}, {paketLangsung.y})">
		<rect x="-92" y="-13" width="184" height="26" rx="8" fill="#0e1317" stroke={WARNA.kuning} stroke-width="1.6" />
		<rect x="-86" y="-7.5" width="34" height="15" rx="4" fill="rgba(245,196,81,0.15)" />
		<text x="-69" y="4" class="lbl-badge" fill={WARNA.kuning}>GET</text>
		<text x="26" y="4.5" class="lbl-paket" fill={WARNA.kuning}>/api/items ◇ varian</text>
	</g>
{/if}

<!-- evaluasi penanganan masukan -->
{#if menilai}
	<g transform="translate({API.x}, {API.y - 76})" class="muncul">
		<rect x="-82" y="-13" width="164" height="24" rx="7" fill="rgba(127,233,216,0.1)" stroke={WARNA.sian} />
		<text y="4" class="lbl-chip" fill={WARNA.sian}>mengevaluasi penanganan…</text>
	</g>
{/if}
