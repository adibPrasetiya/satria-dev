<script lang="ts">
	// Visualisasi fase penemuan: graf entitas (selalu terlihat penuh) + bilah status "processing"
	// ringkas per tahap. Tiap tahap tampil minimal sebentar agar tahap yang cepat tetap terbaca; saat
	// halaman dibuka belakangan (replay), langsung ke tahap terakhir. Seleksi node dibagi dengan
	// daftar aset di halaman (`bind:terpilih`).
	import type { Graf, NodeGraf } from '#lib/penemuan/graf.js';
	import type { KodeTahap } from '#lib/penemuan/peristiwa.js';
	import { svgEntitas, WARNA_RISIKO, type JenisIkon } from '#lib/penemuan/ikon-entitas.js';
	import GrafPenemuan from './GrafPenemuan.svelte';
	import AdeganTahap from './AdeganTahap.svelte';
	import PanelDetail from './PanelDetail.svelte';
	import { cn } from '#lib/utils.js';

	let {
		graf,
		berjalan,
		host,
		terpilih = $bindable(null),
		tepi = { atas: 0, kanan: 0 },
		polos = false
	}: {
		graf: Graf;
		berjalan: boolean;
		host: string;
		terpilih?: string | null;
		tepi?: { atas: number; kanan: number; bawah?: number };
		/** Dipasang di kartu induk yang punya toolbar sendiri: tanpa bingkai, HUD judul, & tombol zoom bawaan. */
		polos?: boolean;
	} = $props();

	// Kendali tampilan untuk toolbar induk.
	let grafEl = $state<ReturnType<typeof GrafPenemuan>>();
	export const perbesar = () => grafEl?.zoom(1.25);
	export const perkecil = () => grafEl?.zoom(0.8);
	export const paskan = () => grafEl?.pas();
	export const pusatkan = () => grafEl?.pusatkan();
	export function aturUlang() {
		terpilih = null;
		grafEl?.pas();
	}

	const MIN_MS: Partial<Record<KodeTahap, number>> = { situs: 1600, recon: 2000 };
	const MIN_DEFAULT = 1200;

	let tampil = $state(-1);
	let mulaiTampil = 0;
	let awal = true;
	$effect(() => {
		const n = graf.tahap.length;
		if (!n) return;
		// Replay: penemuan sudah selesai, peristiwa lama (>15 dtk) atau scan tak berjalan → langsung ke tahap terakhir.
		if (awal) {
			awal = false;
			const terakhir = graf.tahap[n - 1];
			if (!berjalan || graf.selesai || Date.now() - new Date(terakhir.waktu).getTime() > 15_000) {
				tampil = n - 1;
				mulaiTampil = 0;
				return;
			}
			tampil = 0;
			mulaiTampil = performance.now();
		}
	});
	$effect(() => {
		const t = setInterval(() => {
			const n = graf.tahap.length;
			if (tampil < 0 || tampil >= n - 1) return;
			const kini = graf.tahap[tampil].tahap;
			if (performance.now() - mulaiTampil >= (MIN_MS[kini] ?? MIN_DEFAULT)) {
				tampil += 1;
				mulaiTampil = performance.now();
			}
		}, 200);
		return () => clearInterval(t);
	});

	const tahapKini = $derived(tampil >= 0 ? graf.tahap[tampil] : null);
	const riwayat = $derived(graf.tahap.slice(0, tampil + 1).map((t) => t.tahap));
	const jalurRecon = $derived(graf.tahap.find((t) => t.tahap === 'recon')?.jalur ?? []);
	const docs = $derived(graf.nodes.find((n) => n.jenis === 'docs')?.info?.url as string | undefined);

	const nodeTerpilih = $derived<NodeGraf | null>(terpilih ? graf.nodes.find((n) => n.id === terpilih) ?? null : null);

	const LEGENDA: [JenisIkon, string][] = [
		['frontend', 'Frontend'],
		['halaman', 'URL'],
		['js', 'JS'],
		['backend', 'Backend'],
		['endpoint', 'Endpoint'],
		['upload', 'Upload']
	];
</script>

<div class={cn('relative h-full w-full overflow-hidden bg-[#0c1014]', !(tepi.atas > 0) && !polos && 'sudut-taktis rounded-lg border border-[#9fe08a]/20')}>
	<div class="absolute inset-0">
		<GrafPenemuan bind:this={grafEl} {graf} {berjalan} {terpilih} {tepi} kontrol={!polos} onpilih={(id) => (terpilih = id)} />
	</div>

	<!-- HUD atas -->
	<div
		class:hidden={polos} class="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-3 p-4" style:top="{tepi.atas}px" style:right="{tepi.kanan}px">
		<div class="min-w-0">
			<p class="flex items-center gap-1.5 font-heading text-[11px] tracking-[0.25em] text-[#9fe08a] uppercase">
				{#if berjalan && !graf.selesai}<span class="size-1.5 animate-pulse rounded-full bg-[#9fe08a] shadow-[0_0_6px_#9fe08a]"></span>{/if}
				{graf.selesai ? 'Recon and Discovery · peta permukaan serangan' : 'Recon and Discovery'}
			</p>
			<p class="mt-0.5 truncate font-mono text-[10px] text-white/40">TARGET // {host}</p>
		</div>
		{#if graf.terautentikasi !== null}
			<span class="rounded-sm border px-1.5 py-px font-heading text-[10px] tracking-wide uppercase {graf.terautentikasi ? 'border-[#9fe08a]/50 text-[#9fe08a]' : 'border-[#f5c451]/50 text-[#f5c451]'}">
				{graf.terautentikasi ? 'Terautentikasi' : 'Anonim'}
			</span>
		{/if}
	</div>

	<AdeganTahap tahap={tahapKini?.tahap ?? (berjalan ? 'situs' : null)} pesan={tahapKini?.pesan} jalur={jalurRecon} docs={docs ?? null} {riwayat} {tepi} />

	<!-- Legenda entitas & tautan -->
	<div style:max-width="calc(100% - {tepi.kanan}px - 4rem)" style:bottom="{(tepi.bawah ?? 0) + 12}px" class="pointer-events-none absolute left-3 z-10 flex flex-wrap items-center gap-x-3 gap-y-1 rounded border border-white/5 bg-[#0c1014]/85 px-2 py-1 font-mono text-[9px] text-white/55">
		{#each LEGENDA as [j, l] (j)}
			<span class="inline-flex items-center gap-1"><span class="inline-block size-3.5">{@html svgEntitas(j, { ukuran: 14 })}</span>{l}</span>
		{/each}
		<span class="inline-flex items-center gap-1"><span class="h-px w-4 bg-[#9fe08a]"></span>temuan</span>
		<span class="inline-flex items-center gap-1"><span class="h-px w-4 border-t border-dashed border-white/50"></span>sumber</span>
		<span class="inline-flex items-center gap-1"><span class="h-px w-4 bg-[#ff7b6b]"></span>alert</span>
		<span class="inline-flex items-center gap-1"><span class="size-0 border-x-[4px] border-b-[7px] border-x-transparent" style="border-bottom-color:{WARNA_RISIKO.High}"></span>risiko</span>
	</div>

	{#if nodeTerpilih}
		<PanelDetail node={nodeTerpilih} {graf} onpilih={(id) => (terpilih = id)} ontutup={() => (terpilih = null)} {tepi} />
	{/if}
</div>
