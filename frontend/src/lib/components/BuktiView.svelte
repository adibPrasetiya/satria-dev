<script lang="ts">
	import type { Bukti } from '#lib/types.js';
	import { tanggal } from '#lib/format.js';
	import FileText from '@lucide/svelte/icons/file-text';
	import Image from '@lucide/svelte/icons/image';

	let { bukti }: { bukti: Bukti[] } = $props();
</script>

{#each bukti as b, i (i)}
	{#if b.jenis === 'request_response' && b.isi}
		<details class="group mt-2 overflow-hidden rounded border border-black/30 bg-[#0d120c]">
			<summary class="cursor-pointer list-none px-3 py-1.5 font-mono text-[11px] text-[#9fe08a] select-none">
				<span class="inline-block transition group-open:rotate-90">▸</span> Bukti: {b.judul}
			</summary>
			<pre class="max-h-64 overflow-auto border-t border-white/10 p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-[#d7e3cf]">{b.isi}</pre>
		</details>
	{:else}
		<span class="mt-2 mr-2 inline-flex items-center gap-1.5 rounded border bg-muted/50 px-2 py-1 text-xs">
			{#if b.jenis === 'screenshot'}<Image class="size-3.5" />{:else}<FileText class="size-3.5" />{/if}
			{b.nama_file ?? b.judul}
			{#if b.diunggah_oleh}<span class="text-muted-foreground">· {b.diunggah_oleh}, {tanggal(b.waktu)}</span>{/if}
		</span>
	{/if}
{/each}
