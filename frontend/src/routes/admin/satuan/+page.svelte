<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import { relatif } from '#lib/format.js';
	import { JENIS_SATUAN, labelJenis, PROVINSI } from '#lib/data/satuan.js';
	import type { SatuanAdmin } from '#lib/types.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import NativeSelect from '#lib/components/NativeSelect.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import DialogSatuan from '#lib/components/DialogSatuan.svelte';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import Search from '@lucide/svelte/icons/search';
	import CirclePlus from '@lucide/svelte/icons/circle-plus';
	import Pencil from '@lucide/svelte/icons/pencil';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Network from '@lucide/svelte/icons/network';
	import MapPin from '@lucide/svelte/icons/map-pin';
	import Building from '@lucide/svelte/icons/building-2';
	import House from '@lucide/svelte/icons/house';

	type Status = 'aktif' | 'nonaktif' | '';
	type Hasil = { items: SatuanAdmin[]; total: number; totalPages: number; limit: number };

	// Satuan yang sedang dibuka (lihat sub-satuannya) disimpan di URL agar tombol Kembali & tautan berfungsi.
	const indukId = $derived(page.url.searchParams.get('induk'));

	let hasil = $state<Hasil | null>(null);
	let induk = $state<SatuanAdmin | null>(null);
	let cari = $state('');
	let status = $state<Status>('');
	let jenis = $state('');
	let provinsi = $state('');
	let halaman = $state(1);

	// Pencarian/filter jenis/provinsi = daftar datar lintas tingkat; tanpa itu = telusur per tingkat hierarki.
	const modeCari = $derived(!!(cari.trim() || jenis || provinsi));

	async function muat() {
		try {
			hasil = await api.listSatuanAdmin({
				search: cari.trim(),
				status,
				jenis,
				provinsi,
				induk: modeCari ? undefined : (indukId ?? 'akar'),
				page: halaman
			});
		} catch (e) {
			toast.error((e as Error).message);
			hasil = { items: [], total: 0, totalPages: 1, limit: 50 };
		}
	}

	async function muatInduk(id: string | null) {
		if (!id) return (induk = null);
		try {
			induk = await api.getSatuanAdmin(id);
		} catch (e) {
			toast.error((e as Error).message);
			buka(null);
		}
	}

	// Muat ulang saat filter/halaman/induk berubah; pencarian ditunda agar tidak memanggil API per ketikan.
	$effect(() => {
		void [status, jenis, provinsi, halaman, indukId];
		const q = cari;
		const t = setTimeout(muat, q ? 300 : 0);
		return () => clearTimeout(t);
	});
	$effect(() => {
		void muatInduk(indukId);
	});

	// Filter baru selalu mulai dari halaman pertama.
	function gantiFilter() {
		halaman = 1;
	}

	/** Buka satuan untuk melihat sub-satuannya (null = kembali ke satuan teratas). */
	function buka(id: string | null) {
		cari = '';
		jenis = '';
		provinsi = '';
		halaman = 1;
		const url = new URL(page.url.href);
		if (id) url.searchParams.set('induk', id);
		else url.searchParams.delete('induk');
		void goto(url, { reset: false });
	}

	// Dialog tambah / ubah (target null + dialog terbuka = tambah); form bertahap ada di DialogSatuan.
	let dialogBuka = $state(false);
	let target = $state<SatuanAdmin | null>(null);
	function bukaDialog(s: SatuanAdmin | null) {
		target = s;
		dialogBuka = true;
	}

	const awal = $derived(hasil && hasil.total ? (halaman - 1) * hasil.limit + 1 : 0);
	const akhir = $derived(hasil ? Math.min(halaman * hasil.limit, hasil.total) : 0);
	const lokasi = (s: SatuanAdmin) => [s.kota, s.provinsi].filter(Boolean).join(', ');
	const opsiJenis = JENIS_SATUAN.map((j) => ({ value: j.kode, label: j.label }));
	const opsiProvinsi = PROVINSI.map((p) => ({ value: p.kode, label: p.nama }));
</script>

<PageHeader
	label="Administrasi"
	judul="Satuan Kerja"
	deskripsi="Kelola hierarki satuan kerja (Mabes, Kotama, Korem, Kodim, …) beserta lokasinya. Lokasi dipakai peta sebaran sistem informasi per daerah di dasbor."
>
	{#snippet aksi()}
		<Button onclick={() => bukaDialog(null)}>
			<CirclePlus />
			{!modeCari && induk ? 'Tambah sub-satuan' : 'Tambah satuan'}
		</Button>
	{/snippet}
</PageHeader>

<div class="mb-4 grid gap-2 sm:grid-cols-[1fr_auto_auto_auto]">
	<div class="relative">
		<Search class="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
		<Input
			bind:value={cari}
			oninput={gantiFilter}
			placeholder="Cari nama satuan di semua tingkat…"
			class="bg-card pl-8"
		/>
	</div>
	<NativeSelect
		bind:value={jenis}
		onchange={gantiFilter}
		class="bg-card sm:w-40"
		opsi={[{ value: '', label: 'Semua jenis' }, ...opsiJenis]}
	/>
	<NativeSelect
		bind:value={provinsi}
		onchange={gantiFilter}
		class="bg-card sm:w-48"
		opsi={[{ value: '', label: 'Semua provinsi' }, ...opsiProvinsi]}
	/>
	<NativeSelect
		bind:value={status}
		onchange={gantiFilter}
		class="bg-card sm:w-36"
		opsi={[
			{ value: '', label: 'Semua status' },
			{ value: 'aktif', label: 'Aktif' },
			{ value: 'nonaktif', label: 'Nonaktif' }
		]}
	/>
</div>

{#if modeCari}
	<p class="mb-3 text-sm text-muted-foreground">
		Hasil pencarian di semua tingkat hierarki.
		<button
			type="button"
			class="font-medium text-foreground underline-offset-2 hover:underline"
			onclick={() => buka(indukId)}
		>
			Kembali ke penelusuran
		</button>
	</p>
{:else}
	<!-- Breadcrumb hierarki: klik untuk naik ke tingkat mana pun. -->
	<nav aria-label="Hierarki satuan" class="mb-3 flex flex-wrap items-center gap-1 text-sm">
		<button
			type="button"
			class={cn(
				'inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 hover:bg-muted',
				!indukId ? 'font-medium' : 'text-muted-foreground'
			)}
			onclick={() => buka(null)}
			aria-current={!indukId ? 'page' : undefined}
		>
			<House class="size-3.5" /> Satuan teratas
		</button>
		{#if induk}
			{#each induk.leluhur as l (l.id)}
				<ChevronRight class="size-3.5 text-muted-foreground" />
				<button
					type="button"
					class="rounded px-1.5 py-0.5 text-muted-foreground hover:bg-muted"
					onclick={() => buka(l.id)}>{l.nama}</button
				>
			{/each}
			<ChevronRight class="size-3.5 text-muted-foreground" />
			<span class="px-1.5 py-0.5 font-medium" aria-current="page">{induk.nama}</span>
		{/if}
	</nav>

	{#if induk}
		<div
			class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card p-3"
		>
			<div class="flex min-w-0 items-center gap-3">
				<div class="grid size-9 shrink-0 place-items-center rounded-md bg-muted">
					<Building class="size-4" />
				</div>
				<div class="min-w-0">
					<p class="flex flex-wrap items-center gap-2 font-medium">
						{induk.nama}
						<span class="rounded-sm border px-1.5 py-px text-[11px] text-muted-foreground"
							>{labelJenis(induk.jenis)}</span
						>
						{#if !induk.aktif}<span
								class="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
								>Nonaktif</span
							>{/if}
					</p>
					<p class="flex items-center gap-1 text-xs text-muted-foreground">
						<MapPin class="size-3" />
						{lokasi(induk) || 'Lokasi belum diisi'}{induk.alamat ? ` — ${induk.alamat}` : ''}
					</p>
				</div>
			</div>
			<Button size="sm" variant="outline" onclick={() => bukaDialog(induk)}
				><Pencil /> Ubah satuan ini</Button
			>
		</div>
	{/if}
{/if}

{#if !hasil}
	<Memuat />
{:else if hasil.items.length === 0}
	<Kosong
		judul={modeCari ? 'Tidak ada satuan' : induk ? 'Belum ada sub-satuan' : 'Belum ada satuan'}
		pesan={modeCari
			? 'Tidak ada satuan yang cocok dengan filter.'
			: induk
				? `Tambahkan satuan di bawah ${induk.nama}.`
				: 'Mulai dari satuan teratas, mis. Mabes TNI, lalu tambahkan sub-satuannya.'}
	>
		{#if !modeCari}
			<Button variant="outline" onclick={() => bukaDialog(null)}
				><CirclePlus /> {induk ? 'Tambah sub-satuan' : 'Tambah satuan'}</Button
			>
		{/if}
	</Kosong>
{:else}
	<div class="sudut-taktis overflow-hidden rounded-lg border bg-card">
		<Table.Root>
			<Table.Header>
				<Table.Row class="bg-olive-dark hover:bg-olive-dark">
					{#each ['Nama satuan', 'Lokasi', 'Sub-satuan', 'Pengguna / aplikasi', 'Ditambahkan', 'Status', ''] as h, i (i)}
						<Table.Head
							class="font-heading text-[11px] tracking-[0.15em] text-sidebar-foreground uppercase"
							>{h}</Table.Head
						>
					{/each}
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each hasil.items as s (s.id)}
					<Table.Row class={s.aktif ? '' : 'opacity-60'}>
						<Table.Cell class="whitespace-normal">
							<button
								type="button"
								class="group grid text-left"
								onclick={() => buka(s.id)}
								aria-label={`Buka sub-satuan ${s.nama}`}
							>
								<span class="flex flex-wrap items-center gap-2">
									<span class="font-medium group-hover:underline">{s.nama}</span>
									<span class="rounded-sm border px-1.5 py-px text-[11px] text-muted-foreground"
										>{labelJenis(s.jenis)}</span
									>
								</span>
								{#if modeCari && s.jalur}<span class="text-xs text-muted-foreground">{s.jalur}</span
									>{/if}
							</button>
						</Table.Cell>
						<Table.Cell class="text-sm whitespace-normal">
							{#if lokasi(s)}
								<span class="flex items-center gap-1">
									<MapPin
										class={cn(
											'size-3.5 shrink-0',
											s.latitude !== null ? 'text-success' : 'text-muted-foreground'
										)}
									/>
									{lokasi(s)}
								</span>
								{#if s.latitude === null}<span class="text-xs text-muted-foreground"
										>tanpa titik koordinat</span
									>{/if}
							{:else}
								<span class="text-muted-foreground">—</span>
							{/if}
						</Table.Cell>
						<Table.Cell class="text-sm tabular-nums">
							<button
								type="button"
								class="inline-flex items-center gap-1 rounded px-1 hover:bg-muted"
								onclick={() => buka(s.id)}
							>
								<Network class="size-3.5 text-muted-foreground" />{s.jumlah_sub}
							</button>
						</Table.Cell>
						<Table.Cell class="text-sm tabular-nums"
							>{s.jumlah_pengguna} akun · {s.jumlah_aplikasi} aplikasi</Table.Cell
						>
						<Table.Cell class="text-sm text-muted-foreground">{relatif(s.dibuat_pada)}</Table.Cell>
						<Table.Cell>
							<span
								class={cn(
									'inline-flex rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
									s.aktif ? 'bg-success/12 text-success' : 'bg-muted text-muted-foreground'
								)}
							>
								{s.aktif ? 'Aktif' : 'Nonaktif'}
							</span>
						</Table.Cell>
						<Table.Cell class="text-right">
							<Button
								size="sm"
								variant="outline"
								onclick={() => bukaDialog(s)}
								aria-label={`Ubah ${s.nama}`}
							>
								<Pencil /> Ubah
							</Button>
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>

	<div class="mt-3 flex items-center justify-between gap-2 text-sm text-muted-foreground">
		<span>{awal}–{akhir} dari {hasil.total} satuan</span>
		{#if hasil.totalPages > 1}
			<div class="flex gap-1.5">
				<Button size="sm" variant="outline" disabled={halaman <= 1} onclick={() => (halaman -= 1)}>
					<ChevronLeft /> Sebelumnya
				</Button>
				<Button
					size="sm"
					variant="outline"
					disabled={halaman >= hasil.totalPages}
					onclick={() => (halaman += 1)}
				>
					Berikutnya <ChevronRight />
				</Button>
			</div>
		{/if}
	</div>
{/if}

<DialogSatuan
	bind:open={dialogBuka}
	{target}
	indukAwal={modeCari ? null : induk}
	onsimpan={() => Promise.all([muat(), muatInduk(indukId)])}
/>
