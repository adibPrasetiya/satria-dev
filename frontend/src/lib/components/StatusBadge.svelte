<script lang="ts">
	import { LABEL_STATUS } from '#lib/catalog.js';
	import type { StatusMetode } from '#lib/types.js';
	import { cn } from '#lib/utils.js';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import CircleX from '@lucide/svelte/icons/circle-x';
	import CircleHelp from '@lucide/svelte/icons/circle-help';
	import CircleMinus from '@lucide/svelte/icons/circle-minus';
	import CircleSlash from '@lucide/svelte/icons/circle-slash';
	import Clock from '@lucide/svelte/icons/clock';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	let { status, class: className = '' }: { status: StatusMetode; class?: string } = $props();

	const gaya: Record<StatusMetode, string> = {
		lulus: 'bg-success/12 text-success border-success/25',
		gagal: 'bg-critical/12 text-critical border-critical/25',
		tidak_dapat_diverifikasi: 'bg-warning/15 text-warning-foreground border-warning/30',
		tidak_berlaku: 'bg-muted text-muted-foreground border-border',
		luar_cakupan: 'bg-muted text-muted-foreground border-dashed border-border',
		antre: 'bg-transparent text-muted-foreground border-border',
		berjalan: 'bg-info/12 text-info border-info/25'
	};
	const ikon = {
		lulus: CircleCheck,
		gagal: CircleX,
		tidak_dapat_diverifikasi: CircleHelp,
		tidak_berlaku: CircleMinus,
		luar_cakupan: CircleSlash,
		antre: Clock,
		berjalan: LoaderCircle
	};
	const Ikon = $derived(ikon[status]);
</script>

<span
	class={cn(
		'inline-flex h-5 shrink-0 items-center gap-1 rounded-full border px-2 text-xs font-medium whitespace-nowrap',
		gaya[status],
		className
	)}
>
	<Ikon class={cn('size-3', status === 'berjalan' && 'animate-spin')} />
	{LABEL_STATUS[status]}
</span>
