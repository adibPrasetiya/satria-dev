<script lang="ts">
	import { page } from '$app/state';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.js';
	import { relatif } from '#lib/format.js';
	import { cn } from '#lib/utils.js';
	import type { Aplikasi, InventarisKomponen, KategoriKomponen, KomponenAset } from '#lib/types.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import NativeSelect from '#lib/components/NativeSelect.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import DaftarKerentanan from '#lib/components/kerentanan/DaftarKerentanan.svelte';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import CirclePlus from '@lucide/svelte/icons/circle-plus';
	import Trash from '@lucide/svelte/icons/trash-2';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';

	const id = $derived(page.params.id!);
	let app = $state<Aplikasi | null>(null);
	let inv = $state<InventarisKomponen | null>(null);
	let galat = $state<string | null>(null);
	let muatUlang = $state(0);

	let kategori = $state<KategoriKomponen>('server');
	let teks = $state('');
	let galatTeks = $state<string | null>(null);
	let menyimpan = $state(false);
	let menghapus = $state<string | null>(null);

	const KATEGORI: { value: KategoriKomponen; label: string }[] = [
		{ value: 'server', label: 'Server' },
		{ value: 'backend', label: 'Backend' },
		{ value: 'frontend', label: 'Frontend' },
		{ value: 'database', label: 'Basis data' },
		{ value: 'library', label: 'Library' },
		{ value: 'os', label: 'Sistem operasi' },
		{ value: 'lainnya', label: 'Lainnya' }
	];
	const LABEL_KATEGORI = Object.fromEntries(KATEGORI.map((k) => [k.value, k.label])) as Record<KategoriKomponen, string>;
	const LABEL_SUMBER: Record<KomponenAset['sumber'], string> = {
		formulir: 'Formulir aset',
		manual: 'Koreksi manual',
		banner: 'Banner server',
		nuclei: 'Nuclei',
		bundle_js: 'Berkas JS',
		tls: 'TLS'
	};
	const GAYA_KEYAKINAN = {
		tinggi: 'text-success',
		sedang: 'text-warning-foreground',
		rendah: 'text-muted-foreground'
	} as const;

	$effect(() => {
		const aid = id;
		app = null;
		inv = null;
		galat = null;
		Promise.all([api.getAplikasi(aid), api.getKomponen(aid)]).then(
			([a, k]) => {
				app = a;
				inv = k;
			},
			(e) => (galat = (e as Error).message)
		);
	});

	// Backend mencocokkan ulang ±2 dtk setelah komponen berubah; daftar CVE dimuat ulang sesudahnya.
	const segarkanCve = () => setTimeout(() => (muatUlang += 1), 3000);

	async function tambah(e: SubmitEvent) {
		e.preventDefault();
		galatTeks = null;
		if (teks.trim().length < 2) {
			galatTeks = 'Isi nama komponen beserta versinya, mis. "nginx 1.18.0".';
			return;
		}
		menyimpan = true;
		try {
			inv = await api.tambahKomponen(id, { kategori, teks: teks.trim() });
			toast.success('Komponen disimpan. Pencocokan CVE diperbarui.');
			teks = '';
			segarkanCve();
		} catch (err) {
			const g = err as { errors?: { field: string; message: string }[]; message?: string };
			galatTeks = g.errors?.find((x) => x.field === 'teks')?.message ?? g.message ?? 'Gagal menyimpan komponen';
		} finally {
			menyimpan = false;
		}
	}

	async function hapus(k: KomponenAset) {
		menghapus = k.id;
		try {
			inv = await api.hapusKomponen(id, k.id);
			toast.success(`Koreksi ${k.nama} dihapus`);
			segarkanCve();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Gagal menghapus komponen');
		} finally {
			menghapus = null;
		}
	}

	function koreksi(k: KomponenAset) {
		kategori = k.kategori;
		teks = `${k.nama} ${k.versi ?? ''}`.trim();
		document.getElementById('teks-komponen')?.focus();
	}

	const tanpaVersi = $derived(inv ? inv.items.filter((k) => k.dipakai && k.dikenali && !k.versi) : []);
</script>

<svelte:head><title>Komponen & CVE{app ? ` — ${app.nama}` : ''} — SATRIA</title></svelte:head>

{#if galat}
	<Kosong judul="Aplikasi tidak ditemukan" pesan={galat}><Button href="/aplikasi" variant="outline">Kembali</Button></Kosong>
{:else if !app || !inv}
	<Memuat baris={3} />
{:else}
	<PageHeader
		label="Komponen & CVE"
		judul={app.nama}
		deskripsi="Inventaris teknologi aset dan kerentanan (CVE) yang cocok dengan versinya. Versi yang tercatat makin rinci, makin tepat pula pencocokannya."
	>
		{#snippet atas()}
			<a href="/aplikasi" class="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
				<ChevronLeft class="size-3.5" /> Daftar aplikasi
			</a>
		{/snippet}
	</PageHeader>

	<section class="mb-8" aria-labelledby="judul-komponen">
		<div class="mb-2 flex flex-wrap items-end justify-between gap-2">
			<h2 id="judul-komponen" class="text-base font-semibold">Komponen terdeteksi</h2>
			<p class="text-xs text-muted-foreground">
				{inv.ringkasan.produk} produk · {inv.ringkasan.dikenali} dikenali · {inv.ringkasan.berversi} berversi
			</p>
		</div>

		{#if tanpaVersi.length}
			<p class="mb-3 flex gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning-foreground">
				<TriangleAlert class="mt-0.5 size-4 shrink-0" />
				<span>
					Versi belum diketahui untuk {tanpaVersi.map((k) => k.nama).join(', ')}. Untuk komponen ini hanya CVE
					yang dieksploitasi aktif atau yang tinggi/kritis terbaru yang ditampilkan, berstatus "kemungkinan".
					Tambahkan koreksi dengan versinya.
				</span>
			</p>
		{/if}

		{#if !inv.items.length}
			<Kosong
				judul="Belum ada komponen"
				pesan="Isi field teknologi pada data aset, jalankan recon, atau tambahkan komponen secara manual di bawah."
			/>
		{:else}
			<div class="overflow-x-auto rounded-lg border bg-card">
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head>Komponen</Table.Head>
							<Table.Head>Versi</Table.Head>
							<Table.Head class="hidden sm:table-cell">Kategori</Table.Head>
							<Table.Head>Sumber</Table.Head>
							<Table.Head class="hidden md:table-cell">Bukti</Table.Head>
							<Table.Head class="w-0"><span class="sr-only">Aksi</span></Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each inv.items as k (k.id)}
							<Table.Row class={cn(!k.dipakai && 'opacity-55')}>
								<Table.Cell>
									<p class="font-medium">{k.nama}</p>
									<p class="font-mono text-[11px] text-muted-foreground">
										{#if k.dikenali}{k.vendor ? `${k.vendor}:${k.produk}` : k.purl}{:else}<span class="text-warning-foreground">tidak dikenali kamus</span>{/if}
									</p>
								</Table.Cell>
								<Table.Cell class="font-mono text-sm">{k.versi ?? '—'}</Table.Cell>
								<Table.Cell class="hidden text-sm sm:table-cell">{LABEL_KATEGORI[k.kategori]}</Table.Cell>
								<Table.Cell>
									<p class="text-sm">{LABEL_SUMBER[k.sumber]}</p>
									<p class="text-[11px]">
										<span class={GAYA_KEYAKINAN[k.keyakinan]}>keyakinan {k.keyakinan}</span>
										{#if k.dipakai}<span class="text-muted-foreground"> · dipakai</span>{:else}<span class="text-muted-foreground"> · digantikan</span>{/if}
									</p>
								</Table.Cell>
								<Table.Cell class="hidden max-w-64 truncate text-xs text-muted-foreground md:table-cell" title={k.bukti ?? ''}>
									{k.bukti ?? '—'}
									<span class="block">{relatif(k.terakhir_terlihat)}</span>
								</Table.Cell>
								<Table.Cell class="text-right whitespace-nowrap">
									{#if !app.diarsipkan_pada}
										{#if k.sumber === 'manual'}
											<Button size="icon-sm" variant="ghost" aria-label="Hapus koreksi {k.nama}" disabled={menghapus === k.id} onclick={() => hapus(k)}>
												{#if menghapus === k.id}<LoaderCircle class="animate-spin" />{:else}<Trash />{/if}
											</Button>
										{:else}
											<Button size="sm" variant="ghost" onclick={() => koreksi(k)}>Koreksi</Button>
										{/if}
									{/if}
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</div>
		{/if}

		{#if !app.diarsipkan_pada}
			<form onsubmit={tambah} class="mt-3 rounded-lg border bg-card p-3">
				<p class="mb-2 text-sm font-medium">Tambah / koreksi komponen</p>
				<div class="grid gap-2 sm:grid-cols-[11rem_minmax(0,1fr)_auto]">
					<NativeSelect aria-label="Kategori" bind:value={kategori} opsi={KATEGORI} />
					<Input id="teks-komponen" class="h-8" bind:value={teks} maxlength={100} placeholder="mis. nginx 1.18.0, PHP 8.2.12, jQuery 3.4.1" aria-invalid={!!galatTeks} />
					<Button type="submit" size="sm" disabled={menyimpan}>
						{#if menyimpan}<LoaderCircle class="animate-spin" />{:else}<CirclePlus />{/if} Simpan
					</Button>
				</div>
				{#if galatTeks}<p class="mt-1.5 text-xs text-critical" role="alert">{galatTeks}</p>{/if}
				<p class="mt-1.5 text-xs text-muted-foreground">
					Koreksi manual selalu dipakai untuk produk yang sama, mengalahkan isian formulir maupun hasil recon.
				</p>
			</form>
		{/if}
	</section>

	<section aria-labelledby="judul-cve">
		<div class="mb-2 flex flex-wrap items-end justify-between gap-2">
			<h2 id="judul-cve" class="text-base font-semibold">Kerentanan yang cocok</h2>
			<a href="/kerentanan" class="text-xs text-primary hover:underline">Semua aset</a>
		</div>
		<DaftarKerentanan aplikasiId={id} tampilAplikasi={false} {muatUlang} />
	</section>
{/if}
