<script lang="ts">
	// Penanda langkah form bertahap di halaman publik: segmen progres + nomor/label.
	// Langkah yang sudah dilewati bisa diklik untuk kembali; langkah di depan terkunci.
	import { cn } from '#lib/utils.js';
	import Check from '@lucide/svelte/icons/check';

	let {
		langkah,
		label,
		onpilih
	}: {
		/** Indeks langkah aktif (mulai 0). */
		langkah: number;
		label: readonly string[];
		onpilih: (i: number) => void;
	} = $props();
</script>

<ol class="grid gap-2" style:grid-template-columns="repeat({label.length}, minmax(0, 1fr))" aria-label="Langkah pendaftaran">
	{#each label as l, i (l)}
		{@const selesai = i < langkah}
		{@const aktif = i === langkah}
		<li>
			<button
				type="button"
				disabled={!selesai}
				onclick={() => onpilih(i)}
				aria-current={aktif ? 'step' : undefined}
				class="group/langkah grid w-full gap-1.5 text-left disabled:cursor-default"
			>
				<span class="relative block h-1 overflow-hidden rounded-full bg-white/12">
					<span
						class={cn(
							'absolute inset-y-0 left-0 rounded-full bg-gold transition-[width] duration-500 ease-out',
							selesai || aktif ? 'w-full' : 'w-0',
							aktif && 'shadow-[0_0_10px_rgb(230_170_60/0.7)]'
						)}
					></span>
				</span>
				<span
					class={cn(
						'flex items-center gap-1 truncate text-[11px] font-medium tracking-[0.08em] uppercase transition-colors',
						aktif ? 'text-gold' : selesai ? 'text-white/70 group-hover/langkah:text-white' : 'text-white/35'
					)}
				>
					{#if selesai}<Check class="size-3 shrink-0" />{:else}<span class="font-stencil">{String(i + 1).padStart(2, '0')}</span>{/if}
					<span class="truncate">{l}</span>
				</span>
			</button>
		</li>
	{/each}
</ol>
