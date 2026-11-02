<script lang="ts">
	import { api } from '#lib/api/client.js';
	import { indeksMetode } from '#lib/catalog.js';
	import { tanggal } from '#lib/format.js';
	import type { Scan } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import SeverityBadge from './SeverityBadge.svelte';
	import { toast } from 'svelte-sonner';
	import Bot from '@lucide/svelte/icons/bot';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import EyeOff from '@lucide/svelte/icons/eye-off';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	let { scan = $bindable(), bisaBuat = true }: { scan: Scan; bisaBuat?: boolean } = $props();
	let memuat = $state(false);

	async function buat() {
		memuat = true;
		try {
			scan = await api.analisisAi(scan.id);
			toast.success('Analisis AI diperbarui');
		} catch (e) {
			toast.error((e as Error).message);
		} finally {
			memuat = false;
		}
	}

	// Render tebal sederhana **teks** tanpa HTML mentah dari luar.
	function bagian(teks: string) {
		return teks.split(/(\*\*[^*]+\*\*)/g).map((s) => ({ tebal: s.startsWith('**'), teks: s.replaceAll('**', '') }));
	}
</script>

<div class="grid gap-4">
	<div class="sudut-taktis rounded-lg border bg-card p-5">
		<div class="flex flex-wrap items-center gap-2">
			<span class="grid size-8 place-items-center bg-olive-dark text-gold"><Bot class="size-4" /></span>
			<div class="flex-1">
				<p class="font-heading text-sm tracking-[0.1em] uppercase">Ringkasan Eksekutif</p>
				{#if scan.ai}
					<p class="text-[11px] text-muted-foreground">Model {scan.ai.model} · {tanggal(scan.ai.dibuat_pada)}</p>
				{/if}
			</div>
			{#if scan.ai?.disamarkan}
				<span class="inline-flex items-center gap-1 rounded border border-success/40 bg-success/10 px-2 py-0.5 text-[11px] text-success">
					<EyeOff class="size-3" /> Data disamarkan sebelum dikirim
				</span>
			{/if}
			{#if bisaBuat}
				<Button variant="outline" size="sm" onclick={buat} disabled={memuat} class="no-print">
					{#if memuat}<LoaderCircle class="animate-spin" /> Menganalisis…{:else}<Sparkles /> {scan.ai ? 'Analisis ulang' : 'Buat analisis'}{/if}
				</Button>
			{/if}
		</div>
		{#if scan.ai}
			<div class="mt-4 grid gap-3 text-sm leading-relaxed">
				{#each scan.ai.ringkasan_eksekutif.split('\n\n') as par, i (i)}
					<p>
						{#each bagian(par) as s, j (j)}{#if s.tebal}<b>{s.teks}</b>{:else}{s.teks}{/if}{/each}
					</p>
				{/each}
			</div>
			<p class="mt-4 border-t pt-3 text-[11px] text-muted-foreground italic">
				Dihasilkan AI sebagai alat bantu. Status lulus/gagal ditentukan oleh hasil pengujian dan putusan asesor, bukan oleh AI.
			</p>
		{:else}
			<p class="mt-4 text-sm text-muted-foreground">Belum ada analisis AI untuk pengujian ini.</p>
		{/if}
	</div>

	{#if scan.ai?.rekomendasi.length}
		<p class="label-stensil">Rekomendasi Perbaikan ({scan.ai.rekomendasi.length})</p>
		<ol class="grid gap-3">
			{#each scan.ai.rekomendasi as r, i (r.metode_id)}
				{@const m = indeksMetode.get(r.metode_id)}
				<li class="rounded-lg border bg-card p-4">
					<div class="flex flex-wrap items-center gap-2">
						<span class="grid size-6 place-items-center bg-gold font-heading text-xs font-bold text-gold-foreground">{i + 1}</span>
						<span class="flex-1 font-medium">{r.judul}</span>
						{#if m}<SeverityBadge severity={m.metode.severity} />{/if}
					</div>
					<p class="mt-2 text-sm text-muted-foreground">{r.penjelasan}</p>
					<ul class="mt-2 grid gap-1 text-sm">
						{#each r.langkah as l, j (j)}
							<li class="flex gap-2"><span class="text-gold">▸</span>{l}</li>
						{/each}
					</ul>
				</li>
			{/each}
		</ol>
	{/if}
</div>
