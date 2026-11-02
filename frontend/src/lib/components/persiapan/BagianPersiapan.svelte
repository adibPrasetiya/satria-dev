<script lang="ts">
	// Kartu satu bagian formulir persiapan: nomor, judul, metode yang dilayani, status kelengkapan,
	// dan (opsional) pertanyaan "fitur ini ada di aplikasi?" yang menentukan apakah isian ditampilkan.
	import type { Snippet } from 'svelte';
	import type { Ketersediaan } from '#lib/types.js';
	import { cn } from '#lib/utils.js';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import CircleDashed from '@lucide/svelte/icons/circle-dashed';
	import ListChecks from '@lucide/svelte/icons/list-checks';
	import * as Tooltip from '#lib/components/ui/tooltip/index.js';

	let {
		id,
		nomor,
		judul,
		ket,
		metode = [],
		lengkap,
		wajib = false,
		pertanyaan,
		tersedia = $bindable(),
		children
	}: {
		id: string;
		nomor: number;
		judul: string;
		ket: string;
		/** Metode yang memakai isian bagian ini (kode ringkas mis. "1.2-T02" + nama). */
		metode?: { kode: string; nama: string }[];
		/** undefined = bagian tanpa status kelengkapan. */
		lengkap?: boolean;
		wajib?: boolean;
		/** Bila diisi, tampil pilihan Ada / Tidak ada; isian hanya tampil saat "Ada". */
		pertanyaan?: string;
		tersedia?: Ketersediaan;
		children: Snippet;
	} = $props();
</script>

<section {id} class="sudut-taktis scroll-mt-28 rounded-lg border bg-card">
	<header class="flex flex-wrap items-start gap-3 border-b px-5 py-4">
		<span class="grid size-9 shrink-0 place-items-center rounded-sm bg-olive-dark font-stencil text-gold">{nomor}</span>
		<div class="min-w-0 flex-1">
			<h2 class="flex flex-wrap items-center gap-2 font-heading text-[15px] font-semibold tracking-[0.06em] uppercase">
				{judul}
				{#if wajib}<span class="rounded-sm bg-critical/12 px-1.5 py-0.5 font-sans text-[10px] font-medium tracking-normal text-critical normal-case">Wajib</span>{/if}
			</h2>
			<p class="mt-0.5 text-sm text-muted-foreground">{ket}</p>
		</div>
		<!-- Metode yang memakai isian: cukup jumlahnya; daftarnya muncul saat disorot. -->
		{#if metode.length}
			<Tooltip.Root>
				<Tooltip.Trigger
					type="button"
					class="inline-flex shrink-0 items-center gap-1 rounded-sm border px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:border-gold/50 hover:text-foreground"
				>
					<ListChecks class="size-3.5" /> {metode.length} metode uji
				</Tooltip.Trigger>
				<Tooltip.Content class="max-w-80">
					<!-- Dibungkus satu blok: isi tooltip bawaan berupa flex baris. -->
					<div class="grid gap-1 py-0.5">
						<p class="text-[11px] font-semibold">Isian bagian ini dipakai oleh:</p>
						<ul class="grid gap-1 text-[11px]">
							{#each metode as m (m.kode)}
								<li class="grid grid-cols-[52px_1fr] gap-1.5"><span class="font-mono opacity-70">{m.kode}</span><span>{m.nama}</span></li>
							{/each}
						</ul>
					</div>
				</Tooltip.Content>
			</Tooltip.Root>
		{/if}
		{#if lengkap !== undefined}
			<span
				class={cn(
					'inline-flex shrink-0 items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium',
					lengkap ? 'bg-success/12 text-success' : 'bg-muted text-muted-foreground'
				)}
			>
				{#if lengkap}<CircleCheck class="size-3.5" /> Lengkap{:else}<CircleDashed class="size-3.5" /> Belum lengkap{/if}
			</span>
		{/if}
	</header>

	<div class="grid gap-4 p-5">
		{#if pertanyaan}
			<div class="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-muted/30 px-4 py-3">
				<p class="text-sm font-medium">{pertanyaan}</p>
				<div class="inline-flex rounded-md border p-0.5 text-sm" role="radiogroup" aria-label={pertanyaan}>
					{#each [{ v: true, l: 'Ada' }, { v: false, l: 'Tidak ada' }] as o (o.l)}
						<button
							type="button"
							role="radio"
							aria-checked={tersedia === o.v}
							class={cn(
								'rounded px-3 py-1 transition-colors',
								tersedia === o.v ? (o.v ? 'bg-gold text-gold-foreground' : 'bg-muted-foreground/80 text-background') : 'text-muted-foreground hover:bg-muted'
							)}
							onclick={() => (tersedia = o.v)}
						>
							{o.l}
						</button>
					{/each}
				</div>
			</div>
		{/if}

		{#if !pertanyaan || tersedia === true}
			{@render children()}
		{:else if tersedia === false}
			<p class="text-sm text-muted-foreground">Metode di bagian ini akan <b>dilewati</b> karena fitur tidak ada di aplikasi.</p>
		{:else}
			<p class="text-sm text-muted-foreground">Pilih <b>Ada</b> atau <b>Tidak ada</b> terlebih dahulu.</p>
		{/if}
	</div>
</section>
