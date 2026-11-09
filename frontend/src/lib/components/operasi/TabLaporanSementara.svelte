<script lang="ts">
	// Tab "Laporan Sementara": putusan kelaikan, skor kepatuhan, cakupan, dan skor per fungsi keamanan
	// dari hasil yang sudah masuk. Bersifat sementara selama pengujian berjalan; laporan final
	// tersedia setelah pengujian selesai.
	import { LABEL_PUTUSAN, nilaiKelaikan } from '#lib/catalog.js';
	import type { Scan } from '#lib/types.js';
	import { WARNA_SEVERITY, type BarisMetode } from '#lib/operasi/ringkas.js';
	import FileBarChart from '@lucide/svelte/icons/file-chart-column';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';

	let { scan, temuan }: { scan: Scan; temuan: BarisMetode[] } = $props();

	const n = $derived(nilaiKelaikan(scan.hasil));
	const final = $derived(scan.status === 'selesai');
	const WARNA_PUTUSAN = {
		laik: '#9fe08a',
		laik_bersyarat: '#f5c451',
		tidak_laik: '#ff7b6b'
	} as const;
	const sevTemuan = $derived(
		(['kritis', 'tinggi', 'sedang', 'rendah'] as const).map(
			(s) => [s, temuan.filter((t) => t.severity === s).length] as const
		)
	);
	const fungsiDiuji = $derived(
		n.perFungsi.filter(
			(f) => f.hitungan.lulus + f.hitungan.gagal + f.hitungan.tidak_dapat_diverifikasi > 0
		)
	);
</script>

<div class="h-full overflow-y-auto p-4">
	{#if !final}
		<p
			class="mb-4 flex items-start gap-2 rounded-md border border-[#f5c451]/30 bg-[#f5c451]/5 px-3 py-2 text-xs text-[#f5c451]"
		>
			<TriangleAlert class="mt-0.5 size-3.5 shrink-0" />
			{scan.status === 'dibatalkan'
				? 'Pengujian dihentikan — penilaian di bawah hanya mencakup metode yang sempat dijalankan.'
				: 'Penilaian sementara dari hasil yang sudah masuk; dapat berubah sampai pengujian selesai.'}
		</p>
	{/if}

	<div class="grid gap-3 md:grid-cols-3">
		<div class="rounded-lg border border-white/10 bg-black/20 p-4">
			<p class="text-[11px] tracking-wider text-white/50 uppercase">
				Putusan {final ? '' : 'sementara'}
			</p>
			<p class="mt-1 text-2xl font-semibold" style="color:{WARNA_PUTUSAN[n.putusan]}">
				{LABEL_PUTUSAN[n.putusan]}
			</p>
			{#each n.alasan as a, i (i)}<p class="mt-1 text-xs text-white/55">{a}</p>{/each}
		</div>
		<div class="rounded-lg border border-white/10 bg-black/20 p-4">
			<p class="text-[11px] tracking-wider text-white/50 uppercase">Skor kepatuhan</p>
			<p class="mt-1 text-2xl font-semibold text-white tabular-nums">{n.skor}%</p>
			<div class="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
				<div class="h-full rounded-full bg-[#9fe08a]" style:width="{n.skor}%"></div>
			</div>
			<p class="mt-2 text-xs text-white/55">Kontrol lulus dari kontrol yang teruji.</p>
		</div>
		<div class="rounded-lg border border-white/10 bg-black/20 p-4">
			<p class="text-[11px] tracking-wider text-white/50 uppercase">Cakupan pengujian</p>
			<p class="mt-1 text-2xl font-semibold text-white tabular-nums">{n.cakupan}%</p>
			<p class="mt-2 text-xs text-white/55">
				Lulus <span class="text-[#9fe08a]">{n.hitungan.lulus}</span> · Gagal
				<span class="text-[#ff7b6b]">{n.hitungan.gagal}</span>
				· Belum terverifikasi
				<span class="text-[#f5c451]">{n.hitungan.tidak_dapat_diverifikasi}</span>
				· Tidak berlaku {n.hitungan.tidak_berlaku}
			</p>
		</div>
	</div>

	<div class="mt-3 grid gap-3 lg:grid-cols-[2fr_1fr]">
		<div class="rounded-lg border border-white/10 bg-black/20 p-4">
			<p class="mb-3 text-[11px] tracking-wider text-white/50 uppercase">
				Skor per fungsi keamanan
			</p>
			{#each fungsiDiuji as f (f.fungsi.id)}
				<div class="mb-2.5 grid grid-cols-[minmax(0,1fr)_3rem] items-center gap-3">
					<div class="min-w-0">
						<p class="truncate text-[13px] text-white/85">
							<span class="font-mono text-[11px] text-[#5bc8af]">{f.fungsi.id}</span>
							{f.fungsi.nama}
						</p>
						<div class="mt-1 h-1.5 overflow-hidden rounded-full bg-white/10">
							<div
								class="h-full rounded-full {f.skor === null
									? ''
									: f.skor >= 100
										? 'bg-[#9fe08a]'
										: f.skor >= 70
											? 'bg-[#f5c451]'
											: 'bg-[#ff7b6b]'}"
								style:width="{f.skor ?? 0}%"
							></div>
						</div>
					</div>
					<p class="text-right text-sm text-white/80 tabular-nums">
						{f.skor === null ? '—' : `${f.skor}%`}
					</p>
				</div>
			{:else}
				<p class="text-sm text-white/40">Belum ada fungsi keamanan yang teruji.</p>
			{/each}
		</div>
		<div class="rounded-lg border border-white/10 bg-black/20 p-4">
			<p class="mb-3 text-[11px] tracking-wider text-white/50 uppercase">Sebaran temuan</p>
			{#each sevTemuan as [s, jml] (s)}
				<div class="mb-2 flex items-center gap-3">
					<span class="w-14 text-xs font-semibold uppercase" style="color:{WARNA_SEVERITY[s]}"
						>{s}</span
					>
					<div class="h-2 flex-1 overflow-hidden rounded-full bg-white/10">
						<div
							class="h-full rounded-full"
							style:width="{temuan.length ? (jml / temuan.length) * 100 : 0}%"
							style:background={WARNA_SEVERITY[s]}
						></div>
					</div>
					<span class="w-6 text-right text-sm text-white/80 tabular-nums">{jml}</span>
				</div>
			{/each}
			{#if final}
				<a
					href="/laporan/{scan.id}"
					class="mt-4 inline-flex items-center gap-1.5 text-sm text-[#9fe08a] hover:underline"
				>
					<FileBarChart class="size-4" /> Buka laporan lengkap
				</a>
			{/if}
		</div>
	</div>
</div>
