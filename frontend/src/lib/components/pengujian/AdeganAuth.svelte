<svelte:options namespace="svg" />

<script lang="ts" module>
	// Adegan autentikasi (berulang): memindai formulir login, mengisi kredensial pada field
	// tersamar, mengirim permintaan lewat kanal HTTPS, menahannya di proxy uji, menyusun varian
	// masukan, lalu mengirim ulang langsung ke API dan mengevaluasi respons. Elemen SVG murni;
	// ditempatkan di dalam <svg> induk (VisualisasiUji). Gaya teks diwarisi dari .panggung-uji.
	import type { Babak } from '#lib/pengujian/timeline.js';

	export const babak: Babak[] = [
		{ id: 'pindai', label: 'Pindai', teks: 'Memindai formulir login — mendeteksi field kata sandi', dur: 2600 },
		{ id: 'isi', label: 'Kredensial', teks: 'Mengisi kredensial uji pada field tersamar', dur: 2200 },
		{ id: 'kirim', label: 'Kirim', teks: 'Mengirim permintaan autentikasi melalui kanal HTTPS', dur: 2400 },
		{ id: 'intersep', label: 'Intersep', teks: 'Menahan permintaan di proxy uji — membuka badan permintaan', dur: 2400 },
		{ id: 'payload', label: 'Varian', teks: 'Menyusun varian masukan uji untuk field kredensial', dur: 2800 },
		{ id: 'langsung', label: 'Langsung ke API', teks: 'Mengirim ulang langsung ke API, melewati validasi sisi klien', dur: 2600 },
		{ id: 'nilai', label: 'Evaluasi', teks: 'Mengevaluasi respons API terhadap kontrol keamanan', dur: 2400 }
	];
</script>

<script lang="ts">
	import { antara, halus, lerp, kuadrat, sepanjang } from '#lib/pengujian/timeline.js';
	import { WARNA, IKON } from './elemen-uji.js';
	import NodeSatya from './NodeSatya.svelte';
	import NodeBackend from './NodeBackend.svelte';

	let { i, p }: { i: number; p: number } = $props();

	// Tata letak tetap (ruang viewBox 1000×520).
	const B = { x: 110, y: 96, w: 340, h: 250 }; // jendela browser
	const fUser = { x: B.x + 30, y: 176, w: 280, h: 30 };
	const fSandi = { x: B.x + 30, y: 232, w: 280, h: 30 };
	const PROXY = { x: 512, y: 424 };
	const API = { x: 848, y: 196 };
	const keluarBrowser = { x: B.x + B.w, y: 220 };
	// Titik labuh paket di tepi kartu (bukan pusat), agar paket menempel rapi ke node.
	const dockBackend = { x: API.x - 75, y: API.y };
	const dockSatya = { x: PROXY.x, y: PROXY.y - 52 };
	const tengahKanal = { x: (keluarBrowser.x + dockBackend.x) / 2, y: (keluarBrowser.y + dockBackend.y) / 2 };

	const VARIAN = ['masukan kosong', 'string sangat panjang', 'tipe data tak sesuai', 'karakter khusus', 'pola injeksi'];

	// --- keadaan turunan per babak ---
	const memindai = $derived(i === 0);
	const kaca = $derived(
		i === 0
			? sepanjang(
					[
						{ x: fUser.x + 10, y: fUser.y + fUser.h / 2 },
						{ x: fUser.x + fUser.w - 10, y: fUser.y + fUser.h / 2 },
						{ x: fSandi.x + 10, y: fSandi.y + fSandi.h / 2 },
						{ x: fSandi.x + fSandi.w - 10, y: fSandi.y + fSandi.h / 2 }
					],
					p
				)
			: null
	);
	// Sorot field sandi muncul setelah kaca menyapunya, bertahan hingga babak varian.
	const sorotSandi = $derived((i === 0 && p > 0.55) || (i >= 1 && i <= 4));

	// Titik terketik pada field (babak isi).
	const titikUser = $derived(i === 1 ? Math.round(antara(p, 0, 0.45) * 9) : i >= 2 ? 9 : 0);
	const titikSandi = $derived(i === 1 ? Math.round(antara(p, 0.45, 0.95) * 8) : i >= 2 ? 8 : 0);

	// Kanal HTTPS terlihat saat kirim & awal intersep & langsung.
	const adaKanal = $derived(i === 2 || i === 3 || i === 5 || i === 6);

	// Paket pada kanal (babak kirim): browser → API.
	const paketKanal = $derived.by(() => {
		if (i !== 2) return null;
		const u = halus(p);
		return { x: lerp(keluarBrowser.x, dockBackend.x, u), y: lerp(keluarBrowser.y, dockBackend.y, u) };
	});

	// Intersep: paket ditarik dari kanal ke proxy (p<0.5), lalu panel badan terbuka.
	const paketTarik = $derived.by(() => {
		if (i !== 3 || p >= 0.5) return null;
		const u = halus(antara(p, 0, 0.5));
		return { x: lerp(tengahKanal.x, dockSatya.x, u), y: lerp(tengahKanal.y, dockSatya.y, u) };
	});
	const panelBuka = $derived((i === 3 && p >= 0.45) || i === 4);
	const panelH = $derived(i === 3 ? halus(antara(p, 0.45, 0.8)) : 1);

	// Varian masukan yang sedang disusun (babak varian) — berganti bertahap.
	const idxVarian = $derived(i === 4 ? Math.min(VARIAN.length - 1, Math.floor(p * VARIAN.length)) : -1);

	// Kirim langsung proxy → API (arc melewati frontend).
	const paketLangsung = $derived.by(() => {
		if (i !== 5) return null;
		const u = halus(p);
		return kuadrat(dockSatya, { x: 620, y: 118 }, dockBackend, u);
	});
	const lewatiKlien = $derived(i === 5 || i === 6);

	// Evaluasi: denyut & lencana di API.
	const menilai = $derived(i === 6);
</script>

<!-- kanal HTTPS browser ⇄ API -->
{#if adaKanal}
	<line x1={keluarBrowser.x} y1={keluarBrowser.y} x2={dockBackend.x} y2={dockBackend.y} stroke={WARNA.hijau} stroke-width="2.2" opacity="0.7" />
	<image href={IKON.gembok} x={tengahKanal.x - 13} y={tengahKanal.y - 13} width="26" height="26" />
	<text x={tengahKanal.x + 20} y={tengahKanal.y - 13} class="lbl-kanal" fill={WARNA.hijau}>HTTPS · kanal aplikasi</text>
{/if}

<!-- jalur validasi klien dilewati -->
{#if lewatiKlien}
	<text x={B.x + 60} y={B.y + B.h + 34} class="lbl-kecil" fill="rgba(255,255,255,0.45)">validasi sisi klien dilewati</text>
	<line x1={B.x + 36} y1={B.y + B.h + 28} x2={B.x + 54} y2={B.y + B.h + 44} stroke={WARNA.merah} stroke-width="2.2" opacity="0.85" />
	<line x1={B.x + 54} y1={B.y + B.h + 28} x2={B.x + 36} y2={B.y + B.h + 44} stroke={WARNA.merah} stroke-width="2.2" opacity="0.85" />
{/if}

<!-- jendela browser + formulir login -->
<g>
	<rect x={B.x} y={B.y} width={B.w} height={B.h} rx="12" fill="#f4f8ff" />
	<path d="M{B.x} {B.y + 16} a16 16 0 0 1 16-16 h{B.w - 32} a16 16 0 0 1 16 16 v16 h-{B.w} z" fill="#d6e4fb" />
	<circle cx={B.x + 18} cy={B.y + 16} r="3.4" fill="#ff5f57" />
	<circle cx={B.x + 32} cy={B.y + 16} r="3.4" fill="#febc2e" />
	<circle cx={B.x + 46} cy={B.y + 16} r="3.4" fill="#28c840" />
	<rect x={B.x + 70} y={B.y + 9} width={B.w - 160} height="14" rx="7" fill="#fff" />
	<text x={B.x + 82} y={B.y + 19} class="lbl-url-browser">/login</text>

	<text x={fUser.x} y={fUser.y - 8} class="lbl-form">Nama pengguna</text>
	<rect x={fUser.x} y={fUser.y} width={fUser.w} height={fUser.h} rx="6" fill="#fff" stroke="#b9cdee" stroke-width="1.4" />
	{#each Array.from({ length: titikUser }) as _, d (d)}
		<text x={fUser.x + 14 + d * 11} y={fUser.y + fUser.h / 2 + 5} class="lbl-isi-form">•</text>
	{/each}

	<text x={fSandi.x} y={fSandi.y - 8} class="lbl-form">Kata sandi</text>
	<rect
		x={fSandi.x}
		y={fSandi.y}
		width={fSandi.w}
		height={fSandi.h}
		rx="6"
		fill="#fff"
		stroke={sorotSandi ? WARNA.kuning : '#b9cdee'}
		stroke-width={sorotSandi ? 2.4 : 1.4}
	/>
	{#each Array.from({ length: titikSandi }) as _, d (d)}
		<text x={fSandi.x + 14 + d * 11} y={fSandi.y + fSandi.h / 2 + 5} class="lbl-isi-form">•</text>
	{/each}
	{#if sorotSandi}
		<text x={fSandi.x + fSandi.w + 10} y={fSandi.y + 20} class="lbl-kecil" fill={WARNA.kuning}>input[type=password]</text>
	{/if}

	<rect x={fSandi.x} y={fSandi.y + 48} width="120" height="34" rx="7" fill="#3d86f0" />
	<text x={fSandi.x + 60} y={fSandi.y + 70} class="lbl-tombol">Masuk</text>
</g>

<!-- kaca pembesar (babak pindai) -->
{#if memindai && kaca}
	<g transform="translate({kaca.x}, {kaca.y})">
		<circle r="26" fill="rgba(127,233,216,0.08)" stroke={WARNA.sian} stroke-width="3" />
		<line x1="19" y1="19" x2="40" y2="40" stroke={WARNA.sian} stroke-width="5" stroke-linecap="round" />
		<circle r="26" fill="none" stroke={WARNA.sian} stroke-width="1" opacity="0.4" class="denyut-svg" />
	</g>
{/if}

<!-- node SATYA (proxy uji) & Backend (API) -->
<NodeSatya x={PROXY.x} y={PROXY.y} />
<NodeBackend x={API.x} y={API.y} sub="API autentikasi" denyut={menilai} />

<!-- paket pada kanal (kirim) -->
{#if paketKanal}
	<g transform="translate({paketKanal.x}, {paketKanal.y})">
		<rect x="-78" y="-13" width="156" height="26" rx="8" fill="#0e1317" stroke={WARNA.hijau} stroke-width="1.6" />
		<rect x="-72" y="-7.5" width="42" height="15" rx="4" fill="rgba(159,224,138,0.15)" />
		<text x="-51" y="4" class="lbl-badge" fill={WARNA.hijau}>POST</text>
		<text x="36" y="4.5" class="lbl-paket" fill="#e9ecef">/auth/login</text>
	</g>
{/if}

<!-- paket ditarik ke proxy (intersep) -->
{#if paketTarik}
	<line x1={tengahKanal.x} y1={tengahKanal.y} x2={paketTarik.x} y2={paketTarik.y} stroke={WARNA.kuning} stroke-width="1.4" stroke-dasharray="4 4" opacity="0.7" />
	<g transform="translate({paketTarik.x}, {paketTarik.y})">
		<rect x="-78" y="-13" width="156" height="26" rx="8" fill="#0e1317" stroke={WARNA.kuning} stroke-width="1.6" />
		<rect x="-72" y="-7.5" width="42" height="15" rx="4" fill="rgba(245,196,81,0.15)" />
		<text x="-51" y="4" class="lbl-badge" fill={WARNA.kuning}>POST</text>
		<text x="36" y="4.5" class="lbl-paket" fill={WARNA.kuning}>/auth/login</text>
	</g>
{/if}

<!-- lencana intersep -->
{#if i === 3}
	<g transform="translate({dockSatya.x}, {dockSatya.y - 20})" class="muncul">
		<rect x="-52" y="-13" width="104" height="24" rx="7" fill="rgba(245,196,81,0.12)" stroke={WARNA.kuning} />
		<text y="4" class="lbl-chip" fill={WARNA.kuning}>INTERSEP</text>
	</g>
{/if}

<!-- panel badan permintaan di proxy -->
{#if panelBuka}
	{@const PW = 236}
	{@const PH = 92 * panelH}
	<g transform="translate({PROXY.x + 100}, {PROXY.y - 48})" class="muncul">
		<rect width={PW} height={PH} rx="8" fill="#0e1317" stroke={WARNA.biru} stroke-width="1.3" opacity="0.98" />
		{#if panelH > 0.6}
			<text x="12" y="18" class="lbl-form-mono" fill="#91a7ff">{'{'}</text>
			<text x="24" y="38" class="lbl-form-mono" fill="rgba(255,255,255,0.55)">"username":<tspan fill="rgba(255,255,255,0.85)"> "••••••"</tspan></text>
			<text x="24" y="58" class="lbl-form-mono" fill="rgba(255,255,255,0.55)">
				"password":
				<tspan fill={idxVarian >= 0 ? WARNA.kuning : 'rgba(255,255,255,0.85)'}> {idxVarian >= 0 ? `‹${VARIAN[idxVarian]}›` : '"••••••"'}</tspan>
			</text>
			<text x="12" y="78" class="lbl-form-mono" fill="#91a7ff">{'}'}</text>
		{/if}
	</g>
{/if}

<!-- generator varian -->
{#if i === 4}
	<g transform="translate({dockSatya.x}, {dockSatya.y - 20})" class="muncul">
		<rect x="-68" y="-13" width="136" height="24" rx="7" fill="rgba(245,196,81,0.12)" stroke={WARNA.kuning} />
		<text y="4" class="lbl-chip" fill={WARNA.kuning}>GENERATOR VARIAN</text>
	</g>
{/if}

<!-- kirim langsung proxy → API -->
{#if i === 5}
	<path d="M{dockSatya.x} {dockSatya.y} Q 620 118 {dockBackend.x} {dockBackend.y}" fill="none" stroke={WARNA.kuning} stroke-width="1.8" stroke-dasharray="6 5" opacity="0.75" />
{/if}
{#if paketLangsung}
	<g transform="translate({paketLangsung.x}, {paketLangsung.y})">
		<rect x="-92" y="-13" width="184" height="26" rx="8" fill="#0e1317" stroke={WARNA.kuning} stroke-width="1.6" />
		<rect x="-86" y="-7.5" width="42" height="15" rx="4" fill="rgba(245,196,81,0.15)" />
		<text x="-65" y="4" class="lbl-badge" fill={WARNA.kuning}>POST</text>
		<text x="30" y="4.5" class="lbl-paket" fill={WARNA.kuning}>/auth/login ◇ varian</text>
	</g>
{/if}

<!-- evaluasi respons -->
{#if menilai}
	<g transform="translate({API.x}, {API.y - 76})" class="muncul">
		<rect x="-72" y="-13" width="144" height="24" rx="7" fill="rgba(127,233,216,0.1)" stroke={WARNA.sian} />
		<text y="4" class="lbl-chip" fill={WARNA.sian}>menganalisis respons…</text>
	</g>
{/if}
