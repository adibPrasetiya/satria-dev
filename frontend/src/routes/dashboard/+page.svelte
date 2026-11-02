<script lang="ts">
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { ringkasAplikasi, type RingkasanAplikasi } from '#lib/ringkasan.js';
	import { relatif } from '#lib/format.js';
	import type { ItemTinjauan } from '#lib/types.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import StatTaktis from '#lib/components/StatTaktis.svelte';
	import PutusanBadge from '#lib/components/PutusanBadge.svelte';
	import SkorBar from '#lib/components/SkorBar.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import AppWindow from '@lucide/svelte/icons/app-window';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import ShieldAlert from '@lucide/svelte/icons/shield-alert';
	import ClipboardCheck from '@lucide/svelte/icons/clipboard-check';
	import CirclePlus from '@lucide/svelte/icons/circle-plus';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	let data = $state<{ ringkasan: RingkasanAplikasi[]; antrian: ItemTinjauan[] } | null>(null);

	$effect(() => {
		const pemilik = auth.pengguna?.peran === 'pemilik' ? auth.pengguna.id : null;
		Promise.all([
			api.listAplikasi(),
			api.listScan(),
			auth.punya('asesor', 'admin') ? api.antrianTinjauan() : Promise.resolve([])
		]).then(([apps, scans, antrian]) => {
			const milik = pemilik ? apps.filter((a) => a.pemilik_id === pemilik) : apps;
			data = { ringkasan: ringkasAplikasi(milik, scans), antrian };
		});
	});

	const stat = $derived.by(() => {
		if (!data) return null;
		const r = data.ringkasan;
		return {
			total: r.length,
			laik: r.filter((x) => x.penilaian?.putusan === 'laik').length,
			bersyarat: r.filter((x) => x.penilaian?.putusan === 'laik_bersyarat').length,
			tidakLaik: r.filter((x) => x.penilaian?.putusan === 'tidak_laik').length,
			belumDiuji: r.filter((x) => !x.penilaian).length
		};
	});

	interface Tindakan {
		href: string;
		judul: string;
		ket: string;
		ikon: typeof TriangleAlert;
		nada: string;
	}

	const tindakan = $derived.by<Tindakan[]>(() => {
		if (!data) return [];
		const t: Tindakan[] = [];
		for (const { app, berjalan, scanTerakhir } of data.ringkasan) {
			if (berjalan && scanTerakhir)
				t.push({
					href: `/scan/${scanTerakhir.id}`,
					judul: app.nama,
					ket: 'Pengujian sedang berjalan',
					ikon: LoaderCircle,
					nada: 'text-info'
				});
			if (app.izin_intrusif.status === 'menunggu' && auth.punya('asesor', 'admin'))
				t.push({
					href: '/asesor/antrian',
					judul: app.nama,
					ket: 'Permohonan izin pengujian intrusif',
					ikon: ShieldAlert,
					nada: 'text-critical'
				});
		}
		if (data.antrian.length)
			t.push({
				href: '/asesor/antrian',
				judul: `${data.antrian.length} metode uji`,
				ket: 'Menunggu putusan asesor',
				ikon: ClipboardCheck,
				nada: 'text-gold'
			});
		return t;
	});
</script>

<PageHeader
	label="Pusat Komando"
	judul="Dasbor"
	deskripsi={`Selamat bertugas, ${auth.pengguna?.nama}. Ringkasan kelaikan keamanan aplikasi ${auth.pengguna?.peran === 'pemilik' ? 'milik satuan Anda' : 'seluruh satuan'}.`}
>
	{#snippet aksi()}
		{#if auth.punya('pemilik', 'admin')}
			<Button href="/aplikasi/baru"><CirclePlus /> Registrasi Aplikasi</Button>
		{/if}
	{/snippet}
</PageHeader>

{#if !data || !stat}
	<Memuat />
{:else}
	<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
		<StatTaktis label="Aplikasi Terdaftar" nilai={stat.total} ket="{stat.belumDiuji} belum diuji" ikon={AppWindow} href="/aplikasi" />
		<StatTaktis label="Laik" nilai={stat.laik} ket="Siap dioperasikan" ikon={ShieldCheck} nada="success" />
		<StatTaktis label="Laik Bersyarat" nilai={stat.bersyarat} ket="Perlu perbaikan minor" ikon={TriangleAlert} nada="warning" />
		<StatTaktis label="Tidak Laik" nilai={stat.tidakLaik} ket="Temuan kritis/tinggi" ikon={ShieldAlert} nada="critical" />
	</div>

	<div class="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
		<Card.Root class="sudut-taktis gap-0 py-0">
			<Card.Header class="border-b py-4">
				<Card.Title>Status Kelaikan Aplikasi</Card.Title>
				<Card.Description>Berdasarkan pengujian selesai terakhir</Card.Description>
			</Card.Header>
			<Card.Content class="p-0">
				{#if data.ringkasan.length === 0}
					<div class="p-6">
						<Kosong judul="Belum ada aplikasi" pesan="Registrasikan aplikasi pertama untuk mulai pengujian." />
					</div>
				{:else}
					<ul class="divide-y">
						{#each data.ringkasan as r (r.app.id)}
							<li>
								<a
									href="/aplikasi/{r.app.id}"
									class="grid gap-2 px-5 py-3.5 transition hover:bg-muted/60 sm:grid-cols-[1fr_140px_120px_20px] sm:items-center"
								>
									<div class="min-w-0">
										<p class="truncate font-medium">{r.app.nama}</p>
										<p class="truncate text-xs text-muted-foreground">
											{r.app.satuan} · {r.app.url_dasar}
										</p>
									</div>
									<div>
										{#if r.penilaian}
											<SkorBar skor={r.penilaian.skor} putusan={r.penilaian.putusan} />
										{:else}
											<span class="text-xs text-muted-foreground">Belum diuji</span>
										{/if}
									</div>
									<div class="flex flex-col items-start gap-0.5">
										{#if r.berjalan}
											<span class="inline-flex items-center gap-1 text-xs text-info">
												<LoaderCircle class="size-3 animate-spin" /> Berjalan
											</span>
										{:else if r.penilaian}
											<PutusanBadge putusan={r.penilaian.putusan} />
										{/if}
										<span class="text-[11px] text-muted-foreground">{relatif(r.scanTerakhir?.dimulai_pada)}</span>
									</div>
									<ChevronRight class="hidden size-4 text-muted-foreground sm:block" />
								</a>
							</li>
						{/each}
					</ul>
				{/if}
			</Card.Content>
		</Card.Root>

		<Card.Root class="sudut-taktis gap-0 self-start py-0">
			<Card.Header class="border-b py-4">
				<Card.Title>Perlu Tindakan</Card.Title>
				<Card.Description>{tindakan.length} item</Card.Description>
			</Card.Header>
			<Card.Content class="p-0">
				{#if tindakan.length === 0}
					<p class="p-5 text-sm text-muted-foreground">Tidak ada tindakan tertunda. Situasi aman terkendali.</p>
				{:else}
					<ul class="divide-y">
						{#each tindakan as t, i (i)}
							<li>
								<a href={t.href} class="flex items-start gap-3 px-5 py-3 transition hover:bg-muted/60">
									<t.ikon class="mt-0.5 size-4 shrink-0 {t.nada} {t.ikon === LoaderCircle ? 'animate-spin' : ''}" />
									<div class="min-w-0">
										<p class="truncate text-sm font-medium">{t.judul}</p>
										<p class="text-xs text-muted-foreground">{t.ket}</p>
									</div>
								</a>
							</li>
						{/each}
					</ul>
				{/if}
			</Card.Content>
		</Card.Root>
	</div>
{/if}
