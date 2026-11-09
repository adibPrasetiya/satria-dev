<script lang="ts">
	// Panel bawah halaman operasi: tab Log Aktivitas (pewarnaan sintaks, filter level, auto-follow),
	// Temuan (metode gagal), Info & Eksekusi (diisi induk lewat snippet). Bisa diminimalkan agar kanvas
	// di atasnya mendapat ruang penuh di layar pendek.
	import type { Snippet } from 'svelte';
	import type { LogScan } from '#lib/types.js';
	import type { BarisMetode } from '#lib/operasi/ringkas.js';
	import { WARNA_SEVERITY } from '#lib/operasi/ringkas.js';
	import {
		LEVEL,
		LABEL_LEVEL,
		barisTebal,
		jamLog,
		tokenisasi,
		type Level
	} from '#lib/operasi/sorot-log.js';
	import { cn } from '#lib/utils.js';
	import TerminalIkon from '@lucide/svelte/icons/terminal';
	import Bug from '@lucide/svelte/icons/bug';
	import Info from '@lucide/svelte/icons/info';
	import Cpu from '@lucide/svelte/icons/cpu';
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';

	let {
		log,
		berjalan,
		temuan,
		info,
		eksekusi,
		onpilihTemuan,
		ciut = $bindable(false)
	}: {
		/** Diminimalkan: hanya bilah tab yang tampil (kanvas di atasnya mendapat ruang penuh). */
		ciut?: boolean;
		log: LogScan[];
		berjalan: boolean;
		temuan: BarisMetode[];
		info: Snippet;
		eksekusi: Snippet;
		onpilihTemuan?: (id: string) => void;
	} = $props();

	type Tab = 'log' | 'temuan' | 'info' | 'eksekusi';
	let tab = $state<Tab>('log');

	let filterLevel = $state<Record<Level, boolean>>({ info: true, peringatan: true, galat: true });
	const logTampil = $derived(log.filter((l) => l.pesan && filterLevel[l.level]));

	let konsol = $state<HTMLDivElement>();
	let ikut = $state(true);
	function saatGulir() {
		if (!konsol) return;
		ikut = konsol.scrollHeight - konsol.scrollTop - konsol.clientHeight < 24;
	}
	$effect(() => {
		void logTampil.length;
		void tab;
		if (konsol && ikut) queueMicrotask(() => konsol && (konsol.scrollTop = konsol.scrollHeight));
	});
	function keDasar() {
		ikut = true;
		if (konsol) konsol.scrollTop = konsol.scrollHeight;
	}

	const AKSEN: Record<Level, string> = {
		info: 'bg-[#9fe08a]',
		peringatan: 'bg-[#f6d32d]',
		galat: 'bg-[#f66151]'
	};
	const TAB: { k: Tab; label: string; Ikon: typeof Info }[] = [
		{ k: 'log', label: 'Log Aktivitas', Ikon: TerminalIkon },
		{ k: 'temuan', label: 'Temuan', Ikon: Bug },
		{ k: 'info', label: 'Info', Ikon: Info },
		{ k: 'eksekusi', label: 'Eksekusi', Ikon: Cpu }
	];
</script>

<div
	class="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-[#0f1412]"
>
	<!-- tab + aksi -->
	<div class="flex shrink-0 flex-wrap items-center gap-1 border-b border-white/10 px-2 pt-1.5">
		{#each TAB as t (t.k)}
			<button
				type="button"
				onclick={() => ((tab = t.k), (ciut = false))}
				aria-pressed={tab === t.k && !ciut}
				class={cn(
					'-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-[13px] transition',
					tab === t.k
						? 'border-[#9fe08a] text-white'
						: 'border-transparent text-white/55 hover:text-white/85'
				)}
			>
				<t.Ikon class={cn('size-4', tab === t.k && 'text-[#9fe08a]')} />
				{t.label}
				{#if t.k === 'temuan' && temuan.length}
					<span
						class="grid h-4 min-w-4 place-items-center rounded-full bg-[#e5484d] px-1 text-[10px] font-semibold text-white"
						>{temuan.length}</span
					>
				{/if}
			</button>
		{/each}
		<div class="ml-auto flex items-center gap-2 py-1">
			{#if tab === 'log' && !ciut}
				<div
					class="hidden items-center gap-0.5 rounded-md border border-white/10 bg-black/30 p-0.5 md:flex"
					role="group"
					aria-label="Filter level log"
				>
					{#each LEVEL as l (l.k)}
						<button
							type="button"
							onclick={() => (filterLevel[l.k] = !filterLevel[l.k])}
							aria-pressed={filterLevel[l.k]}
							class={cn(
								'rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold transition',
								filterLevel[l.k] ? `bg-white/10 ${l.kelas}` : 'text-white/30 hover:text-white/60'
							)}>{l.label}</button
						>
					{/each}
				</div>
			{/if}
			{#if tab === 'log' && !ciut}<span class="mx-0.5 hidden h-5 w-px bg-white/10 md:block"
				></span>{/if}
			<button
				type="button"
				onclick={() => (ciut = !ciut)}
				aria-expanded={!ciut}
				aria-label={ciut ? 'Tampilkan panel log' : 'Minimalkan panel log'}
				title={ciut ? 'Tampilkan panel log' : 'Minimalkan panel log'}
				class="grid size-8 place-items-center rounded-md border border-white/15 bg-black/30 text-white/80 hover:bg-white/5 hover:text-white"
			>
				{#if ciut}<ChevronUp class="size-4" />{:else}<ChevronDown class="size-4" />{/if}
			</button>
		</div>
	</div>

	<div class="relative min-h-0 flex-1" class:hidden={ciut}>
		{#if tab === 'log'}
			<div
				bind:this={konsol}
				onscroll={saatGulir}
				class="isi h-full overflow-y-auto py-1.5 text-[12.5px] leading-[1.6] text-[#deddda]"
			>
				{#each logTampil as l, i (i)}
					<div
						class={cn(
							'relative flex gap-4 py-px pr-3 pl-4 hover:bg-white/[0.03]',
							barisTebal(l.pesan) && 'font-bold text-white'
						)}
					>
						<span
							class={cn(
								'absolute inset-y-0 left-1.5 w-0.5 rounded-full opacity-70',
								AKSEN[l.level]
							)}
						></span>
						<span class="shrink-0 text-[#77767b] tabular-nums">{jamLog(l.waktu)}</span>
						<span class={cn('w-11 shrink-0 font-semibold', LABEL_LEVEL[l.level].kelas)}
							>{LABEL_LEVEL[l.level].label}</span
						>
						<span
							class={cn(
								'min-w-0 break-words whitespace-pre-wrap',
								l.level === 'galat' && 'text-[#f66151]',
								l.level === 'peringatan' && 'text-[#f9f06b]'
							)}
						>
							{#each tokenisasi(l.pesan) as tk, j (j)}{#if tk.k}<span class={tk.k}>{tk.t}</span
									>{:else}{tk.t}{/if}{/each}
						</span>
					</div>
				{:else}
					<p class="px-4 py-3 text-white/40">
						{berjalan ? 'Menunggu log operasi…' : 'Tidak ada baris log.'}
					</p>
				{/each}
			</div>
			{#if !ikut}
				<button
					type="button"
					onclick={keDasar}
					class="absolute right-4 bottom-3 inline-flex items-center gap-1 rounded-full border border-white/10 bg-[#1a211d] px-2.5 py-1 text-[11px] text-white/85 shadow-lg hover:bg-[#222a25]"
				>
					<ArrowDown class="size-3" /> Baris terbaru
				</button>
			{/if}
		{:else if tab === 'temuan'}
			<div class="h-full overflow-y-auto">
				{#each temuan as t (t.id)}
					<button
						type="button"
						onclick={() => onpilihTemuan?.(t.id)}
						class="flex w-full items-center gap-3 border-b border-white/5 px-4 py-2 text-left text-[13px] hover:bg-white/[0.03]"
					>
						<span
							class="w-14 shrink-0 rounded px-1.5 py-0.5 text-center text-[10px] font-semibold uppercase"
							style="color:{WARNA_SEVERITY[
								t.severity
							]};background:color-mix(in oklab,{WARNA_SEVERITY[t.severity]} 15%,transparent)"
							>{t.severity}</span
						>
						<span class="w-28 shrink-0 font-mono text-[11px] text-[#5bc8af]">{t.id}</span>
						<span class="min-w-0 flex-1">
							<span class="block truncate text-white/90">{t.nama}</span>
							{#if t.ringkasan}<span class="block truncate text-xs text-white/50"
									>{t.ringkasan}</span
								>{/if}
						</span>
					</button>
				{:else}
					<p class="px-4 py-3 text-[13px] text-white/40">
						{berjalan ? 'Belum ada temuan sejauh ini.' : 'Tidak ada temuan pada pengujian ini.'}
					</p>
				{/each}
			</div>
		{:else if tab === 'info'}
			<div class="h-full overflow-y-auto px-4 py-3">{@render info()}</div>
		{:else}
			<div class="h-full overflow-y-auto px-4 py-3">{@render eksekusi()}</div>
		{/if}
	</div>
</div>

<style>
	.isi {
		font-family:
			'Ubuntu Mono', 'Ubuntu Sans Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
	}
	.isi::-webkit-scrollbar {
		width: 10px;
	}
	.isi::-webkit-scrollbar-thumb {
		background: rgba(255, 255, 255, 0.14);
		border-radius: 9999px;
		border: 3px solid #0f1412;
	}
</style>
