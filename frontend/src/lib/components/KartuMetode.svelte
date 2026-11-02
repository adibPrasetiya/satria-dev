<script lang="ts">
	// Satu metode pengujian di detail kriteria, dikelompokkan: Kriteria lulus · Pelaksanaan · Worker.
	import type { Metode } from '#lib/types.js';
	import { LABEL_ENGINE, LABEL_JENIS } from '#lib/catalog.js';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.js';
	import { cn } from '#lib/utils.js';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Pencil from '@lucide/svelte/icons/pencil';
	import EyeOff from '@lucide/svelte/icons/eye-off';
	import Eye from '@lucide/svelte/icons/eye';
	import Cpu from '@lucide/svelte/icons/cpu';
	import UserCheck from '@lucide/svelte/icons/user-check';

	let {
		metode: m,
		bagianAplikasi,
		worker,
		dataContoh = false,
		admin = false,
		onubah,
		onalihaktif
	}: {
		metode: Metode;
		/** Nama titik uji yang mudah dibaca. */
		bagianAplikasi: string;
		/** Ketersediaan worker untuk check_id metode ini (undefined = belum ada worker yang mendukung). */
		worker?: { siap: number; total: number };
		/** true = status worker berasal dari data contoh (registri worker belum ada di backend). */
		dataContoh?: boolean;
		admin?: boolean;
		onubah?: () => void;
		onalihaktif?: () => void;
	} = $props();

	const aktif = $derived(m.aktif !== false);
	const nomor = $derived(m.id.match(/-(T\d+)$/)?.[1] ?? m.id);
	const manual = $derived(m.engine === 'manual');
	const lulusJika = $derived(m.kriteria_lulus.charAt(0).toLowerCase() + m.kriteria_lulus.slice(1));

	// Status worker: asesor (manual) / siap / sebagian / tidak ada.
	type Nada = 'hijau' | 'kuning' | 'merah' | 'abu';
	const statusWorker = $derived.by((): { nada: Nada; judul: string; ket: string } => {
		if (manual) return { nada: 'abu', judul: 'Dikerjakan asesor', ket: 'Tidak memerlukan worker; diperiksa asesor secara manual.' };
		if (!worker || worker.total === 0)
			return { nada: 'merah', judul: 'Belum ada worker', ket: 'Belum ada worker yang mendukung pemeriksa ini.' };
		if (worker.siap === 0)
			return { nada: 'merah', judul: `0 dari ${worker.total} siap`, ket: 'Worker pendukung terdaftar tetapi sedang offline.' };
		if (worker.siap < worker.total)
			return { nada: 'kuning', judul: `${worker.siap} dari ${worker.total} siap`, ket: 'Sebagian worker pendukung sedang offline.' };
		return { nada: 'hijau', judul: `${worker.siap} worker siap`, ket: 'Metode dapat dijalankan otomatis.' };
	});
	const WARNA = {
		hijau: 'border-success/40 bg-success/10 text-success',
		kuning: 'border-warning/50 bg-warning/10 text-warning-foreground',
		merah: 'border-critical/40 bg-critical/10 text-critical',
		abu: 'border-border bg-muted/50 text-muted-foreground'
	};
	const TITIK = { hijau: 'bg-success', kuning: 'bg-warning', merah: 'bg-critical', abu: 'bg-muted-foreground' };
</script>

{#snippet judulBlok(teks: string)}
	<p class="label-stensil mb-2 text-[10px] text-muted-foreground">{teks}</p>
{/snippet}

<article class={cn('overflow-hidden rounded-md border bg-background/40', !aktif && 'border-dashed opacity-70')}>
	<!-- Kepala -->
	<header class="flex items-center gap-3 border-b bg-muted/30 px-4 py-3">
		<span class="grid h-7 shrink-0 place-items-center rounded-sm bg-olive-dark px-2 font-stencil text-xs text-gold">{nomor}</span>
		<h4 class="min-w-0 flex-1 font-medium">{m.nama}</h4>
		<span
			class={cn(
				'shrink-0 rounded-sm px-1.5 py-0.5 text-[11px] font-medium',
				aktif ? 'bg-success/12 text-success' : 'bg-muted text-muted-foreground'
			)}
		>
			{aktif ? 'Aktif' : 'Nonaktif'}
		</span>
		{#if admin}
			<DropdownMenu.Root>
				<DropdownMenu.Trigger
					class="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
					aria-label="Aksi untuk {m.id}"
				>
					<Ellipsis class="size-4" />
				</DropdownMenu.Trigger>
				<DropdownMenu.Content align="end" class="w-48">
					<DropdownMenu.Item onSelect={onubah}><Pencil /> Ubah metode</DropdownMenu.Item>
					<DropdownMenu.Item onSelect={onalihaktif}>
						{#if aktif}<EyeOff /> Nonaktifkan{:else}<Eye /> Aktifkan kembali{/if}
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		{/if}
	</header>

	<!-- Kriteria lulus -->
	<div class="px-4 pt-4">
		{@render judulBlok('Kriteria lulus')}
		<p class="flex items-start gap-2 rounded-md border border-success/30 bg-success/5 px-3 py-2 text-sm">
			<CircleCheck class="mt-0.5 size-4 shrink-0 text-success" />
			<span><span class="font-medium text-success">Lulus jika</span> {lulusJika}</span>
		</p>
		{#if m.efek_samping}
			<p class="mt-2 flex items-start gap-2 rounded-md border border-warning/40 bg-warning/5 px-3 py-2 text-xs text-warning-foreground">
				<TriangleAlert class="mt-0.5 size-3.5 shrink-0" />
				<span><b class="font-semibold">Efek samping:</b> {m.efek_samping}</span>
			</p>
		{/if}
	</div>

	<!-- Pelaksanaan & Worker -->
	<div class="grid gap-4 p-4 md:grid-cols-[1fr_minmax(220px,0.8fr)]">
		<div>
			{@render judulBlok('Pelaksanaan')}
			<dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
				<dt class="text-muted-foreground">Cara uji</dt>
				<dd class="font-medium">{LABEL_JENIS[m.jenis]}</dd>
				<dt class="text-muted-foreground">Alat</dt>
				<dd class="font-medium">{LABEL_ENGINE[m.engine]}</dd>
				<dt class="text-muted-foreground">Bagian aplikasi</dt>
				<dd class="font-medium">{bagianAplikasi}</dd>
				<dt class="text-muted-foreground">Perlu login</dt>
				<dd class="font-medium">{m.butuh_autentikasi ? 'Ya, memakai akun uji' : 'Tidak'}</dd>
				<dt class="text-muted-foreground">Profil</dt>
				<dd class={cn('font-medium', m.profil === 'intrusif' && 'text-critical')}>
					{m.profil === 'intrusif' ? 'Intrusif — perlu izin' : 'Aman'}
				</dd>
				{#if m.parameter}
					<dt class="text-muted-foreground">Parameter</dt>
					<dd class="font-medium">{Object.keys(m.parameter).length} nilai diatur</dd>
				{/if}
			</dl>
		</div>

		<div class="rounded-md border bg-muted/20 p-3">
			<div class="flex items-center justify-between gap-2">
				{@render judulBlok('Worker')}
				{#if dataContoh && !manual}
					<span class="-mt-2 rounded-sm border border-dashed px-1.5 text-[10px] text-muted-foreground" title="Registri worker belum tersambung ke backend">data contoh</span>
				{/if}
			</div>
			<p class={cn('inline-flex items-center gap-2 rounded-sm border px-2 py-1 text-sm font-medium', WARNA[statusWorker.nada])}>
				{#if manual}<UserCheck class="size-4" />{:else}<span class="relative flex size-2"><span class="size-2 rounded-full {TITIK[statusWorker.nada]}"></span></span>{/if}
				{statusWorker.judul}
			</p>
			<p class="mt-2 text-xs text-muted-foreground">{statusWorker.ket}</p>
			{#if !manual}
				<p class="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
					<Cpu class="size-3.5 shrink-0" /> Pemeriksa
					<code class="truncate rounded bg-muted px-1 font-mono text-[11px] text-foreground" title={m.check_id}>{m.check_id}</code>
				</p>
			{/if}
		</div>
	</div>
</article>
