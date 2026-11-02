<script lang="ts">
	// Panel ringkas kesiapan tiap metode suatu fungsi keamanan, dihitung langsung dari isian persiapan.
	import type { Fungsi, KesiapanMetode, Metode, StatusKesiapan } from '#lib/types.js';
	import { cn } from '#lib/utils.js';

	let { fungsi, kesiapan }: { fungsi: Fungsi; kesiapan: (m: Metode) => KesiapanMetode } = $props();

	const aktif = (x: { aktif?: boolean }) => x.aktif !== false;
	const kelompok = $derived(
		fungsi.kontrol.filter(aktif).map((k) => ({
			k,
			metode: k.metode_pengujian.filter(aktif).map((m) => ({ m, s: kesiapan(m) }))
		}))
	);
	const hitung = $derived(
		kelompok
			.flatMap((g) => g.metode)
			.reduce((n, { s }) => ({ ...n, [s.status]: n[s.status] + 1 }), { siap: 0, perlu_data: 0, dilewati: 0, asesor: 0 } as Record<StatusKesiapan, number>)
	);

	const GAYA: Record<StatusKesiapan, { label: string; titik: string; teks: string }> = {
		siap: { label: 'Siap', titik: 'bg-success', teks: 'text-success' },
		perlu_data: { label: 'Perlu data', titik: 'bg-warning', teks: 'text-warning-foreground' },
		dilewati: { label: 'Dilewati', titik: 'bg-muted-foreground/60', teks: 'text-muted-foreground' },
		asesor: { label: 'Asesor', titik: 'bg-info', teks: 'text-info' }
	};
	const nomor = (m: Metode) => m.id.replace(/^[A-Z]+-/, '');
</script>

<div class="sudut-taktis flex min-h-0 flex-col rounded-lg border bg-card">
	<div class="border-b p-4">
		<p class="label-stensil text-[10px]">Kesiapan metode</p>
		<div class="mt-3 grid grid-cols-4 gap-1 text-center">
			{#each Object.entries(GAYA) as [kunci, g] (kunci)}
				<div class="rounded-md bg-muted/40 px-1 py-2">
					<p class={cn('font-stencil text-xl leading-none', g.teks)}>{hitung[kunci as StatusKesiapan]}</p>
					<p class="mt-1 text-[10px] text-muted-foreground">{g.label}</p>
				</div>
			{/each}
		</div>
	</div>
	<ol class="min-h-0 flex-1 overflow-x-hidden overflow-y-auto p-2">
		{#each kelompok as { k, metode } (k.id)}
			<li class="px-2 pt-2 pb-1">
				<p class="mb-1 line-clamp-1 text-[11px] font-semibold text-muted-foreground" title={k.uraian}>
					{k.nomor_referensi} · {k.uraian}
				</p>
				<ul class="grid gap-0.5">
					{#each metode as { m, s } (m.id)}
						<li class="flex items-start gap-2 rounded px-1.5 py-1 hover:bg-muted/40" title={`${m.nama} — ${s.alasan}`}>
							<span class={cn('mt-1.5 size-2 shrink-0 rounded-full', GAYA[s.status].titik)}></span>
							<span class="min-w-0 flex-1">
								<span class="flex items-baseline gap-1.5">
									<span class="font-mono text-[11px] text-muted-foreground">{nomor(m)}</span>
									<span class={cn('text-[11px] font-medium', GAYA[s.status].teks)}>{GAYA[s.status].label}</span>
								</span>
								<span class="block truncate text-xs">{m.nama}</span>
								{#if s.status !== 'siap'}<span class="block text-[11px] leading-snug text-muted-foreground">{s.alasan}</span>{/if}
							</span>
						</li>
					{/each}
				</ul>
			</li>
		{/each}
	</ol>
</div>
