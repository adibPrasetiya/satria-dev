<script lang="ts">
	import type { Putusan } from '#lib/types.js';
	import { cn } from '#lib/utils.js';

	let { skor, putusan, class: className = '' }: { skor: number; putusan?: Putusan; class?: string } =
		$props();

	const warna = $derived(
		putusan === 'tidak_laik'
			? 'bg-critical'
			: putusan === 'laik_bersyarat'
				? 'bg-warning'
				: putusan === 'laik'
					? 'bg-success'
					: 'bg-primary'
	);
</script>

<div class={cn('flex items-center gap-2', className)}>
	<!-- Bar bersegmen seperti indikator amunisi -->
	<div class="flex h-2.5 flex-1 gap-[2px]">
		{#each Array(10) as _, i (i)}
			<span class={cn('flex-1 rounded-[1px]', i < Math.round(skor / 10) ? warna : 'bg-muted')}></span>
		{/each}
	</div>
	<span class="w-9 text-right font-heading text-xs font-semibold tabular-nums">{skor}%</span>
</div>
