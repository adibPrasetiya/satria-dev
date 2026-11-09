<script lang="ts">
	// Daftar metode uji (semua fungsi, atau satu fungsi bila `fungsi` diisi) dikelompokkan per kontrol,
	// dengan status dari worker, pencarian, filter status, dan penanda metode yang sedang disorot.
	// Klik baris → sorot metode & tampilkan ringkasannya pada panggung uji.
	import { semuaMetode, LABEL_STATUS } from '#lib/catalog.js';
	import type { HasilMetode } from '#lib/types.js';
	import { cn } from '#lib/utils.js';
	import Eye from '@lucide/svelte/icons/eye';
	import Loader from '@lucide/svelte/icons/loader-circle';
	import Search from '@lucide/svelte/icons/search';
	import Funnel from '@lucide/svelte/icons/funnel';
	import ListChecks from '@lucide/svelte/icons/list-checks';

	let {
		fungsi,
		hasil,
		aktif,
		onpilih
	}: { fungsi?: string; hasil: Record<string, HasilMetode>; aktif: string | null; onpilih: (id: string) => void } = $props();

	const WARNA: Record<string, string> = {
		lulus: '#9fe08a',
		gagal: '#ff7b6b',
		tidak_dapat_diverifikasi: '#f5c451',
		tidak_berlaku: '#8c9bab',
		luar_cakupan: '#6b7785',
		antre: 'rgba(255,255,255,0.3)',
		berjalan: '#7fe9d8'
	};
	const FILTER = [
		['semua', 'Semua'],
		['gagal', 'Failed'],
		['lulus', 'Pass'],
		['luar_cakupan', 'Out of Scope'],
		['tidak_dapat_diverifikasi', 'Perlu tinjauan'],
		['berjalan', 'Berjalan / antre']
	] as const;

	let cari = $state('');
	let filter = $state<(typeof FILTER)[number][0]>('semua');
	let bukaFilter = $state(false);
	const q = $derived(cari.trim().toLowerCase());
	const statusOf = (id: string) => hasil[id]?.status ?? 'antre';
	const cocokFilter = (st: string) =>
		filter === 'semua' || (filter === 'berjalan' ? st === 'berjalan' || st === 'antre' : st === filter);

	// Semua metode yang ikut pengujian ini (punya hasil) — tak semua katalog.
	const ikut = $derived(semuaMetode.filter((ml) => (!fungsi || ml.fungsi.id === fungsi) && !!hasil[ml.metode.id]));
	const grup = $derived.by(() => {
		const per = new Map<string, { id: string; nama: string; metode: typeof semuaMetode }>();
		for (const ml of ikut) {
			if (!cocokFilter(statusOf(ml.metode.id))) continue;
			if (q && ![ml.metode.id, ml.metode.nama, ml.kontrol.id].some((s) => s.toLowerCase().includes(q))) continue;
			const g = per.get(ml.kontrol.id) ?? { id: ml.kontrol.id, nama: ml.kontrol.uraian, metode: [] };
			g.metode.push(ml);
			per.set(ml.kontrol.id, g);
		}
		return [...per.values()];
	});
	const hitung = $derived.by(() => {
		const n = { total: ikut.length, selesai: 0, gagal: 0, lulus: 0, tinjau: 0 };
		for (const ml of ikut) {
			const st = statusOf(ml.metode.id);
			if (st !== 'antre' && st !== 'berjalan') n.selesai++;
			if (st === 'gagal') n.gagal++;
			if (st === 'lulus') n.lulus++;
			if (st === 'tidak_dapat_diverifikasi') n.tinjau++;
		}
		return n;
	});

	let wadah = $state<HTMLDivElement>();
	$effect(() => {
		const id = aktif;
		if (id) queueMicrotask(() => wadah?.querySelector(`[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest' }));
	});
</script>

<div class="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-[#0f1412]">
	<div class="flex items-center gap-2 px-4 pt-3.5 pb-2">
		<ListChecks class="size-5 text-white/80" />
		<span class="shrink-0 text-[15px] font-semibold whitespace-nowrap text-white/90">Daftar Uji</span>
		<div class="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-x-1.5 font-mono text-[10px] whitespace-nowrap text-white/45 tabular-nums">
			<span>Selesai <span class="text-white/80">{hitung.selesai}/{hitung.total}</span></span>
			<span class="text-white/15">|</span>
			<span>Failed <span class="text-[#ff7b6b]">{hitung.gagal}</span></span>
			<span class="text-white/15">|</span>
			<span>Pass <span class="text-[#9fe08a]">{hitung.lulus}</span></span>
		</div>
	</div>
	<div class="relative flex items-center gap-2 px-3 pb-2">
		<label class="flex h-9 flex-1 items-center gap-2 rounded-md border border-white/10 bg-black/30 px-2.5 focus-within:border-[#9fe08a]/50">
			<Search class="size-4 text-white/40" />
			<input bind:value={cari} placeholder="Cari kode atau nama metode…" class="w-full bg-transparent text-[13px] text-white/85 outline-none placeholder:text-white/35" />
		</label>
		<button
			type="button"
			onclick={() => (bukaFilter = !bukaFilter)}
			aria-label="Filter status"
			aria-expanded={bukaFilter}
			class={cn('grid size-9 place-items-center rounded-md border border-white/10 bg-black/30 text-white/70 hover:text-white', filter !== 'semua' && 'border-[#9fe08a]/50 text-[#9fe08a]')}
		>
			<Funnel class="size-4" />
		</button>
		{#if bukaFilter}
			<div class="absolute top-11 right-3 z-20 w-48 rounded-md border border-white/10 bg-[#141a17] p-1 shadow-xl">
				{#each FILTER as [k, l] (k)}
					<button
						type="button"
						onclick={() => ((filter = k), (bukaFilter = false))}
						class={cn('block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-white/5', filter === k ? 'text-[#9fe08a]' : 'text-white/75')}
					>{l}</button>
				{/each}
			</div>
		{/if}
	</div>
	<div bind:this={wadah} class="min-h-0 flex-1 overflow-y-auto border-t border-white/5 text-[12px]">
		{#if !grup.length}
			<p class="px-3 py-6 text-center text-white/35">
				{q || filter !== 'semua' ? 'Tidak ada metode yang cocok.' : 'Belum ada metode uji pada pengujian ini.'}
			</p>
		{/if}
		{#each grup as g (g.id)}
			<p class="sticky top-0 z-[1] truncate border-b border-white/5 bg-[#131916] px-3 py-1.5 text-[11px] text-white/65" title={g.nama}>
				<span class="font-mono text-[#7fe9d8]">{g.id}</span> · {g.nama}
			</p>
			{#each g.metode as ml (ml.metode.id)}
				{@const st = statusOf(ml.metode.id)}
				<button
					type="button"
					data-id={ml.metode.id}
					onclick={() => onpilih(ml.metode.id)}
					title="Lihat ringkasan metode"
					class="flex w-full items-center gap-2 py-1.5 pr-3 pl-4 text-left transition hover:bg-white/5 {aktif === ml.metode.id ? 'bg-[#9fe08a]/10 outline outline-1 -outline-offset-1 outline-[#9fe08a]/40' : ''}"
				>
					{#if aktif === ml.metode.id}
						<Eye class="size-3.5 shrink-0 text-[#9fe08a]" />
					{:else if st === 'berjalan'}
						<Loader class="size-3.5 shrink-0 animate-spin text-[#7fe9d8]" />
					{:else}
						<span class="size-2 shrink-0 rounded-full" style="background:{WARNA[st] ?? WARNA.antre}"></span>
					{/if}
					<span class="w-24 shrink-0 font-mono text-[11px] text-white/50">{ml.metode.id}</span>
					<span class="min-w-0 flex-1 truncate text-white/85" title={ml.metode.nama}>{ml.metode.nama}</span>
					<span class="shrink-0 text-[10px]" style="color:{WARNA[st] ?? WARNA.antre}">{LABEL_STATUS[st as keyof typeof LABEL_STATUS] ?? st}</span>
				</button>
			{/each}
		{/each}
	</div>
</div>
