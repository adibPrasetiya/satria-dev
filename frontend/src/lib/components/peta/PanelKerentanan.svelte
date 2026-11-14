<script lang="ts">
	// Intel kerentanan (CVE ↔ aset) di dasbor peta: ringkasan kecocokan aktif + CVE berprioritas tertinggi.
	// Cakupan mengikuti peran (pemilik: aset satuannya). Diperbarui tiap 10 menit, seirama peta.
	import { api } from '#lib/api/client.js';
	import type { KerentananAset, RingkasanKerentanan } from '#lib/types.js';
	import Flame from '@lucide/svelte/icons/flame';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	let { ringkas = false }: { /** Versi satu baris untuk layar sempit. */ ringkas?: boolean } = $props();

	let ringkasan = $state<RingkasanKerentanan | null>(null);
	let teratas = $state<KerentananAset[]>([]);
	let galat = $state(false);

	async function muat() {
		try {
			const h = await api.cariKerentanan({ limit: 10, sort: 'prioritas' });
			ringkasan = h.meta.ringkasan;
			teratas = h.items.slice(0, MAKS_DAFTAR);
			galat = false;
		} catch {
			galat = true;
		}
	}

	$effect(() => {
		void muat();
		const t = setInterval(muat, 10 * 60 * 1000);
		return () => clearInterval(t);
	});

	const aktif = $derived(ringkasan ? ringkasan.terdampak + ringkasan.kemungkinan : 0);
	// Daftar ringkas agar panel tak memanjang melewati kolom kanan peta; sisanya lewat "… dan N lainnya".
	const MAKS_DAFTAR = 3;
	const angka = (n: number | null | undefined) => (n ?? 0).toLocaleString('id-ID');
	const WARNA_TINGKAT ={ segera: '#e5484d', tinggi: '#ff7b6b', sedang: '#f5a524', rendah: '#8b9a8f' } as const;
</script>

{#if ringkas}
	{#if ringkasan && aktif}
		<a
			href="/kerentanan"
			class="pointer-events-auto inline-flex items-center gap-1.5 rounded-md border border-white/12 bg-black/55 px-2.5 py-1.5 text-xs text-white/85 backdrop-blur hover:bg-white/10"
		>
			<Flame class="size-3.5 text-[#ff7b6b]" />
			{aktif} CVE aktif{ringkasan.kev ? ` · ${ringkasan.kev} KEV` : ''}
			<ChevronRight class="size-3.5 text-white/50" />
		</a>
	{/if}
{:else}
	<section class="panel pointer-events-auto w-full shrink-0 rounded-lg px-4 pt-3.5 pb-3 text-white" aria-label="Intel kerentanan aset">
		<div class="mb-2.5 flex items-center justify-between">
			<p class="text-[10.5px] font-semibold tracking-[0.2em] text-white/55 uppercase">Intel Kerentanan (CVE)</p>
			<a href="/kerentanan" class="text-[11px] text-[#4ade80] hover:underline">Lihat semua</a>
		</div>

		{#if galat && !ringkasan}
			<p class="text-[13px] text-white/50">Data kerentanan belum dapat dimuat.</p>
		{:else if !ringkasan}
			<p class="text-[13px] text-white/50">Memuat…</p>
		{:else}
			<div class="grid grid-cols-3 gap-2">
				{#each [{ l: 'KEV aktif', n: ringkasan.kev, w: '#e5484d' }, { l: 'Terdampak', n: ringkasan.terdampak, w: '#ff7b6b' }, { l: 'Aplikasi', n: ringkasan.aplikasi, w: '#f5a524' }] as s (s.l)}
					<div class="min-w-0 rounded-md border border-white/8 bg-white/[0.03] px-2.5 py-1.5">
						<p class="truncate text-[10px] tracking-wider uppercase" style="color:{s.w}">{s.l}</p>
						<p class="truncate text-xl leading-tight font-semibold tabular-nums" title={angka(s.n)}>{angka(s.n)}</p>
					</div>
				{/each}
			</div>

			{#if teratas.length}
				<ul class="mt-3 grid gap-1.5">
					{#each teratas as k (k.id)}
						{@const komponen = `${k.komponen.nama}${k.komponen.versi ? ` ${k.komponen.versi}` : ''}`}
						<li class="min-w-0">
							<a
								href="/aplikasi/{k.aplikasi.id}/komponen"
								class="flex min-w-0 items-start gap-2 rounded-md px-1.5 py-1 hover:bg-white/[0.06]"
								title="{k.cve.id} — {komponen} · {k.aplikasi.nama}{k.cve.ringkasan ? `\n\n${k.cve.ringkasan}` : ''}"
							>
								<span class="mt-1.5 size-2 shrink-0 rounded-full" style="background:{WARNA_TINGKAT[k.tingkat]}"></span>
								<span class="min-w-0 flex-1">
									<span class="flex min-w-0 items-center gap-1.5 font-mono text-[12.5px] font-semibold">
										<span class="truncate">{k.cve.id}</span>
										{#if k.cve.kev}<Flame class="size-3 shrink-0 text-[#e5484d]" />{/if}
									</span>
									<span class="block truncate text-[11.5px] text-white/55">{komponen} · {k.aplikasi.nama}</span>
								</span>
								<span class="mt-0.5 shrink-0 text-[11px] text-white/45 tabular-nums">{k.prioritas}</span>
							</a>
						</li>
					{/each}
				</ul>
				{#if aktif > teratas.length}
					<a href="/kerentanan" class="mt-1 block truncate px-1.5 text-[11.5px] text-white/50 hover:text-white/80">
						… dan {angka(aktif - teratas.length)} kecocokan lainnya
					</a>
				{/if}
			{:else}
				<p class="mt-3 text-[12.5px] text-white/50">
					Belum ada CVE yang cocok dengan komponen aset. Isi teknologi beserta versinya atau jalankan recon.
				</p>
			{/if}
			{#if ringkasan.baru7hari}
				<p class="mt-2 text-[11px] text-white/45">{ringkasan.baru7hari} kecocokan baru dalam 7 hari terakhir.</p>
			{/if}
		{/if}
	</section>
{/if}

<style>
	.panel {
		background: rgb(12 15 13 / 0.86);
		border: 1px solid rgb(255 255 255 / 0.08);
		backdrop-filter: blur(10px);
	}
</style>
