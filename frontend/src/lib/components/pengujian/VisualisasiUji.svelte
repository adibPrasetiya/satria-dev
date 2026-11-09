<script lang="ts">
	// Panggung fase pengujian: satu adegan UMUM untuk semua metode uji (siapkan → kirim → respons →
	// evaluasi), diputar berulang (loop) dengan tempo tetap. Data uji nyata dari
	// worker ditumpangkan sebagai HUD tipis: metode yang sedang dijalankan, progres, dan kartu
	// verdict saat sebuah metode selesai. Klik baris di Daftar Uji → sorot & tampilkan ringkasannya.
	import { onMount, untrack } from 'svelte';
	import type { MetodeUji, Uji } from '#lib/pengujian/uji.js';
	import { posisi, totalDurasi, type Babak } from '#lib/pengujian/timeline.js';
	import AdeganUmum, { babak } from './AdeganUmum.svelte';
	import type { RequestUji } from '#lib/pengujian/peristiwa.js';
	import { cn } from '#lib/utils.js';

	let {
		uji,
		berjalan,
		host,
		polos = false,
		dipilih = $bindable(null),
		aktif = $bindable(null),
		tepi = { atas: 0, kanan: 0 },
		judul = 'Operasi uji'
	}: {
		uji: Uji;
		berjalan: boolean;
		host: string;
		/** Tanpa bingkai sendiri (dipasang di dalam kartu induk). */
		polos?: boolean;
		/** Metode yang dipilih di Daftar Uji (disorot & ringkasannya ditampilkan). */
		dipilih?: string | null;
		/** Metode yang sedang disorot (untuk auto-scroll Daftar Uji). */
		aktif?: string | null;
		tepi?: { atas: number; kanan: number; bawah?: number };
		judul?: string;
	} = $props();

	// --- timeline berulang ---
	let jam = $state(0); // ms sejak mulai
	let reduced = $state(false);
	const pos = $derived(reduced ? bingkaiKunci(babak) : posisi(babak, jam));
	const babakKini = $derived(babak[pos.i]);

	// Bingkai statis untuk prefers-reduced-motion: babak "langsung ke API" (inti cerita), tengah.
	function bingkaiKunci(b: Babak[]) {
		const i = Math.max(0, b.findIndex((x) => x.id === 'kirim'));
		return { i, p: 0.6 };
	}

	onMount(() => {
		reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
		if (reduced) return;
		const mulai = performance.now();
		let raf = 0;
		const loop = (now: number) => {
			raf = requestAnimationFrame(loop);
			jam = (now - mulai) % totalDurasi(babak);
		};
		raf = requestAnimationFrame(loop);
		return () => cancelAnimationFrame(raf);
	});

	// --- data uji nyata (HUD) ---
	const daftar = $derived(uji.daftar);
	const metodeDipilih = $derived<MetodeUji | null>(dipilih ? daftar.find((m) => m.id === dipilih) ?? null : null);
	const metodeJalan = $derived<MetodeUji | null>(
		daftar.findLast((m) => m.status === null) ?? (daftar.length ? daftar[daftar.length - 1] : null)
	);
	const fokus = $derived(metodeDipilih ?? metodeJalan);
	const totalN = $derived(daftar.length);
	const selesaiN = $derived(daftar.filter((m) => m.status !== null).length);
	// Request nyata terakhir metode yang difokuskan → ditampilkan pada paket adegan.
	const reqFokus = $derived.by<RequestUji | null>(() => {
		const k = fokus?.ketukan.findLast((x) => x.tipe === 'request');
		return k && k.tipe === 'request' ? k.req : null;
	});

	$effect(() => {
		aktif = (metodeDipilih ?? metodeJalan)?.id ?? null;
	});

	// Kartu verdict: muncul ±4,2 dtk tiap kali sebuah metode baru selesai (saat scan berjalan).
	const selesaiTerakhir = $derived<MetodeUji | null>(daftar.findLast((m) => m.status !== null) ?? null);
	const kunciSelesai = $derived(selesaiTerakhir ? `${selesaiTerakhir.id}:${selesaiTerakhir.status}` : '');
	let kartuVerdict = $state<MetodeUji | null>(null);
	let timerVerdict: ReturnType<typeof setTimeout>;
	$effect(() => {
		if (!kunciSelesai) return; // lacak kunci (string stabil per metode+status)
		untrack(() => {
			if (!berjalan) return;
			kartuVerdict = selesaiTerakhir;
			clearTimeout(timerVerdict);
			timerVerdict = setTimeout(() => (kartuVerdict = null), 4200);
		});
		return () => clearTimeout(timerVerdict);
	});

	const WARNA_VERDICT: Record<string, [string, string]> = {
		lulus: ['#9fe08a', 'LULUS'],
		gagal: ['#ff7b6b', 'GAGAL'],
		tidak_dapat_diverifikasi: ['#f5c451', 'PERLU TINJAUAN'],
		tidak_berlaku: ['#8c9bab', 'TIDAK BERLAKU']
	};
</script>

<div class={cn('panggung-uji kisi relative h-full w-full overflow-hidden bg-[#0c1014]', !(tepi.atas > 0) && !polos && 'sudut-taktis rounded-lg border border-[#9fe08a]/20')}>
	<!-- HUD atas -->
	<div class="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-3 p-4" style:top="{tepi.atas}px" style:right="{tepi.kanan}px">
		<div class="min-w-0">
			<p class="flex items-center gap-1.5 font-heading text-[11px] tracking-[0.25em] text-[#9fe08a] uppercase">
				{#if berjalan}<span class="size-1.5 animate-pulse rounded-full bg-[#9fe08a] shadow-[0_0_6px_#9fe08a]"></span>{/if}
				{judul}
			</p>
			{#if fokus}
				<p class="mt-0.5 truncate font-mono text-[11px] text-white/80"><span class="text-[#7fe9d8]">{fokus.id}</span> — {fokus.judul}</p>
			{:else}
				<p class="mt-0.5 truncate font-mono text-[11px] text-white/45">{berjalan ? 'Menunggu worker…' : 'Belum ada rekaman uji'}</p>
			{/if}
			<p class="truncate font-mono text-[10px] text-white/35">TARGET // {host}</p>
		</div>
		<div class="flex shrink-0 flex-col items-end gap-1">
			{#if totalN > 0}
				<span class="rounded-sm border border-[#7fe9d8]/30 bg-[#7fe9d8]/10 px-1.5 py-px font-mono text-[10px] text-[#7fe9d8]">{selesaiN}/{totalN} metode</span>
			{/if}
			<p class="font-heading text-[10px] tracking-[0.18em] text-[#7fe9d8] uppercase">{babakKini.label}</p>
			<div class="flex gap-1" aria-hidden="true">
				{#each babak as b, k (b.id)}
					<span class="h-1 rounded-full {k === pos.i ? 'w-3 bg-[#7fe9d8]' : k < pos.i ? 'w-1.5 bg-[#9fe08a]/70' : 'w-1.5 bg-white/15'}"></span>
				{/each}
			</div>
		</div>
	</div>

	<svg
		viewBox="90 120 820 270"
		style:top="{tepi.atas + 64}px"
		style:width="calc(100% - {tepi.kanan}px)"
		style:height="calc(100% - {tepi.atas + 64 + (tepi.bawah ?? 0)}px - 48px)"
		class="absolute left-0"
		preserveAspectRatio="xMidYMid meet"
		role="img"
		aria-label="Adegan {judul}: {babakKini.teks}"
	>

		<AdeganUmum i={pos.i} p={pos.p} req={reqFokus} {host} />
	</svg>

	<!-- bilah bawah: verdict (prioritas) / ringkasan metode dipilih / keterangan babak -->
	<div style:right="{tepi.kanan}px" style:bottom="{(tepi.bawah ?? 0) + 12}px" class="pointer-events-none absolute left-0 z-20 flex justify-center px-4">
		{#if kartuVerdict && kartuVerdict.status}
			{@const [c, label] = WARNA_VERDICT[kartuVerdict.status] ?? ['#8c9bab', kartuVerdict.status.toUpperCase()]}
			<div class="kartu-masuk flex max-w-[92%] items-center gap-3 rounded-md border bg-[#0c1014]/95 px-4 py-2" style="border-color:{c}">
				<p class="shrink-0 font-stencil text-xl tracking-[0.2em]" style="color:{c}">{label}</p>
				<p class="min-w-0 text-xs text-white/75"><span class="font-mono text-[#7fe9d8]">{kartuVerdict.id}</span> · {kartuVerdict.ringkasan || kartuVerdict.judul}</p>
			</div>
		{:else if metodeDipilih}
			{@const st = metodeDipilih.status}
			{@const [c, label] = (st && WARNA_VERDICT[st]) ?? ['#8c9bab', st ? st.toUpperCase() : 'BERJALAN']}
			<div class="kartu-masuk flex max-w-[92%] items-center gap-3 rounded-md border bg-[#0c1014]/95 px-4 py-2" style="border-color:{c}">
				<p class="shrink-0 font-stencil text-sm tracking-[0.15em]" style="color:{c}">{label}</p>
				<p class="min-w-0 text-xs text-white/75"><span class="font-mono text-[#7fe9d8]">{metodeDipilih.id}</span> · {metodeDipilih.ringkasan || metodeDipilih.judul}</p>
			</div>
		{:else}
			<p class="max-w-[90%] truncate rounded border border-white/10 bg-[#0c1014]/90 px-3 py-1.5 font-mono text-[11px] text-white/85">{babakKini.teks}</p>
		{/if}
	</div>
</div>

<style>
	/* Kisi latar memenuhi seluruh kanvas (bukan hanya area viewBox adegan). */
	.kisi {
		background-image: linear-gradient(rgba(255,255,255,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.07) 1px, transparent 1px),
			linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px);
		background-size: 120px 120px, 120px 120px, 24px 24px, 24px 24px;
	}
	/* Gaya teks SVG dipakai oleh adegan anak (AdeganUmum, NodeSatya, NodeBackend) via :global. */
	.panggung-uji :global(.lbl-simpul) { font: 600 15px ui-sans-serif, system-ui, sans-serif; fill: rgba(236, 240, 245, 0.95); text-anchor: middle; }
	.panggung-uji :global(.lbl-sub) { font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; fill: rgba(160, 174, 192, 0.85); text-anchor: middle; }
	.panggung-uji :global(.lbl-kanal) { font: 600 12px ui-monospace, SFMono-Regular, Menlo, monospace; paint-order: stroke; stroke: #0c1014; stroke-width: 4px; }
	.panggung-uji :global(.lbl-kecil) { font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; }
	.panggung-uji :global(.lbl-chip) { font: 600 10.5px ui-monospace, SFMono-Regular, Menlo, monospace; text-anchor: middle; }
	.panggung-uji :global(.lbl-paket) { font: 600 11px ui-monospace, SFMono-Regular, Menlo, monospace; text-anchor: middle; }
	.panggung-uji :global(.lbl-badge) { font: 700 9.5px ui-monospace, SFMono-Regular, Menlo, monospace; text-anchor: middle; letter-spacing: 0.04em; }
	.panggung-uji :global(.lbl-win-judul) { font: 600 10px ui-monospace, SFMono-Regular, Menlo, monospace; }
	.panggung-uji :global(.lbl-term) { font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; }
	.panggung-uji :global(.lbl-form) { font: 600 11px ui-sans-serif, system-ui, sans-serif; fill: #5a6b86; }
	.panggung-uji :global(.lbl-isi-form) { font: 700 16px ui-sans-serif, system-ui, sans-serif; fill: #3a4a66; }
	.panggung-uji :global(.lbl-form-mono) { font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; }
	.panggung-uji :global(.lbl-tombol) { font: 600 13px ui-sans-serif, system-ui, sans-serif; fill: #fff; text-anchor: middle; }
	.panggung-uji :global(.lbl-url-browser) { font: 10px ui-monospace, SFMono-Regular, Menlo, monospace; fill: #7a8aa0; }
	.panggung-uji :global(.muncul) { animation: muncul 0.4s ease-out both; }
	@keyframes muncul { from { opacity: 0; } }
	.kartu-masuk { animation: kartu 0.35s ease-out both; }
	@keyframes kartu { from { opacity: 0; transform: translateY(6px); } }
	.panggung-uji :global(.denyut-svg) { animation: denyut 1.2s ease-out infinite; transform-box: fill-box; transform-origin: center; }
	@keyframes denyut { from { opacity: 0.8; transform: scale(0.85); } to { opacity: 0; transform: scale(1.3); } }
	@media (prefers-reduced-motion: reduce) {
		.panggung-uji :global(.muncul), .kartu-masuk, .panggung-uji :global(.denyut-svg) { animation: none; }
	}
</style>
