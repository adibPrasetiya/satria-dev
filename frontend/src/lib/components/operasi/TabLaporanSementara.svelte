<script lang="ts">
	// Tab "Ringkasan Hasil" / "Laporan Sementara": kartu status putusan, cincin skor kepatuhan & cakupan,
	// kartu metode pengujian (Grey Box / Black Box), skor per fungsi keamanan, dan donat sebaran temuan.
	// Penilaian sementara selama pengujian berjalan; final setelah selesai.
	import { LABEL_PUTUSAN, nilaiKelaikan } from '#lib/catalog.js';
	import { durasi } from '#lib/format.js';
	import type { Scan } from '#lib/types.js';
	import { WARNA_SEVERITY, type BarisMetode } from '#lib/operasi/ringkas.js';
	import { cn } from '#lib/utils.js';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import ShieldAlert from '@lucide/svelte/icons/shield-alert';
	import ShieldX from '@lucide/svelte/icons/shield-x';
	import ChartPie from '@lucide/svelte/icons/chart-pie';
	import Code from '@lucide/svelte/icons/code';
	import Box from '@lucide/svelte/icons/box';
	import Info from '@lucide/svelte/icons/info';
	import FileBarChart from '@lucide/svelte/icons/file-chart-column';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';

	let { scan, temuan, ondetail }: { scan: Scan; temuan: BarisMetode[]; ondetail?: () => void } =
		$props();

	const n = $derived(nilaiKelaikan(scan.hasil));
	const final = $derived(scan.status === 'selesai');

	// --- Status putusan ---
	const GAYA_PUTUSAN = {
		laik: {
			warna: '#4ade80',
			latar: 'from-[#4ade80]/[0.14]',
			bingkai: 'border-[#4ade80]/30',
			Ikon: ShieldCheck
		},
		laik_bersyarat: {
			warna: '#e9cf53',
			latar: 'from-[#e9cf53]/[0.12]',
			bingkai: 'border-[#e9cf53]/30',
			Ikon: ShieldAlert
		},
		tidak_laik: {
			warna: '#ff6b6b',
			latar: 'from-[#d93f45]/[0.22]',
			bingkai: 'border-[#d93f45]/40',
			Ikon: ShieldX
		}
	} as const;
	const gp = $derived(GAYA_PUTUSAN[n.putusan]);

	// --- Cincin (skor & cakupan) ---
	const R = 34;
	const KELILING = 2 * Math.PI * R;
	const warnaSkor = (v: number) =>
		v >= 100 ? '#4ade80' : v >= 70 ? '#e9cf53' : v >= 40 ? '#f08a24' : '#d93f45';

	// --- Metode pengujian ---
	const blackbox = $derived(scan.pendekatan === 'blackbox');
	const dijalankan = $derived(
		Object.entries(scan.hasil).filter(
			([k, h]) => !k.startsWith('_') && h.status !== 'tidak_berlaku'
		).length
	);

	// --- Skor per fungsi ---
	let filterFungsi = $state<'semua' | 'perbaikan' | 'penuh'>('semua');
	const fungsiDiuji = $derived(
		n.perFungsi.filter(
			(f) => f.hitungan.lulus + f.hitungan.gagal + f.hitungan.tidak_dapat_diverifikasi > 0
		)
	);
	const fungsiTampil = $derived(
		fungsiDiuji.filter((f) =>
			filterFungsi === 'semua'
				? true
				: filterFungsi === 'penuh'
					? f.skor === 100
					: f.skor === null || f.skor < 100
		)
	);

	// --- Donat sebaran temuan (segmen dipisah celah 2px permukaan) ---
	const SEV = [
		['kritis', 'Kritis'],
		['tinggi', 'Tinggi'],
		['sedang', 'Sedang'],
		['rendah', 'Rendah']
	] as const;
	const sebaran = $derived(
		SEV.map(([k, label]) => ({ k, label, n: temuan.filter((t) => t.severity === k).length }))
	);
	const totalTemuan = $derived(temuan.length);
	const RD = 52;
	const KD = 2 * Math.PI * RD;
	const segmen = $derived.by(() => {
		let awal = 0;
		const ada = sebaran.filter((s) => s.n > 0);
		const celah = ada.length > 1 ? 3 : 0;
		return ada.map((s) => {
			const panjang = (s.n / totalTemuan) * KD;
			const seg = { ...s, dash: Math.max(0.5, panjang - celah), offset: -awal };
			awal += panjang;
			return seg;
		});
	});
	let sorotSev = $state<string | null>(null);
	const pusat = $derived(sorotSev ? sebaran.find((s) => s.k === sorotSev) : null);

	const kartu = 'rounded-xl border border-white/10 bg-[#0f1412]';
	const judulKartu = 'text-[15px] font-semibold text-white/90';
</script>

<div class="h-full overflow-y-auto p-4">
	{#if !final}
		<p
			class="mb-3 flex items-start gap-2 rounded-lg border border-[#e9cf53]/25 bg-[#e9cf53]/[0.06] px-3 py-2 text-xs text-[#e9cf53]"
		>
			<TriangleAlert class="mt-0.5 size-3.5 shrink-0" />
			{scan.status === 'dibatalkan'
				? 'Pengujian dihentikan — penilaian di bawah hanya mencakup metode yang sempat dijalankan.'
				: 'Penilaian sementara dari hasil yang sudah masuk; dapat berubah sampai pengujian selesai.'}
		</p>
	{/if}

	<!-- Baris 1: status · skor · cakupan · metode -->
	<div class="grid gap-3 sm:grid-cols-2 2xl:grid-cols-[1.3fr_1fr_1fr_1.1fr]">
		<!-- Status pengujian -->
		<div
			class={cn(
				'relative overflow-hidden rounded-xl border bg-gradient-to-br to-[#0f1412] p-5',
				gp.latar,
				gp.bingkai
			)}
		>
			<span
				class="pola-diagonal pointer-events-none absolute inset-y-0 right-0 w-40"
				aria-hidden="true"
			></span>
			<div class="relative flex items-center gap-4">
				<span
					class="grid size-14 shrink-0 place-items-center rounded-2xl border"
					style="border-color:color-mix(in oklab,{gp.warna} 45%,transparent);background:color-mix(in oklab,{gp.warna} 14%,transparent)"
				>
					<gp.Ikon class="size-8" style="color:{gp.warna}" />
				</span>
				<div class="min-w-0">
					<p class="text-xs text-white/60">Status Pengujian{final ? '' : ' (sementara)'}</p>
					<p
						class="font-heading text-2xl leading-tight font-bold tracking-wide uppercase sm:text-[1.7rem]"
						style="color:{gp.warna}"
					>
						{LABEL_PUTUSAN[n.putusan]}
					</p>
					{#each n.alasan as a, i (i)}<p class="mt-0.5 text-xs text-white/65">{a}</p>{/each}
				</div>
			</div>
		</div>

		<!-- Skor kepatuhan -->
		<div class={cn(kartu, 'flex items-center gap-4 p-5')}>
			<svg
				viewBox="0 0 84 84"
				class="size-[5.5rem] shrink-0 -rotate-90"
				role="img"
				aria-label="Skor kepatuhan {n.skor}%"
			>
				<circle
					cx="42"
					cy="42"
					r={R}
					fill="none"
					stroke="rgba(255,255,255,0.08)"
					stroke-width="7"
				/>
				<circle
					cx="42"
					cy="42"
					r={R}
					fill="none"
					stroke={warnaSkor(n.skor)}
					stroke-width="7"
					stroke-linecap="round"
					stroke-dasharray="{(n.skor / 100) * KELILING} {KELILING}"
				/>
				<text
					x="42"
					y="42"
					class="[transform-origin:42px_42px] rotate-90"
					text-anchor="middle"
					dominant-baseline="central"
					fill="white"
					font-size="17"
					font-weight="700">{n.skor}%</text
				>
			</svg>
			<div class="min-w-0">
				<p class={judulKartu}>Skor Kepatuhan</p>
				<p class="mt-1 text-xs text-white/55">Kontrol lulus dari kontrol yang teruji.</p>
			</div>
		</div>

		<!-- Cakupan pengujian -->
		<div class={cn(kartu, 'relative flex items-center gap-4 p-5')}>
			<span
				class="absolute top-3 right-3 text-white/35"
				title="Kontrol teruji (lulus + gagal) dari kontrol yang berlaku; sisanya menunggu bukti/asesor."
			>
				<Info class="size-4" />
			</span>
			<svg
				viewBox="0 0 84 84"
				class="size-[5.5rem] shrink-0 -rotate-90"
				role="img"
				aria-label="Cakupan pengujian {n.cakupan}%"
			>
				<circle
					cx="42"
					cy="42"
					r={R}
					fill="none"
					stroke="rgba(255,255,255,0.08)"
					stroke-width="7"
				/>
				<circle
					cx="42"
					cy="42"
					r={R}
					fill="none"
					stroke="#3f88de"
					stroke-width="7"
					stroke-linecap="round"
					stroke-dasharray="{(n.cakupan / 100) * KELILING} {KELILING}"
				/>
				<text
					x="42"
					y="42"
					class="[transform-origin:42px_42px] rotate-90"
					text-anchor="middle"
					dominant-baseline="central"
					fill="white"
					font-size="17"
					font-weight="700">{n.cakupan}%</text
				>
			</svg>
			<div class="min-w-0">
				<p class={judulKartu}>Cakupan Pengujian</p>
				<p class="mt-1 text-xs text-white/60 tabular-nums">
					Pass <span class="text-white">{n.hitungan.lulus}</span> · Failed
					<span class="text-[#ff6b6b]">{n.hitungan.gagal}</span>
				</p>
				<p class="text-xs text-white/60 tabular-nums">
					Belum terverifikasi <span class="text-[#e9cf53]"
						>{n.hitungan.tidak_dapat_diverifikasi}</span
					>
					· Out of scope <span class="text-white/80">{n.hitungan.luar_cakupan}</span>
				</p>
			</div>
		</div>

		<!-- Metode pengujian -->
		<div class={cn(kartu, 'flex items-center gap-4 p-5')}>
			<span class="relative grid size-14 shrink-0 place-items-center text-[#4ade80]">
				<svg viewBox="0 0 44 44" class="absolute inset-0 size-full" aria-hidden="true">
					<polygon
						points="22,2 39.3,12 39.3,32 22,42 4.7,32 4.7,12"
						fill="rgba(74,222,128,0.08)"
						stroke="currentColor"
						stroke-width="1.4"
					/>
				</svg>
				{#if blackbox}<Box class="size-6" />{:else}<Code class="size-6" />{/if}
			</span>
			<div class="min-w-0">
				<p class="text-xs text-white/60">Metode Pengujian</p>
				<p class="font-heading text-xl leading-tight font-bold tracking-wide text-white uppercase">
					{blackbox ? 'Black Box' : 'Grey Box'}
				</p>
				<p class="mt-0.5 text-xs text-white/55">
					{blackbox ? 'Tanpa akun uji & informasi internal' : 'Dengan akun uji terbatas'}
				</p>
				<p class="text-xs text-white/45">
					{scan.mode === 'eksploratif' ? 'Eksploratif' : 'Terarah'} · {dijalankan} metode · {durasi(
						scan.dimulai_pada,
						scan.selesai_pada
					)}
				</p>
			</div>
		</div>
	</div>

	<!-- Baris 2: skor per fungsi · sebaran temuan -->
	<div class="mt-3 grid gap-3 xl:grid-cols-[1.7fr_1fr]">
		<div class={cn(kartu, 'p-5')}>
			<div class="mb-4 flex items-center gap-2.5">
				<ShieldCheck class="size-5 text-[#4ade80]" />
				<p class={judulKartu}>Skor per Fungsi Keamanan</p>
				<select
					bind:value={filterFungsi}
					aria-label="Filter fungsi keamanan"
					class="ml-auto h-9 rounded-lg border border-white/10 bg-black/30 px-3 text-[13px] text-white/85 outline-none focus:border-[#4ade80]/50"
				>
					<option value="semua" class="bg-[#141a17]">Semua Fungsi</option>
					<option value="perbaikan" class="bg-[#141a17]">Perlu perbaikan</option>
					<option value="penuh" class="bg-[#141a17]">Pass penuh (100%)</option>
				</select>
			</div>
			<div class="grid gap-3.5">
				{#each fungsiTampil as f (f.fungsi.id)}
					{@const skor = f.skor ?? 0}
					<div
						class="group grid grid-cols-[3.25rem_minmax(7rem,12rem)_minmax(0,1fr)_3rem] items-center gap-3"
						title="{f.fungsi.nama}: pass {f.hitungan.lulus} · failed {f.hitungan
							.gagal} · belum terverifikasi {f.hitungan.tidak_dapat_diverifikasi} · out of scope {f.hitungan
							.luar_cakupan}"
					>
						<span
							class="rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-center font-mono text-[10.5px] text-white/70"
							>{f.fungsi.id}</span
						>
						<span class="truncate text-[13.5px] text-white/85">{f.fungsi.nama}</span>
						<span class="h-2 overflow-hidden rounded-full bg-white/[0.07]">
							<span
								class="block h-full rounded-full transition-[width] duration-500"
								style:width="{skor}%"
								style:background={f.skor === null ? 'transparent' : warnaSkor(skor)}
							></span>
						</span>
						<span class="text-right text-[13.5px] font-medium text-white/90 tabular-nums"
							>{f.skor === null ? '—' : `${f.skor}%`}</span
						>
					</div>
				{:else}
					<p class="py-4 text-sm text-white/40">
						{fungsiDiuji.length
							? 'Tidak ada fungsi yang cocok dengan filter.'
							: 'Belum ada fungsi keamanan yang teruji.'}
					</p>
				{/each}
			</div>
		</div>

		<div class={cn(kartu, 'p-5')}>
			<div class="mb-4 flex items-center gap-2.5">
				<ChartPie class="size-5 text-[#3f88de]" />
				<p class={judulKartu}>Sebaran Temuan</p>
				{#if ondetail}
					<button
						type="button"
						onclick={ondetail}
						class="ml-auto h-9 rounded-lg border border-white/10 bg-black/30 px-4 text-[13px] text-white/85 hover:bg-white/5"
						>Detail</button
					>
				{/if}
			</div>
			<div class="flex flex-wrap items-center gap-6">
				<svg
					viewBox="0 0 132 132"
					class="size-36 shrink-0 -rotate-90"
					role="img"
					aria-label="Sebaran {totalTemuan} temuan per severity"
				>
					<circle
						cx="66"
						cy="66"
						r={RD}
						fill="none"
						stroke="rgba(255,255,255,0.07)"
						stroke-width="16"
					/>
					{#each segmen as s (s.k)}
						<circle
							role="presentation"
							cx="66"
							cy="66"
							r={RD}
							fill="none"
							stroke={WARNA_SEVERITY[s.k]}
							stroke-width={sorotSev === s.k ? 19 : 16}
							stroke-dasharray="{s.dash} {KD}"
							stroke-dashoffset={s.offset}
							opacity={sorotSev && sorotSev !== s.k ? 0.35 : 1}
							class="cursor-pointer transition-all"
							onmouseenter={() => (sorotSev = s.k)}
							onmouseleave={() => (sorotSev = null)}
						/>
					{/each}
					<g class="[transform-origin:66px_66px] rotate-90">
						<text x="66" y="62" text-anchor="middle" fill="white" font-size="24" font-weight="700"
							>{pusat ? pusat.n : totalTemuan}</text
						>
						<text x="66" y="80" text-anchor="middle" fill="rgba(255,255,255,0.55)" font-size="10.5"
							>{pusat ? pusat.label : 'Temuan'}</text
						>
					</g>
				</svg>
				<ul class="min-w-36 flex-1 space-y-2.5">
					{#each sebaran as s (s.k)}
						<li
							class={cn(
								'flex items-center gap-2.5 rounded-md px-1.5 py-0.5 text-[13.5px] transition',
								sorotSev === s.k && 'bg-white/[0.05]'
							)}
							onmouseenter={() => (sorotSev = s.n ? s.k : null)}
							onmouseleave={() => (sorotSev = null)}
						>
							<span class="size-2.5 shrink-0 rounded-full" style:background={WARNA_SEVERITY[s.k]}
							></span>
							<span class="flex-1 text-white/80">{s.label}</span>
							<span class="font-semibold text-white tabular-nums">{s.n}</span>
						</li>
					{/each}
				</ul>
			</div>
			{#if final}
				<a
					href="/laporan/{scan.id}"
					class="mt-4 inline-flex items-center gap-1.5 text-sm text-[#4ade80] hover:underline"
				>
					<FileBarChart class="size-4" /> Buka laporan lengkap
				</a>
			{/if}
		</div>
	</div>
</div>

<style>
	.pola-diagonal {
		background: repeating-linear-gradient(
			-45deg,
			rgb(255 255 255 / 0.045) 0 10px,
			transparent 10px 22px
		);
		mask-image: linear-gradient(to left, black, transparent);
	}
</style>
