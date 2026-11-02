<script lang="ts">
	// Cap stempel putusan kelaikan, gaya stempel dinas.
	import { LABEL_PUTUSAN } from '#lib/catalog.js';
	import type { Putusan } from '#lib/types.js';
	import { cn } from '#lib/utils.js';

	let { putusan, class: className = '' }: { putusan: Putusan; class?: string } = $props();

	const warna: Record<Putusan, string> = {
		laik: 'border-success text-success',
		laik_bersyarat: 'border-warning-foreground text-warning-foreground',
		tidak_laik: 'border-critical text-critical'
	};
</script>

<div
	class={cn(
		'inline-flex -rotate-6 flex-col items-center rounded-md border-4 border-double px-5 py-2 text-center opacity-90 mix-blend-multiply dark:mix-blend-normal',
		warna[putusan],
		className
	)}
>
	<span class="font-heading text-[10px] tracking-[0.3em] uppercase">Dinyatakan</span>
	<span class="font-stencil text-3xl leading-none tracking-[0.08em] uppercase sm:text-4xl">{LABEL_PUTUSAN[putusan]}</span>
	<span class="mt-0.5 font-heading text-[9px] tracking-[0.25em] uppercase">Per-BSSN 4/2021</span>
</div>
