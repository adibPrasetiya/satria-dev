<script lang="ts">
	import { api } from '#lib/api/client.js';
	import { auth, LABEL_PERAN } from '#lib/stores/auth.svelte.js';
	import { relatif, tanggal } from '#lib/format.js';
	import type { Pengguna, Peran, StatusAkun } from '#lib/types.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import * as Tooltip from '#lib/components/ui/tooltip/index.js';
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
	import UserCog from '@lucide/svelte/icons/user-cog';
	import MailWarning from '@lucide/svelte/icons/mail-warning';

	let daftar = $state<Pengguna[] | null>(null);
	let filter = $state<StatusAkun | ''>('');
	let cari = $state('');
	let sibuk = $state<string | null>(null);

	// Dialog verifikasi manual / tolak pendaftaran / ubah peran
	type Mode = 'verifikasi' | 'tolak' | 'peran';
	let target = $state<Pengguna | null>(null);
	let mode = $state<Mode>('verifikasi');
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

	const jumlah = $derived.by(() => {
		const n: Record<StatusAkun, number> = { pending: 0, verified: 0, inactive: 0 };
		for (const u of daftar ?? []) n[statusDari(u)]++;
		return n;
	});

	function buka(u: Pengguna, m: Mode) {
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
			} else if (mode === 'peran') {
				await api.ubahPeranPengguna(target.id, peranDipilih);
				toast.success(`Peran ${target.nama} diubah menjadi ${LABEL_PERAN[peranDipilih]}`);
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

	const OPSI_PERAN = (Object.entries(LABEL_PERAN) as [Peran, string][]).map(([value, label]) => ({
		value,
		label
	}));
	const KETERANGAN_PERAN: Record<Peran, string> = {
		pemilik: 'Mendaftarkan aplikasi milik satuannya dan melihat hasil asesmen.',
		asesor: 'Menyiapkan & menjalankan pengujian serta menyusun laporan.',
		admin: 'Akses penuh, termasuk mengelola pengguna, satuan, dan katalog.'
	};
	const WARNA_PERAN: Record<Peran, string> = {
		pemilik: 'border-primary/40 text-primary',
		asesor: 'border-gold text-gold',
		admin: 'border-critical/50 text-critical'
	};
	const LABEL_STATUS: Record<StatusAkun, string> = {
		pending: 'Belum verifikasi email',
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

	const KOLOM = [
		{ label: 'Personel', class: 'min-w-56' },
		{ label: 'NRP/NIP', class: 'whitespace-nowrap' },
		{ label: 'Email', class: 'min-w-48' },
		{ label: 'Satuan', class: 'min-w-48' },
		{ label: 'Peran', class: 'whitespace-nowrap' },
		{ label: 'Status', class: 'whitespace-nowrap' },
		{ label: 'Masuk terakhir', class: 'whitespace-nowrap' },
		{ label: 'Terdaftar', class: 'whitespace-nowrap' },
		{ label: '', class: 'text-right' }
	];

	const JUDUL_DIALOG: Record<Mode, string> = {
		verifikasi: 'Verifikasi manual',
		tolak: 'Tolak pendaftaran',
		peran: 'Ubah peran'
	};
</script>

<PageHeader
	label="Administrasi"
	judul="Pengguna"
	deskripsi="Kelola peran dan status personel yang mengakses SATRIA. Akun baru aktif setelah pendaftar memverifikasi emailnya."
/>

<div class="mb-4 flex flex-col gap-2 lg:flex-row lg:items-center">
	<div class="relative flex-1">
		<Search class="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
		<Input
			bind:value={cari}
			placeholder="Cari nama, pangkat, email, NRP, atau satuan…"
			class="bg-card pl-8"
		/>
	</div>
	<NativeSelect
		bind:value={filter}
		class="bg-card lg:w-56"
		opsi={[
			{ value: '', label: 'Semua status' },
			{ value: 'pending', label: 'Belum verifikasi email' },
			{ value: 'verified', label: 'Aktif' },
			{ value: 'inactive', label: 'Nonaktif' }
		]}
	/>
	{#if daftar}
		<p class="text-xs whitespace-nowrap text-muted-foreground tabular-nums lg:ml-2">
			{daftar.length} pengguna{#if filter === ''}
				· {jumlah.verified} aktif · {jumlah.inactive} nonaktif · {jumlah.pending} belum verifikasi{/if}
		</p>
	{/if}
</div>

{#if !daftar}
	<Memuat />
{:else if daftar.length === 0}
	<Kosong judul="Tidak ada pengguna" pesan="Tidak ada pengguna yang cocok dengan filter." />
{:else}
	<div class="sudut-taktis overflow-hidden rounded-lg border bg-card">
		<Table.Root>
			<Table.Header>
				<Table.Row class="bg-olive-dark hover:bg-olive-dark">
					{#each KOLOM as k, i (i)}
						<Table.Head
							class={cn(
								'font-heading text-[11px] tracking-[0.15em] text-sidebar-foreground uppercase',
								k.class
							)}
						>
							{k.label}
						</Table.Head>
					{/each}
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each daftar as u (u.id)}
					{@const status = statusDari(u)}
					{@const diriSendiri = u.id === auth.pengguna?.id}
					<Table.Row class={status === 'inactive' ? 'opacity-60' : ''}>
						<Table.Cell>
							<p class="font-medium">{u.nama}</p>
							{#if u.pangkat || u.status_kepegawaian}
								<p class="text-xs text-muted-foreground">
									{[u.pangkat, u.status_kepegawaian].filter(Boolean).join(' · ')}
								</p>
							{/if}
						</Table.Cell>
						<Table.Cell class="font-mono text-xs tabular-nums">{u.nrp ?? '—'}</Table.Cell>
						<Table.Cell class="text-sm break-all">{u.email}</Table.Cell>
						<Table.Cell class="text-sm">{u.satuan}</Table.Cell>
						<Table.Cell>
							<div class="flex items-center gap-1">
								<span
									class="rounded-sm border px-1.5 py-0.5 font-heading text-[10px] tracking-[0.12em] whitespace-nowrap uppercase {WARNA_PERAN[
										u.peran
									]}"
								>
									{LABEL_PERAN[u.peran]}
								</span>
								{#if status !== 'pending' && !diriSendiri}
									<Tooltip.Root>
										<Tooltip.Trigger>
											{#snippet child({ props })}
												<Button
													{...props}
													size="icon"
													variant="ghost"
													class="size-7 text-muted-foreground hover:text-foreground"
													onclick={() => buka(u, 'peran')}
													disabled={!!sibuk}
													aria-label={`Ubah peran ${u.nama}`}
												>
													<UserCog class="size-4" />
												</Button>
											{/snippet}
										</Tooltip.Trigger>
										<Tooltip.Content>Ubah peran</Tooltip.Content>
									</Tooltip.Root>
								{/if}
							</div>
						</Table.Cell>
						<Table.Cell>
							<span
								class={cn(
									'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
									WARNA_STATUS[status]
								)}
							>
								{#if status === 'pending'}<MailWarning class="size-3" />{/if}
								{LABEL_STATUS[status]}
							</span>
						</Table.Cell>
						<Table.Cell class="text-sm whitespace-nowrap text-muted-foreground">
							{#if u.masuk_terakhir}
								<span title={tanggal(u.masuk_terakhir)}>{relatif(u.masuk_terakhir)}</span>
							{:else}—{/if}
						</Table.Cell>
						<Table.Cell class="text-sm whitespace-nowrap text-muted-foreground">
							{#if u.dibuat_pada}
								<span title={relatif(u.dibuat_pada)}>{tanggal(u.dibuat_pada)}</span>
							{:else}—{/if}
						</Table.Cell>
						<Table.Cell class="text-right">
							{#if status === 'pending'}
								<div class="flex justify-end gap-1.5">
									<Button
										size="sm"
										variant="outline"
										onclick={() => buka(u, 'verifikasi')}
										disabled={!!sibuk}
									>
										<UserCheck /> Verifikasi manual
									</Button>
									<Button
										size="sm"
										variant="destructive"
										onclick={() => buka(u, 'tolak')}
										disabled={!!sibuk}
									>
										<UserX /> Tolak
									</Button>
								</div>
							{:else if !diriSendiri}
								<Switch
									checked={u.aktif}
									disabled={sibuk === u.id}
									onCheckedChange={(v) => ubahAktif(u, v)}
									aria-label={u.aktif ? `Nonaktifkan ${u.nama}` : `Aktifkan ${u.nama}`}
								/>
							{:else}
								<span class="text-xs whitespace-nowrap text-muted-foreground">Akun Anda</span>
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
				<Dialog.Title>{JUDUL_DIALOG[mode]}</Dialog.Title>
				<Dialog.Description>
					{target.nama} · {target.email}{target.nrp ? ` · NRP/NIP ${target.nrp}` : ''} · {target.satuan}
				</Dialog.Description>
			</Dialog.Header>
			{#if mode === 'tolak'}
				<p class="text-sm text-muted-foreground">
					Data pendaftaran akan dihapus. Pendaftar dapat mendaftar ulang bila diperlukan.
				</p>
			{:else}
				<Field
					label="Peran"
					id="peran"
					bantuan={mode === 'verifikasi'
						? 'Gunakan hanya bila email verifikasi tidak sampai ke pendaftar. Pastikan identitas & satuannya sudah dicek.'
						: KETERANGAN_PERAN[peranDipilih]}
				>
					<NativeSelect id="peran" bind:value={peranDipilih} opsi={OPSI_PERAN} />
				</Field>
				{#if mode === 'peran' && peranDipilih !== target.peran}
					<p
						class="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning-foreground"
					>
						Peran berubah dari <b>{LABEL_PERAN[target.peran]}</b> menjadi
						<b>{LABEL_PERAN[peranDipilih]}</b>. Semua sesi {target.nama} akan diakhiri sehingga ia perlu
						masuk ulang.
					</p>
				{/if}
			{/if}
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (target = null)}>Batal</Button>
				<Button
					variant={mode === 'tolak' ? 'destructive' : 'default'}
					onclick={putuskan}
					disabled={!!sibuk || (mode === 'peran' && peranDipilih === target.peran)}
				>
					{mode === 'verifikasi'
						? 'Verifikasi'
						: mode === 'peran'
							? 'Simpan peran'
							: 'Tolak pendaftaran'}
				</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>
