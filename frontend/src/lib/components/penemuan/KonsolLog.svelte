<script lang="ts">
	// Terminal log operasi bergaya GNOME Terminal (Ubuntu): bilah judul `satya@ops: ~/scan/<id>`,
	// tombol jendela bulat, baris ber-label level + pewarnaan sintaks (ID metode, metode HTTP, URL,
	// status), prompt dengan kursor blok. Auto-follow hanya bila pengguna di dasar log; filter level
	// & pencarian di bilah judul. Mode dock: tombol minimize/maximize dikendalikan induk.
	import type { LogScan } from '#lib/types.js';
	import { cn } from '#lib/utils.js';
	import Search from '@lucide/svelte/icons/search';
	import Minus from '@lucide/svelte/icons/minus';
	import Square from '@lucide/svelte/icons/square';
	import Copy from '@lucide/svelte/icons/copy';
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import TerminalIkon from '@lucide/svelte/icons/square-terminal';

	let {
		log,
		berjalan,
		durasi,
		jalur = '~',
		mengambang = false,
		ciut = false,
		onminimize,
		onmaximize
	}: {
		log: LogScan[];
		berjalan: boolean;
		durasi: string;
		/** Direktori kerja pada prompt/judul, mis. `~/scan/41`. */
		jalur?: string;
		mengambang?: boolean;
		/** Mode dock diciutkan: hanya bilah judul yang tampil. */
		ciut?: boolean;
		onminimize?: () => void;
		onmaximize?: () => void;
	} = $props();

	type Level = 'info' | 'peringatan' | 'galat';
	const LEVEL: { k: Level; label: string; kelas: string }[] = [
		{ k: 'info', label: 'INFO', kelas: 'text-[#62a0ea]' },
		{ k: 'peringatan', label: 'WARN', kelas: 'text-[#f6d32d]' },
		{ k: 'galat', label: 'ERROR', kelas: 'text-[#f66151]' }
	];
	const LABEL = Object.fromEntries(LEVEL.map((l) => [l.k, l])) as Record<Level, (typeof LEVEL)[number]>;

	let filterLevel = $state<Record<Level, boolean>>({ info: true, peringatan: true, galat: true });
	let cari = $state('');
	let bukaCari = $state(false);
	const q = $derived(cari.trim().toLowerCase());
	// Baris tanpa teks = peristiwa data murni (mis. verdict animasi uji) → tak ditampilkan.
	const logTampil = $derived(log.filter((l) => l.pesan && filterLevel[l.level] && (!q || l.pesan.toLowerCase().includes(q))));

	// --- pewarnaan sintaks ---
	type Token = { t: string; k?: string };
	const RX = /(▶|■|→|←|•|↳)|(\b[A-Z]{3,5}-\d+\.\d+-T\d+\b)|(\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b)|(https?:\/\/[^\s·,)]+)|(\bHTTP \d{3}\b)|(\b(?:GAGAL|gagal|FAILED)\b)|(\b(?:Lulus|lulus|LULUS|berhasil)\b)|(\b(?:menunggu tinjauan asesor|Belum Terverifikasi|tidak_dapat_diverifikasi)\b)|(\d+(?:[.,]\d+)?\s?(?:ms|s|detik))/g;
	const KELAS = ['', 'text-[#c0bfbc]', 'font-bold text-[#5bc8af]', 'text-[#dc8add]', 'text-[#62a0ea] underline decoration-[#62a0ea]/30 underline-offset-2', '', 'font-bold text-[#f66151]', 'text-[#8ff0a4]', 'text-[#f6d32d]', 'text-[#9a9996]'];
	function warnaStatus(teks: string): string {
		const n = Number(teks.slice(5));
		return n < 300 ? 'text-[#8ff0a4]' : n < 400 ? 'text-[#f6d32d]' : n < 500 ? 'text-[#ffa348]' : 'text-[#f66151]';
	}
	function tokenisasi(s: string): Token[] {
		const out: Token[] = [];
		let i = 0;
		for (const m of s.matchAll(RX)) {
			if (m.index! > i) out.push({ t: s.slice(i, m.index) });
			const g = m.slice(1).findIndex((x) => x !== undefined) + 1;
			out.push({ t: m[0], k: g === 5 ? warnaStatus(m[0]) : KELAS[g] });
			i = m.index! + m[0].length;
		}
		if (i < s.length) out.push({ t: s.slice(i) });
		return out;
	}
	const jam = (w: string) => new Date(w).toLocaleTimeString('id-ID', { hour12: false });
	const tebal = (p: string) => /^(─|═|-{3,})|REKAPITULASI|Total metode diuji/.test(p.trim());

	// --- follow: gulir otomatis hanya saat pengguna di dasar log ---
	let konsol = $state<HTMLDivElement>();
	let ikut = $state(true);
	function saatGulir() {
		if (!konsol) return;
		ikut = konsol.scrollHeight - konsol.scrollTop - konsol.clientHeight < 24;
	}
	$effect(() => {
		void logTampil.length;
		if (konsol && ikut) queueMicrotask(() => konsol && (konsol.scrollTop = konsol.scrollHeight));
	});
	function keDasar() {
		ikut = true;
		if (konsol) konsol.scrollTop = konsol.scrollHeight;
	}
	let tersalin = $state(false);
	async function salin() {
		try {
			await navigator.clipboard.writeText(logTampil.map((l) => `${jam(l.waktu)} ${LABEL[l.level].label.padEnd(5)} ${l.pesan}`).join('\n'));
			tersalin = true;
			setTimeout(() => (tersalin = false), 1500);
		} catch {
			/* clipboard tak tersedia */
		}
	}
</script>

<div
	class={cn(
		'terminal flex h-full min-h-0 flex-col overflow-hidden',
		mengambang ? 'rounded-lg border border-black/60 shadow-[0_12px_40px_rgba(0,0,0,0.55)]' : 'rounded-lg border border-black/50'
	)}
>
	<!-- bilah judul (headerbar GNOME) -->
	<div class="relative flex h-9 shrink-0 items-center gap-2 border-b border-black/50 bg-[#2a2a2e] px-2 select-none">
		<div class="flex min-w-0 items-center gap-1.5">
			<span class="grid size-6 place-items-center rounded-md text-[#deddda]"><TerminalIkon class="size-3.5" /></span>
			<div class="hidden items-center gap-0.5 rounded-md bg-black/25 p-0.5 sm:flex" role="group" aria-label="Filter level log">
				{#each LEVEL as l (l.k)}
					<button
						type="button"
						onclick={() => (filterLevel[l.k] = !filterLevel[l.k])}
						aria-pressed={filterLevel[l.k]}
						class={cn('rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold transition', filterLevel[l.k] ? `bg-white/10 ${l.kelas}` : 'text-white/30 hover:text-white/60')}
					>{l.label}</button>
				{/each}
			</div>
		</div>

		<p class="pointer-events-none absolute inset-x-0 mx-auto w-fit max-w-[45%] truncate text-center font-[Ubuntu,ui-sans-serif,system-ui] text-[12.5px] font-semibold text-[#deddda]">
			satya@ops: {jalur}
			<span class="ml-1 font-normal text-[#9a9996]">— {durasi}</span>
		</p>

		<div class="ml-auto flex items-center gap-1">
			{#if bukaCari}
				<input
					bind:value={cari}
					placeholder="Cari di log…"
					class="h-6 w-40 rounded-md border border-white/10 bg-black/30 px-2 font-mono text-[11px] text-[#deddda] outline-none placeholder:text-white/30 focus:border-[#62a0ea]/60"
					onkeydown={(e) => e.key === 'Escape' && ((bukaCari = false), (cari = ''))}
				/>
			{/if}
			<button type="button" class="tombol" onclick={() => (bukaCari = !bukaCari)} aria-label="Cari di log" title="Cari"><Search class="size-3.5" /></button>
			<button type="button" class="tombol" onclick={salin} aria-label="Salin log" title={tersalin ? 'Tersalin' : 'Salin log'}><Copy class="size-3.5" /></button>
			{#if onminimize || onmaximize}
				<span class="mx-1 h-4 w-px bg-white/10"></span>
				{#if onminimize}
					<button type="button" class="tombol-bulat" onclick={onminimize} aria-label={ciut ? 'Pulihkan terminal' : 'Ciutkan terminal'} title={ciut ? 'Pulihkan' : 'Ciutkan'}><Minus class="size-3" /></button>
				{/if}
				{#if onmaximize}
					<button type="button" class="tombol-bulat" onclick={onmaximize} aria-label="Perbesar terminal" title="Perbesar / kecilkan"><Square class="size-2.5" /></button>
				{/if}
			{/if}
		</div>
	</div>

	{#if !ciut}
		<div class="relative min-h-0 flex-1 bg-[#1e1e1e]">
			<div bind:this={konsol} onscroll={saatGulir} class="isi h-full overflow-y-auto px-3 py-2 text-[12.5px] leading-[1.55] text-[#deddda]">
				{#each logTampil as l, i (i)}
					<div class={cn('flex gap-3 rounded-sm px-1 hover:bg-white/[0.04]', tebal(l.pesan) && 'font-bold text-white')}>
						<span class="shrink-0 text-[#77767b] tabular-nums">{jam(l.waktu)}</span>
						<span class={cn('w-11 shrink-0 font-semibold', LABEL[l.level].kelas)}>{LABEL[l.level].label}</span>
						<span class={cn('min-w-0 break-words whitespace-pre-wrap', l.level === 'galat' && 'text-[#f66151]', l.level === 'peringatan' && 'text-[#f9f06b]')}>
							{#each tokenisasi(l.pesan) as tk, j (j)}{#if tk.k}<span class={tk.k}>{tk.t}</span>{:else}{tk.t}{/if}{/each}
						</span>
					</div>
				{/each}
				{#if q && !logTampil.length}<p class="px-1 text-[#9a9996]">grep: tidak ada baris yang cocok dengan “{cari}”</p>{/if}
				<!-- prompt -->
				<p class="mt-1 px-1">
					<span class="font-bold text-[#8ae234]">satya@ops</span><span class="text-[#deddda]">:</span><span class="font-bold text-[#729fcf]">{jalur}</span><span class="text-[#deddda]">$ </span>{#if berjalan}<span class="text-[#9a9996]">tail -f operasi.log </span>{/if}<span class={cn('kursor inline-block h-[1.05em] w-[0.6em] translate-y-[2px] bg-[#deddda]', berjalan && 'kedip')}></span>
				</p>
			</div>
			{#if !ikut}
				<button type="button" onclick={keDasar} class="absolute right-4 bottom-3 inline-flex items-center gap-1 rounded-full border border-white/10 bg-[#2a2a2e] px-2.5 py-1 font-[Ubuntu,ui-sans-serif,system-ui] text-[11px] text-[#deddda] shadow-lg hover:bg-[#353539]">
					<ArrowDown class="size-3" /> Baris terbaru
				</button>
			{/if}
		</div>
	{/if}
</div>

<style>
	.terminal .isi { font-family: 'Ubuntu Mono', 'Ubuntu Sans Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
	.tombol { display: grid; place-items: center; width: 1.6rem; height: 1.6rem; border-radius: 0.375rem; color: #deddda; }
	.tombol:hover { background: rgba(255, 255, 255, 0.08); }
	.tombol-bulat { display: grid; place-items: center; width: 1.35rem; height: 1.35rem; border-radius: 9999px; background: rgba(255, 255, 255, 0.1); color: #deddda; }
	.tombol-bulat:hover { background: rgba(255, 255, 255, 0.18); }
	.kedip { animation: kedip 1.06s steps(1) infinite; }
	@keyframes kedip { 50% { opacity: 0; } }
	.isi::-webkit-scrollbar { width: 10px; }
	.isi::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.14); border-radius: 9999px; border: 3px solid #1e1e1e; }
	@media (prefers-reduced-motion: reduce) { .kedip { animation: none; } }
</style>
