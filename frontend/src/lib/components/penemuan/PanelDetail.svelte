<script lang="ts">
	// Panel detail node graf penemuan (drawer kanan di area visual).
	import { labelSumber, tetangga, type Graf, type NodeGraf } from '#lib/penemuan/graf.js';
	import { warnaMetode } from '#lib/penemuan/kanvas.js';
	import { svgEntitas, WARNA_RISIKO, type JenisIkon } from '#lib/penemuan/ikon-entitas.js';
	import X from '@lucide/svelte/icons/x';
	import Lock from '@lucide/svelte/icons/lock';
	import ExternalLink from '@lucide/svelte/icons/external-link';

	let {
		node,
		graf,
		onpilih,
		ontutup,
		tepi = { atas: 0, kanan: 0 }
	}: { node: NodeGraf; graf: Graf; onpilih: (id: string) => void; ontutup: () => void; tepi?: { atas: number; kanan: number; bawah?: number } } = $props();

	const JUDUL: Record<NodeGraf['jenis'], string> = {
		situs: 'Situs target',
		docs: 'Dokumentasi API',
		backend: 'Backend',
		frontend: 'Frontend · URL',
		aset: 'Aset statis',
		js: 'Berkas JavaScript',
		upload: 'Upload berkas',
		endpoint: 'Endpoint',
		halaman: 'Halaman',
		titik: 'Titik uji',
		sesi: 'Sesi login',
		alur: 'Alur proses bisnis',
		zap: 'OWASP ZAP',
		katana: 'Katana'
	};

	const rel = $derived(tetangga(graf, node.id));
	const ep = $derived(node.endpoint);
	const anakEndpoint = $derived(rel.filter((n) => n.jenis === 'endpoint'));
	const alurMemuat = $derived(rel.filter((n) => n.jenis === 'alur'));
	const info = $derived((node.info ?? {}) as Record<string, any>);
	const nAuth = $derived(anakEndpoint.filter((n) => n.endpoint?.butuh_autentikasi).length);
	const anakHalaman = $derived(rel.filter((n) => n.jenis === 'halaman'));
	const anakJs = $derived(rel.filter((n) => n.jenis === 'js'));
	const kontribusi = $derived(Object.entries((info.kontribusi ?? {}) as Record<string, number>).map(([id, n]) => ({ node: graf.nodes.find((x) => x.id === id), n })));
</script>

<aside style:top="{tepi.atas}px" style:right="{tepi.kanan}px" style:bottom="{tepi.bawah ?? 0}px" class="panel-masuk absolute z-20 flex w-[min(360px,100%)] flex-col border-l border-white/10 bg-[#0c1014]/95 text-white/85 backdrop-blur">
	<header class="flex items-start gap-2 border-b border-white/10 px-4 py-3">
		<span class="mt-0.5 inline-block size-8 shrink-0">{@html svgEntitas(node.jenis as JenisIkon, { metode: ep?.metode_http, ukuran: 32 })}</span>
		<div class="min-w-0 flex-1">
			<p class="font-heading text-[10px] tracking-[0.25em] text-[#7fe9d8] uppercase">{JUDUL[node.jenis]}</p>
			{#if ep}
				<p class="mt-1 flex items-center gap-2 font-mono text-sm">
					<span class="rounded-sm px-1.5 py-px text-[11px] font-semibold text-black" style="background:{warnaMetode(ep.metode_http)}">{ep.metode_http}</span>
					<span class="break-all">{ep.path_template}</span>
				</p>
			{:else}
				<p class="mt-1 font-mono text-sm break-all">{node.label}</p>
			{/if}
		</div>
		<button type="button" onclick={ontutup} class="rounded p-1 text-white/50 hover:bg-white/10 hover:text-white" aria-label="Tutup detail"><X class="size-4" /></button>
	</header>

	<div class="flex-1 space-y-4 overflow-y-auto px-4 py-3 text-xs">
		{#if ep}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">URL</dt><dd class="font-mono break-all">{ep.url}</dd>
				<dt class="text-white/40">Backend</dt><dd class="font-mono break-all">{ep.origin}</dd>
				{#if node.upload}<dt class="text-white/40">Upload berkas</dt><dd class="text-[#f5c451]">Ya — menerima unggahan</dd>{/if}
				<dt class="text-white/40">Autentikasi</dt>
				<dd>{#if ep.butuh_autentikasi}<span class="inline-flex items-center gap-1 text-[#9fe08a]"><Lock class="size-3" /> Butuh sesi login</span>{:else}Terbuka (anonim){/if}</dd>
				<dt class="text-white/40">Lapisan</dt><dd>Backend (API)</dd>
				<dt class="text-white/40">Sumber</dt><dd>{@render sumber(ep.sumber)}</dd>
				<dt class="text-white/40">Status terlihat</dt><dd class="font-mono">{ep.status_terlihat.join(', ') || '—'}</dd>
				<dt class="text-white/40">Content-Type</dt><dd class="font-mono break-all">{ep.content_type ?? '—'}</dd>
				<dt class="text-white/40">Titik uji</dt><dd>{[ep.titik_uji, ...(node.titik ?? [])].filter(Boolean).join(', ') || '—'}</dd>
			</dl>

			{@render alert()}

			{#if node.kategori?.length}
				<section>
					<p class="label-panel">Kandidat uji</p>
					<div class="flex flex-wrap gap-1.5">
						{#each node.kategori as k (k)}<span class="rounded-sm border border-[#f5c451]/40 bg-[#f5c451]/10 px-1.5 py-px font-mono text-[10px] text-[#f5c451]">{k}</span>{/each}
					</div>
				</section>
			{/if}

			<section>
				<p class="label-panel">Field request ({ep.request_fields.length})</p>
				{#if ep.request_fields.length}
					<table class="w-full font-mono text-[11px]">
						<thead><tr class="text-left text-white/35"><th class="py-1 font-normal">nama</th><th class="font-normal">lokasi</th><th class="font-normal">tipe</th><th></th></tr></thead>
						<tbody>
							{#each ep.request_fields as f, i (i)}
								<tr class="border-t border-white/5"><td class="py-1 pr-2 break-all">{f.nama}</td><td class="pr-2 text-white/55">{f.lokasi}</td><td class="pr-2 text-white/55">{f.tipe ?? '—'}</td><td class="text-[#ff7b6b]">{f.wajib ? '*' : ''}</td></tr>
							{/each}
						</tbody>
					</table>
				{:else}<p class="text-white/35">Tidak ada field terdeteksi.</p>{/if}
			</section>

			{#if ep.response_fields.length}
				<section>
					<p class="label-panel">Field respons ({ep.response_fields.length})</p>
					<div class="flex flex-wrap gap-1.5 font-mono text-[10px]">
						{#each ep.response_fields as f, i (i)}<span class="rounded-sm bg-white/5 px-1.5 py-px">{f}</span>{/each}
					</div>
				</section>
			{/if}
		{:else if node.jenis === 'backend'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">Origin</dt><dd class="font-mono break-all">{info.origin}</dd>
				<dt class="text-white/40">Posisi</dt><dd>{info.same_origin ? 'Satu origin dengan frontend' : 'Origin terpisah (API)'}</dd>
				<dt class="text-white/40">Endpoint</dt><dd>{anakEndpoint.length} ({nAuth} butuh login)</dd>
			</dl>
		{:else if node.jenis === 'frontend'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">URL</dt><dd>{info.jumlah_url}{info.halaman_lain ? ` (${info.halaman_lain} tak ditampilkan)` : ''}</dd>
			</dl>
			{#if anakHalaman.length}
				<section>
					<p class="label-panel">URL frontend ({anakHalaman.length})</p>
					<ul class="space-y-0.5 font-mono text-[11px]">
						{#each anakHalaman as n (n.id)}
							<li>
								<button type="button" class="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-white/5" onclick={() => onpilih(n.id)}>
									<span class="w-8 shrink-0 text-white/40">{n.info?.status ?? ''}</span>
									<span class="truncate">{n.label}</span>
								</button>
							</li>
						{/each}
					</ul>
				</section>
			{/if}
		{:else if node.jenis === 'upload'}
			<p class="text-white/55">Endpoint yang menerima unggahan berkas (multipart / field file / titik uji unggah) — prioritas uji validasi tipe, ukuran &amp; konten berkas.</p>
		{:else if node.jenis === 'katana'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">Ditemukan</dt><dd>{info.jumlah} URL/endpoint (crawl + parsing JS)</dd>
				{#if info.ringkas}<dt class="text-white/40">Per lapisan</dt><dd>frontend {info.ringkas.frontend} · API {info.ringkas.api} · aset {info.ringkas.aset}</dd>{/if}
			</dl>
			{@render kontribusiKe()}
		{:else if node.jenis === 'docs'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">Judul</dt><dd>{info.judul || '—'}</dd>
				<dt class="text-white/40">Versi</dt><dd>{info.versi || '—'}</dd>
				<dt class="text-white/40">Endpoint</dt><dd>{info.jumlah_endpoint}</dd>
				<dt class="text-white/40">Base API</dt><dd class="font-mono break-all">{info.base_api || '—'}</dd>
				<dt class="text-white/40">Spec</dt>
				<dd><a href={info.url} target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 font-mono break-all text-[#7fe9d8] hover:underline">{info.url} <ExternalLink class="size-3 shrink-0" /></a></dd>
			</dl>
		{:else if node.jenis === 'halaman'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">URL</dt><dd class="font-mono break-all">{info.url}</dd>
				<dt class="text-white/40">Status</dt><dd class="font-mono">{info.status}</dd>
				<dt class="text-white/40">Judul</dt><dd>{info.judul || '—'}</dd>
				<dt class="text-white/40">Titik uji</dt><dd>{node.titik?.join(', ') || '—'}</dd>
				<dt class="text-white/40">Lapisan</dt><dd>Frontend (halaman/rute)</dd>
				<dt class="text-white/40">Sumber</dt><dd>{@render sumber(node.sumber ?? [])}</dd>
			</dl>
			{@render alert()}
		{:else if node.jenis === 'js'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">URL</dt><dd class="font-mono break-all">{info.url}</dd>
				<dt class="text-white/40">Sumber</dt><dd>{@render sumber(node.sumber ?? [])}</dd>
			</dl>
			<p class="text-white/45">Bundle JS dianalisis untuk menemukan panggilan API (termasuk non-GET) yang tak tampak saat crawl.</p>
		{:else if node.jenis === 'aset'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">Berkas JS</dt><dd>{info.jumlah}{info.lain ? ` (${info.lain} tak ditampilkan)` : ''}</dd>
			</dl>
			{#if anakJs.length}
				<section>
					<p class="label-panel">Berkas ({anakJs.length})</p>
					{#each anakJs as n (n.id)}<button type="button" class="tautan font-mono text-[11px]" onclick={() => onpilih(n.id)}>{n.sub ?? n.label}</button>{/each}
				</section>
			{/if}
		{:else if node.jenis === 'situs'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">URL</dt><dd class="font-mono break-all">{info.url}</dd>
				<dt class="text-white/40">Docs</dt><dd>{graf.hitung.docs}</dd>
				<dt class="text-white/40">Backend</dt><dd>{graf.hitung.backend}</dd>
				<dt class="text-white/40">Endpoint</dt><dd>{graf.hitung.endpoint}</dd>
				<dt class="text-white/40">URL frontend</dt><dd>{graf.hitung.halaman}</dd>
				<dt class="text-white/40">Upload</dt><dd>{graf.hitung.upload}</dd>
				<dt class="text-white/40">Titik uji</dt><dd>{graf.hitung.titik}</dd>
			</dl>
		{:else if node.jenis === 'sesi'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">Hasil</dt><dd class={info.berhasil ? 'text-[#9fe08a]' : 'text-[#ff7b6b]'}>{info.berhasil ? 'Login terkonfirmasi' : 'Login tak terkonfirmasi'}</dd>
				<dt class="text-white/40">Akun</dt><dd class="font-mono">{info.akun}</dd>
			</dl>
		{:else if node.jenis === 'titik'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">Titik</dt><dd>{info.titik}</dd>
				<dt class="text-white/40">Metode</dt><dd class="font-mono">{info.metode}</dd>
				<dt class="text-white/40">URL</dt><dd class="font-mono break-all">{info.url}</dd>
			</dl>
		{:else if node.jenis === 'zap'}
			<dl class="grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5">
				<dt class="text-white/40">URL</dt><dd>{info.jumlah_url} dijelajahi spider</dd>
				<dt class="text-white/40">Alert pasif</dt><dd class="text-[#ff7b6b]">{info.alert ?? 0}</dd>
				{#if info.ringkas}<dt class="text-white/40">Per lapisan</dt><dd>frontend {info.ringkas.frontend} · API {info.ringkas.api} · aset {info.ringkas.aset}</dd>{/if}
			</dl>
			{@render kontribusiKe()}
			{#if info.temuan?.length}<p class="label-panel">Alert teratas</p>{/if}
			<ul class="space-y-1">
				{#each info.temuan ?? [] as t, i (i)}<li class="flex justify-between gap-2"><span>{t.nama}</span><span class="font-mono text-[#ff7b6b]">×{t.n}</span></li>{/each}
			</ul>
		{:else if node.jenis === 'alur'}
			<p class="text-white/55">Sumber: {info.sumber}</p>
		{/if}

		{#if alurMemuat.length}
			<section>
				<p class="label-panel">Bagian dari alur</p>
				{#each alurMemuat as a (a.id)}<button type="button" class="tautan" onclick={() => onpilih(a.id)}>{a.label}</button>{/each}
			</section>
		{/if}

		{#if !ep && anakEndpoint.length}
			<section>
				<p class="label-panel">{node.jenis === 'upload' ? 'Endpoint upload' : 'Endpoint terkait'} ({anakEndpoint.length})</p>
				<ul class="space-y-0.5 font-mono text-[11px]">
					{#each anakEndpoint.slice(0, 80) as n (n.id)}
						<li>
							<button type="button" class="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-white/5" onclick={() => onpilih(n.id)}>
								<span class="w-12 shrink-0" style="color:{warnaMetode(n.endpoint?.metode_http ?? 'GET')}">{n.endpoint?.metode_http}</span>
								<span class="truncate">{n.endpoint?.path_template}</span>
								{#if n.endpoint?.butuh_autentikasi}<Lock class="ml-auto size-3 shrink-0 text-[#9fe08a]" />{/if}
							</button>
						</li>
					{/each}
				</ul>
			</section>
		{:else if !ep && !['frontend', 'aset', 'zap', 'katana'].includes(node.jenis)}
			{@const lain = rel.filter((n) => n.jenis !== 'endpoint')}
			{#if lain.length}
				<section>
					<p class="label-panel">Terhubung ke</p>
					{#each lain as n (n.id)}<button type="button" class="tautan" onclick={() => onpilih(n.id)}>{n.label}</button>{/each}
				</section>
			{/if}
		{/if}
	</div>
</aside>

{#snippet sumber(daftar: string[])}
	{#if daftar.length}
		<span class="flex flex-wrap gap-1">{#each daftar as s (s)}<span class="rounded-sm border border-white/15 bg-white/5 px-1.5 py-px text-[10px]">{labelSumber(s)}</span>{/each}</span>
	{:else}—{/if}
{/snippet}

{#snippet alert()}
	{#if node.alert?.length}
		<section>
			<p class="label-panel">Alert ZAP ({node.alert.length})</p>
			<ul class="space-y-1">
				{#each node.alert as a, i (i)}
					<li class="flex items-center gap-2">
						<span class="size-2 shrink-0 rounded-full" style="background:{WARNA_RISIKO[a.risk] ?? WARNA_RISIKO.Informational}"></span>
						<span class="flex-1">{a.nama}</span><span class="font-mono text-[10px] text-white/45">{a.risk}</span>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
{/snippet}

{#snippet kontribusiKe()}
	{#if kontribusi.length}
		<section>
			<p class="label-panel">Masuk ke klaster</p>
			{#each kontribusi as k (k.node?.id)}
				{#if k.node}
					<button type="button" class="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-white/5" onclick={() => onpilih(k.node!.id)}>
						<span class="inline-block size-4">{@html svgEntitas(k.node.jenis as JenisIkon, { ukuran: 16 })}</span>
						<span class="flex-1 text-[#7fe9d8]">{k.node.label}</span><span class="font-mono text-white/55">{k.n}</span>
					</button>
				{/if}
			{/each}
		</section>
	{/if}
{/snippet}

<style>
	.label-panel { margin-bottom: 0.35rem; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: rgba(255, 255, 255, 0.4); }
	.tautan { display: block; width: 100%; text-align: left; padding: 0.15rem 0.25rem; border-radius: 0.25rem; color: #7fe9d8; }
	.tautan:hover { background: rgba(255, 255, 255, 0.05); }
	.panel-masuk { animation: geser 0.25s ease-out both; }
	@keyframes geser { from { transform: translateX(24px); opacity: 0; } }
	@media (prefers-reduced-motion: reduce) { .panel-masuk { animation: none; } }
</style>
