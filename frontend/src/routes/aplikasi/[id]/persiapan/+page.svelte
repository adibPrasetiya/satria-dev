<script lang="ts">
	// Hub persiapan pengujian: kartu per fungsi keamanan + status keterpenuhan data.
	// Autentikasi aktif (menaut ke daftar bagiannya); fungsi lain "Segera".
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import type { Aplikasi, Katalog, PersiapanAuth } from '#lib/types.js';
	import { persiapanAuthKosong } from '#lib/persiapan/auth.js';
	import { ringkasBagianAuth } from '#lib/persiapan/bagian.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { cn } from '#lib/utils.js';
	import { relatif } from '#lib/format.js';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Lock from '@lucide/svelte/icons/lock';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import CircleDashed from '@lucide/svelte/icons/circle-dashed';

	const id = $derived(page.params.id!);

	// Fungsi yang persiapannya sudah tersedia. Sisanya tampil terkunci.
	const AKTIF = new Set(['AUTH']);

	let app = $state<Aplikasi | null>(null);
	let katalog = $state<Katalog | null>(null);
	let p = $state<PersiapanAuth | null>(null);
	let galat = $state<string | null>(null);

	$effect(() => {
		const aid = id;
		Promise.all([api.getAplikasi(aid), api.getKatalog(), api.getPersiapanAuth(aid)])
			.then(([a, k, simpanan]) => {
				app = a;
				katalog = k;
				p = simpanan ? { ...persiapanAuthKosong(), ...simpanan } : persiapanAuthKosong();
			})
			.catch((e) => (galat = (e as Error).message));
	});

	const ringkas = $derived(p ? ringkasBagianAuth(p) : { selesai: 0, total: 0 });
	const nomor = (n: number) => String(n).padStart(2, '0');
</script>

<svelte:head><title>Isi data pengujian — {app?.nama ?? 'Aplikasi'} — SATRIA</title></svelte:head>

{#if galat}
	<Kosong judul="Aplikasi tidak ditemukan" pesan={galat}><Button href="/aplikasi" variant="outline">Kembali</Button></Kosong>
{:else if !app || !katalog || !p}
	<Memuat />
{:else}
	<div class="mb-6">
		<a href="/aplikasi/{app.id}" class="mb-1.5 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
			<ChevronLeft class="size-3.5" /> {app.nama}
		</a>
		<p class="label-stensil text-[10px]">Isi data pengujian</p>
		<h1 class="font-heading text-2xl font-semibold tracking-[0.04em] uppercase">Fungsi Keamanan</h1>
		<p class="mt-1 max-w-2xl text-sm text-muted-foreground">
			Pilih fungsi keamanan untuk mengisi data yang dibutuhkan mesin uji. Data diisi per bagian — Anda tidak
			perlu melengkapi semuanya sekaligus.
		</p>
	</div>

	<div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
		{#each katalog.fungsi_keamanan as f (f.id)}
			{@const aktif = AKTIF.has(f.id)}
			{@const lengkap = aktif && ringkas.selesai === ringkas.total}
			{#if aktif}
				<a
					href="/aplikasi/{app.id}/persiapan/auth"
					class="sudut-taktis group flex flex-col rounded-lg border bg-card p-5 transition hover:border-gold/60 hover:bg-gold/5"
				>
					<div class="flex items-start justify-between gap-3">
						<span class="font-stencil text-2xl text-gold">{nomor(f.nomor)}</span>
						<span
							class={cn(
								'inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium',
								lengkap ? 'bg-success/12 text-success' : 'bg-muted text-muted-foreground'
							)}
						>
							{#if lengkap}<CircleCheck class="size-3.5" /> Lengkap{:else}<CircleDashed class="size-3.5" /> {ringkas.selesai}/{ringkas.total} bagian{/if}
						</span>
					</div>
					<h2 class="mt-3 font-heading text-base font-semibold tracking-[0.04em] uppercase">{f.nama}</h2>
					<p class="mt-1 flex-1 text-sm text-muted-foreground">
						Data login, pendaftaran, akun uji, dan dokumen pendukung untuk menilai keamanan autentikasi.
					</p>
					<!-- Bilah kemajuan ringkas. -->
					<div class="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
						<div class="h-full rounded-full bg-gold transition-all" style="width: {ringkas.total ? (ringkas.selesai / ringkas.total) * 100 : 0}%"></div>
					</div>
					<span class="mt-3 inline-flex items-center gap-1 text-sm font-medium text-gold">
						{ringkas.selesai > 0 ? 'Lanjutkan isian' : 'Isi data'}
						<ChevronRight class="size-4 transition-transform group-hover:translate-x-0.5" />
					</span>
					{#if p.diperbarui_pada}
						<span class="mt-1 text-[11px] text-muted-foreground">Diperbarui {relatif(p.diperbarui_pada)}</span>
					{/if}
				</a>
			{:else}
				<div class="sudut-taktis flex flex-col rounded-lg border border-dashed bg-muted/20 p-5 opacity-70">
					<div class="flex items-start justify-between gap-3">
						<span class="font-stencil text-2xl text-muted-foreground/60">{nomor(f.nomor)}</span>
						<span class="inline-flex items-center gap-1 rounded-sm border border-dashed px-2 py-0.5 text-xs text-muted-foreground">
							<Lock class="size-3" /> Segera
						</span>
					</div>
					<h2 class="mt-3 font-heading text-base font-semibold tracking-[0.04em] text-muted-foreground uppercase">{f.nama}</h2>
					<p class="mt-1 text-sm text-muted-foreground/80">Persiapan untuk fungsi ini belum tersedia.</p>
				</div>
			{/if}
		{/each}
	</div>
{/if}
