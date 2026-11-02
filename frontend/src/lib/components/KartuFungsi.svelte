<script lang="ts">
	// Kartu ringkas satu fungsi keamanan di ikhtisar katalog, bergaya emblem satuan: kepala loreng dengan nomor
	// stensil & lencana ikon, lalu hanya jumlah kontrol dan metode uji. Seluruh kartu menuju daftar kontrolnya.
	import type { Component } from 'svelte';
	import type { Fungsi } from '#lib/types.js';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import Timer from '@lucide/svelte/icons/timer';
	import Lock from '@lucide/svelte/icons/lock';
	import TextCursorInput from '@lucide/svelte/icons/text-cursor-input';
	import Binary from '@lucide/svelte/icons/binary';
	import ScrollText from '@lucide/svelte/icons/scroll-text';
	import Database from '@lucide/svelte/icons/database';
	import RadioTower from '@lucide/svelte/icons/radio-tower';
	import Bug from '@lucide/svelte/icons/bug';
	import Workflow from '@lucide/svelte/icons/workflow';
	import FileLock from '@lucide/svelte/icons/file-lock';
	import Webhook from '@lucide/svelte/icons/webhook';
	import Settings from '@lucide/svelte/icons/settings';
	import Shield from '@lucide/svelte/icons/shield';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	let {
		fungsi,
		cocok = null
	}: {
		fungsi: Fungsi;
		/** Jumlah metode yang cocok dengan pencarian; null = tidak sedang mencari. */
		cocok?: number | null;
	} = $props();

	const IKON: Record<string, Component<{ class?: string }>> = {
		AUTH: KeyRound,
		SESS: Timer,
		ACCS: Lock,
		INPV: TextCursorInput,
		CRYP: Binary,
		ERRL: ScrollText,
		DATA: Database,
		COMM: RadioTower,
		MALC: Bug,
		BLOG: Workflow,
		FILE: FileLock,
		APIS: Webhook,
		CONF: Settings
	};
	const Ikon = $derived(IKON[fungsi.id] ?? Shield);

	const aktif = (x: { aktif?: boolean }) => x.aktif !== false;
	const kontrol = $derived(fungsi.kontrol.filter(aktif));
	const metode = $derived(kontrol.reduce((n, k) => n + k.metode_pengujian.filter(aktif).length, 0));
</script>

<a
	href="/katalog/{fungsi.id}"
	class="kartu-fungsi group sudut-taktis relative flex flex-col overflow-hidden rounded-lg border bg-card transition-all duration-200 hover:-translate-y-0.5 hover:border-gold/70 hover:shadow-[0_14px_34px_rgb(0_0_0/0.35)] focus-visible:border-gold focus-visible:ring-2 focus-visible:ring-gold/40 focus-visible:outline-none"
>
	<!-- Kepala loreng: nomor stensil + kode sandi fungsi + lencana ikon. -->
	<div class="kepala bg-loreng relative flex h-24 items-center gap-4 border-b-2 border-gold/70 px-5">
		<span class="font-stencil text-5xl leading-none text-gold drop-shadow-[0_2px_6px_rgb(0_0_0/0.7)]">
			{String(fungsi.nomor).padStart(2, '0')}
		</span>
		<span class="h-10 w-px bg-gold/50" aria-hidden="true"></span>
		<span class="font-stencil text-2xl leading-none tracking-[0.18em] text-white/90 drop-shadow-[0_2px_4px_rgb(0_0_0/0.7)]">
			{fungsi.id}
		</span>
		<span
			class="ml-auto grid size-12 place-items-center rounded-full border-2 border-gold/70 bg-black/45 text-gold shadow-[inset_0_0_0_3px_rgb(0_0_0/0.35)] transition-transform duration-300 group-hover:rotate-[8deg]"
		>
			<Ikon class="size-5" />
		</span>
		{#if cocok !== null}
			<span class="absolute top-2 right-2 rounded-sm bg-gold px-1.5 py-0.5 font-heading text-[10px] font-semibold tracking-wider text-gold-foreground uppercase">
				{cocok} cocok
			</span>
		{/if}
	</div>

	<div class="flex flex-1 flex-col gap-4 p-5">
		<h2 class="line-clamp-2 min-h-[2.6em] font-heading text-base leading-snug font-semibold tracking-[0.06em] uppercase">
			{fungsi.nama}
		</h2>

		<div class="grid grid-cols-2 divide-x divide-border rounded-md border bg-muted/30">
			<div class="px-4 py-3">
				<p class="font-stencil text-3xl leading-none">{kontrol.length}</p>
				<p class="label-stensil mt-1.5 text-[10px] text-muted-foreground">Kontrol</p>
			</div>
			<div class="px-4 py-3">
				<p class="font-stencil text-3xl leading-none">{metode}</p>
				<p class="label-stensil mt-1.5 text-[10px] text-muted-foreground">Metode uji</p>
			</div>
		</div>

		<span
			class="mt-auto inline-flex items-center gap-1 self-end font-heading text-xs tracking-[0.14em] text-muted-foreground uppercase transition-colors group-hover:text-gold"
		>
			Buka <ChevronRight class="size-3.5 transition-transform group-hover:translate-x-0.5" />
		</span>
	</div>
</a>

<style>
	/* Motif loreng sedikit membesar saat disorot. */
	.kepala {
		transition: background-size 0.5s ease;
	}
	.kartu-fungsi:hover .kepala {
		background-size:
			auto,
			400px 400px;
	}
	@media (prefers-reduced-motion: reduce) {
		.kepala {
			transition: none;
		}
	}
</style>
