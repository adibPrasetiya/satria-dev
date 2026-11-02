<svelte:options namespace="svg" />

<script lang="ts">
	// Node Backend/API sebagai kartu TERANG bergaya sama dengan jendela browser frontend
	// (permukaan aplikasi target). Elemen SVG; ditempatkan di dalam <svg> induk.
	let {
		x,
		y,
		label = 'Backend',
		sub = 'API autentikasi',
		denyut = false
	}: { x: number; y: number; label?: string; sub?: string; denyut?: boolean } = $props();

	const W = 150;
	const H = 110;
	const L = $derived(x - W / 2);
	const T = $derived(y - H / 2);
</script>

<g>
	{#if denyut}
		<rect x={L - 7} y={T - 7} width={W + 14} height={H + 14} rx="20" fill="none" stroke="#7fe9d8" stroke-width="1.6" class="denyut-svg" />
	{/if}
	<!-- kartu -->
	<rect x={L} y={T} width={W} height={H} rx="14" fill="#f4f8ff" stroke="#c3d6f0" stroke-width="1.4" />
	<!-- bilah judul -->
	<path d="M{L} {T + 14} a14 14 0 0 1 14-14 h{W - 28} a14 14 0 0 1 14 14 v12 h-{W} z" fill="#d6e4fb" />
	<circle cx={L + 15} cy={T + 14} r="3.2" fill="#28c840" />
	<text x={L + 26} y={T + 18} class="lbl-win-judul" fill="#5f7696">API</text>
	<!-- rak server: tiga baris layanan -->
	{#each [0, 1, 2] as r (r)}
		{@const by = T + 34 + r * 23}
		<rect x={L + 14} y={by} width={W - 28} height="18" rx="5" fill="#eef4fe" stroke="#cadcf6" stroke-width="1.1" />
		<circle cx={L + 24} cy={by + 9} r="2.6" fill="#7fb0f0" />
		<path d="M{L + 34} {by + 6.5}h{W - 72}M{L + 34} {by + 11.5}h{W - 92}" stroke="#b7cdee" stroke-width="1.6" stroke-linecap="round" />
	{/each}
	<!-- label -->
	<text x={x} y={T + H + 18} class="lbl-simpul">{label}</text>
	<text x={x} y={T + H + 32} class="lbl-sub">{sub}</text>
</g>
