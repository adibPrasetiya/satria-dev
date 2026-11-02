<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import { indeksMetode, nilaiKelaikan, LABEL_JENIS, LABEL_ENGINE } from '#lib/catalog.js';
	import { tanggal } from '#lib/format.js';
	import type { Aplikasi, Scan, Status } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import StatusBadge from '#lib/components/StatusBadge.svelte';
	import SeverityBadge from '#lib/components/SeverityBadge.svelte';
	import PutusanBadge from '#lib/components/PutusanBadge.svelte';
	import SkorBar from '#lib/components/SkorBar.svelte';
	import BuktiView from '#lib/components/BuktiView.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import FileBarChart from '@lucide/svelte/icons/file-chart-column';
	import Gavel from '@lucide/svelte/icons/gavel';

	const scanId = $derived(page.params.scanId!);

	let scan = $state<Scan | null>(null);
	let app = $state<Aplikasi | null>(null);
	let tampil = $state<'menunggu' | 'selesai'>('menunggu');
	let draf = $state<Record<string, { putusan: Status | ''; catatan: string }>>({});
	let menyimpan = $state<string | null>(null);

	$effect(() => {
		api.getScan(scanId).then(async (s) => {
			scan = s;
			app = await api.getAplikasi(s.aplikasi_id);
		});
	});

	const nilai = $derived(scan ? nilaiKelaikan(scan.hasil) : null);

	const daftar = $derived(
		scan
			? Object.values(scan.hasil)
					.filter((h) => (tampil === 'menunggu' ? h.menunggu_tinjauan : !!h.tinjauan))
					.map((h) => ({ h, ...indeksMetode.get(h.metode_id)! }))
					// Metode yang sudah ada bukti didahulukan.
					.sort((a, b) => Number(b.h.bukti.some((x) => x.jenis !== 'request_response')) - Number(a.h.bukti.some((x) => x.jenis !== 'request_response')))
			: []
	);

	// Siapkan draf putusan untuk setiap metode yang tampil.
	$effect(() => {
		for (const { metode } of daftar) draf[metode.id] ??= { putusan: '', catatan: '' };
	});

	async function simpan(metodeId: string) {
		const x = draf[metodeId];
		if (!x?.putusan) return;
		menyimpan = metodeId;
		try {
			scan = await api.tinjauMetode(scanId, metodeId, x.putusan, x.catatan);
			delete draf[metodeId];
			toast.success(`Putusan ${metodeId} disimpan`);
		} catch (e) {
			toast.error((e as Error).message);
		} finally {
			menyimpan = null;
		}
	}

	const PILIHAN: { v: Status; l: string; c: string }[] = [
		{ v: 'lulus', l: 'Lulus', c: 'data-[on=true]:bg-success data-[on=true]:text-white data-[on=true]:border-success' },
		{ v: 'gagal', l: 'Gagal', c: 'data-[on=true]:bg-critical data-[on=true]:text-white data-[on=true]:border-critical' },
		{ v: 'tidak_berlaku', l: 'Tidak Berlaku', c: 'data-[on=true]:bg-muted-foreground data-[on=true]:text-background' }
	];
</script>

{#if !scan || !app || !nilai}
	<Memuat />
{:else}
	<PageHeader label="Meja Asesor" judul="Tinjauan Manual" deskripsi="{app.nama} · pengujian {tanggal(scan.dimulai_pada)}">
		{#snippet aksi()}
			<Button variant="outline" href="/laporan/{scan!.id}"><FileBarChart /> Lihat Laporan</Button>
		{/snippet}
	</PageHeader>

	<div class="sticky top-14 z-10 mb-4 flex flex-wrap items-center gap-4 rounded-lg border bg-card/95 p-3 shadow-sm backdrop-blur lg:top-14">
		<span class="label-stensil text-muted-foreground">Putusan sementara</span>
		<PutusanBadge putusan={nilai.putusan} />
		<SkorBar skor={nilai.skor} putusan={nilai.putusan} class="w-48" />
		<span class="text-xs text-muted-foreground">{nilai.hitungan.tidak_dapat_diverifikasi} kontrol belum terverifikasi</span>
		<div class="ml-auto inline-flex rounded-md border p-0.5">
			{#each [['menunggu', 'Menunggu'], ['selesai', 'Sudah diputus']] as [v, l] (v)}
				<button
					class={cn('rounded px-3 py-1 font-heading text-xs tracking-[0.08em] uppercase', tampil === v ? 'bg-primary text-primary-foreground' : 'text-muted-foreground')}
					onclick={() => (tampil = v as typeof tampil)}>{l}</button
				>
			{/each}
		</div>
	</div>

	{#if daftar.length === 0}
		<Kosong judul={tampil === 'menunggu' ? 'Tidak ada yang menunggu' : 'Belum ada putusan'} />
	{:else}
		<ul class="grid gap-4">
			{#each daftar as { h, metode, kontrol, fungsi } (metode.id)}
				{@const x = draf[metode.id] ?? { putusan: '', catatan: '' }}
				<li class="sudut-taktis grid gap-4 rounded-lg border bg-card p-4 lg:grid-cols-[1fr_320px]">
					<div class="min-w-0">
						<div class="flex flex-wrap items-center gap-2">
							<span class="font-mono text-xs text-muted-foreground">{metode.id}</span>
							<StatusBadge status={h.status} />
							<SeverityBadge severity={metode.severity} />
							<span class="font-heading text-[10px] tracking-[0.1em] text-muted-foreground uppercase">{LABEL_JENIS[metode.jenis]} · {LABEL_ENGINE[metode.engine]}</span>
						</div>
						<p class="mt-1 font-medium">{metode.nama}</p>
						<p class="text-xs text-muted-foreground">Fungsi {fungsi.nomor} {fungsi.nama} · Kontrol {kontrol.nomor_referensi}: {kontrol.uraian}</p>
						<p class="mt-2 rounded border-l-4 border-gold bg-gold/5 p-2 text-sm"><b>Kriteria lulus:</b> {metode.kriteria_lulus}</p>
						{#if h.ringkasan}<p class="mt-2 text-sm text-muted-foreground">{h.ringkasan}</p>{/if}
						{#if h.bukti.length}
							<BuktiView bukti={h.bukti} />
						{:else}
							<p class="mt-2 text-xs text-warning-foreground italic">Belum ada bukti diunggah pemilik aplikasi.</p>
						{/if}
					</div>

					<div class="rounded-md border bg-muted/30 p-3">
						{#if h.tinjauan && tampil === 'selesai'}
							<p class="label-stensil text-muted-foreground">Putusan</p>
							<StatusBadge status={h.tinjauan.putusan} class="mt-1" />
							<p class="mt-2 text-sm">{h.tinjauan.catatan || '—'}</p>
							<p class="mt-1 text-[11px] text-muted-foreground">{h.tinjauan.asesor} · {tanggal(h.tinjauan.waktu)}</p>
						{:else if draf[metode.id]}
							<p class="label-stensil mb-2 text-muted-foreground">Putusan asesor</p>
							<div class="grid grid-cols-3 gap-1">
								{#each PILIHAN as p (p.v)}
									<button
										data-on={x.putusan === p.v}
										class={cn('rounded border px-1 py-1.5 font-heading text-[11px] tracking-[0.06em] uppercase transition hover:bg-muted', p.c)}
										onclick={() => (draf[metode.id].putusan = p.v)}>{p.l}</button
									>
								{/each}
							</div>
							<Textarea bind:value={draf[metode.id].catatan} rows={3} placeholder="Dasar putusan / catatan…" class="mt-2 bg-card text-sm" />
							<Button class="mt-2 w-full" disabled={!x.putusan || menyimpan === metode.id} onclick={() => simpan(metode.id)}>
								<Gavel /> {menyimpan === metode.id ? 'Menyimpan…' : 'Simpan Putusan'}
							</Button>
						{/if}
					</div>
				</li>
			{/each}
		</ul>
	{/if}
{/if}
