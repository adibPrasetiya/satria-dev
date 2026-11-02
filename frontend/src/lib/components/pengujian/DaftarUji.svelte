<script lang="ts">
	// Daftar metode uji satu fungsi keamanan (mis. AUTH) dikelompokkan per kontrol, dengan status
	// dari worker dan penanda metode yang sedang disorot. Klik baris → sorot metode & tampilkan
	// ringkasannya pada panggung uji.
	import { semuaMetode, LABEL_STATUS } from '#lib/catalog.js';
	import type { HasilMetode } from '#lib/types.js';
	import { cn } from '#lib/utils.js';
	import Eye from '@lucide/svelte/icons/eye';
	import Loader from '@lucide/svelte/icons/loader-circle';

	let {
		fungsi,
		hasil,
		aktif,
		onpilih,
		mengambang = false
	}: { fungsi: string; hasil: Record<string, HasilMetode>; aktif: string | null; onpilih: (id: string) => void; mengambang?: boolean } = $props();

	const grup = $derived.by(() => {
		const per = new Map<string, { id: string; nama: string; metode: typeof semuaMetode }>();
		for (const ml of semuaMetode) {
			if (ml.fungsi.id !== fungsi) continue;
			// Tampilkan metode yang ikut pengujian ini (punya hasil) — tak semua katalog.
			if (!hasil[ml.metode.id]) continue;
			const g = per.get(ml.kontrol.id) ?? { id: ml.kontrol.id, nama: ml.kontrol.uraian, metode: [] };
			g.metode.push(ml);
			per.set(ml.kontrol.id, g);
		}
		return [...per.values()];
	});

	const WARNA: Record<string, string> = {
		lulus: '#9fe08a',
		gagal: '#ff7b6b',
		tidak_dapat_diverifikasi: '#f5c451',
		tidak_berlaku: '#8c9bab',
		antre: 'rgba(255,255,255,0.3)',
		berjalan: '#7fe9d8'
	};
	const total = $derived(grup.reduce((s, g) => s + g.metode.length, 0));
	const selesai = $derived(grup.reduce((s, g) => s + g.metode.filter((m) => !['antre', 'berjalan'].includes(hasil[m.metode.id]?.status ?? 'antre')).length, 0));

	let wadah = $state<HTMLDivElement>();
	$effect(() => {
		const id = aktif;
		if (id) queueMicrotask(() => wadah?.querySelector(`[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest' }));
	});
</script>

<div class={cn('flex h-full min-h-0 flex-col overflow-hidden', mengambang ? 'rounded-md border border-white/10 bg-[#0c1014]/85 shadow-2xl backdrop-blur-md' : 'sudut-taktis rounded-lg border border-[#9fe08a]/20 bg-[#0c1014]')}>
	<div class="flex items-center gap-2 border-b border-white/10 bg-black/40 px-3 py-1.5">
		<span class="font-heading text-[10px] tracking-[0.2em] text-white/70 uppercase">Daftar uji · {fungsi}</span>
		<span class="ml-auto font-mono text-[10px] text-white/45 tabular-nums">{selesai}/{total} selesai</span>
	</div>
	<div bind:this={wadah} class="min-h-0 flex-1 overflow-y-auto font-mono text-[11px]">
		{#if !grup.length}
			<p class="px-3 py-4 text-center text-white/35">Belum ada metode {fungsi} pada pengujian ini.</p>
		{/if}
		{#each grup as g (g.id)}
			<p class="sticky top-0 z-[1] border-b border-white/5 bg-[#11161c] px-2 py-1 text-white/70"><span class="text-[#7fe9d8]">{g.id}</span> · {g.nama}</p>
			{#each g.metode as ml (ml.metode.id)}
				{@const st = hasil[ml.metode.id]?.status ?? 'antre'}
				<button
					type="button"
					data-id={ml.metode.id}
					onclick={() => onpilih(ml.metode.id)}
					title="Lihat ringkasan metode"
					class="flex w-full items-center gap-2 py-[3px] pr-2 pl-3 text-left transition hover:bg-white/5 {aktif === ml.metode.id ? 'bg-[#4dabf7]/15 outline outline-1 -outline-offset-1 outline-[#4dabf7]/50' : ''}"
				>
					{#if aktif === ml.metode.id}
						<Eye class="size-3 shrink-0 text-[#4dabf7]" />
					{:else if st === 'berjalan'}
						<Loader class="size-3 shrink-0 animate-spin text-[#7fe9d8]" />
					{:else}
						<span class="size-2 shrink-0 rounded-full" style="background:{WARNA[st] ?? WARNA.antre}"></span>
					{/if}
					<span class="w-24 shrink-0 text-white/50">{ml.metode.id}</span>
					<span class="min-w-0 flex-1 truncate text-white/80" title={ml.metode.nama}>{ml.metode.nama}</span>
					<span class="shrink-0 text-[10px]" style="color:{WARNA[st] ?? WARNA.antre}">{LABEL_STATUS[st as keyof typeof LABEL_STATUS] ?? st}</span>
				</button>
			{/each}
		{/each}
	</div>
</div>
