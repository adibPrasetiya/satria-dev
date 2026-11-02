<script lang="ts">
	// Daftar metode yang menunggu bukti dokumen/asesor; pemilik aplikasi mengunggah bukti di sini.
	import { api } from '#lib/api/client.js';
	import { indeksMetode } from '#lib/catalog.js';
	import { tanggal } from '#lib/format.js';
	import type { Scan } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import StatusBadge from './StatusBadge.svelte';
	import Kosong from './Kosong.svelte';
	import { toast } from 'svelte-sonner';
	import Upload from '@lucide/svelte/icons/upload';
	import FileText from '@lucide/svelte/icons/file-text';

	let { scan = $bindable(), bisaUnggah }: { scan: Scan; bisaUnggah: boolean } = $props();

	const item = $derived(
		Object.values(scan.hasil)
			.filter((h) => h.menunggu_tinjauan || h.tinjauan)
			.map((h) => ({ h, m: indeksMetode.get(h.metode_id)! }))
			.filter((x) => x.m)
	);

	let mengunggah = $state<string | null>(null);

	async function unggah(metodeId: string, e: Event & { currentTarget: HTMLInputElement }) {
		const file = e.currentTarget.files?.[0];
		if (!file) return;
		mengunggah = metodeId;
		try {
			scan = await api.unggahBukti(scan.id, metodeId, {
				jenis: file.type.startsWith('image/') ? 'screenshot' : 'dokumen',
				judul: file.name.replace(/\.[^.]+$/, ''),
				nama_file: file.name
			});
			toast.success('Bukti diunggah, menunggu tinjauan asesor');
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			mengunggah = null;
			e.currentTarget.value = '';
		}
	}
</script>

{#if item.length === 0}
	<Kosong judul="Tidak ada metode yang menunggu bukti" />
{:else}
	<ul class="divide-y rounded-lg border bg-card">
		{#each item as { h, m } (h.metode_id)}
			<li class="grid gap-3 p-4 md:grid-cols-[1fr_auto] md:items-start">
				<div class="min-w-0">
					<div class="flex flex-wrap items-center gap-2">
						<span class="font-mono text-[11px] text-muted-foreground">{m.metode.id}</span>
						<StatusBadge status={h.status} />
						{#if h.menunggu_tinjauan && h.bukti.some((b) => b.jenis !== 'request_response')}
							<span class="text-[11px] text-gold">● Bukti terkirim, menunggu asesor</span>
						{/if}
					</div>
					<p class="mt-1 font-medium">{m.metode.nama}</p>
					<p class="text-xs text-muted-foreground">
						{m.kontrol.nomor_referensi} {m.kontrol.uraian} — <i>{m.metode.kriteria_lulus}</i>
					</p>
					{#if h.bukti.filter((b) => b.jenis !== 'request_response').length}
						<ul class="mt-2 flex flex-wrap gap-2">
							{#each h.bukti.filter((b) => b.jenis !== 'request_response') as b, i (i)}
								<li class="inline-flex items-center gap-1.5 rounded border bg-muted/50 px-2 py-1 text-xs">
									<FileText class="size-3.5 text-muted-foreground" />{b.nama_file}
									<span class="text-muted-foreground">· {tanggal(b.waktu)}</span>
								</li>
							{/each}
						</ul>
					{/if}
					{#if h.tinjauan}
						<p class="mt-2 border-l-2 border-gold pl-2 text-xs">
							<b>{h.tinjauan.asesor}:</b> {h.tinjauan.catatan}
						</p>
					{/if}
				</div>
				{#if bisaUnggah && h.menunggu_tinjauan}
					<label>
						<input type="file" class="sr-only" onchange={(e) => unggah(h.metode_id, e)} disabled={!!mengunggah} />
						<Button variant="outline" size="sm" class="pointer-events-none" disabled={!!mengunggah}>
							<Upload /> {mengunggah === h.metode_id ? 'Mengunggah…' : 'Unggah bukti'}
						</Button>
					</label>
				{/if}
			</li>
		{/each}
	</ul>
{/if}
