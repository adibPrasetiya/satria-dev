<script lang="ts">
	import { api } from '#lib/api/client.js';
	import { relatif } from '#lib/format.js';
	import type { SatuanAdmin } from '#lib/types.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import Field from '#lib/components/Field.svelte';
	import NativeSelect from '#lib/components/NativeSelect.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import Search from '@lucide/svelte/icons/search';
	import CirclePlus from '@lucide/svelte/icons/circle-plus';
	import Pencil from '@lucide/svelte/icons/pencil';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	type Status = 'aktif' | 'nonaktif' | '';

	let hasil = $state<{ items: SatuanAdmin[]; total: number; totalPages: number; limit: number } | null>(null);
	let cari = $state('');
	let status = $state<Status>('');
	let halaman = $state(1);
	// Dialog tambah / ubah (target null + dialog terbuka = tambah): nama & status sekaligus.
	let dialogBuka = $state(false);
	let target = $state<SatuanAdmin | null>(null);
	let nama = $state('');
	let aktif = $state(true);
	let galatNama = $state<string | null>(null);
	let menyimpan = $state(false);

	async function muat() {
		try {
			hasil = await api.listSatuanAdmin({ search: cari.trim(), status, page: halaman });
		} catch (e) {
			toast.error((e as Error).message);
			hasil = { items: [], total: 0, totalPages: 1, limit: 50 };
		}
	}

	// Muat ulang saat filter/halaman berubah; pencarian ditunda agar tidak memanggil API per ketikan.
	$effect(() => {
		void status;
		void halaman;
		const q = cari;
		const t = setTimeout(muat, q ? 300 : 0);
		return () => clearTimeout(t);
	});

	// Filter baru selalu mulai dari halaman pertama.
	function gantiFilter() {
		halaman = 1;
	}

	function bukaDialog(s: SatuanAdmin | null) {
		target = s;
		nama = s?.nama ?? '';
		aktif = s?.aktif ?? true;
		galatNama = null;
		dialogBuka = true;
	}

	async function simpan(e: SubmitEvent) {
		e.preventDefault();
		const n = nama.trim().replace(/\s+/g, ' ');
		if (n.length < 2) {
			galatNama = 'Nama satuan minimal 2 karakter.';
			return;
		}
		menyimpan = true;
		try {
			if (target) {
				// Kirim hanya yang berubah.
				const ubah = { ...(n !== target.nama && { nama: n }), ...(aktif !== target.aktif && { aktif }) };
				if (Object.keys(ubah).length) {
					await api.ubahSatuan(target.id, ubah);
					toast.success(`Satuan "${n}" diperbarui`);
				}
			} else {
				await api.tambahSatuan(n, aktif);
				toast.success(`Satuan "${n}" ditambahkan${aktif ? '' : ' (nonaktif)'}`);
			}
			dialogBuka = false;
			await muat();
		} catch (err) {
			galatNama = (err as Error).message;
		} finally {
			menyimpan = false;
		}
	}

	const awal = $derived(hasil && hasil.total ? (halaman - 1) * hasil.limit + 1 : 0);
	const akhir = $derived(hasil ? Math.min(halaman * hasil.limit, hasil.total) : 0);
</script>

<PageHeader
	label="Administrasi"
	judul="Satuan Kerja"
	deskripsi="Kelola daftar satuan/instansi yang dapat dipilih saat pendaftaran akun."
>
	{#snippet aksi()}
		<Button onclick={() => bukaDialog(null)}><CirclePlus /> Tambah satuan</Button>
	{/snippet}
</PageHeader>

<div class="mb-4 flex flex-col gap-2 sm:flex-row">
	<div class="relative flex-1">
		<Search class="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
		<Input bind:value={cari} oninput={gantiFilter} placeholder="Cari nama satuan…" class="bg-card pl-8" />
	</div>
	<NativeSelect
		bind:value={status}
		onchange={gantiFilter}
		class="bg-card sm:w-48"
		opsi={[
			{ value: '', label: 'Semua status' },
			{ value: 'aktif', label: 'Aktif' },
			{ value: 'nonaktif', label: 'Nonaktif' }
		]}
	/>
</div>

{#if !hasil}
	<Memuat />
{:else if hasil.items.length === 0}
	<Kosong
		judul="Tidak ada satuan"
		pesan={cari || status ? 'Tidak ada satuan yang cocok dengan filter.' : 'Tambahkan satuan pertama agar bisa dipilih saat pendaftaran.'}
	/>
{:else}
	<div class="sudut-taktis overflow-hidden rounded-lg border bg-card">
		<Table.Root>
			<Table.Header>
				<Table.Row class="bg-olive-dark hover:bg-olive-dark">
					{#each ['Nama satuan', 'Pengguna', 'Ditambahkan', 'Status', ''] as h, i (i)}
						<Table.Head class="font-heading text-[11px] tracking-[0.15em] text-sidebar-foreground uppercase">{h}</Table.Head>
					{/each}
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each hasil.items as s (s.id)}
					<Table.Row class={s.aktif ? '' : 'opacity-60'}>
						<Table.Cell class="font-medium whitespace-normal">{s.nama}</Table.Cell>
						<Table.Cell class="text-sm tabular-nums">{s.jumlah_pengguna} akun</Table.Cell>
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
							<Button size="sm" variant="outline" onclick={() => bukaDialog(s)} aria-label={`Ubah ${s.nama}`}>
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
				<Button size="sm" variant="outline" disabled={halaman >= hasil.totalPages} onclick={() => (halaman += 1)}>
					Berikutnya <ChevronRight />
				</Button>
			</div>
		{/if}
	</div>
{/if}

<Dialog.Root bind:open={dialogBuka}>
	<Dialog.Content>
		<form class="grid gap-4" onsubmit={simpan} novalidate>
			<Dialog.Header>
				<Dialog.Title>{target ? 'Ubah satuan' : 'Tambah satuan'}</Dialog.Title>
				{#if target?.jumlah_pengguna}
					<Dialog.Description>
						Dipakai {target.jumlah_pengguna} akun. Nama baru langsung tampil di akun tersebut.
					</Dialog.Description>
				{/if}
			</Dialog.Header>
			<Field label="Nama satuan" id="nama-satuan" wajib>
				<Input
					id="nama-satuan"
					bind:value={nama}
					oninput={() => (galatNama = null)}
					maxlength={120}
					aria-invalid={!!galatNama}
					placeholder="mis. Detasemen Siber"
				/>
				{#if galatNama}<p class="text-xs text-critical" role="alert">{galatNama}</p>{/if}
			</Field>
			<div class="flex items-start justify-between gap-4 rounded-lg border p-3">
				<div class="grid gap-0.5">
					<label for="aktif-satuan" class="text-sm font-medium">Aktif</label>
					<p class="text-xs text-muted-foreground">
						{#if aktif}
							Dapat dipilih saat pendaftaran akun.
						{:else}
							Tidak muncul di pilihan pendaftaran{target?.jumlah_pengguna ? `; ${target.jumlah_pengguna} akun yang sudah memakainya tetap sah` : ''}.
						{/if}
					</p>
				</div>
				<Switch id="aktif-satuan" bind:checked={aktif} />
			</div>
			<Dialog.Footer>
				<Button type="button" variant="outline" onclick={() => (dialogBuka = false)}>Batal</Button>
				<Button type="submit" disabled={menyimpan}>{target ? 'Simpan' : 'Tambah'}</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
