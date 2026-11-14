<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { relatif } from '#lib/format.js';
	import { cn } from '#lib/utils.js';
	import type { RingkasanKerentanan, StatusSinkronIntel } from '#lib/types.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import DaftarKerentanan from '#lib/components/kerentanan/DaftarKerentanan.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import X from '@lucide/svelte/icons/x';

	const aplikasiId = $derived(page.url.searchParams.get('aplikasi') ?? undefined);
	let ringkasan = $state<RingkasanKerentanan | null>(null);
	let namaAplikasi = $state<string | null>(null);
	let sinkron = $state<StatusSinkronIntel | null>(null);
	let memicu = $state(false);
	let muatUlang = $state(0);

	const bolehLihatSinkron = $derived(auth.punya('asesor', 'admin'));

	$effect(() => {
		const id = aplikasiId;
		namaAplikasi = null;
		if (id) api.getAplikasi(id).then((a) => (namaAplikasi = a.nama), () => {});
	});

	async function muatSinkron() {
		try {
			sinkron = await api.statusSinkronIntel();
		} catch {
			sinkron = null;
		}
	}

	$effect(() => {
		if (!bolehLihatSinkron) return;
		void muatSinkron();
		// Selama sinkron berjalan, pantau tiap 10 dtk lalu muat ulang daftar saat selesai.
		const t = setInterval(async () => {
			const sebelum = sinkron?.global?.status;
			await muatSinkron();
			if (sebelum === 'berjalan' && sinkron?.global?.status !== 'berjalan') muatUlang += 1;
		}, 10_000);
		return () => clearInterval(t);
	});

	async function picuSinkron() {
		memicu = true;
		try {
			await api.mulaiSinkronIntel();
			toast.success('Sinkron intel kerentanan dimulai. Proses bisa beberapa menit.');
			setTimeout(muatSinkron, 1500);
		} catch (e) {
			toast.error(e instanceof Error ? e.message : 'Gagal memulai sinkron');
		} finally {
			memicu = false;
		}
	}

	const STAT = $derived([
		{ label: 'Dieksploitasi aktif', nilai: ringkasan?.kev, warna: 'bg-critical', bantuan: 'Tercantum di CISA KEV' },
		{ label: 'Terdampak', nilai: ringkasan?.terdampak, warna: 'bg-critical/60', bantuan: 'Versi komponen dalam rentang rentan' },
		{ label: 'Kemungkinan', nilai: ringkasan?.kemungkinan, warna: 'bg-warning', bantuan: 'Versi belum diketahui/kurang rinci' },
		{ label: 'Aplikasi terdampak', nilai: ringkasan?.aplikasi, warna: 'bg-primary', bantuan: 'Memiliki kecocokan aktif' },
		{ label: 'Ditangani', nilai: ringkasan?.ditangani, warna: 'bg-success', bantuan: 'Ditandai sudah ditambal' }
	]);

	const berjalan = $derived(sinkron?.global?.status === 'berjalan');
</script>

<svelte:head><title>Kerentanan — SATRIA</title></svelte:head>

<PageHeader
	label="Intel Kerentanan"
	judul="CVE pada Aset"
	deskripsi="CVE terbaru dari NVD, CISA KEV, EPSS, dan OSV yang dicocokkan dengan komponen dan versi aset, dari isian formulir, koreksi manual, dan hasil recon. Hasil ini bersifat indikatif, bukan hasil pengujian."
>
	{#snippet aksi()}
		{#if auth.punya('admin')}
			<Button variant="outline" disabled={memicu || berjalan} onclick={picuSinkron}>
				<RefreshCw class={cn(berjalan && 'animate-spin')} />
				{berjalan ? 'Sinkron berjalan…' : 'Sinkron sekarang'}
			</Button>
		{/if}
	{/snippet}
</PageHeader>

{#if aplikasiId}
	<div class="mb-3 flex flex-wrap items-center gap-2 text-sm">
		<span class="text-muted-foreground">Aplikasi:</span>
		<span class="inline-flex items-center gap-1 rounded-md border bg-card px-2 py-1">
			{namaAplikasi ?? `#${aplikasiId}`}
			<button type="button" class="text-muted-foreground hover:text-foreground" aria-label="Tampilkan semua aplikasi" onclick={() => goto('/kerentanan')}>
				<X class="size-3.5" />
			</button>
		</span>
		<a href="/aplikasi/{aplikasiId}/komponen" class="text-primary hover:underline">Lihat komponen aset</a>
	</div>
{/if}

<div class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
	{#each STAT as s (s.label)}
		<div class="relative overflow-hidden rounded-lg border bg-card px-4 py-3" title={s.bantuan}>
			<span class={cn('absolute inset-y-0 left-0 w-1', s.warna)}></span>
			<p class="font-heading text-[10px] tracking-[0.15em] text-muted-foreground uppercase">{s.label}</p>
			<p class="mt-1 text-2xl font-semibold tabular-nums">{s.nilai ?? '—'}</p>
		</div>
	{/each}
</div>

{#if bolehLihatSinkron && sinkron}
	<div class="mb-4 rounded-lg border bg-card px-4 py-3 text-xs text-muted-foreground">
		{#if !sinkron.aktif}
			<p>Sinkron intel dinonaktifkan (<code>CVE_SYNC_ENABLED=false</code>).</p>
		{:else}
			<p class="flex flex-wrap gap-x-4 gap-y-1">
				<span>
					Sinkron terakhir:
					<span class={cn('font-medium', sinkron.global?.status === 'gagal' ? 'text-critical' : 'text-foreground')}>
						{sinkron.global ? `${relatif(sinkron.global.diperbarui)} · ${sinkron.global.status}` : 'belum pernah'}
					</span>
					{#if sinkron.global?.pesan}<span> — {sinkron.global.pesan}</span>{/if}
				</span>
				<span>NVD: {sinkron.nvd?.kursor ? relatif(sinkron.nvd.kursor) : '—'}</span>
				<span>KEV: {sinkron.kev?.pesan ?? '—'}</span>
				<span>{sinkron.produk.length} produk tersinkron</span>
				{#if !sinkron.kunci_nvd}<span class="text-warning-foreground">Tanpa NVD_API_KEY (sinkron lebih lambat)</span>{/if}
			</p>
			{@const gagal = sinkron.produk.filter((p) => p.status === 'gagal')}
			{#if gagal.length}
				<p class="mt-1 text-critical">Gagal disinkron (akan dicoba lagi): {gagal.map((p) => p.produk).join(', ')}</p>
			{/if}
		{/if}
	</div>
{/if}

{#key aplikasiId}
	<DaftarKerentanan {aplikasiId} tampilAplikasi={!aplikasiId} {muatUlang} onringkasan={(r) => (ringkasan = r)} />
{/key}
