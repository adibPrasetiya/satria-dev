<script lang="ts">
	import { api } from '#lib/api/client.js';
	import { tanggal, relatif } from '#lib/format.js';
	import type { Aplikasi, ItemTinjauan } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import PageHeader from '#lib/components/PageHeader.svelte';
	import StatTaktis from '#lib/components/StatTaktis.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import ShieldAlert from '@lucide/svelte/icons/shield-alert';
	import ClipboardCheck from '@lucide/svelte/icons/clipboard-check';
	import FileCheck from '@lucide/svelte/icons/file-check';
	import FileText from '@lucide/svelte/icons/file-text';

	let data = $state<{ antrian: ItemTinjauan[]; izin: Aplikasi[] } | null>(null);

	$effect(() => {
		Promise.all([api.antrianTinjauan(), api.listAplikasi()]).then(([antrian, apps]) => {
			data = { antrian, izin: apps.filter((a) => a.izin_intrusif.status === 'menunggu') };
		});
	});

	const perScan = $derived.by(() => {
		const g = new Map<string, { nama: string; scan_id: string; total: number; bukti: number }>();
		for (const i of data?.antrian ?? []) {
			const x = g.get(i.scan_id) ?? { nama: i.aplikasi_nama, scan_id: i.scan_id, total: 0, bukti: 0 };
			x.total++;
			if (i.ada_bukti) x.bukti++;
			g.set(i.scan_id, x);
		}
		return [...g.values()];
	});
</script>

<PageHeader
	label="Meja Asesor"
	judul="Antrian Tinjauan"
	deskripsi="Permohonan izin pengujian intrusif dan metode uji manual yang menunggu putusan asesor."
/>

{#if !data}
	<Memuat />
{:else}
	<div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
		<StatTaktis label="Izin Intrusif" nilai={data.izin.length} ket="Menunggu keputusan" ikon={ShieldAlert} nada="critical" />
		<StatTaktis label="Metode Menunggu" nilai={data.antrian.length} ket="Manual / belum konklusif" ikon={ClipboardCheck} nada="gold" />
		<StatTaktis label="Bukti Masuk" nilai={data.antrian.filter((a) => a.ada_bukti).length} ket="Siap diputuskan" ikon={FileCheck} nada="success" />
	</div>

	<h2 class="mt-8 mb-3 text-lg font-semibold uppercase">Permohonan Izin Intrusif</h2>
	{#if data.izin.length === 0}
		<Kosong judul="Tidak ada permohonan" />
	{:else}
		<ul class="grid gap-3">
			{#each data.izin as a (a.id)}
				<li class="sudut-taktis flex flex-col gap-3 rounded-lg border border-l-4 border-l-critical bg-card p-4 sm:flex-row sm:items-center">
					<div class="min-w-0 flex-1">
						<p class="font-medium">{a.nama}</p>
						<p class="text-xs text-muted-foreground">
							{a.satuan} · {a.url_dasar} · lingkungan {a.lingkungan} · diajukan {relatif(a.izin_intrusif.diajukan_pada)}
						</p>
						<p class="mt-1 inline-flex items-center gap-1.5 text-xs">
							<FileText class="size-3.5" /> {a.izin_intrusif.dokumen_nama} · jendela {tanggal(a.izin_intrusif.jendela_mulai)} – {tanggal(a.izin_intrusif.jendela_selesai)}
						</p>
					</div>
					<Button href="/aplikasi/{a.id}" variant="outline"><ShieldAlert /> Periksa & Putuskan</Button>
				</li>
			{/each}
		</ul>
	{/if}

	<h2 class="mt-8 mb-3 text-lg font-semibold uppercase">Metode Menunggu Putusan</h2>
	{#if perScan.length === 0}
		<Kosong judul="Antrian kosong" pesan="Semua metode manual sudah diputuskan." />
	{:else}
		<ul class="grid gap-3">
			{#each perScan as s (s.scan_id)}
				<li class="flex flex-col gap-3 rounded-lg border bg-card p-4 sm:flex-row sm:items-center">
					<div class="min-w-0 flex-1">
						<p class="font-medium">{s.nama}</p>
						<p class="text-xs text-muted-foreground">Pengujian <span class="font-mono">{s.scan_id}</span></p>
					</div>
					<div class="flex gap-4 text-center">
						<div><p class="font-stencil text-2xl text-gold">{s.total}</p><p class="font-heading text-[10px] tracking-[0.12em] text-muted-foreground uppercase">Menunggu</p></div>
						<div><p class="font-stencil text-2xl text-success">{s.bukti}</p><p class="font-heading text-[10px] tracking-[0.12em] text-muted-foreground uppercase">Ada bukti</p></div>
					</div>
					<Button href="/asesor/tinjau/{s.scan_id}"><ClipboardCheck /> Tinjau</Button>
				</li>
			{/each}
		</ul>
	{/if}
{/if}
