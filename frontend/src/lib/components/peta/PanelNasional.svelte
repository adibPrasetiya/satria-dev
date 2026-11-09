<script lang="ts">
	// Sebaran severity temuan secara NASIONAL (seluruh sistem informasi teruji) — gaya panel peta,
	// ditampilkan di bawah kartu sorotan provinsi. Data dari ringkasan peta (tanpa panggilan tambahan).
	import type { SebaranTingkat } from '#lib/peta/tipe.js';
	import BatangSeveritas from './BatangSeveritas.svelte';

	let { sebaran }: { sebaran: SebaranTingkat } = $props();

	const total = $derived(sebaran.kritis + sebaran.tinggi + sebaran.sedang + sebaran.rendah);
</script>

<section
	class="panel w-full shrink-0 rounded-lg px-4 pt-3.5 pb-4 text-white"
	aria-label="Sebaran severity nasional"
>
	<p class="mb-3 text-xs text-white/50 tabular-nums">
		Total temuan <span class="ml-1 text-sm font-semibold text-white">{total}</span>
	</p>
	{#if total}
		<BatangSeveritas {sebaran} />
	{:else}
		<p class="text-[13px] text-white/50">Belum ada temuan.</p>
	{/if}
</section>

<style>
	.panel {
		background: rgb(12 15 13 / 0.86);
		border: 1px solid rgb(255 255 255 / 0.08);
		backdrop-filter: blur(10px);
	}
</style>
