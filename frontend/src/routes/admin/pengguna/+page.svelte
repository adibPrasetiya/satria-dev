<script lang="ts">
	import { api } from '#lib/api/client.js';
	import { auth, LABEL_PERAN } from '#lib/stores/auth.svelte.js';
	import { relatif } from '#lib/format.js';
	import type { Pengguna, Peran, StatusAkun } from '#lib/types.js';
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
	import UserCheck from '@lucide/svelte/icons/user-check';
	import UserX from '@lucide/svelte/icons/user-x';
	import Clock from '@lucide/svelte/icons/clock';

	let daftar = $state<Pengguna[] | null>(null);
	let filter = $state<StatusAkun | ''>('');
	let cari = $state('');
	let sibuk = $state<string | null>(null);

	// Dialog verifikasi / tolak
	let target = $state<Pengguna | null>(null);
	let mode = $state<'verifikasi' | 'tolak'>('verifikasi');
	let peranDipilih = $state<Peran>('pemilik');

	async function muat() {
		try {
			daftar = await api.listPengguna({ status: filter, search: cari.trim() });
		} catch (e) {
			toast.error((e as Error).message);
			daftar = [];
		}
	}

	// Muat ulang saat filter berubah; pencarian ditunda agar tidak memanggil API per ketikan.
	$effect(() => {
		void filter;
		const q = cari;
		const t = setTimeout(muat, q ? 300 : 0);
		return () => clearTimeout(t);
	});

	const jumlahPending = $derived(daftar?.filter((u) => u.status === 'pending').length ?? 0);

	function buka(u: Pengguna, m: typeof mode) {
		target = u;
		mode = m;
		peranDipilih = u.peran;
	}

	async function putuskan() {
		if (!target) return;
		sibuk = target.id;
		try {
			if (mode === 'verifikasi') {
				await api.verifikasiPengguna(target.id, peranDipilih);
				toast.success(`${target.nama} diverifikasi sebagai ${LABEL_PERAN[peranDipilih]}`);
			} else {
				await api.tolakPendaftaran(target.id);
				toast.success(`Pendaftaran ${target.nama} ditolak`);
			}
			target = null;
			await muat();
		} catch (e) {
			toast.error((e as Error).message);
		} finally {
			sibuk = null;
		}
	}

	async function ubahAktif(u: Pengguna, aktif: boolean) {
		sibuk = u.id;
		try {
			await api.ubahStatusPengguna(u.id, aktif);
			toast.success(aktif ? 'Akun diaktifkan' : 'Akun dinonaktifkan; sesinya dicabut');
			await muat();
		} catch (e) {
			toast.error((e as Error).message);
		} finally {
			sibuk = null;
		}
	}

	const OPSI_PERAN = (Object.entries(LABEL_PERAN) as [Peran, string][]).map(([value, label]) => ({ value, label }));
	const WARNA_PERAN: Record<Peran, string> = {
		pemilik: 'border-primary/40 text-primary',
		asesor: 'border-gold text-gold',
		admin: 'border-critical/50 text-critical'
	};
	const LABEL_STATUS: Record<StatusAkun, string> = {
		pending: 'Menunggu verifikasi',
		verified: 'Aktif',
		inactive: 'Nonaktif'
	};
	const WARNA_STATUS: Record<StatusAkun, string> = {
		pending: 'bg-warning/15 text-warning-foreground',
		verified: 'bg-success/12 text-success',
		inactive: 'bg-muted text-muted-foreground'
	};
	const statusDari = (u: Pengguna): StatusAkun =>
		u.status ?? (u.terverifikasi === false ? 'pending' : u.aktif ? 'verified' : 'inactive');
</script>

<PageHeader
	label="Administrasi"
	judul="Pengguna"
	deskripsi="Verifikasi pendaftaran akun baru dan kelola status personel yang mengakses SATRIA."
/>

<div class="mb-4 flex flex-col gap-2 sm:flex-row">
	<div class="relative flex-1">
		<Search class="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
		<Input bind:value={cari} placeholder="Cari nama, email, NRP, atau satuan…" class="bg-card pl-8" />
	</div>
	<NativeSelect
		bind:value={filter}
		class="bg-card sm:w-56"
		opsi={[
			{ value: '', label: 'Semua status' },
			{ value: 'pending', label: 'Menunggu verifikasi' },
			{ value: 'verified', label: 'Aktif' },
			{ value: 'inactive', label: 'Nonaktif' }
		]}
	/>
</div>

{#if filter === '' && jumlahPending > 0}
	<button
		class="mb-4 flex w-full items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-left text-sm text-warning-foreground hover:bg-warning/15"
		onclick={() => (filter = 'pending')}
	>
		<Clock class="size-4" />
		<span><b>{jumlahPending}</b> pendaftaran menunggu verifikasi. Tampilkan saja yang menunggu ›</span>
	</button>
{/if}

{#if !daftar}
	<Memuat />
{:else if daftar.length === 0}
	<Kosong judul="Tidak ada pengguna" pesan="Tidak ada pengguna yang cocok dengan filter." />
{:else}
	<div class="sudut-taktis overflow-hidden rounded-lg border bg-card">
		<Table.Root>
			<Table.Header>
				<Table.Row class="bg-olive-dark hover:bg-olive-dark">
					{#each ['Nama', 'Email', 'Satuan', 'Peran', 'Status', ''] as h, i (i)}
						<Table.Head class="font-heading text-[11px] tracking-[0.15em] text-sidebar-foreground uppercase">{h}</Table.Head>
					{/each}
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each daftar as u (u.id)}
					{@const status = statusDari(u)}
					<Table.Row class={status === 'inactive' ? 'opacity-60' : ''}>
						<Table.Cell>
							<p class="font-medium">{u.nama}</p>
							{#if u.nrp}<p class="text-xs text-muted-foreground">NRP/NIP {u.nrp}</p>{/if}
						</Table.Cell>
						<Table.Cell class="text-sm">{u.email}</Table.Cell>
						<Table.Cell class="text-sm">{u.satuan}</Table.Cell>
						<Table.Cell>
							<span class="rounded-sm border px-1.5 py-0.5 font-heading text-[10px] tracking-[0.12em] uppercase {WARNA_PERAN[u.peran]}">
								{LABEL_PERAN[u.peran]}
							</span>
						</Table.Cell>
						<Table.Cell>
							<span class={cn('inline-flex rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap', WARNA_STATUS[status])}>
								{LABEL_STATUS[status]}
							</span>
							{#if status === 'pending' && u.dibuat_pada}
								<p class="mt-0.5 text-[11px] text-muted-foreground">mendaftar {relatif(u.dibuat_pada)}</p>
							{/if}
						</Table.Cell>
						<Table.Cell class="text-right">
							{#if status === 'pending'}
								<div class="flex justify-end gap-1.5">
									<Button size="sm" onclick={() => buka(u, 'verifikasi')} disabled={!!sibuk}><UserCheck /> Verifikasi</Button>
									<Button size="sm" variant="destructive" onclick={() => buka(u, 'tolak')} disabled={!!sibuk}><UserX /> Tolak</Button>
								</div>
							{:else if u.id !== auth.pengguna?.id}
								<Switch
									checked={u.aktif}
									disabled={sibuk === u.id}
									onCheckedChange={(v) => ubahAktif(u, v)}
									aria-label={u.aktif ? `Nonaktifkan ${u.nama}` : `Aktifkan ${u.nama}`}
								/>
							{:else}
								<span class="text-xs text-muted-foreground">Akun Anda</span>
							{/if}
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
{/if}

<Dialog.Root open={!!target} onOpenChange={(o) => !o && (target = null)}>
	<Dialog.Content>
		{#if target}
			<Dialog.Header>
				<Dialog.Title>{mode === 'verifikasi' ? 'Verifikasi akun' : 'Tolak pendaftaran'}</Dialog.Title>
				<Dialog.Description>
					{target.nama} · {target.email}{target.nrp ? ` · NRP/NIP ${target.nrp}` : ''} · {target.satuan}
				</Dialog.Description>
			</Dialog.Header>
			{#if mode === 'verifikasi'}
				<Field label="Peran" id="peran" bantuan="Pastikan identitas & satuan pendaftar sudah dicek sebelum memberi akses.">
					<NativeSelect id="peran" bind:value={peranDipilih} opsi={OPSI_PERAN} />
				</Field>
			{:else}
				<p class="text-sm text-muted-foreground">Data pendaftaran akan dihapus. Pendaftar dapat mendaftar ulang bila diperlukan.</p>
			{/if}
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (target = null)}>Batal</Button>
				<Button variant={mode === 'tolak' ? 'destructive' : 'default'} onclick={putuskan} disabled={!!sibuk}>
					{mode === 'verifikasi' ? 'Verifikasi' : 'Tolak pendaftaran'}
				</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>
