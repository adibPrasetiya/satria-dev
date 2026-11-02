<script lang="ts">
	// Pohon fungsi → kontrol → metode dengan status hasil.
	import { katalog, statusKontrol, skorFungsi, LABEL_ENGINE, LABEL_JENIS } from '#lib/catalog.js';
	import type { HasilMetode, Status } from '#lib/types.js';
	import * as Accordion from '#lib/components/ui/accordion/index.js';
	import StatusBadge from './StatusBadge.svelte';
	import SeverityBadge from './SeverityBadge.svelte';
	import BuktiView from './BuktiView.svelte';
	import { cn } from '#lib/utils.js';

	let {
		hasil,
		filter = 'semua'
	}: { hasil: Record<string, HasilMetode>; filter?: 'semua' | Status } = $props();

	let terbuka = $state<string[]>([]);

	const data = $derived(
		katalog.fungsi_keamanan.map((f) => ({
			f,
			skor: skorFungsi(f, hasil),
			kontrol: f.kontrol
				.map((k) => ({ k, status: statusKontrol(k, hasil) }))
				.filter((x) => filter === 'semua' || x.status === filter)
		}))
	);
</script>

<Accordion.Root type="multiple" bind:value={terbuka} class="rounded-lg border bg-card">
	{#each data as { f, skor, kontrol } (f.id)}
		<Accordion.Item value={f.id} class="border-b last:border-b-0">
			<Accordion.Trigger class="px-4 hover:no-underline">
				<div class="flex flex-1 items-center gap-3 text-left">
					<span class="grid size-8 shrink-0 place-items-center bg-olive-dark font-stencil text-sm text-gold">{f.nomor}</span>
					<span class="flex-1">
						<span class="block font-heading text-sm tracking-[0.06em] uppercase">{f.nama}</span>
						<span class="text-xs text-muted-foreground">
							{skor.hitungan.lulus} lulus · {skor.hitungan.gagal} gagal · {skor.hitungan.tidak_dapat_diverifikasi} ditinjau · {skor.hitungan.tidak_berlaku} N/A
						</span>
					</span>
					{#if skor.hitungan.gagal}
						<span class="hidden rounded bg-critical/12 px-1.5 py-0.5 text-xs font-semibold text-critical sm:inline">{skor.hitungan.gagal} gagal</span>
					{/if}
					<span class="w-12 text-right font-heading text-sm tabular-nums">{skor.skor === null ? '—' : `${skor.skor}%`}</span>
				</div>
			</Accordion.Trigger>
			<Accordion.Content class="px-4">
				{#if kontrol.length === 0}
					<p class="pb-2 text-sm text-muted-foreground">Tidak ada kontrol dengan status ini.</p>
				{/if}
				<div class="grid gap-3 pb-2">
					{#each kontrol as { k, status } (k.id)}
						<div class={cn('rounded-md border', status === 'gagal' && 'border-critical/40')}>
							<div class="flex flex-wrap items-start gap-2 border-b bg-muted/40 px-3 py-2">
								<span class="font-mono text-xs font-semibold">{k.nomor_referensi}</span>
								<span class="min-w-0 flex-1 text-sm">{k.uraian}</span>
								<SeverityBadge severity={k.severity_default} />
								<StatusBadge {status} />
							</div>
							<ul class="divide-y">
								{#each k.metode_pengujian as m (m.id)}
									{@const h = hasil[m.id]}
									<li class="px-3 py-2.5">
										<div class="flex flex-wrap items-center gap-2">
											<StatusBadge status={h?.status ?? 'antre'} />
											<span class="text-sm font-medium">{m.nama}</span>
											<span class="ml-auto font-heading text-[10px] tracking-[0.1em] text-muted-foreground uppercase">
												{LABEL_JENIS[m.jenis]} · {LABEL_ENGINE[m.engine]}{m.profil === 'intrusif' ? ' · intrusif' : ''}
											</span>
										</div>
										<p class="mt-1 text-xs text-muted-foreground"><b>Kriteria:</b> {m.kriteria_lulus}</p>
										{#if h?.ringkasan}
											<p class={cn('mt-1 text-sm', h.status === 'gagal' && 'text-critical')}>{h.ringkasan}</p>
										{/if}
										{#if h?.tinjauan}
											<p class="mt-1 border-l-2 border-gold pl-2 text-xs">Asesor {h.tinjauan.asesor}: {h.tinjauan.catatan}</p>
										{/if}
										{#if h?.bukti.length}<BuktiView bukti={h.bukti} />{/if}
									</li>
								{/each}
							</ul>
						</div>
					{/each}
				</div>
			</Accordion.Content>
		</Accordion.Item>
	{/each}
</Accordion.Root>
