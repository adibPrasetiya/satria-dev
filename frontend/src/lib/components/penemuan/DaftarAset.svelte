<script lang="ts">
	// Daftar aset hasil penemuan (panel kanan atas): tree terkelompok per klaster — Frontend (URL),
	// Aset JS, Backend per origin, Upload, Docs, Sesi, alert ZAP, kontribusi Katana — dengan
	// pencarian. Seleksi dibagi dengan graf: klik baris → node tersorot & dipusatkan; klik node →
	// baris tersorot & digulir ke tampilan.
	import { labelSumber, PERINGKAT_RISIKO, type Graf, type NodeGraf } from '#lib/penemuan/graf.js';
	import { svgEntitas, WARNA_RISIKO, type JenisIkon } from '#lib/penemuan/ikon-entitas.js';
	import { warnaMetode } from '#lib/penemuan/kanvas.js';
	import { cn } from '#lib/utils.js';
	import Search from '@lucide/svelte/icons/search';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Lock from '@lucide/svelte/icons/lock';
	import Crosshair from '@lucide/svelte/icons/crosshair';
	import Layers from '@lucide/svelte/icons/layers';
	import Funnel from '@lucide/svelte/icons/funnel';

	let { graf, terpilih = $bindable(null) }: { graf: Graf; terpilih?: string | null } = $props();

	type Baris = { id: string; ikon: JenisIkon; metode?: string; nama: string; ket?: string; sumber: string[]; risiko?: string; auth?: boolean; titik?: boolean };
	type Grup = { id: string; judul: string; ikon: JenisIkon; hub?: string; jumlah: number; baris: Baris[] };

	const SINGKAT: Record<string, string> = { openapi: 'OA', html: 'HTML', browser: 'BRW', 'browser-intersep': 'INT', js: 'JS', katana: 'KTN', zap: 'ZAP', heuristik: 'HEUR', ai: 'AI', browser_urutan: 'BRW' };

	const urutPath = (a: Baris, b: Baris) => a.nama.localeCompare(b.nama) || (a.metode ?? '').localeCompare(b.metode ?? '');
	const risikoTertinggi = (n: NodeGraf) => n.alert?.[0]?.risk;

	function baris(n: NodeGraf): Baris {
		const ep = n.endpoint;
		return {
			id: n.id,
			ikon: n.jenis as JenisIkon,
			metode: ep?.metode_http,
			nama: ep ? ep.path_template : n.jenis === 'js' ? (n.sub ?? n.label) : n.label,
			ket: n.jenis === 'halaman' ? ((n.info?.judul as string) || undefined) : undefined,
			sumber: n.sumber ?? [],
			risiko: risikoTertinggi(n),
			auth: ep?.butuh_autentikasi,
			titik: !!n.titik?.length
		};
	}

	const grup = $derived.by<Grup[]>(() => {
		const per = (f: (n: NodeGraf) => boolean) => graf.nodes.filter(f);
		const out: Grup[] = [];
		const hal = per((n) => n.jenis === 'halaman').map(baris).sort(urutPath);
		if (hal.length) out.push({ id: 'frontend', judul: 'Frontend · URL', ikon: 'frontend', hub: 'hub:frontend', jumlah: graf.hitung.halaman, baris: hal });
		const js = per((n) => n.jenis === 'js').map(baris).sort(urutPath);
		if (js.length) out.push({ id: 'aset', judul: 'Aset statis · JS', ikon: 'aset', hub: 'hub:aset', jumlah: graf.hitung.aset, baris: js });
		for (const be of per((n) => n.jenis === 'backend')) {
			const eps = per((n) => n.jenis === 'endpoint' && n.induk === be.id).map(baris).sort(urutPath);
			out.push({ id: be.id, judul: `${be.label} · ${String(be.info?.origin ?? '').replace(/^https?:\/\//, '')}`, ikon: 'backend', hub: be.id, jumlah: eps.length, baris: eps });
		}
		const up = per((n) => n.jenis === 'endpoint' && !!n.upload).map(baris).sort(urutPath);
		if (up.length) out.push({ id: 'upload', judul: 'Upload berkas', ikon: 'upload', hub: 'hub:upload', jumlah: up.length, baris: up });
		const docs = per((n) => n.jenis === 'docs');
		if (docs.length) out.push({ id: 'docs', judul: 'Dokumentasi API', ikon: 'docs', jumlah: docs.length, baris: docs.map((n) => ({ ...baris(n), nama: n.label, ket: String(n.info?.url ?? '') })) });
		const sesi = per((n) => n.jenis === 'sesi');
		if (sesi.length) out.push({ id: 'sesi', judul: 'Sesi', ikon: 'sesi', jumlah: sesi.length, baris: sesi.map((n) => ({ ...baris(n), nama: n.label, ket: n.sub })) });
		// Alur proses bisnis: urutan endpoint yang membentuk satu proses (mis. ajukan → setujui cuti).
		const alur = per((n) => n.jenis === 'alur');
		if (alur.length) {
			const langkah = (n: NodeGraf) =>
				graf.edges
					.filter((e) => e.dari === n.id && e.jenis === 'alur')
					.map((e) => graf.nodes.find((x) => x.id === e.ke)?.endpoint)
					.filter((ep): ep is NonNullable<typeof ep> => !!ep)
					.map((ep) => `${ep.metode_http} ${ep.path_template.split('/').slice(-2).join('/')}`)
					.join(' → ');
			out.push({
				id: 'alur',
				judul: 'Alur proses bisnis',
				ikon: 'alur',
				jumlah: alur.length,
				baris: alur.map((n) => ({ ...baris(n), nama: n.label, ket: langkah(n) || n.sub, sumber: [String(n.info?.sumber ?? '')].filter(Boolean) }))
			});
		}
		const zap = graf.nodes.find((n) => n.jenis === 'zap');
		if (zap) {
			const beralert = per((n) => !!n.alert?.length)
				.sort((a, b) => (PERINGKAT_RISIKO[risikoTertinggi(b) ?? ''] ?? 0) - (PERINGKAT_RISIKO[risikoTertinggi(a) ?? ''] ?? 0))
				.map((n) => ({ ...baris(n), ket: n.alert!.map((a) => a.nama).join(' · ') }));
			out.push({ id: 'zap', judul: 'OWASP ZAP · alert', ikon: 'zap', hub: 'zap', jumlah: graf.hitung.zapAlert, baris: beralert });
		}
		const katana = graf.nodes.find((n) => n.jenis === 'katana');
		if (katana) {
			const kontribusi = (katana.info?.kontribusi ?? {}) as Record<string, number>;
			const rows = Object.entries(kontribusi).map(([id, n]) => {
				const k = graf.nodes.find((x) => x.id === id);
				return { id, ikon: (k?.jenis ?? 'frontend') as JenisIkon, nama: k?.label ?? id, ket: `${n} temuan dari katana`, sumber: ['katana'] } satisfies Baris;
			});
			out.push({ id: 'katana', judul: 'Katana · kontribusi', ikon: 'katana', hub: 'katana', jumlah: graf.hitung.katana, baris: rows });
		}
		return out;
	});

	let cari = $state('');
	const q = $derived(cari.trim().toLowerCase());
	// Filter: semua aset, hanya titik uji, yang berisiko (alert ZAP), atau yang butuh autentikasi.
	const FILTER = [
		['semua', 'Semua aset'],
		['titik', 'Titik uji'],
		['risiko', 'Berisiko (alert)'],
		['auth', 'Butuh autentikasi']
	] as const;
	let filter = $state<(typeof FILTER)[number][0]>('semua');
	let bukaFilter = $state(false);
	const lolos = (b: Baris) =>
		filter === 'semua' || (filter === 'titik' ? !!b.titik : filter === 'risiko' ? !!b.risiko : !!b.auth);
	const cocokCari = (b: Baris) =>
		!q || `${b.metode ?? ''} ${b.nama} ${b.ket ?? ''} ${b.sumber.join(' ')}`.toLowerCase().includes(q);
	const tersaring = $derived(
		q || filter !== 'semua'
			? grup.map((g) => ({ ...g, baris: g.baris.filter((b) => lolos(b) && cocokCari(b)) })).filter((g) => g.baris.length)
			: grup
	);

	// Grup terlipat (default terbuka); grup berisi baris terpilih otomatis dibuka.
	let tertutup = $state<Record<string, boolean>>({});
	const BATAS = 60;
	let lebih = $state<Record<string, boolean>>({});

	let wadah = $state<HTMLDivElement>();
	$effect(() => {
		const id = terpilih;
		if (!id) return;
		const g = grup.find((g) => g.baris.some((b) => b.id === id));
		if (g && tertutup[g.id]) tertutup[g.id] = false;
		queueMicrotask(() => wadah?.querySelector(`[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest' }));
	});

	const RINGKAS = $derived([
		['URL', graf.hitung.halaman, '#7fe9d8'],
		['JS', graf.hitung.aset, '#f7c843'],
		['API', graf.hitung.endpoint, '#9fe08a'],
		['Upload', graf.hitung.upload, '#ff922b'],
		['Alert', graf.hitung.zapAlert, '#ff7b6b']
	] as const);
</script>

<div class="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-[#0f1412]">
	<div class="flex items-center gap-2 px-4 pt-3.5 pb-2">
		<Layers class="size-5 text-white/80" />
		<span class="shrink-0 text-[15px] font-semibold whitespace-nowrap text-white/90">Daftar Aset</span>
		<div class="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-x-1.5 font-mono text-[10px] whitespace-nowrap tabular-nums">
			{#each RINGKAS as [l, n, c], i (l)}
				{#if i}<span class="text-white/15">|</span>{/if}
				<span class="text-white/45">{l} <span style="color:{c}">{n}</span></span>
			{/each}
		</div>
	</div>
	<div class="relative flex items-center gap-2 px-3 pb-2">
		<label class="flex h-9 flex-1 items-center gap-2 rounded-md border border-white/10 bg-black/30 px-2.5 focus-within:border-[#9fe08a]/50">
			<Search class="size-4 text-white/40" />
			<input bind:value={cari} placeholder="Cari URL, endpoint, sumber…" class="w-full bg-transparent text-[13px] text-white/85 outline-none placeholder:text-white/35" />
		</label>
		<button
			type="button"
			onclick={() => (bukaFilter = !bukaFilter)}
			aria-label="Filter aset"
			aria-expanded={bukaFilter}
			class={cn('grid size-9 place-items-center rounded-md border border-white/10 bg-black/30 text-white/70 hover:text-white', filter !== 'semua' && 'border-[#9fe08a]/50 text-[#9fe08a]')}
		>
			<Funnel class="size-4" />
		</button>
		{#if bukaFilter}
			<div class="absolute top-11 right-3 z-20 w-48 rounded-md border border-white/10 bg-[#141a17] p-1 shadow-xl">
				{#each FILTER as [k, l] (k)}
					<button
						type="button"
						onclick={() => ((filter = k), (bukaFilter = false))}
						class={cn('block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-white/5', filter === k ? 'text-[#9fe08a]' : 'text-white/75')}
					>{l}</button>
				{/each}
			</div>
		{/if}
	</div>

	<div bind:this={wadah} class="min-h-0 flex-1 overflow-y-auto border-t border-white/5 font-mono text-[12px]">
		{#if !tersaring.length}
			<p class="px-3 py-6 text-center text-white/35">{q || filter !== 'semua' ? 'Tidak ada aset yang cocok.' : 'Belum ada aset ditemukan.'}</p>
		{/if}
		{#each tersaring as g (g.id)}
			{@const buka = q || filter !== 'semua' ? true : !tertutup[g.id]}
			<div class="sticky top-0 z-[1] flex items-center gap-1.5 border-b border-white/5 bg-[#131916] px-3 py-1.5">
				<button type="button" class="flex min-w-0 flex-1 items-center gap-1.5 text-left" onclick={() => (tertutup[g.id] = buka)} aria-expanded={buka}>
					<ChevronRight class="size-3 shrink-0 text-white/40 transition-transform {buka ? 'rotate-90' : ''}" />
					<span class="inline-block size-4 shrink-0">{@html svgEntitas(g.ikon, { ukuran: 16 })}</span>
					<span class="truncate text-white/80">{g.judul}</span>
				</button>
				{#if g.hub}
					<button type="button" class="rounded px-1 text-[10px] tabular-nums text-white/45 hover:bg-white/10 hover:text-white" onclick={() => (terpilih = g.hub!)} title="Sorot di graf">{g.jumlah}</button>
				{:else}
					<span class="px-1 text-[10px] tabular-nums text-white/45">{g.jumlah}</span>
				{/if}
			</div>
			{#if buka}
				{#each g.baris.slice(0, lebih[g.id] ? undefined : BATAS) as b (g.id + b.id)}
					<button
						type="button"
						data-id={b.id}
						onclick={() => (terpilih = b.id)}
						class="flex w-full items-center gap-1.5 py-1 pr-3 pl-7 text-left transition hover:bg-white/5 {terpilih === b.id ? 'bg-[#9fe08a]/10 outline outline-1 -outline-offset-1 outline-[#9fe08a]/40' : ''}"
					>
						<span class="inline-block size-3.5 shrink-0">{@html svgEntitas(b.ikon, { metode: b.metode, ukuran: 14 })}</span>
						{#if b.metode}<span class="w-11 shrink-0 text-[10px] font-semibold" style="color:{warnaMetode(b.metode)}">{b.metode}</span>{/if}
						<span class="min-w-0 flex-1 truncate text-white/80" title={b.ket ? `${b.nama} — ${b.ket}` : b.nama}>
							{b.nama}{#if b.ket}<span class="text-white/35"> · {b.ket}</span>{/if}
						</span>
						{#if b.titik}<Crosshair class="size-3 shrink-0 text-[#ffd43b]" />{/if}
						{#if b.auth}<Lock class="size-3 shrink-0 text-[#9fe08a]" />{/if}
						{#if b.risiko}<span class="size-2 shrink-0 rounded-full" style="background:{WARNA_RISIKO[b.risiko] ?? WARNA_RISIKO.Informational}" title="Risiko {b.risiko}"></span>{/if}
						<span class="flex shrink-0 gap-0.5">
							{#each b.sumber.slice(0, 3) as s (s)}<span class="rounded-sm border border-white/10 px-1 text-[8.5px] leading-[13px] text-white/45" title={labelSumber(s)}>{SINGKAT[s] ?? s}</span>{/each}
						</span>
					</button>
				{/each}
				{#if g.baris.length > BATAS && !lebih[g.id]}
					<button type="button" class="w-full py-1 pl-6 text-left text-[10px] text-[#7fe9d8]/80 hover:text-[#7fe9d8]" onclick={() => (lebih[g.id] = true)}>
						Tampilkan {g.baris.length - BATAS} lagi…
					</button>
				{/if}
			{/if}
		{/each}
	</div>
</div>
