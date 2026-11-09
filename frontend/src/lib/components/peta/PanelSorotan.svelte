<script lang="ts">
	// Sorotan provinsi bergilir otomatis: indeks ketahanan & kerentanan yang terdeteksi. Berhenti saat
	// disorot kursor/fokus keyboard; klik provinsi di peta untuk langsung menyorotnya. Provinsi aktif ikut disorot di peta (`kode`).
	import { untrack } from 'svelte';
	import { fade } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { Tween } from 'svelte/motion';
	import type { RingkasProvinsi } from '#lib/peta/agregat.js';
	import { storePeta } from '#lib/peta/store.svelte.js';
	import BatangSeveritas from './BatangSeveritas.svelte';
	import { statusIndeks, warnaIndeks as warna } from '#lib/peta/warna.js';

	let {
		daftar,
		kode = $bindable(null),
		durasiMs = 8000
	}: {
		/** Urutan sorotan (umumnya dari paling rawan). */
		daftar: RingkasProvinsi[];
		/** Kode provinsi yang sedang disorot. */
		kode?: string | null;
		durasiMs?: number;
	} = $props();

	let indeks = $state(0);
	let putaran = $state(0);
	let disorot = $state(false);
	const berhenti = $derived(disorot);
	const aktif = $derived(daftar.length ? daftar[indeks % daftar.length] : null);

	// `kode` diubah dari luar (klik provinsi di peta) atau data diperbarui (siklus 10 menit): lompat ke /
	// pertahankan provinsi itu. Hanya melacak `kode` & `daftar` — bukan `indeks`, agar tidak membalik
	// perpindahan giliran yang baru saja terjadi.
	$effect(() => {
		const k = kode;
		const d = daftar;
		untrack(() => {
			const i = d.findIndex((p) => p.kode === k);
			if (i >= 0 && i !== indeks) {
				indeks = i;
				putaran += 1;
			} else if (i < 0 && indeks >= d.length) indeks = 0;
		});
	});
	$effect(() => {
		kode = aktif?.kode ?? null;
	});

	function ke(langkah: number) {
		if (!daftar.length) return;
		indeks = (indeks + langkah + daftar.length) % daftar.length;
		putaran += 1;
	}

	// Pewaktu giliran: dimulai ulang setiap pindah provinsi (`putaran`); berhenti selama kartu disorot.
	$effect(() => {
		void putaran;
		void indeks;
		if (berhenti || daftar.length < 2) return;
		const t = setTimeout(() => ke(1), durasiMs);
		return () => clearTimeout(t);
	});

	// Angka indeks berhitung dari nilai sebelumnya ke nilai provinsi baru.
	// Rincian provinsi aktif diambil sekali per versi data (lihat storePeta).
	$effect(() => {
		if (aktif) void storePeta.muatRincian(aktif.kode);
	});
	const r = $derived(aktif ? storePeta.rincian(aktif.kode) : undefined);
	const totalTemuan = $derived(
		r ? r.sebaran.kritis + r.sebaran.tinggi + r.sebaran.sedang + r.sebaran.rendah : 0
	);

	const angka = new Tween(0, { duration: 600, easing: cubicOut });
	$effect(() => {
		if (aktif) angka.target = aktif.indeks;
	});

	// Donat indeks (r=38 pada viewBox 96).
	const R = 38;
	const KELILING = 2 * Math.PI * R;
</script>

{#if aktif}
	<section
		class="panel relative w-full overflow-hidden rounded-lg text-white"
		aria-label="Sorotan provinsi"
		aria-live="polite"
		onpointerenter={() => (disorot = true)}
		onpointerleave={() => (disorot = false)}
		onfocusin={() => (disorot = true)}
		onfocusout={() => (disorot = false)}
	>
		<!-- minmax(0,1fr) + min-w-0: lebar kolom terkunci ke kartu sehingga teks panjang terpotong "…", bukan melebarkan kartu. -->
		<div class="grid grid-cols-[minmax(0,1fr)]">
			{#key aktif.kode}
				<div
					class="min-w-0 px-4 pt-4 pb-3 [grid-area:1/1]"
					in:fade={{ duration: 260, delay: 90 }}
					out:fade={{ duration: 90 }}
				>
					<div class="flex items-start justify-between gap-3">
						<div class="min-w-0">
							<h2 class="font-sans text-base leading-tight font-semibold tracking-normal">
								{aktif.nama}
							</h2>
							<p class="mt-0.5 text-xs text-white/45">
								{aktif.satuan} satuan · {aktif.aplikasi} sistem informasi
							</p>
						</div>
						<!-- Level kerawanan: badge berlatar warna level, mudah terlihat. -->
						<span
							class="shrink-0 rounded px-2 py-1 text-[11px] leading-none font-semibold tracking-wider uppercase"
							style="color: {warna(aktif.indeks)}; background: {warna(
								aktif.indeks,
								0.14
							)}; box-shadow: inset 0 0 0 1px {warna(aktif.indeks, 0.4)}"
						>
							{statusIndeks(aktif.indeks)}
						</span>
					</div>

					<!-- Indeks ketahanan: donat 0–100, warna mengikuti skala indeks -->
					<div class="mt-4 flex items-center gap-4">
						<svg
							viewBox="0 0 96 96"
							class="size-24 shrink-0 -rotate-90"
							role="img"
							aria-label="Indeks ketahanan {aktif.indeks.toFixed(1)} dari 100"
						>
							<circle
								cx="48"
								cy="48"
								r={R}
								fill="none"
								stroke="rgb(255 255 255 / 0.08)"
								stroke-width="9"
							/>
							<circle
								cx="48"
								cy="48"
								r={R}
								fill="none"
								stroke={warna(aktif.indeks)}
								stroke-width="9"
								stroke-linecap="round"
								stroke-dasharray="{(angka.current / 100) * KELILING} {KELILING}"
							/>
							<g class="[transform-origin:48px_48px] rotate-90">
								<text
									x="48"
									y="46"
									text-anchor="middle"
									dominant-baseline="central"
									fill={warna(aktif.indeks)}
									font-size="21"
									font-weight="700">{angka.current.toFixed(1)}</text
								>
								<text
									x="48"
									y="64"
									text-anchor="middle"
									fill="rgb(255 255 255 / 0.4)"
									font-size="9.5">/ 100</text
								>
							</g>
						</svg>
						<div class="min-w-0">
							<p class="text-xs text-white/50">Indeks ketahanan</p>
							<p class="mt-1 text-sm font-semibold" style="color: {warna(aktif.indeks)}">
								{statusIndeks(aktif.indeks)}
							</p>
							<p class="mt-1 text-[11px] leading-snug text-white/40">
								Rata-rata tertimbang skor kepatuhan sistem informasi di provinsi ini.
							</p>
						</div>
					</div>

					<!-- Sebaran severity temuan provinsi (rincian diambil per provinsi, tersimpan per versi data) -->
					<div class="mt-5 mb-2.5 flex items-baseline justify-between">
						<p class="text-xs text-white/50">Sebaran kerentanan</p>
						<p class="text-xs text-white/50 tabular-nums">{r ? `${totalTemuan} temuan` : ''}</p>
					</div>
					{#if !r}
						<div class="space-y-2" aria-label="Memuat rincian provinsi">
							{#each [0, 1, 2, 3] as i (i)}
								<div class="h-2 animate-pulse rounded-full bg-white/[0.07]"></div>
							{/each}
						</div>
					{:else if totalTemuan}
						<BatangSeveritas sebaran={r.sebaran} />
					{:else}
						<p class="text-[13px] text-white/50">Tidak ada kerentanan terdeteksi.</p>
					{/if}
				</div>
			{/key}
		</div>
	</section>
{/if}

<style>
	.panel {
		background: rgb(12 15 13 / 0.86);
		border: 1px solid rgb(255 255 255 / 0.08);
		backdrop-filter: blur(10px);
	}
</style>
