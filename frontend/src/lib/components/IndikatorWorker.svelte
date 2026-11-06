<script lang="ts">
	// Indikator status worker pengujian di bilah atas: aktif/sibuk/tak ada worker, plus rincian
	// worker & antrean pada panel tarik-turun. Data dari store yang dipoll (lihat stores/worker).
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.js';
	import { storeWorker, teksPerkiraan } from '#lib/stores/worker.svelte.js';
	import { cn } from '#lib/utils.js';
	import Server from '@lucide/svelte/icons/server';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';

	/** ciut = sidebar diciutkan: hanya titik status (rincian tetap di panel tarik-turun). */
	let { ciut = false }: { ciut?: boolean } = $props();

	let buka = $state(false);
	$effect(() => storeWorker.pakai());

	const s = $derived(storeWorker.status);
	const keadaan = $derived<'memuat' | 'galat' | 'mati' | 'sibuk' | 'siaga'>(
		storeWorker.galat ? 'galat' : !s ? 'memuat' : s.aktif === 0 ? 'mati' : s.siaga === 0 ? 'sibuk' : 'siaga'
	);
	const WARNA = { memuat: 'bg-muted-foreground/50', galat: 'bg-[#ff7b6b]', mati: 'bg-[#ff7b6b]', sibuk: 'bg-[#f5c451]', siaga: 'bg-[#9fe08a]' };
	const label = $derived.by(() => {
		if (keadaan === 'memuat') return 'Memeriksa worker…';
		if (keadaan === 'galat') return 'Status worker tak terjangkau';
		if (keadaan === 'mati') return 'Tidak ada worker aktif';
		const sibuk = s!.workers.find((w) => w.status === 'sibuk' && w.sedang);
		if (keadaan === 'sibuk') return `Worker sibuk${sibuk?.sedang?.tahap ? ` · ${sibuk.sedang.tahap}` : ''}`;
		return `${s!.aktif} worker siaga`;
	});
	const antre = $derived(s ? s.antrean.scan.filter((x) => !x.sedang_dikerjakan).length : 0);
	const WARNA_STATUS: Record<string, string> = { siaga: 'text-[#9fe08a]', sibuk: 'text-[#f5c451]', terputus: 'text-[#ff7b6b]', berhenti: 'text-white/40' };
	const umur = (d: number) => (d < 60 ? `${d} dtk lalu` : d < 3600 ? `${Math.round(d / 60)} mnt lalu` : `${Math.round(d / 3600)} jam lalu`);
</script>

<DropdownMenu.Root bind:open={buka}>
	<DropdownMenu.Trigger
		class={cn(
			'flex w-full items-center gap-2.5 rounded-lg border border-border bg-background/60 px-3 py-2.5 text-left transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:outline-none',
			buka && 'bg-muted',
			ciut && 'lg:justify-center lg:px-0'
		)}
		aria-label="Status worker pengujian: {label}"
		title={ciut ? label : undefined}
	>
		<span class="relative flex size-2.5 shrink-0">
			{#if keadaan === 'sibuk' || keadaan === 'siaga'}<span class={cn('absolute inline-flex size-full animate-ping rounded-full opacity-60', WARNA[keadaan])}></span>{/if}
			<span class={cn('relative inline-flex size-2.5 rounded-full', WARNA[keadaan])}></span>
		</span>
		<span class={cn('min-w-0 flex-1 leading-tight', ciut && 'lg:hidden')}>
			<span class="block text-[11px] text-muted-foreground">Worker pengujian</span>
			<span class="block truncate text-xs font-semibold text-foreground">{label}</span>
		</span>
		{#if antre > 0}<span class={cn('rounded-md bg-warning/15 px-1.5 py-0.5 text-[10px] font-semibold text-warning-foreground dark:text-warning', ciut && 'lg:hidden')} title="Pengujian mengantre">{antre} antre</span>{/if}
		<ChevronDown class={cn('size-3.5 shrink-0 text-muted-foreground transition-transform', buka && 'rotate-180', ciut && 'lg:hidden')} />
	</DropdownMenu.Trigger>

	<DropdownMenu.Content side="right" align="end" sideOffset={12} class="w-96 rounded-none border-gold/35 bg-[#10150e] p-0 text-white shadow-[0_24px_60px_rgb(0_0_0/0.6)]">
		<div class="flex items-center gap-2 border-b border-gold/30 bg-black/40 px-4 py-2.5">
			<Server class="size-4 text-gold" />
			<p class="font-heading text-[11px] tracking-[0.18em] text-gold uppercase">Worker pengujian</p>
			<span class="ml-auto font-mono text-[10px] text-white/45">diperbarui tiap 10 dtk</span>
		</div>

		{#if keadaan === 'galat'}
			<p class="px-4 py-3 text-xs text-[#ff7b6b]">Backend tidak menjawab permintaan status worker.</p>
		{:else if s}
			<div class="max-h-72 space-y-2 overflow-y-auto px-4 py-3 text-xs">
				{#if !s.workers.length}
					<p class="text-white/55">Belum ada worker yang pernah terhubung. Jalankan <code class="rounded bg-white/10 px-1">python -m satya_worker.main</code> di folder <code class="rounded bg-white/10 px-1">worker</code>.</p>
				{/if}
				{#each s.workers as w (w.id)}
					<div class="rounded-sm border border-white/10 bg-black/30 p-2">
						<p class="flex items-center gap-2">
							<span class="font-mono text-white/90">{w.id}</span>
							<span class={cn('font-heading text-[10px] tracking-wider uppercase', WARNA_STATUS[w.status])}>{w.status}</span>
							<span class="ml-auto text-[10px] text-white/40">{umur(w.terakhir_terlihat_detik)}</span>
						</p>
						{#if w.sedang}
							<p class="mt-1 truncate text-white/70">
								{#if w.sedang.scan_id}<a href="/scan/{w.sedang.scan_id}" class="text-[#7fe9d8] hover:underline">Scan #{w.sedang.scan_id}</a>{/if}
								· {w.sedang.aplikasi} · <span class="font-mono">{w.sedang.tahap ?? '—'}</span>
							</p>
						{/if}
						<p class="mt-1 font-mono text-[10px] text-white/35">engine: {w.engines.join(', ') || '—'}{w.versi ? ` · ${w.versi}` : ''}</p>
					</div>
				{/each}
			</div>
			<div class="border-t border-white/10 px-4 py-2.5 text-xs">
				<p class="font-heading text-[10px] tracking-[0.18em] text-white/45 uppercase">Antrean</p>
				{#if s.antrean.scan.length}
					<ul class="mt-1 space-y-0.5">
						{#each s.antrean.scan as a (a.scan_id)}
							<li class="flex items-center gap-2">
								<span class="w-16 shrink-0 font-mono text-[10px] {a.sedang_dikerjakan ? 'text-[#f5c451]' : 'text-white/45'}">{a.sedang_dikerjakan ? 'berjalan' : `ke-${a.posisi}`}</span>
								<a href="/scan/{a.scan_id}" class="min-w-0 flex-1 truncate text-white/80 hover:underline">{a.aplikasi}</a>
								{#if !a.sedang_dikerjakan}<span class="text-[10px] text-white/45">{teksPerkiraan(a.perkiraan_tunggu_detik)}</span>{/if}
							</li>
						{/each}
					</ul>
				{:else}
					<p class="mt-1 text-white/50">Kosong — pengujian baru akan langsung dikerjakan.</p>
				{/if}
			</div>
		{/if}
	</DropdownMenu.Content>
</DropdownMenu.Root>
