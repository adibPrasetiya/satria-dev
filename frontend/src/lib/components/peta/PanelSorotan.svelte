<script lang="ts">
	// Sorotan provinsi bergilir otomatis: indeks ketahanan & kerentanan yang terdeteksi. Berhenti saat
	// disorot kursor/fokus keyboard; klik provinsi di peta untuk langsung menyorotnya. Provinsi aktif ikut disorot di peta (`kode`).
	import { untrack } from 'svelte';
	import { fade } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { Tween } from 'svelte/motion';
	import type { RingkasProvinsi } from '#lib/peta/agregat.js';
	import type { Tingkat } from '#lib/peta/tipe.js';
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
	const angka = new Tween(0, { duration: 600, easing: cubicOut });
	$effect(() => {
		if (aktif) angka.target = aktif.indeks;
	});

	const TINGKAT: Record<Tingkat, { label: string; warna: string }> = {
		kritis: { label: 'Kritis', warna: '#f87171' },
		tinggi: { label: 'Tinggi', warna: '#fb923c' },
		sedang: { label: 'Sedang', warna: '#facc15' },
		rendah: { label: 'Rendah', warna: '#a3a3a3' }
	};
	const MAKS_TAMPIL = 4;
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

					<p class="mt-4 text-xs text-white/50">Indeks ketahanan</p>
					<p
						class="mt-1 text-3xl leading-none font-semibold tracking-tight tabular-nums"
						style="color: {warna(aktif.indeks)}"
					>
						{angka.current.toFixed(1)}<span class="ml-1 text-sm font-normal text-white/35"
							>/ 100</span
						>
					</p>
					<div class="mt-3 h-1 overflow-hidden rounded-full bg-white/[0.08]" aria-hidden="true">
						<div
							class="h-full rounded-full"
							style="width: {angka.current}%; background: {warna(aktif.indeks)}"
						></div>
					</div>

					<div class="mt-5 flex items-baseline justify-between">
						<p class="text-xs text-white/50">Kerentanan terdeteksi</p>
						<p class="text-xs text-white/50 tabular-nums">{aktif.kerentanan.length}</p>
					</div>
					{#if aktif.kerentanan.length}
						<ul class="mt-1.5 divide-y divide-white/[0.06]">
							{#each aktif.kerentanan.slice(0, MAKS_TAMPIL) as k (k.kode)}
								<li class="flex items-center gap-3 py-2 text-[13px]">
									<span
										class="w-11 shrink-0 text-[11px] font-medium"
										style="color: {TINGKAT[k.tingkat].warna}">{TINGKAT[k.tingkat].label}</span
									>
									<span class="min-w-0 flex-1 truncate text-white/85" title={k.nama}>{k.nama}</span>
									<span class="shrink-0 text-xs text-white/40 tabular-nums">{k.aplikasi} SI</span>
								</li>
							{/each}
						</ul>
						{#if aktif.kerentanan.length > MAKS_TAMPIL}
							<p class="pt-1 text-xs text-white/35">
								+{aktif.kerentanan.length - MAKS_TAMPIL} kerentanan lainnya
							</p>
						{/if}
					{:else}
						<p class="mt-2 text-[13px] text-white/50">Tidak ada kerentanan terdeteksi.</p>
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
