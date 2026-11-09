<script lang="ts">
	// Tab "Temuan": metode uji yang GAGAL, dikelompokkan per severity (kritis → rendah).
	import { WARNA_SEVERITY, type BarisMetode } from '#lib/operasi/ringkas.js';
	import { cn } from '#lib/utils.js';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';

	let {
		temuan,
		berjalan,
		onrinci
	}: { temuan: BarisMetode[]; berjalan: boolean; onrinci?: (id: string) => void } = $props();

	const SEV = ['kritis', 'tinggi', 'sedang', 'rendah'] as const;
	const per = $derived(SEV.map((s) => ({ s, daftar: temuan.filter((t) => t.severity === s) })));
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
			<div class="grid gap-2 xl:grid-cols-2">
				{#each daftar as t (t.id)}
					<button
						type="button"
						onclick={() => onrinci?.(t.id)}
						class={cn(
							'rounded-lg border bg-black/20 p-3 text-left transition hover:bg-white/[0.03]'
						)}
						style="border-color:color-mix(in oklab,{WARNA_SEVERITY[s]} 35%,transparent)"
					>
						<p class="flex items-center gap-2">
							<span class="font-mono text-[11.5px] text-[#5bc8af]">{t.id}</span>
							<span class="text-[11px] text-white/40"
								>{t.fungsi}{t.namaFungsi ? ` · ${t.namaFungsi}` : ''}</span
							>
						</p>
						<p class="mt-1 text-[13.5px] font-medium text-white/90">{t.nama}</p>
						{#if t.ringkasan}<p class="mt-1 text-[13px] text-white/60">{t.ringkasan}</p>{/if}
					</button>
				{/each}
			</div>
		{/if}
	{/each}
</div>
