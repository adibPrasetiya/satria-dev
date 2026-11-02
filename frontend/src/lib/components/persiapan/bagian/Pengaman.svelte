<script lang="ts">
	import type { PersiapanAuth } from '#lib/types.js';
	import { Switch } from '#lib/components/ui/switch/index.js';

	let { p = $bindable() }: { p: PersiapanAuth } = $props();

	const IP_WORKER_CONTOH = ['10.20.30.41', '10.20.30.42'];
	const HAMBATAN = [
		{ k: 'captcha', l: 'CAPTCHA', d: 'centang "saya bukan robot" atau teka-teki gambar' },
		{ k: 'mfa', l: 'Kode OTP', d: 'kode tambahan saat login' },
		{ k: 'waf', l: 'Firewall / pembatas akses', d: 'memblokir akses otomatis berulang' }
	] as const;
</script>

<div class="grid gap-3 sm:grid-cols-3">
	{#each HAMBATAN as h (h.k)}
		<label class="flex items-start justify-between gap-3 rounded-md border p-3">
			<span><span class="block text-sm font-medium">{h.l}</span><span class="text-xs text-muted-foreground">{h.d}</span></span>
			<Switch bind:checked={p.hambatan[h.k]} />
		</label>
	{/each}
</div>
{#if p.hambatan.captcha || p.hambatan.mfa || p.hambatan.waf}
	<div class="grid gap-3 rounded-md border bg-muted/30 p-4">
		<label class="flex items-start justify-between gap-3">
			<span>
				<span class="block text-sm font-medium">Alamat IP mesin uji sudah diizinkan</span>
				<span class="text-xs text-muted-foreground">Tanpa ini, pengujian otomatis yang terkait tidak dapat dijalankan.</span>
			</span>
			<Switch bind:checked={p.hambatan.dikecualikan_untuk_worker} />
		</label>
		<p class="text-xs text-muted-foreground">
			Alamat IP mesin uji yang perlu diizinkan:
			{#each IP_WORKER_CONTOH as ip (ip)}<code class="mx-0.5 rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">{ip}</code>{/each}
			<span class="ml-1 rounded-sm border border-dashed px-1 text-[10px]">data contoh</span>
		</p>
	</div>
{/if}
