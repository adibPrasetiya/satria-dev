<script lang="ts">
	// Panel bukti & PoC satu metode (halaman operasi, tema gelap): langkah reproduksi, bukti
	// request/response yang tertangkap, screenshot (bila ada), dan detail teknis.
	import type { Bukti } from '#lib/types.js';

	let {
		poc = [],
		detail = '',
		bukti = []
	}: { poc?: string[]; detail?: string; bukti?: Bukti[] } = $props();

	const gambar = $derived(bukti.filter((b) => b.jenis === 'screenshot' && (b.nama_file || b.isi)));
	const teks = $derived(bukti.filter((b) => b.jenis !== 'screenshot' && b.isi));
	let bukaDetail = $state(false);
</script>

{#if poc.length}
	<p class="mt-3 text-[11px] tracking-wider text-white/45 uppercase">Langkah reproduksi (PoC)</p>
	<ol class="mt-1 list-decimal space-y-1 pl-5 text-[13px] text-white/80 marker:text-white/40">
		{#each poc as l, i (i)}<li>{l}</li>{/each}
	</ol>
{/if}

{#if gambar.length}
	<p class="mt-3 text-[11px] tracking-wider text-white/45 uppercase">Tangkapan layar</p>
	<div class="mt-1 flex flex-wrap gap-2">
		{#each gambar as b, i (i)}
			<figure class="max-w-full">
				<a href={b.nama_file || b.isi} target="_blank" rel="noopener">
					<img
						src={b.nama_file || b.isi}
						alt={b.judul}
						class="max-h-64 rounded border border-white/10 bg-black/20 object-contain"
						loading="lazy"
					/>
				</a>
				<figcaption class="mt-0.5 text-[11px] text-white/45">{b.judul}</figcaption>
			</figure>
		{/each}
	</div>
{/if}

{#if teks.length}
	<p class="mt-3 text-[11px] tracking-wider text-white/45 uppercase">
		Bukti request/response ({teks.length})
	</p>
	<div class="mt-1 space-y-2">
		{#each teks as b, i (i)}
			<div class="overflow-hidden rounded border border-white/10">
				<p class="border-b border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] text-white/55">
					{b.judul}
				</p>
				<pre class="overflow-x-auto px-2 py-1.5 font-mono text-[11.5px] leading-relaxed text-white/75 whitespace-pre-wrap">{b.isi}</pre>
			</div>
		{/each}
	</div>
{/if}

{#if detail}
	<button
		type="button"
		class="mt-3 text-[11px] tracking-wider text-white/45 uppercase hover:text-white/70"
		onclick={() => (bukaDetail = !bukaDetail)}
	>
		{bukaDetail ? '▾' : '▸'} Detail teknis
	</button>
	{#if bukaDetail}
		<pre class="mt-1 overflow-x-auto rounded border border-white/10 bg-white/[0.02] px-2 py-1.5 font-mono text-[11.5px] leading-relaxed text-white/65 whitespace-pre-wrap">{detail}</pre>
	{/if}
{/if}

{#if !poc.length && !gambar.length && !teks.length && !detail}
	<p class="mt-2 text-[12px] text-white/40 italic">Tidak ada bukti terlampir untuk metode ini.</p>
{/if}
