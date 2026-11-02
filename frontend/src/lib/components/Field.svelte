<script lang="ts">
	import type { Snippet } from 'svelte';
	import { Label } from '#lib/components/ui/label/index.js';
	import * as Tooltip from '#lib/components/ui/tooltip/index.js';
	import TandaAlamat from '#lib/components/persiapan/TandaAlamat.svelte';
	import Info from '@lucide/svelte/icons/info';

	let {
		label,
		id,
		bantuan,
		info,
		tanda,
		tandaJenis,
		wajib = false,
		children
	}: {
		/** Penanda kecil di samping label, mis. "Frontend" / "Backend". */
		tanda?: string;
		/** Penanda alamat beranimasi (hover menjelaskan posisi frontend/backend). Menggantikan `tanda`. */
		tandaJenis?: 'frontend' | 'backend';
		label: string;
		id?: string;
		/** Teks bantuan yang selalu tampil di bawah kolom. */
		bantuan?: string;
		/** Bantuan ringkas lewat ikon ⓘ di samping label; tinggi kolom tetap seragam. */
		info?: string;
		wajib?: boolean;
		children: Snippet;
	} = $props();
</script>

<div class="grid gap-1.5">
	<!-- Tinggi tetap agar label dengan/tanpa ikon ⓘ tetap sejajar antarkolom. -->
	<div class="flex h-5 items-center gap-1.5">
		<Label for={id}>{label}{#if wajib}<span class="text-critical">*</span>{/if}</Label>
		{#if tandaJenis}
			<TandaAlamat jenis={tandaJenis} />
		{:else if tanda}
			<span class="rounded-sm border px-1 py-px font-mono text-[10px] leading-none tracking-wide text-muted-foreground uppercase">{tanda}</span>
		{/if}
		{#if info}
			<Tooltip.Root>
				<Tooltip.Trigger
					type="button"
					class="grid size-4 place-items-center rounded-full text-muted-foreground transition-colors hover:text-gold focus-visible:text-gold focus-visible:outline-none"
					aria-label="Bantuan: {label}"
				>
					<Info class="size-3.5" />
				</Tooltip.Trigger>
				<Tooltip.Content class="max-w-64 text-xs leading-snug">{info}</Tooltip.Content>
			</Tooltip.Root>
		{/if}
	</div>
	{@render children()}
	{#if bantuan}<p class="text-xs text-muted-foreground">{bantuan}</p>{/if}
</div>
