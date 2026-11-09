<script lang="ts" module>
	import type { Component } from 'svelte';

	export interface OpsiTaktis<T extends string = string> {
		id: T;
		judul: string;
		keterangan: string;
		/** Foto (grayscale) di sisi kiri kartu. */
		gambar: string;
		/** `object-position` foto, mis. 'left center' atau '70% center'. */
		posisiGambar?: string;
		Ikon: Component;
	}
</script>

<script lang="ts" generics="T extends string">
	// Modal pilihan bergaya taktis (dipakai "Operasi Pengujian" & "Metode Pengujian"): header bergaris,
	// dua kartu berfoto prajurit, ikon dalam heksagon, dan tanda centang pada kartu yang disorot.
	// Selalu bertema gelap (kelas `dark`), apa pun tema aplikasi. Klik kartu langsung memilih.
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { cn } from '#lib/utils.js';
	import Check from '@lucide/svelte/icons/check';

	let {
		open = $bindable(false),
		judul,
		deskripsi,
		opsi,
		onpilih
	}: {
		open?: boolean;
		judul: string;
		deskripsi: string;
		opsi: OpsiTaktis<T>[];
		onpilih: (id: T) => void;
	} = $props();

	// Kartu yang disorot (hover/fokus); bawaan kartu pertama setiap kali modal dibuka.
	let sorot = $state<T | null>(null);
	$effect(() => {
		if (open) sorot = opsi[0]?.id ?? null;
	});

	function pilih(id: T) {
		open = false;
		onpilih(id);
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content
		class="dark max-h-[calc(100dvh-2rem)] gap-0 overflow-y-auto border border-white/10 bg-card p-0 text-card-foreground shadow-2xl sm:max-w-[min(960px,calc(100%-2rem))] [&>button[data-slot=dialog-close]]:top-4 [&>button[data-slot=dialog-close]]:right-4"
	>
		<Dialog.Header class="flex-row items-center gap-4 border-b border-white/10 px-5 py-4 text-left sm:px-6">
			<span class="garis-taktis hidden h-6 w-14 shrink-0 sm:block" aria-hidden="true"></span>
			<div class="min-w-0">
				<Dialog.Title class="text-xl font-semibold sm:text-2xl">{judul}</Dialog.Title>
				<Dialog.Description class="mt-0.5 text-sm text-muted-foreground">{deskripsi}</Dialog.Description>
			</div>
		</Dialog.Header>

		<div class="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">
			{#each opsi as o (o.id)}
				{@const aktif = sorot === o.id}
				<button
					type="button"
					onclick={() => pilih(o.id)}
					onmouseenter={() => (sorot = o.id)}
					onfocus={() => (sorot = o.id)}
					aria-label="{o.judul}: {o.keterangan}"
					class={cn(
						'group relative grid min-h-56 grid-cols-[44%_1fr] overflow-hidden rounded-lg border bg-background/60 text-left transition-all duration-200 outline-none sm:min-h-64',
						aktif ? 'border-gold shadow-[0_0_0_1px_var(--gold),0_0_24px_-6px_var(--gold)]' : 'border-white/15'
					)}
				>
					<!-- Pola garis diagonal di pojok kanan atas -->
					<span class="pola-diagonal pointer-events-none absolute -top-2 -right-2 h-24 w-40" aria-hidden="true"></span>

					<!-- Foto prajurit, memudar ke kanan -->
					<span class="relative block overflow-hidden" aria-hidden="true">
						<img
							src={o.gambar}
							alt=""
							loading="lazy"
							style:object-position={o.posisiGambar ?? 'left center'}
							class={cn(
								'absolute inset-0 h-full w-full object-cover grayscale transition duration-300',
								aktif ? 'scale-[1.03] opacity-100' : 'opacity-80'
							)}
						/>
						<span class="absolute inset-0 bg-gradient-to-r from-transparent from-55% to-background/95"></span>
					</span>

					<span class="relative flex flex-col justify-center gap-2.5 py-5 pr-4 pl-1 sm:pr-5">
						<!-- Ikon dalam heksagon -->
						<span class={cn('relative grid size-11 place-items-center', aktif ? 'text-gold' : 'text-foreground/80')}>
							<svg viewBox="0 0 44 44" class="absolute inset-0 size-full" aria-hidden="true">
								<polygon
									points="22,2 39.3,12 39.3,32 22,42 4.7,32 4.7,12"
									fill="none"
									stroke="currentColor"
									stroke-width="1.6"
								/>
							</svg>
							<o.Ikon class="size-5" />
						</span>
						<span class="font-heading text-xl leading-none font-bold tracking-wide uppercase sm:text-2xl">{o.judul}</span>
						<span class="text-xs leading-relaxed text-muted-foreground sm:text-[13px]">{o.keterangan}</span>
					</span>

					{#if aktif}
						<span
							class="absolute top-3 right-3 grid size-6 place-items-center rounded bg-gold text-gold-foreground"
							aria-hidden="true"
						>
							<Check class="size-4" strokeWidth={3} />
						</span>
					{/if}
				</button>
			{/each}
		</div>
	</Dialog.Content>
</Dialog.Root>

<style>
	.garis-taktis {
		background: repeating-linear-gradient(-60deg, var(--gold) 0 7px, transparent 7px 12px);
		opacity: 0.85;
	}
	.pola-diagonal {
		background: repeating-linear-gradient(-45deg, rgb(255 255 255 / 0.05) 0 10px, transparent 10px 22px);
		mask-image: linear-gradient(to bottom left, black, transparent 70%);
	}
</style>
