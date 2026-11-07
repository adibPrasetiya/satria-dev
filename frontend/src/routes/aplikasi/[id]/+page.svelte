<script lang="ts">
	// Berkas aset aplikasi: data dasar + riwayat pengujian. Persiapan pengujian (kepemilikan, titik uji,
	// akun uji, izin intrusif) dipindah ke fitur pengujian yang terpisah.
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { nilaiKelaikan } from '#lib/catalog.js';
	import { tanggal, relatif, durasi } from '#lib/format.js';
	import type { Aplikasi, Scan } from '#lib/types.js';
	import * as Tabs from '#lib/components/ui/tabs/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import DialogPilihMetode from '#lib/components/pengujian/DialogPilihMetode.svelte';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import PutusanBadge from '#lib/components/PutusanBadge.svelte';
	import SkorBar from '#lib/components/SkorBar.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import BuktiManual from '#lib/components/BuktiManual.svelte';
	import FileBarChart from '@lucide/svelte/icons/file-chart-column';
	import Pencil from '@lucide/svelte/icons/pencil';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import FlaskConical from '@lucide/svelte/icons/flask-conical';
	import Globe from '@lucide/svelte/icons/globe';
	import Copy from '@lucide/svelte/icons/copy';
	import Building from '@lucide/svelte/icons/building-2';
	import UserRound from '@lucide/svelte/icons/user-round';
	import Phone from '@lucide/svelte/icons/phone';
	import Layers from '@lucide/svelte/icons/layers';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import Monitor from '@lucide/svelte/icons/monitor';
	import Cpu from '@lucide/svelte/icons/cpu';
	import Database from '@lucide/svelte/icons/database';
	import Server from '@lucide/svelte/icons/server';
	import CalendarPlus from '@lucide/svelte/icons/calendar-plus';
	import History from '@lucide/svelte/icons/history';
	import { toast } from 'svelte-sonner';
	import type { Component } from 'svelte';

	const id = $derived(page.params.id!);

	let app = $state<Aplikasi | null>(null);
	let scans = $state<Scan[]>([]);
	let galat = $state<string | null>(null);
	let dialogMetode = $state(false);

	$effect(() => {
		const aid = id;
		Promise.all([api.getAplikasi(aid), api.listScan(aid)])
			.then(([a, s]) => {
				app = a;
				scans = s;
			})
			.catch((e) => (galat = e.message));
	});

	const scanSelesai = $derived(scans.find((s) => s.status === 'selesai'));
	const scanBerjalan = $derived(scans.find((s) => s.status === 'berjalan'));
	const penilaian = $derived(scanSelesai ? nilaiKelaikan(scanSelesai.hasil) : null);
	// Admin, atau pemilik dari satuan yang sama (data mock lama: pendaftarnya sendiri).
	const bisaUbah = $derived(
		!!app &&
			(auth.punya('admin') ||
				(auth.punya('pemilik') &&
					(app.satuan_id ? app.satuan_id === auth.pengguna?.satuan_id : app.pemilik_id === auth.pengguna?.id)))
	);

	const LABEL_LINGKUNGAN = { produksi: 'Produksi', staging: 'Staging', pengembangan: 'Pengembangan' };
	const LABEL_KLASIFIKASI = { biasa: 'Biasa', terbatas: 'Terbatas', rahasia: 'Rahasia' };
	const LABEL_STATUS_SCAN = { antre: 'Antre', berjalan: 'Berjalan', selesai: 'Selesai', dibatalkan: 'Dibatalkan' };
	const WARNA_KLASIFIKASI = {
		biasa: 'text-muted-foreground',
		terbatas: 'border-warning/60 bg-warning/10 text-warning-foreground',
		rahasia: 'border-critical/60 bg-critical/10 text-critical'
	};
	const TEKNOLOGI = [
		{ k: 'frontend', label: 'Frontend', ikon: Monitor },
		{ k: 'backend', label: 'Backend', ikon: Cpu },
		{ k: 'database', label: 'Basis data', ikon: Database },
		{ k: 'server', label: 'Server', ikon: Server }
	] as const;

	async function salinUrl() {
		try {
			await navigator.clipboard.writeText(app!.url_dasar);
			toast.success('URL disalin');
		} catch {
			toast.error('Gagal menyalin URL');
		}
	}
</script>

{#snippet judulBagian(nomor: string, judul: string)}
	<div class="mb-4 flex items-baseline gap-2.5 border-b pb-2.5">
		<span class="font-stencil text-gold">{nomor}</span>
		<h2 class="font-heading text-xs font-semibold tracking-[0.14em] uppercase">{judul}</h2>
	</div>
{/snippet}

{#snippet baris(Ikon: Component<{ class?: string }>, label: string, nilai: string)}
	<li class="flex items-start gap-3">
		<Ikon class="mt-0.5 size-4 shrink-0 text-gold" />
		<div class="min-w-0">
			<p class="label-stensil text-[10px]">{label}</p>
			<p class="break-words">{nilai}</p>
		</div>
	</li>
{/snippet}

<svelte:head><title>{app?.nama ?? 'Aplikasi'} — SATRIA</title></svelte:head>

{#if galat}
	<Kosong judul="Aplikasi tidak ditemukan" pesan={galat}><Button href="/aplikasi" variant="outline">Kembali</Button></Kosong>
{:else if !app}
	<Memuat />
{:else}
	<PageHeader label="Berkas Aplikasi" judul={app.nama} deskripsi={app.deskripsi}>
		{#snippet atas()}
			<a href="/aplikasi" class="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
				<ChevronLeft class="size-3.5" /> Daftar aplikasi
			</a>
		{/snippet}
		{#snippet aksi()}
			{#if scanSelesai}
				<Button variant="outline" href="/laporan/{scanSelesai.id}"><FileBarChart /> Laporan Terakhir</Button>
			{/if}
			{#if scanBerjalan}
				<Button href="/scan/{scanBerjalan.id}"><LoaderCircle class="animate-spin" /> Pantau Pengujian</Button>
			{:else if bisaUbah}
				<Button onclick={() => (dialogMetode = true)} class="bg-gold text-gold-foreground hover:bg-gold/85">
					<FlaskConical /> Mulai Pengujian
				</Button>
			{/if}
			{#if bisaUbah}
				<Button variant="outline" href="/aplikasi/{app!.id}/ubah"><Pencil /> Ubah data</Button>
			{/if}
		{/snippet}
	</PageHeader>

	<DialogPilihMetode
		bind:open={dialogMetode}
		onotomatis={() => goto(`/aplikasi/${app!.id}/pengujian/otomatis`)}
	/>

	<div class="grid gap-3 sm:grid-cols-3">
		<div class="sudut-taktis border bg-card p-4">
			<p class="label-stensil text-muted-foreground">Putusan Terakhir</p>
			{#if penilaian}
				<PutusanBadge putusan={penilaian.putusan} class="mt-2" />
				<SkorBar skor={penilaian.skor} putusan={penilaian.putusan} class="mt-2" />
			{:else}
				<p class="mt-2 text-sm text-muted-foreground">Belum diuji</p>
			{/if}
		</div>
		<div class="sudut-taktis border bg-card p-4">
			<p class="label-stensil text-muted-foreground">Lingkungan</p>
			<p class="mt-2 font-medium">{LABEL_LINGKUNGAN[app.lingkungan]}</p>
			<p class="text-xs text-muted-foreground">Klasifikasi data {LABEL_KLASIFIKASI[app.klasifikasi_data].toLowerCase()}</p>
		</div>
		<div class="sudut-taktis border bg-card p-4">
			<p class="label-stensil text-muted-foreground">Satuan Pemilik</p>
			<p class="mt-2 truncate font-medium">{app.satuan}</p>
			<p class="truncate text-xs text-muted-foreground">PIC {app.pic_nama}</p>
		</div>
	</div>

	<!-- Pengujian disiapkan terpisah dari data aset. -->
	<div class="sudut-taktis mt-6 flex flex-col gap-3 rounded-lg border border-dashed border-gold/50 bg-gold/5 p-4 sm:flex-row sm:items-center">
		<FlaskConical class="size-5 shrink-0 text-gold" />
		<div class="flex-1 text-sm">
			<p class="font-medium">Data pengujian</p>
			<p class="text-muted-foreground">
				Isi data yang dibutuhkan mesin uji per fungsi keamanan — diisi bertahap per bagian, tidak sekaligus.
				Saat ini tersedia untuk fungsi Autentikasi.
			</p>
		</div>
		<Button href="/aplikasi/{app.id}/persiapan" class="bg-gold text-gold-foreground hover:bg-gold/85">
			{bisaUbah ? 'Isi data pengujian' : 'Lihat data pengujian'}
		</Button>
	</div>

	<Tabs.Root value="aset" class="mt-6">
		<Tabs.List class="w-full justify-start overflow-x-auto sm:w-auto">
			<Tabs.Trigger value="aset">Informasi Aset</Tabs.Trigger>
			<Tabs.Trigger value="riwayat">Riwayat Pengujian</Tabs.Trigger>
			<Tabs.Trigger value="bukti">Bukti & Tinjauan</Tabs.Trigger>
		</Tabs.List>

		<Tabs.Content value="aset" class="mt-3 grid gap-4">
			<!-- Alamat aplikasi: elemen paling sering dipakai, jadi ditonjolkan di atas. -->
			<div class="sudut-taktis flex flex-col gap-3 rounded-lg border bg-card p-4 sm:flex-row sm:items-center">
				<span class="grid size-10 shrink-0 place-items-center rounded-md border border-gold/40 bg-gold/10 text-gold">
					<Globe class="size-5" />
				</span>
				<div class="min-w-0 flex-1">
					<p class="label-stensil text-[10px]">URL dasar</p>
					<p class="truncate font-mono text-sm">{app.url_dasar}</p>
				</div>
				<div class="flex gap-2">
					<Button variant="outline" size="sm" onclick={salinUrl}><Copy /> Salin</Button>
					<Button variant="outline" size="sm" href={app.url_dasar} target="_blank" rel="noreferrer">
						<ExternalLink /> Buka
					</Button>
				</div>
			</div>

			<div class="grid gap-4 lg:grid-cols-2">
				<section class="sudut-taktis rounded-lg border bg-card p-5">
					{@render judulBagian('01', 'Identitas aplikasi')}
					<p class="label-stensil text-[10px]">Deskripsi</p>
					{#if app.deskripsi}
						<p class="mt-1 text-sm leading-relaxed whitespace-pre-line">{app.deskripsi}</p>
					{:else}
						<p class="mt-1 text-sm text-muted-foreground italic">Belum ada deskripsi.</p>
					{/if}
				</section>

				<section class="sudut-taktis rounded-lg border bg-card p-5">
					{@render judulBagian('02', 'Penanggung jawab')}
					<ul class="grid gap-3 text-sm">
						{@render baris(Building, 'Satuan pemilik', app.satuan)}
						{@render baris(UserRound, 'Nama PIC', app.pic_nama)}
						{@render baris(Phone, 'Kontak PIC', app.pic_kontak)}
					</ul>
				</section>

				<section class="sudut-taktis rounded-lg border bg-card p-5 lg:col-span-2">
					{@render judulBagian('03', 'Lingkungan & teknologi')}
					<div class="flex flex-wrap gap-2">
						<span class="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs">
							<Layers class="size-3.5 text-muted-foreground" /> Lingkungan
							<b class="font-semibold">{LABEL_LINGKUNGAN[app.lingkungan]}</b>
						</span>
						<span class="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs {WARNA_KLASIFIKASI[app.klasifikasi_data]}">
							<ShieldCheck class="size-3.5" /> Data
							<b class="font-semibold">{LABEL_KLASIFIKASI[app.klasifikasi_data]}</b>
						</span>
					</div>
					<div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
						{#each TEKNOLOGI as t (t.k)}
							{@const nilai = app.teknologi[t.k]}
							<div class="flex items-center gap-3 rounded-md border bg-muted/30 p-3">
								<t.ikon class="size-5 shrink-0 {nilai ? 'text-gold' : 'text-muted-foreground/50'}" />
								<div class="min-w-0">
									<p class="label-stensil text-[10px]">{t.label}</p>
									<p class="truncate text-sm {nilai ? 'font-medium' : 'text-muted-foreground'}">{nilai || 'Tidak diisi'}</p>
								</div>
							</div>
						{/each}
					</div>
				</section>
			</div>

			<p class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
				<span class="inline-flex items-center gap-1.5"><CalendarPlus class="size-3.5" /> Didaftarkan {tanggal(app.dibuat_pada)}</span>
				{#if app.diubah_pada && app.diubah_pada !== app.dibuat_pada}
					<span class="inline-flex items-center gap-1.5"><History class="size-3.5" /> Diubah {relatif(app.diubah_pada)}</span>
				{/if}
			</p>
		</Tabs.Content>

		<Tabs.Content value="riwayat" class="mt-3">
			{#if scans.length === 0}
				<Kosong judul="Belum ada pengujian" pesan="Riwayat muncul setelah aplikasi diuji." />
			{:else}
				<ul class="divide-y rounded-lg border bg-card">
					{#each scans as s (s.id)}
						{@const p = s.status === 'selesai' ? nilaiKelaikan(s.hasil) : null}
						<li>
							<a
								href={s.status === 'berjalan' ? `/scan/${s.id}` : `/laporan/${s.id}`}
								class="grid gap-2 p-4 transition hover:bg-muted/50 sm:grid-cols-[1fr_160px_130px_110px] sm:items-center"
							>
								<div>
									<p class="font-medium">{tanggal(s.dimulai_pada)}</p>
									<p class="text-xs text-muted-foreground">
										Profil {s.profil} · durasi {durasi(s.dimulai_pada, s.selesai_pada)} · <span class="font-mono">{s.id}</span>
									</p>
								</div>
								<div>{#if p}<SkorBar skor={p.skor} putusan={p.putusan} />{/if}</div>
								<div>
									{#if p}<PutusanBadge putusan={p.putusan} />{:else}<span class="text-xs text-muted-foreground">{LABEL_STATUS_SCAN[s.status]}</span>{/if}
								</div>
								<span class="text-right text-xs font-medium text-primary">{s.status === 'berjalan' ? 'Pantau ›' : 'Laporan ›'}</span>
							</a>
						</li>
					{/each}
				</ul>
			{/if}
		</Tabs.Content>

		<Tabs.Content value="bukti" class="mt-3">
			{#if scanSelesai}
				<p class="mb-3 text-sm text-muted-foreground">
					Metode manual atau yang belum konklusif pada pengujian {tanggal(scanSelesai.dimulai_pada)}. Unggah dokumen
					pendukung agar asesor dapat memberi putusan.
				</p>
				<BuktiManual bind:scan={scans[scans.indexOf(scanSelesai)]} bisaUnggah={bisaUbah} />
			{:else}
				<Kosong judul="Belum ada pengujian selesai" />
			{/if}
		</Tabs.Content>
	</Tabs.Root>
{/if}
