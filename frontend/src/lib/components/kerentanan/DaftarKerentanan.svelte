<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.js';
	import { relatif, tanggal } from '#lib/format.js';
	import { cn } from '#lib/utils.js';
	import type { FilterKerentanan, HalamanKerentanan, KerentananAset, RingkasanKerentanan, Severity, StatusKerentanan, TingkatPrioritas } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import NativeSelect from '#lib/components/NativeSelect.svelte';
	import SeverityBadge from '#lib/components/SeverityBadge.svelte';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import DialogStatusKerentanan from './DialogStatusKerentanan.svelte';
	import Search from '@lucide/svelte/icons/search';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import Flame from '@lucide/svelte/icons/flame';
	import Info from '@lucide/svelte/icons/info';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import CircleSlash from '@lucide/svelte/icons/circle-slash';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	let {
		aplikasiId,
		tampilAplikasi = true,
		muatUlang = 0,
		onringkasan
	}: {
		/** Batasi ke satu aplikasi. */
		aplikasiId?: string;
		tampilAplikasi?: boolean;
		/** Naikkan nilainya untuk memuat ulang dari luar (mis. setelah komponen berubah). */
		muatUlang?: number;
		onringkasan?: (r: RingkasanKerentanan) => void;
	} = $props();

	const KELOMPOK = [
		{ value: '', label: 'Aktif (terdampak & kemungkinan)' },
		{ value: 'terdampak', label: 'Terdampak' },
		{ value: 'kemungkinan', label: 'Kemungkinan' },
		{ value: 'ditangani', label: 'Ditangani' },
		{ value: 'dikecualikan', label: 'Dikecualikan' },
		{ value: 'kedaluwarsa', label: 'Kedaluwarsa' },
		{ value: 'terdampak,kemungkinan,ditangani,dikecualikan,kedaluwarsa', label: 'Semua status' }
	];
	const OPSI_SEVERITAS = [
		{ value: '', label: 'Semua severitas' },
		{ value: 'kritis', label: 'Kritis' },
		{ value: 'tinggi', label: 'Tinggi' },
		{ value: 'sedang', label: 'Sedang' },
		{ value: 'rendah', label: 'Rendah' }
	];
	const OPSI_URUT = [
		{ value: 'prioritas', label: 'Prioritas tertinggi' },
		{ value: 'terbaru', label: 'Baru ditemukan' },
		{ value: 'publikasi', label: 'CVE terbaru' }
	];

	const LABEL_STATUS: Record<StatusKerentanan, string> = {
		terdampak: 'Terdampak',
		kemungkinan: 'Kemungkinan',
		ditangani: 'Ditangani',
		dikecualikan: 'Dikecualikan',
		kedaluwarsa: 'Kedaluwarsa'
	};
	const GAYA_STATUS: Record<StatusKerentanan, string> = {
		terdampak: 'border-critical/40 bg-critical/10 text-critical',
		kemungkinan: 'border-warning/50 bg-warning/15 text-warning-foreground',
		ditangani: 'border-success/40 bg-success/10 text-success',
		dikecualikan: 'border-border bg-muted text-muted-foreground',
		kedaluwarsa: 'border-border bg-muted text-muted-foreground'
	};
	const GAYA_TINGKAT: Record<TingkatPrioritas, string> = {
		segera: 'bg-critical text-white',
		tinggi: 'bg-critical/15 text-critical',
		sedang: 'bg-warning/20 text-warning-foreground',
		rendah: 'bg-muted text-muted-foreground'
	};
	const LABEL_SUMBER: Record<string, string> = {
		formulir: 'isian formulir',
		manual: 'koreksi manual',
		banner: 'banner server',
		nuclei: 'nuclei',
		bundle_js: 'berkas JS',
		tls: 'TLS'
	};

	let cari = $state('');
	let cariAktif = $state('');
	let fStatus = $state('');
	let fSeveritas = $state('');
	let fKev = $state(false);
	let fUrut = $state<'prioritas' | 'terbaru' | 'publikasi'>('prioritas');
	let halaman = $state(1);
	let data = $state<HalamanKerentanan | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(false);

	let akanDitangani = $state<KerentananAset | null>(null);
	let akanDikecualikan = $state<KerentananAset | null>(null);
	let membuka = $state<string | null>(null);

	// Pencarian ditunda 300 ms agar tidak memanggil server tiap ketukan.
	$effect(() => {
		const kata = cari;
		const t = setTimeout(() => {
			cariAktif = kata.trim();
			halaman = 1;
		}, 300);
		return () => clearTimeout(t);
	});

	const filter = $derived<FilterKerentanan>({
		page: halaman,
		limit: 25,
		aplikasi_id: aplikasiId,
		status: fStatus || undefined,
		severitas: (fSeveritas || '') as Severity | '',
		kev: fKev,
		search: cariAktif,
		sort: fUrut
	});

	async function muat(f: FilterKerentanan) {
		memuat = true;
		try {
			data = await api.cariKerentanan(f);
			galat = null;
			onringkasan?.(data.meta.ringkasan);
		} catch (e) {
			galat = e instanceof Error ? e.message : 'Gagal memuat kerentanan';
		} finally {
			memuat = false;
		}
	}

	$effect(() => {
		void muatUlang;
		void muat(filter);
	});

	function gantiFilter(fn: () => void) {
		fn();
		halaman = 1;
	}

	function diubah(k: KerentananAset) {
		if (data) data.items = data.items.map((x) => (x.id === k.id ? k : x));
		void muat(filter);
	}

	async function buka(k: KerentananAset) {
		membuka = k.id;
		try {
			diubah(await api.ubahStatusKerentanan(k.id, { status: 'buka' }));
			toast.success(`${k.cve.id} dibuka kembali untuk evaluasi otomatis`);
		} catch (e) {
			toast.error(e instanceof Error ? e.message : 'Gagal membuka kembali');
		} finally {
			membuka = null;
		}
	}

	const persen = (v: number | null) => (v === null ? '—' : `${(v * 100).toFixed(v < 0.01 ? 2 : 1)}%`);
</script>

<div class="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_auto_auto_auto_auto]">
	<label class="relative block sm:col-span-2 lg:col-span-1">
		<span class="sr-only">Cari CVE, komponen, atau aplikasi</span>
		<Search class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
		<Input class="h-8 pl-8" bind:value={cari} placeholder="Cari CVE, komponen{tampilAplikasi ? ', aplikasi' : ''}…" />
	</label>
	<NativeSelect aria-label="Status" value={fStatus} onchange={(e) => gantiFilter(() => (fStatus = e.currentTarget.value))} opsi={KELOMPOK} class="lg:w-56" />
	<NativeSelect aria-label="Severitas" value={fSeveritas} onchange={(e) => gantiFilter(() => (fSeveritas = e.currentTarget.value))} opsi={OPSI_SEVERITAS} class="lg:w-40" />
	<NativeSelect
		aria-label="Urutkan"
		value={fUrut}
		onchange={(e) => gantiFilter(() => (fUrut = e.currentTarget.value as typeof fUrut))}
		opsi={OPSI_URUT}
		class="lg:w-44"
	/>
	<button
		type="button"
		aria-pressed={fKev}
		onclick={() => gantiFilter(() => (fKev = !fKev))}
		class={cn(
			'inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border px-3 text-sm transition-colors',
			fKev ? 'border-critical bg-critical/10 text-critical' : 'hover:bg-muted'
		)}
	>
		<Flame class="size-4" /> Dieksploitasi aktif
	</button>
</div>

{#if !data && galat}
	<Kosong judul="Gagal memuat kerentanan" pesan={galat}>
		<Button variant="outline" onclick={() => muat(filter)}>Coba lagi</Button>
	</Kosong>
{:else if !data}
	<Memuat baris={3} />
{:else if !data.items.length}
	<Kosong
		judul={fStatus || fSeveritas || fKev || cariAktif ? 'Tidak ada yang cocok dengan filter' : 'Belum ada kerentanan yang cocok'}
		pesan={fStatus || fSeveritas || fKev || cariAktif
			? 'Ubah atau hapus filter untuk melihat hasil lain.'
			: 'Kerentanan muncul setelah intel CVE disinkron dan komponen aset (beserta versinya) tercatat.'}
	/>
{:else}
	<ul class={cn('grid gap-2 transition-opacity', memuat && 'opacity-60')} aria-busy={memuat}>
		{#each data.items as k (k.id)}
			{@const manual = k.status === 'ditangani' || k.status === 'dikecualikan'}
			<li class="relative overflow-hidden rounded-lg border bg-card p-3 pl-4 sm:p-4 sm:pl-5">
				<span class={cn('absolute inset-y-0 left-0 w-1', k.cve.kev ? 'bg-critical' : k.tingkat === 'tinggi' ? 'bg-critical/60' : k.tingkat === 'sedang' ? 'bg-warning' : 'bg-border')}></span>
				<div class="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
					<div class="min-w-0 flex-1">
						<div class="flex flex-wrap items-center gap-1.5">
							<a href={k.cve.tautan} target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 font-mono text-sm font-semibold hover:underline">
								{k.cve.id}<ExternalLink class="size-3 text-muted-foreground" />
							</a>
							{#if k.cve.kev}
								<span class="inline-flex h-5 items-center gap-1 rounded bg-critical px-1.5 text-[11px] font-semibold tracking-wide text-white uppercase" title="Tercantum di katalog CISA Known Exploited Vulnerabilities{k.cve.kev_tenggat ? ` · tenggat ${tanggal(k.cve.kev_tenggat)}` : ''}">
									<Flame class="size-3" /> KEV{k.cve.kev_ransomware ? ' · ransomware' : ''}
								</span>
							{/if}
							{#if k.cve.severitas}<SeverityBadge severity={k.cve.severitas} />{/if}
							<span class={cn('inline-flex h-5 items-center rounded border px-1.5 text-[11px] font-medium', GAYA_STATUS[k.status])}>{LABEL_STATUS[k.status]}</span>
						</div>
						<p class="mt-1 text-sm">
							<span class="font-medium">{k.komponen.nama}{k.komponen.versi ? ` ${k.komponen.versi}` : ''}</span>
							<span class="text-muted-foreground"> · {LABEL_SUMBER[k.komponen.sumber] ?? k.komponen.sumber}</span>
							{#if tampilAplikasi}
								<span class="text-muted-foreground"> · </span>
								<a href="/aplikasi/{k.aplikasi.id}/komponen" class="hover:underline">{k.aplikasi.nama}</a>
								<span class="text-muted-foreground"> ({k.aplikasi.satuan})</span>
							{/if}
						</p>
						{#if k.cve.ringkasan}
							<p class="mt-1.5 line-clamp-2 text-sm text-muted-foreground" title={k.cve.ringkasan}>{k.cve.ringkasan}</p>
						{/if}
						<p class="mt-1.5 flex gap-1.5 text-xs text-muted-foreground">
							<Info class="mt-px size-3.5 shrink-0" /><span>{k.alasan}</span>
						</p>
						{#if manual && k.catatan}
							<p class="mt-1.5 rounded-md bg-muted px-2.5 py-1.5 text-xs">
								<span class="font-medium">{LABEL_STATUS[k.status]}{k.ditangani_oleh ? ` oleh ${k.ditangani_oleh}` : ''}{k.ditangani_pada ? `, ${relatif(k.ditangani_pada)}` : ''}:</span>
								{k.catatan}
							</p>
						{/if}
					</div>
					<div class="flex shrink-0 flex-col items-end gap-1.5 text-right">
						<span class={cn('inline-flex h-6 items-center rounded px-2 text-xs font-semibold uppercase', GAYA_TINGKAT[k.tingkat])} title="Skor prioritas {k.prioritas}/100">
							{k.tingkat} · {k.prioritas}
						</span>
						<dl class="grid grid-cols-[auto_auto] gap-x-2 text-xs text-muted-foreground">
							<dt>CVSS</dt><dd class="font-mono text-foreground">{k.cve.cvss ?? '—'}</dd>
							<dt title="Peluang dieksploitasi dalam 30 hari (FIRST EPSS)">EPSS</dt><dd class="font-mono text-foreground">{persen(k.cve.epss)}</dd>
						</dl>
						<p class="text-[11px] text-muted-foreground" title={tanggal(k.pertama_ditemukan)}>ditemukan {relatif(k.pertama_ditemukan)}</p>
					</div>
				</div>
				<div class="mt-3 flex flex-wrap gap-2">
					{#if k.status === 'terdampak' || k.status === 'kemungkinan'}
						<Button size="sm" variant="outline" onclick={() => (akanDitangani = k)}><CircleCheck /> Sudah ditangani</Button>
						<Button size="sm" variant="ghost" onclick={() => (akanDikecualikan = k)}><CircleSlash /> Kecualikan</Button>
					{:else if manual}
						<Button size="sm" variant="ghost" disabled={membuka === k.id} onclick={() => buka(k)}><RotateCcw /> Buka kembali</Button>
					{/if}
				</div>
			</li>
		{/each}
	</ul>

	{#if data.meta.totalPages > 1}
		<div class="mt-3 flex items-center justify-between gap-2 text-sm text-muted-foreground">
			<span>{data.meta.total} kecocokan · halaman {data.meta.page} dari {data.meta.totalPages}</span>
			<div class="flex gap-1">
				<Button size="icon-sm" variant="outline" aria-label="Halaman sebelumnya" disabled={halaman <= 1} onclick={() => (halaman -= 1)}><ChevronLeft /></Button>
				<Button size="icon-sm" variant="outline" aria-label="Halaman berikutnya" disabled={halaman >= data.meta.totalPages} onclick={() => (halaman += 1)}><ChevronRight /></Button>
			</div>
		</div>
	{/if}
{/if}

<DialogStatusKerentanan bind:target={akanDitangani} status="ditangani" ondiubah={diubah} />
<DialogStatusKerentanan bind:target={akanDikecualikan} status="dikecualikan" ondiubah={diubah} />
