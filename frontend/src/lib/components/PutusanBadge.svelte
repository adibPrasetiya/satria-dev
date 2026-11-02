<script lang="ts">
	import { LABEL_PUTUSAN } from '#lib/catalog.js';
	import type { Putusan } from '#lib/types.js';
	import { cn } from '#lib/utils.js';

	let { putusan, class: className = '' }: { putusan: Putusan; class?: string } = $props();

	const gaya: Record<Putusan, string> = {
		laik: 'bg-success/12 text-success border-success/30',
		laik_bersyarat: 'bg-warning/15 text-warning-foreground border-warning/35',
		tidak_laik: 'bg-critical/12 text-critical border-critical/30'
	};
</script>

<span
	class={cn(
		'inline-flex h-6 items-center rounded-md border px-2 text-xs font-semibold whitespace-nowrap',
		gaya[putusan],
		className
	)}>{LABEL_PUTUSAN[putusan]}</span
>
