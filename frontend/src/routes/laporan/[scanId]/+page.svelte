<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { indeksMetode, nilaiKelaikan, URUTAN_SEVERITY, LABEL_STATUS, katalog, statusKontrol } from '#lib/catalog.js';
	import { tanggal, durasi } from '#lib/format.js';
	import type { Aplikasi, Scan, Status } from '#lib/types.js';
	import * as Tabs from '#lib/components/ui/tabs/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import CapPutusan from '#lib/components/CapPutusan.svelte';
	import ControlTree from '#lib/components/ControlTree.svelte';
	import PanelAi from '#lib/components/PanelAi.svelte';
	import SeverityBadge from '#lib/components/SeverityBadge.svelte';
	import StatusBadge from '#lib/components/StatusBadge.svelte';
	import BuktiView from '#lib/components/BuktiView.svelte';
	import NativeSelect from '#lib/components/NativeSelect.svelte';
	import Lambang from '#lib/components/Lambang.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { cn } from '#lib/utils.js';
	import Printer from '@lucide/svelte/icons/printer';
	import ClipboardCheck from '@lucide/svelte/icons/clipboard-check';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';

	const scanId = $derived(page.params.scanId!);

	let scan = $state<Scan | null>(null);
	let app = $state<Aplikasi | null>(null);
	let galat = $state<string | null>(null);
	let filterKontrol = $state<'semua' | Status>('semua');

	$effect(() => {
		api
			.getScan(scanId)
			.then(async (s) => {
				scan = s;
				app = await api.getAplikasi(s.aplikasi_id);
			})
			.catch((e) => (galat = e.message));
	});

	const nilai = $derived(scan ? nilaiKelaikan(scan.hasil) : null);

	const temuan = $derived(
		scan
			? Object.values(scan.hasil)
					.filter((h) => h.status === 'gagal')
					.map((h) => ({ h, ...indeksMetode.get(h.metode_id)! }))
					.sort((a, b) => URUTAN_SEVERITY.indexOf(a.metode.severity) - URUTAN_SEVERITY.indexOf(b.metode.severity))
			: []
	);

	const perSeverity = $derived(
		URUTAN_SEVERITY.filter((s) => s !== 'info').map((s) => ({ s, n: temuan.filter((t) => t.metode.severity === s).length }))
	);

	const nomor = $derived(
		scan ? `LAP/SATRIA/${scan.id.replace(/^scan-/, '').toUpperCase()}/${new Date(scan.dimulai_pada).getFullYear()}` : ''
	);

	const WARNA_BAR = (skor: number | null, gagal: number) =>
		skor === null ? 'bg-muted' : gagal ? (skor < 60 ? 'bg-critical' : 'bg-warning') : 'bg-success';
</script>

{#if galat}
	<Kosong judul="Laporan tidak ditemukan" pesan={galat} />
{:else if !scan || !app || !nilai}
	<Memuat />
{:else}
	<div class="no-print">
		<PageHeader label="Laporan Asesmen" judul="Hasil Kelaikan Keamanan" deskripsi="{app.nama} · pengujian {tanggal(scan.dimulai_pada)}">
			{#snippet atas()}
				<a href="/aplikasi/{app!.id}" class="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
					<ChevronLeft class="size-3.5" /> Berkas aplikasi
				</a>
			{/snippet}
			{#snippet aksi()}
				{#if auth.punya('asesor', 'admin') && nilai!.hitungan.tidak_dapat_diverifikasi}
					<Button variant="outline" href="/asesor/tinjau/{scan!.id}"><ClipboardCheck /> Tinjau Manual</Button>
				{/if}
				<Button variant="outline" onclick={() => window.print()}><Printer /> Cetak / PDF</Button>
			{/snippet}
		</PageHeader>
	</div>

	<!-- Kop dokumen -->
	<section class="sudut-taktis relative overflow-hidden rounded-lg border bg-card shadow-sm print:border-0 print:shadow-none">
		<div class="bg-loreng flex items-center gap-4 px-5 py-4 text-sidebar-foreground print:bg-none print:text-black">
			<Lambang class="size-12 shrink-0" />
			<div class="min-w-0 flex-1">
				<p class="font-heading text-[11px] tracking-[0.25em] text-gold uppercase">Laporan Hasil Asesmen</p>
				<p class="font-heading text-lg leading-tight tracking-[0.05em] uppercase sm:text-xl">Kelaikan Keamanan Aplikasi Berbasis Web</p>
				<p class="text-xs opacity-80">Nomor: {nomor}</p>
			</div>
			<span class="cap-stempel hidden border-red-400 text-red-300 sm:inline-block print:text-red-700">Terbatas</span>
		</div>

		<div class="grid gap-6 p-5 lg:grid-cols-[1fr_auto]">
			<dl class="grid content-start gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[150px_1fr]">
				<dt class="text-muted-foreground">Aplikasi</dt><dd class="font-medium">{app.nama}</dd>
				<dt class="text-muted-foreground">Satuan</dt><dd>{app.satuan}</dd>
				<dt class="text-muted-foreground">Sasaran</dt><dd class="break-all">{app.url_dasar} ({app.lingkungan})</dd>
				<dt class="text-muted-foreground">Waktu uji</dt><dd>{tanggal(scan.dimulai_pada)} · durasi {durasi(scan.dimulai_pada, scan.selesai_pada)}</dd>
				<dt class="text-muted-foreground">Profil</dt><dd class="capitalize">{scan.profil}</dd>
				<dt class="text-muted-foreground">Acuan</dt><dd>{katalog.sumber.peraturan} — {katalog.sumber.bagian}</dd>
			</dl>
			<div class="flex flex-col items-center justify-center gap-3 lg:min-w-64">
				<CapPutusan putusan={nilai.putusan} />
				<ul class="text-center text-xs text-muted-foreground">
					{#each nilai.alasan as a, i (i)}<li>{a}</li>{/each}
				</ul>
			</div>
		</div>

		<div class="grid grid-cols-2 border-t sm:grid-cols-3 lg:grid-cols-6 [&>div]:border-r [&>div]:border-b [&>div]:p-4">
			<div><p class="label-stensil text-muted-foreground">Kepatuhan</p><p class="font-stencil text-3xl">{nilai.skor}%</p></div>
			<div><p class="label-stensil text-muted-foreground">Cakupan</p><p class="font-stencil text-3xl">{nilai.cakupan}%</p></div>
			<div><p class="label-stensil text-muted-foreground">Lulus</p><p class="font-stencil text-3xl text-success">{nilai.hitungan.lulus}</p></div>
			<div><p class="label-stensil text-muted-foreground">Gagal</p><p class="font-stencil text-3xl text-critical">{nilai.hitungan.gagal}</p></div>
			<div><p class="label-stensil text-muted-foreground">Ditinjau</p><p class="font-stencil text-3xl text-warning-foreground">{nilai.hitungan.tidak_dapat_diverifikasi}</p></div>
			<div><p class="label-stensil text-muted-foreground">Tidak Berlaku</p><p class="font-stencil text-3xl text-muted-foreground">{nilai.hitungan.tidak_berlaku}</p></div>
		</div>
		<p class="px-5 py-2 text-[11px] text-muted-foreground">
			Satuan hitung: butir kontrol. Kepatuhan = lulus ÷ (lulus + gagal). Cakupan = kontrol yang sudah teruji ÷ kontrol yang berlaku.
		</p>
	</section>

	<!-- Skor per fungsi & sebaran severity -->
	<div class="mt-6 grid gap-6 lg:grid-cols-[1fr_300px]">
		<section class="rounded-lg border bg-card p-5">
			<p class="label-stensil mb-3">Kepatuhan per Fungsi Keamanan</p>
			<ul class="grid gap-2">
				{#each nilai.perFungsi as p (p.fungsi.id)}
					<li class="flex items-center gap-3 text-sm">
						<span class="w-5 shrink-0 font-heading text-xs text-muted-foreground">{p.fungsi.nomor}</span>
						<span class="w-32 shrink-0 truncate sm:w-56" title={p.fungsi.nama}>{p.fungsi.nama}</span>
						<div class="flex h-3 flex-1 overflow-hidden rounded-sm bg-muted">
							<span class={cn('transition-all', WARNA_BAR(p.skor, p.hitungan.gagal))} style="width: {p.skor ?? 0}%"></span>
						</div>
						<span class="w-20 shrink-0 text-right font-heading text-xs tabular-nums">
							{p.skor === null ? 'N/A' : `${p.skor}%`}
							<span class="text-muted-foreground">({p.hitungan.lulus}/{p.hitungan.lulus + p.hitungan.gagal})</span>
						</span>
					</li>
				{/each}
			</ul>
		</section>
		<section class="rounded-lg border bg-card p-5">
			<p class="label-stensil mb-3">Sebaran Temuan</p>
			<ul class="grid gap-2">
				{#each perSeverity as { s, n } (s)}
					<li class="flex items-center gap-2">
						<SeverityBadge severity={s} class="w-16 justify-center" />
						<div class="flex h-3 flex-1 overflow-hidden rounded-sm bg-muted">
							<span
								class={cn(s === 'kritis' || s === 'tinggi' ? 'bg-critical' : s === 'sedang' ? 'bg-warning' : 'bg-info')}
								style="width: {temuan.length ? (n / temuan.length) * 100 : 0}%"
							></span>
						</div>
						<span class="w-6 text-right font-stencil">{n}</span>
					</li>
				{/each}
			</ul>
			<p class="mt-3 text-xs text-muted-foreground">{temuan.length} metode uji gagal dari pengujian ini.</p>
		</section>
	</div>

	<!-- Tampilan layar -->
	<Tabs.Root value="temuan" class="no-print mt-6">
		<Tabs.List class="w-full justify-start overflow-x-auto sm:w-auto">
			<Tabs.Trigger value="temuan">Temuan ({temuan.length})</Tabs.Trigger>
			<Tabs.Trigger value="kontrol">Seluruh Kontrol</Tabs.Trigger>
			<Tabs.Trigger value="ai">Analisis AI</Tabs.Trigger>
		</Tabs.List>
		<Tabs.Content value="temuan" class="mt-3">
			{#if temuan.length === 0}
				<Kosong judul="Tidak ada temuan" pesan="Seluruh metode yang dijalankan lulus atau masih menunggu tinjauan." />
			{:else}
				<ol class="grid gap-3">
					{#each temuan as t (t.metode.id)}
						<li class="rounded-lg border border-l-4 border-l-critical bg-card p-4">
							<div class="flex flex-wrap items-center gap-2">
								<SeverityBadge severity={t.metode.severity} />
								<span class="font-mono text-xs text-muted-foreground">{t.metode.id}</span>
								<span class="font-medium">{t.metode.nama}</span>
								<span class="ml-auto text-xs text-muted-foreground">Fungsi {t.fungsi.nomor} · {t.fungsi.nama}</span>
							</div>
							<p class="mt-1 text-xs text-muted-foreground">
								Kontrol {t.kontrol.nomor_referensi}: {t.kontrol.uraian}
							</p>
							<p class="mt-2 text-sm text-critical">{t.h.ringkasan}</p>
							<p class="mt-1 text-xs"><b>Kriteria lulus:</b> {t.metode.kriteria_lulus}</p>
							{#if t.kontrol.referensi_pendukung?.length}
								<p class="mt-1 text-[11px] text-muted-foreground">Referensi: {t.kontrol.referensi_pendukung.join(', ')}</p>
							{/if}
							<BuktiView bukti={t.h.bukti} />
						</li>
					{/each}
				</ol>
			{/if}
		</Tabs.Content>
		<Tabs.Content value="kontrol" class="mt-3">
			<div class="mb-3 flex items-center justify-end gap-2">
				<span class="text-xs text-muted-foreground">Tampilkan kontrol</span>
				<NativeSelect
					bind:value={filterKontrol}
					class="w-48 bg-card"
					opsi={[{ value: 'semua', label: 'Semua status' }, ...(['gagal', 'tidak_dapat_diverifikasi', 'lulus', 'tidak_berlaku'] as Status[]).map((s) => ({ value: s, label: LABEL_STATUS[s] }))]}
				/>
			</div>
			<ControlTree hasil={scan.hasil} filter={filterKontrol} />
		</Tabs.Content>
		<Tabs.Content value="ai" class="mt-3">
			<PanelAi bind:scan />
		</Tabs.Content>
	</Tabs.Root>

	<!-- Tampilan cetak -->
	<div class="hidden print:block">
		{#if scan.ai}
			<h2 class="mt-6 mb-2 text-lg font-semibold uppercase">Ringkasan Eksekutif</h2>
			{#each scan.ai.ringkasan_eksekutif.split('\n\n') as p, i (i)}<p class="mb-2 text-sm">{p.replaceAll('**', '')}</p>{/each}
		{/if}
		<h2 class="mt-6 mb-2 text-lg font-semibold uppercase">Daftar Kontrol</h2>
		<table class="w-full border-collapse text-xs">
			<thead><tr class="border-b-2"><th class="p-1 text-left">No.</th><th class="p-1 text-left">Kontrol</th><th class="p-1 text-left">Severity</th><th class="p-1 text-left">Status</th></tr></thead>
			<tbody>
				{#each katalog.fungsi_keamanan as f (f.id)}
					<tr><td colspan="4" class="bg-muted p-1 font-semibold">{f.nomor}. {f.nama}</td></tr>
					{#each f.kontrol as k (k.id)}
						<tr class="border-b"><td class="p-1">{k.nomor_referensi}</td><td class="p-1">{k.uraian}</td><td class="p-1">{k.severity_default}</td><td class="p-1"><StatusBadge status={statusKontrol(k, scan.hasil)} /></td></tr>
					{/each}
				{/each}
			</tbody>
		</table>
		{#if scan.ai?.rekomendasi.length}
			<h2 class="mt-6 mb-2 text-lg font-semibold uppercase">Rekomendasi Perbaikan</h2>
			<ol class="list-decimal pl-5 text-sm">
				{#each scan.ai.rekomendasi as r (r.metode_id)}<li class="mb-2"><b>{r.judul}</b> — {r.langkah.join(' ')}</li>{/each}
			</ol>
		{/if}
		<div class="mt-10 grid grid-cols-2 gap-10 text-center text-sm">
			<div><p>Pemilik Aplikasi</p><div class="h-20"></div><p class="border-t pt-1">{app.pic_nama}</p></div>
			<div><p>Asesor</p><div class="h-20"></div><p class="border-t pt-1">(.................................)</p></div>
		</div>
	</div>
{/if}
