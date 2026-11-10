<script lang="ts">
	// Banner keterangan saat worker diblokir / target tak terjangkau (peristiwa `terblokir`).
	// Fatal (task dihentikan) = merah; peringatan (hasil mungkin tak lengkap) = kuning.
	import { judulBlokir, type KeteranganBlokir } from '#lib/penemuan/terblokir.js';
	import { cn } from '#lib/utils.js';
	import ShieldBan from '@lucide/svelte/icons/shield-ban';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import Copy from '@lucide/svelte/icons/copy';
	import Check from '@lucide/svelte/icons/check';

	let { info }: { info: KeteranganBlokir } = $props();

	let tersalin = $state(false);
	async function salinIp() {
		if (!info.ip_worker) return;
		try {
			await navigator.clipboard.writeText(info.ip_worker);
			tersalin = true;
			setTimeout(() => (tersalin = false), 1500);
		} catch {
			/* clipboard tak tersedia — abaikan */
		}
	}

	const jam = $derived(
		new Date(info.waktu).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
	);
</script>

<div
	role={info.fatal ? 'alert' : 'status'}
	class={cn(
		'flex gap-3 rounded-xl border px-4 py-3',
		info.fatal ? 'border-[#e5484d]/40 bg-[#e5484d]/[0.08]' : 'border-[#f5c451]/40 bg-[#f5c451]/[0.07]'
	)}
>
	{#if info.fatal}
		<ShieldBan class="mt-0.5 size-5 shrink-0 text-[#f66151]" />
	{:else}
		<TriangleAlert class="mt-0.5 size-5 shrink-0 text-[#f5c451]" />
	{/if}
	<div class="min-w-0 flex-1 space-y-1.5">
		<p class={cn('text-[14px] font-semibold', info.fatal ? 'text-[#ff8a80]' : 'text-[#f5c451]')}>
			{judulBlokir(info)}
		</p>
		<p class="text-[13px] leading-relaxed text-white/80">{info.alasan}</p>
		<p class="text-[13px] leading-relaxed text-white/65">
			<span class="font-medium text-white/80">Saran:</span>
			{info.saran}
		</p>
		<div class="flex flex-wrap items-center gap-x-3 gap-y-1 pt-0.5 font-mono text-[11px] text-white/45">
			{#if info.host}<span>target {info.host}</span>{/if}
			{#if info.status}<span>HTTP {info.status}</span>{/if}
			{#if info.ip_worker}
				<button
					type="button"
					onclick={salinIp}
					class="inline-flex items-center gap-1 rounded border border-white/10 px-1.5 py-px text-white/70 transition hover:border-white/30 hover:text-white"
					title="Salin IP worker untuk diminta di-whitelist"
				>
					IP worker {info.ip_worker}
					{#if tersalin}<Check class="size-3 text-[#4ade80]" />{:else}<Copy class="size-3" />{/if}
				</button>
			{/if}
			<span>terdeteksi {jam}</span>
			{#if info.jumlah > 1}<span>{info.jumlah}× tercatat</span>{/if}
		</div>
	</div>
</div>
