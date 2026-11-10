<script lang="ts">
	// Tab "Detail Analisis": tabel seluruh metode uji pada scan dengan filter fungsi & status.
	// Klik baris → rincian (ringkasan hasil, kriteria lulus, durasi).
	import { LABEL_STATUS } from '#lib/catalog.js';
	import { WARNA_SEVERITY, WARNA_STATUS, type BarisMetode } from '#lib/operasi/ringkas.js';
	import { cn } from '#lib/utils.js';
	import BuktiTemuan from '#lib/components/operasi/BuktiTemuan.svelte';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Loader from '@lucide/svelte/icons/loader-circle';
	import Search from '@lucide/svelte/icons/search';

	let { baris, sorot = $bindable(null) }: { baris: BarisMetode[]; sorot?: string | null } =
		$props();

	let cari = $state('');
	let fFungsi = $state('');
	let fStatus = $state('');
	const fungsi = $derived([
		...new Map(baris.map((b) => [b.fungsi, b.namaFungsi || b.fungsi])).entries()
	]);
	const q = $derived(cari.trim().toLowerCase());
	const tampil = $derived(
		baris.filter(
			(b) =>
				(!fFungsi || b.fungsi === fFungsi) &&
				(!fStatus ||
					(fStatus === 'berjalan'
						? b.status === 'berjalan' || b.status === 'antre'
						: b.status === fStatus)) &&
				(!q || `${b.id} ${b.nama} ${b.ringkasan}`.toLowerCase().includes(q))
		)
	);

	$effect(() => {
		const id = sorot;
		if (id)
			queueMicrotask(() =>
				document
					.querySelector(`[data-metode="${CSS.escape(id)}"]`)
					?.scrollIntoView({ block: 'nearest' })
			);
	});

	const pilihan =
		'h-9 rounded-md border border-white/10 bg-black/30 px-2.5 text-[13px] text-white/85 outline-none focus:border-[#9fe08a]/50';
</script>

<div class="flex h-full min-h-0 flex-col">
	<div class="flex flex-wrap items-center gap-2 border-b border-white/10 p-3">
		<label
			class="flex h-9 min-w-56 flex-1 items-center gap-2 rounded-md border border-white/10 bg-black/30 px-2.5 focus-within:border-[#9fe08a]/50 lg:max-w-sm"
		>
			<Search class="size-4 text-white/40" />
			<input
				bind:value={cari}
				placeholder="Cari kode, nama metode, atau hasil…"
				class="w-full bg-transparent text-[13px] text-white/85 outline-none placeholder:text-white/35"
			/>
		</label>
		<select bind:value={fFungsi} class={pilihan} aria-label="Filter fungsi keamanan">
			<option value="" class="bg-[#141a17]">Semua fungsi</option>
			{#each fungsi as [k, n] (k)}<option value={k} class="bg-[#141a17]">{k} · {n}</option>{/each}
		</select>
		<select bind:value={fStatus} class={pilihan} aria-label="Filter status">
			<option value="" class="bg-[#141a17]">Semua status</option>
			<option value="gagal" class="bg-[#141a17]">Failed</option>
			<option value="lulus" class="bg-[#141a17]">Pass</option>
			<option value="luar_cakupan" class="bg-[#141a17]">Out of Scope</option>
			<option value="tidak_dapat_diverifikasi" class="bg-[#141a17]">Belum terverifikasi</option>
			<option value="tidak_berlaku" class="bg-[#141a17]">Tidak berlaku</option>
			<option value="berjalan" class="bg-[#141a17]">Berjalan / antre</option>
		</select>
		<span class="ml-auto text-xs text-white/45">{tampil.length} dari {baris.length} metode</span>
	</div>

	<div class="min-h-0 flex-1 overflow-auto">
		<table class="w-full min-w-[720px] text-left text-[13px]">
			<thead
				class="sticky top-0 z-[1] bg-[#131916] text-[11px] tracking-wider text-white/50 uppercase"
			>
				<tr>
					<th class="w-8 px-3 py-2"></th>
					<th class="px-3 py-2 font-medium">Kode</th>
					<th class="px-3 py-2 font-medium">Metode</th>
					<th class="px-3 py-2 font-medium">Severity</th>
					<th class="px-3 py-2 font-medium">Status</th>
					<th class="px-3 py-2 text-right font-medium">Durasi</th>
				</tr>
			</thead>
			<tbody>
				{#each tampil as b (b.id)}
					{@const buka = sorot === b.id}
					<tr
						data-metode={b.id}
						class={cn(
							'cursor-pointer border-b border-white/5 hover:bg-white/[0.03]',
							buka && 'bg-[#9fe08a]/[0.06]'
						)}
						onclick={() => (sorot = buka ? null : b.id)}
					>
						<td class="px-3 py-2"
							><ChevronRight
								class={cn('size-4 text-white/40 transition-transform', buka && 'rotate-90')}
							/></td
						>
						<td class="px-3 py-2 font-mono text-[11.5px] whitespace-nowrap text-[#5bc8af]"
							>{b.id}</td
						>
						<td class="max-w-[28rem] px-3 py-2">
							<span class="block truncate text-white/90">{b.nama}</span>
							{#if b.ringkasan && !buka}<span class="block truncate text-xs text-white/45"
									>{b.ringkasan}</span
								>{/if}
						</td>
						<td class="px-3 py-2"
							><span
								class="text-[11px] font-semibold uppercase"
								style="color:{WARNA_SEVERITY[b.severity]}">{b.severity}</span
							></td
						>
						<td class="px-3 py-2 whitespace-nowrap">
							<span
								class="inline-flex items-center gap-1.5 text-xs"
								style="color:{WARNA_STATUS[b.status]}"
							>
								{#if b.status === 'berjalan'}<Loader class="size-3 animate-spin" />{:else}<span
										class="size-2 rounded-full"
										style="background:{WARNA_STATUS[b.status]}"
									></span>{/if}
								{LABEL_STATUS[b.status]}{#if b.menunggu_tinjauan}
									· tinjauan{/if}
							</span>
						</td>
						<td class="px-3 py-2 text-right font-mono text-xs whitespace-nowrap text-white/50">
							{b.durasi_ms !== undefined ? `${(b.durasi_ms / 1000).toFixed(1)} dtk` : '—'}
						</td>
					</tr>
					{#if buka}
						<tr class="border-b border-white/5 bg-[#9fe08a]/[0.04]">
							<td></td>
							<td colspan="5" class="px-3 pt-1 pb-3 text-[13px]">
								<p class="text-[11px] tracking-wider text-white/45 uppercase">Hasil</p>
								<p class="mt-0.5 text-white/85">{b.ringkasan || 'Belum ada ringkasan hasil.'}</p>
								{#if b.kriteria}
									<p class="mt-2 text-[11px] tracking-wider text-white/45 uppercase">
										Kriteria lulus
									</p>
									<p class="mt-0.5 text-white/70">{b.kriteria}</p>
								{/if}
								<p class="mt-2 text-xs text-white/45">
									{b.fungsi}{b.namaFungsi ? ` · ${b.namaFungsi}` : ''} · kontrol {b.kontrol || '—'}
								</p>
								<BuktiTemuan poc={b.poc} detail={b.detail} bukti={b.bukti} />
							</td>
						</tr>
					{/if}
				{:else}
					<tr
						><td colspan="6" class="px-3 py-8 text-center text-white/40"
							>{baris.length
								? 'Tidak ada metode yang cocok.'
								: 'Belum ada metode uji pada pengujian ini.'}</td
						></tr
					>
				{/each}
			</tbody>
		</table>
	</div>
</div>
