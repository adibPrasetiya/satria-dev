<script lang="ts">
	// Intel kerentanan (CVE ↔ aset) di dasbor peta: ringkasan kecocokan aktif + CVE berprioritas tertinggi.
	// Mengikuti provinsi yang sedang disorot (sorotan bergilir / klik di peta), dengan pilihan tampilan nasional.
	// Cakupan mengikuti peran (pemilik: aset satuannya). Hasil di-cache per cakupan selama 10 menit, seirama peta.
	import { api } from '#lib/api/client.js';
	import type { KerentananAset, RingkasanKerentanan } from '#lib/types.js';
	import Flame from '@lucide/svelte/icons/flame';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	let {
		ringkas = false,
		provinsi = null
	}: {
		/** Versi satu baris untuk layar sempit (selalu nasional). */
		ringkas?: boolean;
		/** Provinsi yang sedang disorot di peta. */
		provinsi?: { kode: string; nama: string } | null;
	} = $props();

	const SIKLUS_MS = 10 * 60 * 1000;
	let cakupan = $state<'provinsi' | 'nasional'>('provinsi');
	const kodeAktif = $derived(!ringkas && cakupan === 'provinsi' && provinsi ? provinsi.kode : null);

	let ringkasan = $state<RingkasanKerentanan | null>(null);
	let teratas = $state<KerentananAset[]>([]);
	let galat = $state(false);
	// Sorotan bergilir tiap beberapa detik: hasil per provinsi disimpan agar tak memanggil server tiap giliran.
	const cache = new Map<string, { waktu: number; ringkasan: RingkasanKerentanan; teratas: KerentananAset[] }>();

	async function muat(kode: string | null, paksa = false) {
		const kunci = kode ?? 'nasional';
		const c = cache.get(kunci);
		if (c && !paksa && Date.now() - c.waktu < SIKLUS_MS) {
			({ ringkasan, teratas } = c);
			return;
		}
		try {
			const h = await api.cariKerentanan({ limit: 10, sort: 'prioritas', provinsi: kode ?? undefined });
			const isi = { waktu: Date.now(), ringkasan: h.meta.ringkasan, teratas: h.items.slice(0, MAKS_DAFTAR) };
			cache.set(kunci, isi);
			// Abaikan jawaban yang datang terlambat setelah sorotan pindah.
			if ((kodeAktif ?? 'nasional') !== kunci) return;
			({ ringkasan, teratas } = isi);
			galat = false;
		} catch {
			galat = true;
		}
	}

	$effect(() => {
		void muat(kodeAktif);
	});
	$effect(() => {
		const t = setInterval(() => {
			cache.clear();
			void muat(kodeAktif, true);
		}, SIKLUS_MS);
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
		<div class="mb-1 flex items-center justify-between gap-2">
			<p class="truncate text-[10.5px] font-semibold tracking-[0.2em] text-white/55 uppercase">Intel Kerentanan (CVE)</p>
			<a
				href={kodeAktif ? `/kerentanan?provinsi=${kodeAktif}` : '/kerentanan'}
				class="shrink-0 text-[11px] text-[#4ade80] hover:underline">Lihat semua</a
			>
		</div>
		<div class="mb-2.5 flex items-center justify-between gap-2">
			<p class="min-w-0 truncate text-[13px] font-medium" title={kodeAktif ? provinsi?.nama : 'Seluruh Indonesia'}>
				{kodeAktif ? provinsi?.nama : 'Seluruh Indonesia'}
			</p>
			{#if provinsi}
				<div class="flex shrink-0 rounded-md border border-white/10 p-0.5 text-[10.5px]" role="group" aria-label="Cakupan">
					{#each [['provinsi', 'Provinsi'], ['nasional', 'Nasional']] as [k, l] (k)}
						<button
							type="button"
							aria-pressed={cakupan === k}
							onclick={() => (cakupan = k as typeof cakupan)}
							class={[
								'rounded px-2 py-0.5 transition',
								cakupan === k ? 'bg-white/12 text-white' : 'text-white/50 hover:text-white/80'
							]}>{l}</button
						>
					{/each}
				</div>
			{/if}
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
					<a
						href={kodeAktif ? `/kerentanan?provinsi=${kodeAktif}` : '/kerentanan'}
						class="mt-1 block truncate px-1.5 text-[11.5px] text-white/50 hover:text-white/80"
					>
						… dan {angka(aktif - teratas.length)} kecocokan lainnya
					</a>
				{/if}
			{:else}
				<p class="mt-3 text-[12.5px] text-white/50">
					{kodeAktif
						? 'Tidak ada CVE aktif pada aset di provinsi ini.'
						: 'Belum ada CVE yang cocok dengan komponen aset. Isi teknologi beserta versinya atau jalankan recon.'}
				</p>
			{/if}
			{#if ringkasan.baru7hari}
				<p class="mt-2 truncate text-[11px] text-white/45">{angka(ringkasan.baru7hari)} kecocokan baru dalam 7 hari terakhir.</p>
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
