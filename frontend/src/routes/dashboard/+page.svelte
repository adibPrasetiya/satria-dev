<script lang="ts">
	import { USE_MOCK } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import PetaIndonesia from '#lib/components/peta/PetaIndonesia.svelte';
	import { indeksTertimbang, ringkasProvinsi } from '#lib/peta/agregat.js';
	import { SIKLUS_PEMBARUAN_MS, storePeta } from '#lib/peta/store.svelte.js';

	// Dasbor = peta Indeks Ketahanan Keamanan Siber satu layar, dari GET /dashboard/peta (ringkas;
	// mode demo: data contoh). Data disimpan sementara di frontend (storePeta) & diperbarui tiap 10 menit;
	// rincian provinsi diambil per provinsi saat disorot.
	const data = $derived(storePeta.data);
	const galat = $derived(storePeta.galat);
	const muat = () => storePeta.muat(true);

	$effect(() => {
		void storePeta.muat(); // memakai data tersimpan bila belum lewat 10 menit
		const t = setInterval(() => void storePeta.muat(true), SIKLUS_PEMBARUAN_MS);
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
		sebaranNasional={data?.nasional?.sebaran ?? null}
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
