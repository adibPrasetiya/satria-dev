<script lang="ts">
	// Ikhtisar katalog kontrol: satu kartu per fungsi keamanan. Detail kontrol & metode di /katalog/[fungsi].
	import { api } from '#lib/api/client.js';
	import type { Fungsi, Katalog } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import KartuFungsi from '#lib/components/KartuFungsi.svelte';
	import Search from '@lucide/svelte/icons/search';

	let katalog = $state<Katalog | null>(null);
	let galatMuat = $state<string | null>(null);
	let cari = $state('');

	async function muat() {
		try {
			katalog = await api.getKatalog();
			galatMuat = null;
		} catch (e) {
			galatMuat = (e as Error).message;
		}
	}
	$effect(() => {
		muat();
	});

	const aktif = (x: { aktif?: boolean }) => x.aktif !== false;
	const kontrolAktif = $derived((katalog?.fungsi_keamanan ?? []).flatMap((f) => f.kontrol.filter(aktif)));
	const jumlahMetode = $derived(kontrolAktif.reduce((n, k) => n + k.metode_pengujian.filter(aktif).length, 0));

	/** Jumlah metode aktif dalam fungsi yang cocok dengan kata kunci (nama fungsi cocok = semua metode). */
	function hitungCocok(f: Fungsi, q: string): number {
		const semua = f.kontrol.filter(aktif).flatMap((k) => k.metode_pengujian.filter(aktif).map((m) => ({ k, m })));
		if ([f.nama, f.id].some((s) => s.toLowerCase().includes(q))) return semua.length;
		return semua.filter(({ k, m }) =>
			[k.id, k.uraian, m.id, m.nama, m.check_id, m.kriteria_lulus].some((s) => s.toLowerCase().includes(q))
		).length;
	}

	const q = $derived(cari.trim().toLowerCase());
	const daftar = $derived(
		(katalog?.fungsi_keamanan ?? [])
			.map((f) => ({ f, cocok: q ? hitungCocok(f, q) : null }))
			.filter((x) => x.cocok === null || x.cocok > 0)
	);
</script>

<svelte:head><title>Katalog Kontrol — SATRIA</title></svelte:head>

<PageHeader
	label="Referensi"
	judul="Katalog Kontrol"
	deskripsi={katalog ? `${katalog.sumber.peraturan} — ${katalog.sumber.bagian}.` : undefined}
/>

{#if galatMuat}
	<Kosong judul="Katalog gagal dimuat" pesan={galatMuat}><Button variant="outline" onclick={muat}>Coba lagi</Button></Kosong>
{:else if !katalog}
	<Memuat />
{:else}
	<div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
		<p class="flex flex-wrap gap-x-4 gap-y-1 font-heading text-xs tracking-[0.14em] text-muted-foreground uppercase">
			<span><b class="font-stencil text-base text-gold">{katalog.fungsi_keamanan.length}</b> fungsi keamanan</span>
			<span><b class="font-stencil text-base text-foreground">{kontrolAktif.length}</b> kontrol</span>
			<span><b class="font-stencil text-base text-foreground">{jumlahMetode}</b> metode uji</span>
		</p>
		<div class="relative sm:w-80">
			<Search class="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
			<Input bind:value={cari} placeholder="Cari fungsi, kontrol, atau metode…" class="bg-card pl-8" />
		</div>
	</div>

	{#if daftar.length}
		<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
			{#each daftar as { f, cocok } (f.id)}
				<KartuFungsi fungsi={f} {cocok} />
			{/each}
		</div>
	{:else}
		<Kosong judul="Tidak ada yang cocok" pesan="Tidak ada fungsi, kontrol, atau metode yang cocok dengan “{cari}”." />
	{/if}
{/if}
