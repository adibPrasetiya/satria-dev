<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { ringkasAplikasi, type RingkasanAplikasi } from '#lib/ringkasan.js';
	import { relatif } from '#lib/format.js';
	import type { Putusan } from '#lib/types.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import DialogPilihTindakan from '#lib/components/pengujian/DialogPilihTindakan.svelte';
	import DialogPilihMetode from '#lib/components/pengujian/DialogPilihMetode.svelte';
	import PutusanBadge from '#lib/components/PutusanBadge.svelte';
	import SkorBar from '#lib/components/SkorBar.svelte';
	import NativeSelect from '#lib/components/NativeSelect.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import CirclePlus from '@lucide/svelte/icons/circle-plus';
	import Search from '@lucide/svelte/icons/search';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	let daftar = $state<RingkasanAplikasi[] | null>(null);
	let cari = $state('');
	let filter = $state<'semua' | Putusan | 'belum'>('semua');

	// Modal berjenjang saat baris aset diklik: tindakan (riwayat/pengujian) → metode.
	let dipilih = $state<string | null>(null);
	let dlgTindakan = $state(false);
	let dlgMetode = $state(false);
	function bukaAset(id: string) {
		dipilih = id;
		dlgTindakan = true;
	}

	// Cakupan (pemilik: satuannya; asesor/admin: semua) ditentukan backend.
	$effect(() => {
		Promise.all([api.listAplikasi(), api.listScan()]).then(([apps, scans]) => {
			daftar = ringkasAplikasi(apps, scans);
		});
	});

	const tersaring = $derived(
		(daftar ?? []).filter((r) => {
			const q = cari.toLowerCase();
			const cocok =
				!q || [r.app.nama, r.app.satuan, r.app.url_dasar].some((s) => s.toLowerCase().includes(q));
			const f =
				filter === 'semua' ||
				(filter === 'belum' ? !r.penilaian : r.penilaian?.putusan === filter);
			return cocok && f;
		})
	);

	const LABEL_LINGKUNGAN = { produksi: 'Produksi', staging: 'Staging', pengembangan: 'Pengembangan' };
	const LABEL_KLASIFIKASI = { biasa: 'Biasa', terbatas: 'Terbatas', rahasia: 'Rahasia' };
	const WARNA_KLASIFIKASI = {
		biasa: 'border-border text-muted-foreground',
		terbatas: 'border-warning/60 text-warning-foreground',
		rahasia: 'border-critical/60 text-critical'
	};
</script>

<PageHeader
	label="Inventaris"
	judul="Aplikasi"
	deskripsi="Daftar aplikasi web yang diregistrasikan untuk asesmen kelaikan keamanan."
>
	{#snippet aksi()}
		{#if auth.punya('pemilik', 'admin')}
			<Button href="/aplikasi/baru"><CirclePlus /> Registrasi Aplikasi</Button>
		{/if}
	{/snippet}
</PageHeader>

<div class="mb-4 flex flex-col gap-2 sm:flex-row">
	<div class="relative flex-1">
		<Search class="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
		<Input bind:value={cari} placeholder="Cari nama, satuan, atau URL…" class="bg-card pl-8" />
	</div>
	<NativeSelect
		bind:value={filter}
		class="bg-card sm:w-52"
		opsi={[
			{ value: 'semua', label: 'Semua putusan' },
			{ value: 'laik', label: 'Laik' },
			{ value: 'laik_bersyarat', label: 'Laik Bersyarat' },
			{ value: 'tidak_laik', label: 'Tidak Laik' },
			{ value: 'belum', label: 'Belum diuji' }
		]}
	/>
</div>

{#if !daftar}
	<Memuat />
{:else if daftar.length === 0}
	<Kosong judul="Belum ada aplikasi" pesan="Registrasikan aplikasi untuk memulai asesmen.">
		{#if auth.punya('pemilik', 'admin')}
			<Button href="/aplikasi/baru"><CirclePlus /> Registrasi Aplikasi</Button>
		{/if}
	</Kosong>
{:else}
	<div class="sudut-taktis overflow-hidden rounded-lg border bg-card">
		<Table.Root>
			<Table.Header>
				<Table.Row class="bg-olive-dark hover:bg-olive-dark">
					{#each ['Aplikasi', 'Lingkungan', 'Klasifikasi', 'Kepatuhan', 'Putusan', 'Uji Terakhir'] as h (h)}
						<Table.Head class="font-heading text-[11px] tracking-[0.15em] text-sidebar-foreground uppercase">
							{h}
						</Table.Head>
					{/each}
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each tersaring as r (r.app.id)}
					<Table.Row class="cursor-pointer" onclick={() => bukaAset(r.app.id)}>
						<Table.Cell class="max-w-72">
							<span class="block truncate font-medium">{r.app.nama}</span>
							<p class="truncate text-xs text-muted-foreground">{r.app.satuan} · {r.app.url_dasar}</p>
						</Table.Cell>
						<Table.Cell class="text-sm">{LABEL_LINGKUNGAN[r.app.lingkungan]}</Table.Cell>
						<Table.Cell>
							<span class="rounded-sm border px-1.5 py-0.5 font-heading text-[10px] tracking-[0.12em] uppercase {WARNA_KLASIFIKASI[r.app.klasifikasi_data]}">
								{LABEL_KLASIFIKASI[r.app.klasifikasi_data]}
							</span>
						</Table.Cell>
						<Table.Cell class="w-44">
							{#if r.penilaian}
								<SkorBar skor={r.penilaian.skor} putusan={r.penilaian.putusan} />
							{:else}
								<span class="text-xs text-muted-foreground">—</span>
							{/if}
						</Table.Cell>
						<Table.Cell>
							{#if r.berjalan}
								<span class="inline-flex items-center gap-1 text-xs text-info"><LoaderCircle class="size-3 animate-spin" /> Berjalan</span>
							{:else if r.penilaian}
								<PutusanBadge putusan={r.penilaian.putusan} />
							{:else}
								<span class="text-xs text-muted-foreground">Belum diuji</span>
							{/if}
						</Table.Cell>
						<Table.Cell class="text-xs text-muted-foreground">{relatif(r.scanTerakhir?.dimulai_pada)}</Table.Cell>
					</Table.Row>
				{:else}
					<Table.Row>
						<Table.Cell colspan={6} class="py-8 text-center text-sm text-muted-foreground">
							Tidak ada aplikasi yang cocok dengan filter.
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
{/if}

<DialogPilihTindakan
	bind:open={dlgTindakan}
	onlihatRiwayat={() => dipilih && goto(`/aplikasi/${dipilih}`)}
	onpengujian={() => (dlgMetode = true)}
/>
<DialogPilihMetode bind:open={dlgMetode} onotomatis={() => dipilih && goto(`/aplikasi/${dipilih}/pengujian/otomatis`)} />
