<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		judul,
		label,
		deskripsi,
		aksi,
		atas
	}: {
		judul: string;
		/** Label stensil kecil di atas judul, mis. "Laporan Asesmen". */
		label?: string;
		deskripsi?: string;
		aksi?: Snippet;
		atas?: Snippet;
	} = $props();
</script>

<div class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
	<div class="min-w-0">
		{@render atas?.()}
		{#if label}<p class="label-stensil mb-1">{label}</p>{/if}
		<h1 class="text-2xl font-semibold uppercase sm:text-[1.7rem]">{judul}</h1>
		<div class="strip-pangkat mt-2"></div>
		{#if deskripsi}
			<p class="mt-2 max-w-3xl text-sm text-muted-foreground">{deskripsi}</p>
		{/if}
	</div>
	{#if aksi}
		<div class="no-print flex flex-wrap gap-2">{@render aksi()}</div>
	{/if}
</div>
