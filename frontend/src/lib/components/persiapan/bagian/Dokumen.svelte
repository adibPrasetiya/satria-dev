<script lang="ts">
	import type { PersiapanAuth } from '#lib/types.js';
	import { cn } from '#lib/utils.js';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import FileUp from '@lucide/svelte/icons/file-up';

	let { p = $bindable() }: { p: PersiapanAuth } = $props();

	const DOKUMEN = [
		{ k: 'kebijakan_masa_berlaku', l: 'Kebijakan masa berlaku kata sandi', d: 'Mis. SOP atau konfigurasi kedaluwarsa kata sandi' },
		{ k: 'bukti_hashing', l: 'Bukti algoritma hashing kata sandi', d: 'Mis. potongan konfigurasi/kode (bcrypt, argon2)' }
	] as const;
</script>

<div class="grid gap-3 sm:grid-cols-2">
	{#each DOKUMEN as d (d.k)}
		{@const berkas = p.dokumen[d.k]}
		<label class={cn('flex cursor-pointer flex-col gap-2 rounded-md border border-dashed p-4 transition-colors hover:border-gold/60', berkas && 'border-solid border-success/40 bg-success/5')}>
			<span class="flex items-center gap-2 text-sm font-medium">
				{#if berkas}<CircleCheck class="size-4 text-success" />{:else}<FileUp class="size-4 text-muted-foreground" />{/if}
				{d.l}
			</span>
			<span class="text-xs text-muted-foreground">{berkas || d.d}</span>
			<input type="file" class="sr-only" accept=".pdf,.png,.jpg,.txt,.docx"
				onchange={(e) => (p.dokumen[d.k] = e.currentTarget.files?.[0]?.name ?? berkas)} />
		</label>
	{/each}
</div>
