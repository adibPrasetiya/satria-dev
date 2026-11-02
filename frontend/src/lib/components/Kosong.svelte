<script lang="ts">
	import type { Snippet } from 'svelte';
	let { judul, pesan, children }: { judul: string; pesan?: string; children?: Snippet } = $props();
</script>

<div class="flex flex-col items-center justify-center rounded-xl border border-dashed p-10 text-center">
	<p class="font-medium">{judul}</p>
	{#if pesan}<p class="mt-1 max-w-md text-sm text-muted-foreground">{pesan}</p>{/if}
	{#if children}<div class="mt-4">{@render children()}</div>{/if}
</div>
