<script lang="ts" module>
	import Globe from '@lucide/svelte/icons/globe';
	import Search from '@lucide/svelte/icons/search';
	import Network from '@lucide/svelte/icons/network';
	import AppWindow from '@lucide/svelte/icons/app-window';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import Zap from '@lucide/svelte/icons/zap';
	import Sword from '@lucide/svelte/icons/sword';
	import MousePointerClick from '@lucide/svelte/icons/mouse-pointer-click';
	import FileCode from '@lucide/svelte/icons/file-code';
	import ListTree from '@lucide/svelte/icons/list-tree';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import CheckCheck from '@lucide/svelte/icons/check-check';
	import type { KodeTahap } from '#lib/penemuan/peristiwa.js';

	export const INFO_TAHAP: Record<KodeTahap, { label: string; ket: string; ikon: typeof Globe }> = {
		situs: { label: 'Akuisisi target', ket: 'Membuka situs target', ikon: Globe },
		recon: { label: 'Recon · API docs', ket: 'Menyisir jalur dokumentasi API', ikon: Search },
		crawl: { label: 'Crawl HTML', ket: 'Menelusuri halaman & tautan', ikon: Network },
		browser: { label: 'Render SPA', ket: 'Browser merender rute & menyadap XHR', ikon: AppWindow },
		login: { label: 'Login akun uji', ket: 'Masuk untuk menjelajah area terautentikasi', ikon: KeyRound },
		intersep: { label: 'Intersep aksi', ket: 'Memicu form & tombol — request mutasi dibatalkan', ikon: MousePointerClick },
		zap: { label: 'OWASP ZAP', ket: 'Spider + ajax spider + pindai pasif', ikon: Zap },
		katana: { label: 'Katana', ket: 'Crawl mendalam + parsing JavaScript', ikon: Sword },
		bundle: { label: 'Analisis bundle JS', ket: 'Mengekstrak panggilan API dari kode frontend', ikon: FileCode },
		inventaris: { label: 'Inventaris endpoint', ket: 'Menyatukan endpoint dari semua sumber', ikon: ListTree },
		ai: { label: 'Analisis AI', ket: 'Menyempurnakan kandidat uji', ikon: Sparkles },
		selesai: { label: 'Recon and Discovery selesai', ket: 'Peta permukaan serangan siap', ikon: CheckCheck }
	};
</script>

<script lang="ts">
	// Bilah status "processing" ringkas di atas-tengah: ikon tahap, label berkilau, pesan log,
	// jalur yang sedang diprobe (recon) dan stepper tahap. Tidak menutupi graf; memudar saat selesai.
	let {
		tahap,
		pesan = '',
		jalur = [],
		docs = null,
		riwayat = [],
		tepi = { atas: 0, kanan: 0 }
	}: {
		tahap: KodeTahap | null;
		pesan?: string;
		jalur?: string[];
		docs?: string | null;
		/** Kode tahap yang sudah tampil, berurutan. */
		riwayat?: KodeTahap[];
		/** Area kanvas yang tertutup toolbar/panel (px) — bilah dipusatkan di area bebas. */
		tepi?: { atas: number; kanan: number; bawah?: number };
	} = $props();

	const info = $derived(tahap ? INFO_TAHAP[tahap] : null);
	const selesai = $derived(tahap === 'selesai');

	// Recon: jalur docs yang sedang diprobe berganti satu per satu.
	const daftarJalur = $derived(jalur.length ? jalur : ['/openapi.json', '/swagger.json', '/api-docs', '/v3/api-docs', '/api/openapi.json', '/docs']);
	let idxJalur = $state(0);
	$effect(() => {
		if (tahap !== 'recon' || docs) return;
		const n = daftarJalur.length;
		const t = setInterval(() => (idxJalur = (idxJalur + 1) % n), 420);
		return () => clearInterval(t);
	});
	const detail = $derived(tahap === 'recon' && !docs ? `GET ${daftarJalur[idxJalur % daftarJalur.length]}` : tahap === 'recon' && docs ? `docs → ${docs}` : pesan.trim() || info?.ket || '');

	// Setelah selesai, bilah memudar agar peta bersih.
	let pudar = $state(false);
	$effect(() => {
		if (!selesai) {
			pudar = false;
			return;
		}
		const t = setTimeout(() => (pudar = true), 3200);
		return () => clearTimeout(t);
	});

	const URUTAN: KodeTahap[] = ['situs', 'recon', 'crawl', 'browser', 'login', 'intersep', 'zap', 'katana', 'bundle', 'inventaris', 'ai', 'selesai'];
	const langkah = $derived(URUTAN.filter((k) => riwayat.includes(k)));
</script>

{#if info}
	{@const Ikon = info.ikon}
	<div
		style:top="{tepi.atas + 56}px" style:left="calc((100% - {tepi.kanan}px) / 2)" class="pointer-events-none absolute left-1/2 z-10 w-[min(440px,calc(100%-2rem))] -translate-x-1/2 transition-opacity duration-700"
		style:opacity={pudar ? 0 : 1}
		role="status"
		aria-live="polite"
	>
		{#key tahap}
			<div class="bilah-masuk flex items-center gap-3 rounded-md border bg-black/55 px-3 py-2 backdrop-blur-sm {selesai ? 'border-[#9fe08a]/30' : 'border-[#7fe9d8]/20'}">
				<span class="relative grid size-7 shrink-0 place-items-center rounded-full border {selesai ? 'border-[#9fe08a]/50 text-[#9fe08a]' : 'border-[#7fe9d8]/40 text-[#7fe9d8]'}">
					{#if !selesai}<span class="denyut absolute inset-0 rounded-full border border-[#7fe9d8]/50"></span>{/if}
					<Ikon class="size-3.5" />
				</span>
				<div class="min-w-0 flex-1">
					<p class="flex items-baseline gap-1 font-heading text-[11px] tracking-[0.22em] uppercase">
						<span class={selesai ? 'text-[#9fe08a]' : 'kilau'}>{info.label}</span>
						{#if !selesai}<span class="titik text-[#7fe9d8]/70" aria-hidden="true"><i>.</i><i>.</i><i>.</i></span>{/if}
					</p>
					<p class="mt-0.5 truncate font-mono text-[10px] text-white/50">{detail}</p>
				</div>
				{#if langkah.length > 1 || selesai}
					<div class="flex shrink-0 items-center gap-1" aria-hidden="true">
						{#each langkah as k (k)}
							<span
								class="h-1 rounded-full transition-all {k === tahap && !selesai ? 'aktif w-3 bg-[#7fe9d8]' : 'w-1 bg-[#9fe08a]/70'}"
								title={INFO_TAHAP[k].label}
							></span>
						{/each}
					</div>
				{/if}
			</div>
		{/key}
		{#if !selesai}
			<div class="mx-3 h-px overflow-hidden bg-white/5"><div class="progres h-full w-1/4 bg-gradient-to-r from-transparent via-[#7fe9d8]/80 to-transparent"></div></div>
		{/if}
	</div>
{/if}

<style>
	.bilah-masuk { animation: masuk 0.35s ease-out both; }
	@keyframes masuk { from { opacity: 0; transform: translateY(-4px); } }
	.kilau {
		color: transparent;
		background: linear-gradient(90deg, #7fe9d8 0%, #7fe9d8 40%, #e9fffb 50%, #7fe9d8 60%, #7fe9d8 100%);
		background-size: 250% 100%;
		-webkit-background-clip: text;
		background-clip: text;
		animation: kilau 2.4s linear infinite;
	}
	@keyframes kilau { from { background-position: 100% 0; } to { background-position: -150% 0; } }
	.titik i { font-style: normal; animation: titik 1.2s infinite; opacity: 0.2; }
	.titik i:nth-child(2) { animation-delay: 0.2s; }
	.titik i:nth-child(3) { animation-delay: 0.4s; }
	@keyframes titik { 30% { opacity: 1; } 60%, 100% { opacity: 0.2; } }
	.denyut { animation: denyut 1.8s ease-out infinite; }
	@keyframes denyut { from { transform: scale(1); opacity: 0.8; } to { transform: scale(1.6); opacity: 0; } }
	.aktif { animation: aktif 1.2s ease-in-out infinite; }
	@keyframes aktif { 50% { opacity: 0.45; } }
	.progres { animation: jalan 1.6s ease-in-out infinite; }
	@keyframes jalan { from { transform: translateX(-100%); } to { transform: translateX(400%); } }
	@media (prefers-reduced-motion: reduce) {
		.bilah-masuk, .kilau, .titik i, .denyut, .aktif, .progres { animation: none; }
		.kilau { color: #7fe9d8; background: none; }
		.titik i { opacity: 0.7; }
	}
</style>
