<script lang="ts">
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { relatif } from '#lib/format.js';
	import { cn } from '#lib/utils.js';
	import type {
		FilterAplikasi,
		FilterPutusan,
		HalamanAplikasi,
		KlasifikasiData,
		Lingkungan,
		TemuanSeverity,
		UrutAplikasi
	} from '#lib/types.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import * as Tooltip from '#lib/components/ui/tooltip/index.js';
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
	import ArrowUpDown from '@lucide/svelte/icons/arrow-up-down';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import ChevronsLeft from '@lucide/svelte/icons/chevrons-left';
	import ChevronsRight from '@lucide/svelte/icons/chevrons-right';
	import X from '@lucide/svelte/icons/x';

	// Filter, urutan, dan paginasi dikerjakan di backend (GET /applications); halaman ini hanya
	// menyimpan parameter & menampilkan satu halaman hasil.

	let data = $state<HalamanAplikasi | null>(null);
	let memuat = $state(false);
	let galat = $state<string | null>(null);

	// --- Filter ('' = semua) ---
	let cari = $state('');
	let cariAktif = $state(''); // `cari` setelah debounce
	let fPutusan = $state<FilterPutusan | ''>('');
	let fLingkungan = $state<Lingkungan | ''>('');
	let fKlasifikasi = $state<KlasifikasiData | ''>('');
	let fSatuan = $state('');

	// --- Urutan & halaman ---
	let urut = $state<UrutAplikasi>('uji');
	let arah = $state<'asc' | 'desc'>('desc');
	let halaman = $state(1);
	let perHalaman = $state('25');

	// Modal berjenjang saat baris aset diklik: tindakan (riwayat/pengujian) → metode.
	let dipilih = $state<string | null>(null);
	let dlgTindakan = $state(false);
	let dlgMetode = $state(false);
	// Pemilik tidak melakukan pengujian → langsung ke riwayat/hasil tanpa modal tindakan.
	function bukaAset(id: string) {
		dipilih = id;
		if (auth.bisaMenguji) dlgTindakan = true;
		else bukaRiwayat(id);
	}

	// Riwayat pengujian → halaman operasi pengujian terakhir (riwayat lain dipilih di sana);
	// aplikasi yang belum pernah diuji → berkas aplikasi.
	async function bukaRiwayat(id: string) {
		try {
			const [terakhir] = await api.listScan(id);
			if (terakhir) return goto(`/scan/${terakhir.id}`);
			toast.info('Aplikasi ini belum pernah diuji.');
		} catch {
			/* gagal memuat riwayat → tampilkan berkas aplikasi */
		}
		goto(`/aplikasi/${id}`);
	}

	// Pencarian dikirim setelah pengguna berhenti mengetik.
	$effect(() => {
		const q = cari;
		const t = setTimeout(() => (cariAktif = q.trim()), 300);
		return () => clearTimeout(t);
	});

	// Perubahan filter/urutan/ukuran halaman → kembali ke halaman 1 (tanpa permintaan ganda).
	const kunciFilter = $derived(
		JSON.stringify([
			cariAktif,
			fPutusan,
			fLingkungan,
			fKlasifikasi,
			fSatuan,
			urut,
			arah,
			perHalaman
		])
	);
	let kunciTerakhir = '';

	// Cakupan (pemilik: satuannya; asesor/admin: semua) ditentukan backend.
	let nomorPermintaan = 0;
	$effect(() => {
		if (kunciFilter !== kunciTerakhir) {
			kunciTerakhir = kunciFilter;
			if (halaman !== 1) {
				halaman = 1; // efek berjalan ulang dengan halaman 1
				return;
			}
		}
		const filter: FilterAplikasi = {
			page: halaman,
			limit: Number(perHalaman) as FilterAplikasi['limit'],
			search: cariAktif,
			putusan: fPutusan,
			lingkungan: fLingkungan,
			klasifikasi: fKlasifikasi,
			satuan_id: fSatuan,
			sort: urut,
			order: arah,
			ringkasan: true
		};
		const ini = ++nomorPermintaan;
		memuat = true;
		api
			.cariAplikasi(filter)
			.then((hasil) => {
				if (ini !== nomorPermintaan) return; // jawaban usang
				data = hasil;
				galat = null;
				// Halaman di luar jangkauan (mis. data berkurang) → loncat ke halaman terakhir.
				if (hasil.total > 0 && halaman > hasil.totalPages) halaman = hasil.totalPages;
			})
			.catch((e) => {
				if (ini === nomorPermintaan)
					galat = e instanceof Error ? e.message : 'Gagal memuat daftar aplikasi';
			})
			.finally(() => {
				if (ini === nomorPermintaan) memuat = false;
			});
	});

	const adaFilter = $derived(
		cari !== '' || fPutusan !== '' || fLingkungan !== '' || fKlasifikasi !== '' || fSatuan !== ''
	);
	function resetFilter() {
		cari = '';
		cariAktif = '';
		fPutusan = '';
		fLingkungan = '';
		fKlasifikasi = '';
		fSatuan = '';
	}

	function aturUrut(k: UrutAplikasi) {
		if (urut === k) arah = arah === 'asc' ? 'desc' : 'asc';
		else {
			urut = k;
			// Skor, temuan, & tanggal paling berguna dimulai dari yang terbesar/terbaru.
			arah = k === 'skor' || k === 'temuan' || k === 'uji' ? 'desc' : 'asc';
		}
	}

	const totalHalaman = $derived(data?.totalPages ?? 1);
	const awal = $derived(data ? (data.page - 1) * data.limit : 0);

	// Nomor halaman ringkas: 1 … 4 5 6 … 12
	const nomorHalaman = $derived.by(() => {
		const n = totalHalaman;
		const c = halaman;
		if (n <= 7) return Array.from({ length: n }, (_, i) => i + 1);
		const urutan = [...new Set([1, n, c - 1, c, c + 1].filter((p) => p >= 1 && p <= n))].sort(
			(a, b) => a - b
		);
		const hasil: (number | '…')[] = [];
		urutan.forEach((p, i) => {
			if (i > 0 && p - urutan[i - 1] > 1) hasil.push('…');
			hasil.push(p);
		});
		return hasil;
	});

	const opsiSatuan = $derived([
		{ value: '', label: 'Semua satuan' },
		...(data?.opsi_satuan ?? []).map((s) => ({ value: s.id, label: `${s.nama} (${s.jumlah})` }))
	]);

	const LABEL_LINGKUNGAN: Record<Lingkungan, string> = {
		produksi: 'Produksi',
		staging: 'Staging',
		pengembangan: 'Pengembangan'
	};
	const LABEL_KLASIFIKASI: Record<KlasifikasiData, string> = {
		biasa: 'Biasa',
		terbatas: 'Terbatas',
		rahasia: 'Rahasia'
	};
	const WARNA_KLASIFIKASI: Record<KlasifikasiData, string> = {
		biasa: 'border-border text-muted-foreground',
		terbatas: 'border-warning/60 text-warning-foreground',
		rahasia: 'border-critical/60 text-critical'
	};
	const WARNA_LINGKUNGAN: Record<Lingkungan, string> = {
		produksi: 'bg-critical',
		staging: 'bg-warning',
		pengembangan: 'bg-info'
	};

	// Sel temuan: satu kotak per severity (warna senada SeverityBadge); nol diredupkan.
	const SEVERITAS: { k: keyof TemuanSeverity; singkat: string; label: string; warna: string }[] = [
		{ k: 'kritis', singkat: 'K', label: 'Kritis', warna: 'bg-critical text-white' },
		{ k: 'tinggi', singkat: 'T', label: 'Tinggi', warna: 'bg-critical/15 text-critical' },
		{ k: 'sedang', singkat: 'S', label: 'Sedang', warna: 'bg-warning/20 text-warning-foreground' },
		{ k: 'rendah', singkat: 'R', label: 'Rendah', warna: 'bg-info/12 text-info' }
	];
	const totalTemuan = (t: TemuanSeverity) => t.kritis + t.tinggi + t.sedang + t.rendah;

	const KOLOM: { label: string; urut?: UrutAplikasi; class?: string }[] = [
		{ label: 'Aplikasi', urut: 'nama', class: 'min-w-64' },
		{ label: 'Satuan', urut: 'satuan', class: 'min-w-40' },
		{ label: 'Lingkungan', urut: 'lingkungan' },
		{ label: 'Klasifikasi', urut: 'klasifikasi' },
		{ label: 'Kepatuhan', urut: 'skor', class: 'w-44' },
		{ label: 'Temuan', urut: 'temuan' },
		{ label: 'Putusan' },
		{ label: 'Uji Terakhir', urut: 'uji' }
	];

	const STAT: { key: FilterPutusan | ''; label: string; warna: string }[] = [
		{ key: '', label: 'Total Aplikasi', warna: 'bg-primary' },
		{ key: 'laik', label: 'Laik', warna: 'bg-success' },
		{ key: 'laik_bersyarat', label: 'Laik Bersyarat', warna: 'bg-warning' },
		{ key: 'tidak_laik', label: 'Tidak Laik', warna: 'bg-critical' },
		{ key: 'belum', label: 'Belum Diuji', warna: 'bg-muted-foreground/50' }
	];
</script>

<PageHeader
	label="Inventaris"
	judul="Aplikasi"
	deskripsi="Daftar aplikasi web yang diregistrasikan untuk asesmen kelaikan keamanan."
>
	{#snippet aksi()}
		{#if auth.bisaMendaftarkan}
			<Button href="/aplikasi/baru"><CirclePlus /> Registrasi Aplikasi</Button>
		{/if}
	{/snippet}
</PageHeader>

{#if !data && galat}
	<Kosong judul="Gagal memuat" pesan={galat} />
{:else if !data}
	<Memuat />
{:else if data.ringkasan?.semua === 0 && !adaFilter}
	<Kosong judul="Belum ada aplikasi" pesan="Registrasikan aplikasi untuk memulai asesmen.">
		{#if auth.bisaMendaftarkan}
			<Button href="/aplikasi/baru"><CirclePlus /> Registrasi Aplikasi</Button>
		{/if}
	</Kosong>
{:else}
	<!-- Strip statistik: jumlah per putusan (filter lain tetap berlaku) sekaligus pintasan filter -->
	<div class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
		{#each STAT as s (s.key)}
			{@const aktif = fPutusan === s.key}
			<button
				type="button"
				onclick={() => (fPutusan = aktif ? '' : s.key)}
				aria-pressed={aktif}
				class={cn(
					'relative overflow-hidden rounded-lg border bg-card px-4 py-3 text-left transition-colors hover:border-primary/50',
					aktif && 'border-primary ring-2 ring-primary/20'
				)}
			>
				<span class={cn('absolute inset-y-0 left-0 w-1', s.warna)}></span>
				<p class="font-heading text-[10px] tracking-[0.15em] text-muted-foreground uppercase">
					{s.label}
				</p>
				<p class="mt-0.5 text-2xl font-semibold tabular-nums">
					{data.ringkasan?.[s.key || 'semua'] ?? 0}
				</p>
			</button>
		{/each}
	</div>

	<div class="sudut-taktis overflow-hidden rounded-lg border bg-card">
		<!-- Bilah filter -->
		<div class="flex flex-col gap-2 border-b p-3 lg:flex-row lg:items-center">
			<div class="relative lg:max-w-sm lg:flex-1">
				<Search class="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
				<Input bind:value={cari} placeholder="Cari nama, satuan, URL, atau PIC…" class="pl-8" />
			</div>
			<div class="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:flex lg:flex-1 lg:flex-wrap">
				<NativeSelect
					bind:value={fSatuan}
					class="lg:w-52"
					aria-label="Filter satuan"
					opsi={opsiSatuan}
				/>
				<NativeSelect
					bind:value={fLingkungan}
					class="lg:w-44"
					aria-label="Filter lingkungan"
					opsi={[
						{ value: '', label: 'Semua lingkungan' },
						{ value: 'produksi', label: 'Produksi' },
						{ value: 'staging', label: 'Staging' },
						{ value: 'pengembangan', label: 'Pengembangan' }
					]}
				/>
				<NativeSelect
					bind:value={fKlasifikasi}
					class="lg:w-44"
					aria-label="Filter klasifikasi data"
					opsi={[
						{ value: '', label: 'Semua klasifikasi' },
						{ value: 'biasa', label: 'Biasa' },
						{ value: 'terbatas', label: 'Terbatas' },
						{ value: 'rahasia', label: 'Rahasia' }
					]}
				/>
				<NativeSelect
					bind:value={fPutusan}
					class="lg:w-44"
					aria-label="Filter putusan"
					opsi={[
						{ value: '', label: 'Semua putusan' },
						{ value: 'laik', label: 'Laik' },
						{ value: 'laik_bersyarat', label: 'Laik Bersyarat' },
						{ value: 'tidak_laik', label: 'Tidak Laik' },
						{ value: 'belum', label: 'Belum diuji' }
					]}
				/>
			</div>
			<div class="flex items-center justify-between gap-2 lg:justify-end">
				<span
					class="inline-flex items-center gap-1.5 text-xs whitespace-nowrap text-muted-foreground"
				>
					{#if memuat}<LoaderCircle class="size-3 animate-spin" />{/if}
					{data.total} aplikasi
				</span>
				{#if adaFilter}
					<Button variant="ghost" size="sm" onclick={resetFilter}><X /> Reset</Button>
				{/if}
			</div>
		</div>

		{#if galat}
			<p class="border-b bg-destructive/10 px-3 py-2 text-xs text-destructive">{galat}</p>
		{/if}

		<!-- Tabel -->
		<div class={cn('overflow-x-auto transition-opacity', memuat && 'opacity-60')}>
			<Table.Root>
				<Table.Header>
					<Table.Row class="bg-olive-dark hover:bg-olive-dark">
						{#each KOLOM as kol (kol.label)}
							<Table.Head
								class={cn(
									'font-heading text-[11px] tracking-[0.15em] text-sidebar-foreground uppercase',
									kol.class
								)}
								aria-sort={kol.urut && urut === kol.urut
									? arah === 'asc'
										? 'ascending'
										: 'descending'
									: undefined}
							>
								{#if kol.urut}
									{@const k = kol.urut}
									<button
										type="button"
										class="-mx-1 inline-flex items-center gap-1 rounded px-1 py-0.5 uppercase hover:text-white"
										onclick={() => aturUrut(k)}
									>
										{kol.label}
										{#if urut === k}
											{#if arah === 'asc'}<ArrowUp class="size-3" />{:else}<ArrowDown
													class="size-3"
												/>{/if}
										{:else}
											<ArrowUpDown class="size-3 opacity-40" />
										{/if}
									</button>
								{:else}
									{kol.label}
								{/if}
							</Table.Head>
						{/each}
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.items as r (r.id)}
						{@const p = r.pengujian}
						<Table.Row
							class="cursor-pointer"
							tabindex={0}
							onclick={() => bukaAset(r.id)}
							onkeydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') {
									e.preventDefault();
									bukaAset(r.id);
								}
							}}
						>
							<Table.Cell class="max-w-md">
								<span class="block truncate font-medium">{r.nama}</span>
								<p class="truncate font-mono text-xs text-muted-foreground">{r.url_dasar}</p>
							</Table.Cell>
							<Table.Cell class="max-w-64">
								<span class="block truncate text-sm">{r.satuan || '—'}</span>
								{#if r.pic_nama}
									<p class="truncate text-xs text-muted-foreground">PIC: {r.pic_nama}</p>
								{/if}
							</Table.Cell>
							<Table.Cell class="text-sm">
								<span class="inline-flex items-center gap-1.5">
									<span class={cn('size-1.5 rounded-full', WARNA_LINGKUNGAN[r.lingkungan])}></span>
									{LABEL_LINGKUNGAN[r.lingkungan]}
								</span>
							</Table.Cell>
							<Table.Cell>
								<span
									class="rounded-sm border px-1.5 py-0.5 font-heading text-[10px] tracking-[0.12em] uppercase {WARNA_KLASIFIKASI[
										r.klasifikasi_data
									]}"
								>
									{LABEL_KLASIFIKASI[r.klasifikasi_data]}
								</span>
							</Table.Cell>
							<Table.Cell>
								{#if p.putusan && p.skor !== null}
									<SkorBar skor={p.skor} putusan={p.putusan} />
								{:else}
									<span class="text-xs text-muted-foreground">—</span>
								{/if}
							</Table.Cell>
							<Table.Cell>
								{#if p.temuan}
									{@const t = p.temuan}
									<Tooltip.Root>
										<Tooltip.Trigger>
											{#snippet child({ props })}
												<div {...props} class="flex items-center gap-1">
													{#each SEVERITAS as s (s.k)}
														<span
															class={cn(
																'inline-flex h-5 min-w-7 items-center justify-center gap-0.5 rounded px-1 text-[11px] font-semibold tabular-nums',
																t[s.k] ? s.warna : 'bg-muted/60 text-muted-foreground/50'
															)}
														>
															<span class="text-[9px] opacity-75">{s.singkat}</span>{t[s.k]}
														</span>
													{/each}
												</div>
											{/snippet}
										</Tooltip.Trigger>
										<Tooltip.Content>
											{#if totalTemuan(t)}
												{totalTemuan(t)} temuan:
												{SEVERITAS.filter((s) => t[s.k])
													.map((s) => `${t[s.k]} ${s.label.toLowerCase()}`)
													.join(', ')}
											{:else}
												Tidak ada temuan pada pengujian terakhir
											{/if}
										</Tooltip.Content>
									</Tooltip.Root>
								{:else}
									<span class="text-xs text-muted-foreground">—</span>
								{/if}
							</Table.Cell>
							<Table.Cell>
								{#if p.berjalan}
									<span class="inline-flex items-center gap-1 text-xs text-info"
										><LoaderCircle class="size-3 animate-spin" /> Berjalan</span
									>
								{:else if p.putusan}
									<PutusanBadge putusan={p.putusan} />
								{:else}
									<span class="text-xs text-muted-foreground">Belum diuji</span>
								{/if}
							</Table.Cell>
							<Table.Cell class="text-xs whitespace-nowrap text-muted-foreground">
								{relatif(p.scan_terakhir_pada ?? undefined)}
							</Table.Cell>
						</Table.Row>
					{:else}
						<Table.Row>
							<Table.Cell
								colspan={KOLOM.length}
								class="py-10 text-center text-sm text-muted-foreground"
							>
								Tidak ada aplikasi yang cocok dengan filter.
								{#if adaFilter}
									<Button variant="link" size="sm" onclick={resetFilter}>Reset filter</Button>
								{/if}
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>

		<!-- Pagination -->
		<div
			class="flex flex-col gap-3 border-t px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between"
		>
			<div class="flex items-center gap-2 text-xs text-muted-foreground">
				<span>Baris per halaman</span>
				<NativeSelect
					bind:value={perHalaman}
					class="h-7 w-18"
					aria-label="Baris per halaman"
					opsi={['10', '25', '50', '100'].map((v) => ({ value: v, label: v }))}
				/>
				<span class="ml-2 tabular-nums">
					{#if data.total}
						{awal + 1}–{Math.min(awal + data.limit, data.total)} dari {data.total}
					{:else}
						0 dari 0
					{/if}
				</span>
			</div>
			<nav class="flex items-center gap-1" aria-label="Navigasi halaman">
				<Button
					variant="outline"
					size="icon-sm"
					disabled={halaman <= 1}
					onclick={() => (halaman = 1)}
					aria-label="Halaman pertama"
				>
					<ChevronsLeft />
				</Button>
				<Button
					variant="outline"
					size="icon-sm"
					disabled={halaman <= 1}
					onclick={() => (halaman = halaman - 1)}
					aria-label="Halaman sebelumnya"
				>
					<ChevronLeft />
				</Button>
				{#each nomorHalaman as n, i (i)}
					{#if n === '…'}
						<span class="px-1 text-xs text-muted-foreground">…</span>
					{:else}
						<Button
							variant={n === halaman ? 'default' : 'ghost'}
							size="icon-sm"
							class="tabular-nums"
							aria-current={n === halaman ? 'page' : undefined}
							onclick={() => (halaman = n)}
						>
							{n}
						</Button>
					{/if}
				{/each}
				<Button
					variant="outline"
					size="icon-sm"
					disabled={halaman >= totalHalaman}
					onclick={() => (halaman = halaman + 1)}
					aria-label="Halaman berikutnya"
				>
					<ChevronRight />
				</Button>
				<Button
					variant="outline"
					size="icon-sm"
					disabled={halaman >= totalHalaman}
					onclick={() => (halaman = totalHalaman)}
					aria-label="Halaman terakhir"
				>
					<ChevronsRight />
				</Button>
			</nav>
		</div>
	</div>
{/if}

<DialogPilihTindakan
	bind:open={dlgTindakan}
	onlihatRiwayat={() => dipilih && bukaRiwayat(dipilih)}
	onpengujian={() => (dlgMetode = true)}
/>
<DialogPilihMetode
	bind:open={dlgMetode}
	onpilih={(p) => dipilih && goto(`/aplikasi/${dipilih}/pengujian/otomatis?pendekatan=${p}`)}
/>
