<script lang="ts">
	import { api, USE_MOCK } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import PetaIndonesia from '#lib/components/peta/PetaIndonesia.svelte';
	import { indeksTertimbang, ringkasProvinsi } from '#lib/peta/agregat.js';
	import type { DataPeta } from '#lib/peta/tipe.js';

	// Dasbor = peta Indeks Ketahanan Keamanan Siber satu layar, dari GET /dashboard/peta
	// (mode demo: data contoh). Dimuat ulang tiap 10 menit, sesuai siklus pembaruan data.
	const MUAT_ULANG_MS = 10 * 60_000;

	let data = $state<DataPeta | null>(null);
	let galat = $state<string | null>(null);

	async function muat() {
		try {
			data = await api.getPeta();
			galat = null;
		} catch (e) {
			// Data lama tetap ditampilkan bila pemuatan ulang gagal.
			galat = (e as Error).message;
		}
	}
	$effect(() => {
		void muat();
		const t = setInterval(muat, MUAT_ULANG_MS);
		return () => clearInterval(t);
	});

	const ringkasan = $derived(data ? ringkasProvinsi(data.titik) : []);
	const nasional = $derived(data ? indeksTertimbang(data.titik) : null);
</script>

<svelte:head><title>Dasbor — SATRIA</title></svelte:head>

<!-- Peta satu layar: mengisi tinggi di bawah bilah atas (dan banner mode latihan bila tampil). -->
<section
	class={[
		'min-h-[420px] w-full',
		USE_MOCK ? 'h-[calc(100svh-4rem-1.8rem)]' : 'h-[calc(100svh-4rem)]'
	]}
	aria-label="Peta indeks ketahanan keamanan siber"
>
	<PetaIndonesia
		titik={data?.titik ?? []}
		kotama={data?.kotama ?? []}
		provinsi={ringkasan}
		{nasional}
	>
		{#snippet kosong()}
			{#if !data && !galat}
				<p class="text-sm text-white/60">Memuat peta…</p>
			{:else if !data}
				<p class="text-sm font-medium">Peta belum dapat dimuat</p>
				<p class="mt-1 text-xs text-white/55">{galat}</p>
				<button
					type="button"
					class="pointer-events-auto mt-3 rounded-md border border-white/15 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10"
					onclick={muat}>Coba lagi</button
				>
			{:else}
				{@const r = data.ringkasan}
				<p class="text-sm font-medium">Belum ada data ketahanan di peta</p>
				<p class="mt-1 max-w-sm text-xs leading-relaxed text-white/55">
					{#if r.aplikasi_belum_terpetakan}
						{r.aplikasi_belum_terpetakan} sistem informasi sudah diuji, tetapi satuan pemiliknya belum
						memiliki lokasi.
						{auth.punya('admin')
							? 'Lengkapi provinsi & koordinat satuan tersebut (atau induknya).'
							: 'Hubungi administrator untuk melengkapi lokasi satuan.'}
					{:else}
						Peta terisi setelah sistem informasi milik satuan berlokasi selesai diuji.
					{/if}
				</p>
				{#if r.aplikasi_belum_terpetakan && auth.punya('admin')}
					<a
						href="/admin/satuan"
						class="pointer-events-auto mt-3 inline-block rounded-md border border-white/15 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10"
						>Buka Satuan Kerja</a
					>
				{/if}
			{/if}
		{/snippet}
	</PetaIndonesia>
</section>
