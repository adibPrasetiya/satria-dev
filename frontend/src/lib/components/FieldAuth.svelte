<script lang="ts">
	// Kolom isian halaman publik: label (+ aksi di kanan label), ikon kiri, galat/petunjuk di bawah.
	import type { Component, Snippet } from 'svelte';
	import type { HTMLInputAttributes } from 'svelte/elements';
	import { Label } from '#lib/components/ui/label/index.js';
	import { cn } from '#lib/utils.js';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';

	let {
		id,
		label,
		ikon: Ikon,
		value = $bindable(''),
		ref = $bindable(null),
		galat = null,
		petunjuk = null,
		aksiLabel,
		kanan,
		bawah,
		class: className = '',
		...rest
	}: Omit<HTMLInputAttributes, 'value'> & {
		id: string;
		label: string;
		ikon: Component<{ class?: string }>;
		value?: string;
		ref?: HTMLInputElement | null;
		/** Galat yang sudah layak ditampilkan (null bila tidak ada). */
		galat?: string | null;
		petunjuk?: string | null;
		aksiLabel?: Snippet;
		kanan?: Snippet;
		bawah?: Snippet;
	} = $props();
</script>

<div class={cn('grid gap-1.5', className)}>
	<div class="flex items-center justify-between gap-2">
		<Label for={id} class="text-sm font-medium text-white/85">{label}</Label>
		{@render aksiLabel?.()}
	</div>
	<div class="group relative">
		<Ikon
			class="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-white/40 transition group-focus-within:text-gold"
		/>
		<!-- input native (bukan Input shadcn) karena tipe props-nya union file/non-file yang bentrok dengan spread. -->
		<input
			{id}
			bind:this={ref}
			bind:value
			aria-invalid={!!galat}
			aria-describedby="{id}-pesan"
			class={cn(
				'h-10 w-full min-w-0 rounded-lg border px-2.5 py-1 outline-none transition-colors focus-visible:ring-3 aria-invalid:ring-3 border-white/12 bg-black/40 pl-10 text-[15px] text-white placeholder:text-white/30 focus-visible:border-gold/70 focus-visible:ring-gold/20 aria-invalid:border-red-400/70 aria-invalid:ring-red-400/15',
				kanan && 'pr-11'
			)}
			{...rest}
		/>
		{@render kanan?.()}
	</div>
	<!-- Ruang pesan tidak dicadangkan agar kartu tetap pendek; kosong = tidak memakan tinggi. -->
	<div id="{id}-pesan" aria-live="polite" class="flex flex-wrap items-center gap-2 text-xs empty:hidden">
		{#if galat}
			<p class="flex items-center gap-1.5 text-red-300"><CircleAlert class="size-3.5" />{galat}</p>
		{:else if petunjuk}
			<p class="text-white/50">{petunjuk}</p>
		{/if}
		{@render bawah?.()}
	</div>
</div>
