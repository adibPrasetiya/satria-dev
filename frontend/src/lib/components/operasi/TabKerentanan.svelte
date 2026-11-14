<script lang="ts">
	// Tab "Kerentanan (CVE)": CVE terbaru yang cocok dengan komponen & versi aplikasi ini (indikatif,
	// dari intel NVD/KEV/EPSS/OSV — bukan hasil metode uji). Data bersifat terkini per aplikasi, bukan
	// potret saat pengujian berjalan; komponen hasil recon pengujian ini ikut memperbaruinya.
	import type { RingkasanKerentanan } from '#lib/types.js';
	import DaftarKerentanan from '#lib/components/kerentanan/DaftarKerentanan.svelte';
	import Flame from '@lucide/svelte/icons/flame';
	import ExternalLink from '@lucide/svelte/icons/external-link';

	let {
		aplikasiId,
		onringkasan
	}: { aplikasiId: string; onringkasan?: (r: RingkasanKerentanan) => void } = $props();

	let ringkasan = $state<RingkasanKerentanan | null>(null);

	const STAT = $derived([
		{ label: 'Dieksploitasi aktif', nilai: ringkasan?.kev, warna: '#e5484d' },
		{ label: 'Terdampak', nilai: ringkasan?.terdampak, warna: '#ff7b6b' },
		{ label: 'Kemungkinan', nilai: ringkasan?.kemungkinan, warna: '#f5a524' },
		{ label: 'Ditangani', nilai: ringkasan?.ditangani, warna: '#4ade80' }
	]);
</script>

<div class="h-full overflow-y-auto p-4">
	<div class="mb-3 flex flex-wrap items-start justify-between gap-2">
		<p class="max-w-2xl text-xs text-white/55">
			<Flame class="mr-1 inline size-3.5 text-[#ff7b6b]" />
			CVE yang cocok dengan komponen & versi aplikasi ini (formulir, koreksi manual, dan fingerprint recon).
			Bersifat <span class="text-white/80">indikatif</span> — tidak memengaruhi putusan kelaikan pengujian.
		</p>
		<a href="/aplikasi/{aplikasiId}/komponen" class="inline-flex items-center gap-1 text-xs text-[#4ade80] hover:underline">
			Kelola komponen <ExternalLink class="size-3" />
		</a>
	</div>

	<div class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
		{#each STAT as s (s.label)}
			<div class="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
				<p class="text-[11px] tracking-wider uppercase" style="color:{s.warna}">{s.label}</p>
				<p class="text-2xl font-semibold text-white tabular-nums">{s.nilai ?? '—'}</p>
			</div>
		{/each}
	</div>

	<DaftarKerentanan
		{aplikasiId}
		tampilAplikasi={false}
		onringkasan={(r) => {
			ringkasan = r;
			onringkasan?.(r);
		}}
	/>
</div>
