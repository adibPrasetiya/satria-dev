<script lang="ts">
	import { cn } from '#lib/utils.js';
	import type { HTMLSelectAttributes } from 'svelte/elements';

	let {
		value = $bindable(),
		opsi,
		class: className = '',
		...rest
	}: HTMLSelectAttributes & { opsi: { value: string; label: string }[] } = $props();
</script>

<select
	bind:value
	class={cn(
		'h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30',
		className
	)}
	{...rest}
>
	{#each opsi as o (o.value)}
		<option value={o.value} class="bg-popover text-popover-foreground">{o.label}</option>
	{/each}
</select>
