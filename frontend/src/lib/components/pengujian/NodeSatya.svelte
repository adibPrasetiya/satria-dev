<svelte:options namespace="svg" />

<script lang="ts">
	// Node SATYA sebagai jendela TERMINAL gelap-hijau — mencerminkan chrome jendela browser
	// (tiga lampu + bilah judul) tetapi dalam bahasa "perkakas operator" (console) milik app.
	// Elemen SVG; ditempatkan di dalam <svg> induk.
	let { x, y, judul = 'satya ▸ proxy' }: { x: number; y: number; judul?: string } = $props();

	const W = 176;
	const H = 104;
	const L = $derived(x - W / 2);
	const T = $derived(y - H / 2);
</script>

<g>
	<!-- kartu terminal -->
	<rect x={L} y={T} width={W} height={H} rx="14" fill="#0e1317" stroke="rgba(159,224,138,0.5)" stroke-width="1.3" />
	<!-- bilah judul -->
	<path d="M{L} {T + 14} a14 14 0 0 1 14-14 h{W - 28} a14 14 0 0 1 14 14 v12 h-{W} z" fill="#16211a" />
	<circle cx={L + 15} cy={T + 14} r="3.2" fill="#ff5f57" />
	<circle cx={L + 26} cy={T + 14} r="3.2" fill="#febc2e" />
	<circle cx={L + 37} cy={T + 14} r="3.2" fill="#9fe08a" />
	<text x={x + 8} y={T + 18} class="lbl-win-judul" fill="#9fe08a" text-anchor="middle">{judul}</text>
	<!-- lencana perisai (identitas SATYA) -->
	<g transform="translate({L + 24}, {T + 58})">
		<path d="M0 -15 L13 -10 L13 1 C13 11 0 16 0 16 C0 16 -13 11 -13 1 L-13 -10 Z" fill="rgba(159,224,138,0.12)" stroke="#9fe08a" stroke-width="1.6" />
		<path d="M-5 0 L-1.5 4 L6 -6" fill="none" stroke="#9fe08a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
	</g>
	<!-- baris prompt -->
	<text x={L + 46} y={T + 48} class="lbl-term" fill="#9fe08a">▸ listening :8080</text>
	<text x={L + 46} y={T + 66} class="lbl-term" fill="rgba(159,224,138,0.55)">▸ awaiting request</text>
	<!-- label -->
	<text x={x} y={T + H + 18} class="lbl-simpul">SATRIA</text>
	<text x={x} y={T + H + 32} class="lbl-sub">proxy uji</text>
</g>
