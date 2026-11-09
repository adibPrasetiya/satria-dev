<script lang="ts" module>
	import type { Tingkat } from '#lib/peta/tipe.js';

	/** Warna & label tingkat severity di panel peta (dipakai bersama). */
	export const TINGKAT_PETA: { k: Tingkat; label: string; warna: string }[] = [
		{ k: 'kritis', label: 'Kritis', warna: '#f87171' },
		{ k: 'tinggi', label: 'Tinggi', warna: '#fb923c' },
		{ k: 'sedang', label: 'Sedang', warna: '#facc15' },
		{ k: 'rendah', label: 'Rendah', warna: '#60a5fa' }
	];
</script>

<script lang="ts">
	// Diagram batang horizontal sebaran severity (kritis → rendah) bergaya panel peta: label + jumlah
	// di setiap batang (identitas tidak bergantung warna saja), skala = tingkat terbanyak.
	import type { SebaranTingkat } from '#lib/peta/tipe.js';

	let { sebaran, satuan = 'temuan' }: { sebaran: SebaranTingkat; satuan?: string } = $props();

	const total = $derived(TINGKAT_PETA.reduce((s, t) => s + sebaran[t.k], 0));
	const maks = $derived(Math.max(1, ...TINGKAT_PETA.map((t) => sebaran[t.k])));
</script>

<ul class="space-y-2" role="list">
	{#each TINGKAT_PETA as t (t.k)}
		{@const n = sebaran[t.k]}
		<li
			class="grid grid-cols-[3.5rem_minmax(0,1fr)_2rem] items-center gap-2.5 text-[12.5px]"
			title="{t.label}: {n} {satuan}{total ? ` (${Math.round((n / total) * 100)}%)` : ''}"
		>
			<span class="font-medium" style="color: {t.warna}">{t.label}</span>
			<span class="h-2 overflow-hidden rounded-full bg-white/[0.07]" aria-hidden="true">
				<span
					class="block h-full rounded-full transition-[width] duration-500 ease-out"
					style="width: {(n / maks) * 100}%; background: {t.warna}"
				></span>
			</span>
			<span class="text-right text-white/85 tabular-nums">{n}</span>
		</li>
	{/each}
</ul>
