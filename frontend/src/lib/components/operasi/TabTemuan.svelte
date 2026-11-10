<script lang="ts">
	// Tab "Temuan": metode uji yang GAGAL, dikelompokkan per severity (kritis → rendah).
	// Tiap temuan bisa diperluas inline untuk melihat langkah PoC & bukti request/response.
	import { WARNA_SEVERITY, type BarisMetode } from '#lib/operasi/ringkas.js';
	import BuktiTemuan from '#lib/components/operasi/BuktiTemuan.svelte';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';

	let { temuan, berjalan }: { temuan: BarisMetode[]; berjalan: boolean } = $props();

	const SEV = ['kritis', 'tinggi', 'sedang', 'rendah'] as const;
	const per = $derived(SEV.map((s) => ({ s, daftar: temuan.filter((t) => t.severity === s) })));
	let terbuka = $state<Record<string, boolean>>({});
</script>

<div class="h-full overflow-y-auto p-4">
	<div class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
		{#each per as { s, daftar } (s)}
			<div class="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
				<p class="text-[11px] tracking-wider uppercase" style="color:{WARNA_SEVERITY[s]}">{s}</p>
				<p class="text-2xl font-semibold text-white tabular-nums">{daftar.length}</p>
			</div>
		{/each}
	</div>

	{#if !temuan.length}
		<div class="grid place-items-center gap-2 py-10 text-center text-white/50">
			<ShieldCheck class="size-8 text-[#9fe08a]" />
			<p class="text-sm">
				{berjalan ? 'Belum ada temuan sejauh ini.' : 'Tidak ada temuan pada pengujian ini.'}
			</p>
		</div>
	{/if}

	{#each per as { s, daftar } (s)}
		{#if daftar.length}
			<p
				class="mt-4 mb-2 text-[11px] font-semibold tracking-wider uppercase"
				style="color:{WARNA_SEVERITY[s]}"
			>
				{s} · {daftar.length}
			</p>
			<div class="grid items-start gap-2 xl:grid-cols-2">
				{#each daftar as t (t.id)}
					{@const buka = terbuka[t.id]}
					<div
						class="rounded-lg border bg-black/20 p-3"
						style="border-color:color-mix(in oklab,{WARNA_SEVERITY[s]} 35%,transparent)"
					>
						<button
							type="button"
							onclick={() => (terbuka[t.id] = !buka)}
							class="w-full text-left"
							aria-expanded={buka}
						>
							<p class="flex items-center gap-2">
								<ChevronRight
									class={`size-4 shrink-0 text-white/40 transition-transform ${buka ? 'rotate-90' : ''}`}
								/>
								<span class="font-mono text-[11.5px] text-[#5bc8af]">{t.id}</span>
								<span class="text-[11px] text-white/40"
									>{t.fungsi}{t.namaFungsi ? ` · ${t.namaFungsi}` : ''}</span
								>
							</p>
							<p class="mt-1 pl-6 text-[13.5px] font-medium text-white/90">{t.nama}</p>
							{#if t.ringkasan}<p class="mt-1 pl-6 text-[13px] text-white/60">{t.ringkasan}</p>{/if}
						</button>
						{#if buka}
							<div class="mt-1 pl-6">
								<BuktiTemuan poc={t.poc} detail={t.detail} bukti={t.bukti} />
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	{/each}
</div>
