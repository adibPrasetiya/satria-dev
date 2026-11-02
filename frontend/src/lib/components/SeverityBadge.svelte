<script lang="ts">
	import type { Severity } from '#lib/types.js';
	import { cn } from '#lib/utils.js';

	let { severity, class: className = '' }: { severity: Severity; class?: string } = $props();

	const gaya: Record<Severity, string> = {
		kritis: 'bg-critical text-white',
		tinggi: 'bg-critical/15 text-critical',
		sedang: 'bg-warning/20 text-warning-foreground',
		rendah: 'bg-info/12 text-info',
		info: 'bg-muted text-muted-foreground'
	};
</script>

<span
	class={cn(
		'inline-flex h-5 shrink-0 items-center rounded px-1.5 text-[11px] font-semibold tracking-wide uppercase',
		gaya[severity],
		className
	)}>{severity}</span
>
