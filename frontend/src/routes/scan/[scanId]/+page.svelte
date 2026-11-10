<script lang="ts">
	// Halaman operasi pengujian (juga tujuan "Riwayat Pengujian"): header berjudul + tombol mode visual
	// (Rekon & Discovery / Operasi Uji), tab utama (Topologi · Detail Analisis · Temuan · Laporan
	// Sementara), kartu kanvas + panel kanan (daftar aset / daftar uji), panel log bawah, dan bilah status.
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { durasi } from '#lib/format.js';
	import type { Aplikasi, Scan } from '#lib/types.js';
	import VisualisasiPenemuan from '#lib/components/penemuan/VisualisasiPenemuan.svelte';
	import DaftarAset from '#lib/components/penemuan/DaftarAset.svelte';
	import VisualisasiUji from '#lib/components/pengujian/VisualisasiUji.svelte';
	import DaftarUji from '#lib/components/pengujian/DaftarUji.svelte';
	import PanelLog from '#lib/components/operasi/PanelLog.svelte';
	import PilihRiwayat from '#lib/components/operasi/PilihRiwayat.svelte';
	import TabDetailAnalisis from '#lib/components/operasi/TabDetailAnalisis.svelte';
	import TabTemuan from '#lib/components/operasi/TabTemuan.svelte';
	import TabLaporanSementara from '#lib/components/operasi/TabLaporanSementara.svelte';
	import { bangunUji } from '#lib/pengujian/uji.js';
	import { bangunGraf } from '#lib/penemuan/graf.js';
	import { barisMetode, daftarTemuan } from '#lib/operasi/ringkas.js';
	import { indeksMetode } from '#lib/catalog.js';
	import Memuat from '#lib/components/Memuat.svelte';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import { storeWorker, teksPerkiraan } from '#lib/stores/worker.svelte.js';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Box from '@lucide/svelte/icons/box';
	import FileText from '@lucide/svelte/icons/file-text';
	import Square from '@lucide/svelte/icons/square';
	import Network from '@lucide/svelte/icons/network';
	import Play from '@lucide/svelte/icons/play';
	import { petaTemuanTopologi, tandaiGraf } from '#lib/operasi/temuan-topologi.js';
	import ClipboardList from '@lucide/svelte/icons/clipboard-list';
	import ShieldAlert from '@lucide/svelte/icons/shield-alert';
	import ChartColumn from '@lucide/svelte/icons/chart-column';
	import ZoomIn from '@lucide/svelte/icons/zoom-in';
	import ZoomOut from '@lucide/svelte/icons/zoom-out';
	import Paskan from '@lucide/svelte/icons/scan';
	import Crosshair from '@lucide/svelte/icons/crosshair';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import Server from '@lucide/svelte/icons/server';

	const scanId = $derived(page.params.scanId!);

	let scan = $state<Scan | null>(null);
	let app = $state<Aplikasi | null>(null);
	let riwayat = $state<Scan[]>([]);
	let terkini = $state<string | null>(null);
	// Entitas terpilih — dibagi antara graf penemuan & daftar aset.
	let asetTerpilih = $state<string | null>(null);

	$effect(() => {
		const sid = scanId;
		let berhenti = () => {};
		let batal = false;
		scan = null;
		tabUtama = 'topologi';
		api.getScan(sid).then(async (s) => {
			if (batal) return;
			scan = s;
			app = await api.getAplikasi(s.aplikasi_id);
			api
				.listScan(s.aplikasi_id)
				.then((xs) => (riwayat = xs))
				.catch(() => {});
			berhenti = api.pantauScan(sid, (e) => {
				if (!scan) return;
				if (e.tipe === 'metode') {
					scan.hasil[e.hasil.metode_id] = e.hasil;
					if (e.hasil.status === 'berjalan') terkini = e.hasil.metode_id;
				} else if (e.tipe === 'log') {
					scan.log.push(e.log);
				} else if (e.tipe === 'status') {
					scan.status = e.status;
					scan.selesai_pada = e.selesai_pada;
					terkini = null;
					menghentikan = false;
					if (e.status === 'selesai') toast.success('Pengujian selesai — laporan siap ditinjau');
				} else if (e.tipe === 'worker') {
					void segarkanAntrean();
					void storeWorker.segarkan();
				}
			});
		});
		return () => {
			batal = true;
			berhenti();
		};
	});

	// Posisi antrean & worker yang mengerjakan scan ini; disegarkan berkala selama berjalan.
	async function segarkanAntrean() {
		if (!scan || scan.status !== 'berjalan') return;
		try {
			const s = await api.getScan(scan.id);
			if (scan && s.id === scan.id) scan.antrean = s.antrean;
		} catch {
			/* abaikan: banner memakai data terakhir */
		}
	}
	$effect(() => {
		if (scan?.status !== 'berjalan') return;
		const t = setInterval(() => void segarkanAntrean(), 10_000);
		return () => clearInterval(t);
	});
	$effect(() => storeWorker.pakai());

	// Jam (durasi berjalan & bilah status).
	let sekarang = $state(Date.now());
	$effect(() => {
		const t = setInterval(() => (sekarang = Date.now()), 1000);
		return () => clearInterval(t);
	});
	const jamWib = $derived(
		new Date(sekarang)
			.toLocaleTimeString('id-ID', { timeZone: 'Asia/Jakarta', hour12: false })
			.replace(/:/g, '.')
	);

	const banner = $derived.by<{ nada: 'antre' | 'jalan' | 'putus' | 'mati'; teks: string } | null>(
		() => {
			if (!scan || scan.status !== 'berjalan') return null;
			const a = scan.antrean;
			if (storeWorker.status && storeWorker.status.aktif === 0)
				return {
					nada: 'mati',
					teks: 'Tidak ada worker aktif — pengujian tertahan sampai worker dinyalakan'
				};
			if (!a) return null;
			if (a.worker)
				return {
					nada: 'jalan',
					teks: `Dikerjakan ${a.worker.id}${a.worker.tahap ? ` · ${a.worker.tahap}` : ''}`
				};
			if (a.sedang_dikerjakan)
				return { nada: 'putus', teks: 'Worker terputus — menunggu worker lain mengambil alih' };
			return {
				nada: 'antre',
				teks: `Menunggu worker — antrean ke-${a.posisi} (${teksPerkiraan(a.perkiraan_tunggu_detik)})`
			};
		}
	);
	const WARNA_BANNER = {
		antre: 'border-[#f5c451]/40 text-[#f5c451]',
		jalan: 'border-[#9fe08a]/40 text-[#9fe08a]',
		putus: 'border-[#ff7b6b]/40 text-[#ff7b6b]',
		mati: 'border-[#ff7b6b]/40 text-[#ff7b6b]'
	};

	// Fase operasi: penemuan (discovery) → pengujian → selesai. Diturunkan dari status + hasil.
	const adaUji = $derived(!!scan && Object.keys(scan.hasil).some((k) => !k.startsWith('_')));
	const fase = $derived.by<'penemuan' | 'pengujian' | 'selesai' | 'dihentikan'>(() => {
		if (!scan) return 'penemuan';
		if (scan.status === 'selesai') return 'selesai';
		if (scan.status === 'dibatalkan') return 'dihentikan';
		return adaUji ? 'pengujian' : 'penemuan';
	});

	// Recon & Discovery: dari scan ini sendiri, atau dari scan sumber yang hasil penemuannya dipakai
	// ulang (rujukan `recon_scan_id`) — data recon tidak disalin, cukup dibaca dari scan sumbernya.
	let reconSumber = $state<{ id: string; mulai: string; log: Scan['log'] } | null>(null);
	$effect(() => {
		const rid = scan?.recon_scan_id;
		const sid = scan?.id;
		reconSumber = null;
		if (!rid || rid === sid) return;
		let batal = false;
		api
			.getScan(rid)
			.then((s) => !batal && (reconSumber = { id: s.id, mulai: s.dimulai_pada, log: s.log }))
			.catch(() => {});
		return () => {
			batal = true;
		};
	});

	// Data turunan.
	const uji = $derived(scan ? bangunUji(scan.log) : { daftar: [], per: new Map() });
	const baris = $derived(scan ? barisMetode(scan) : []);
	const temuan = $derived(daftarTemuan(baris));
	const grafDasar = $derived(
		scan && app ? bangunGraf(reconSumber ? reconSumber.log : scan.log, app.url_dasar) : null
	);
	// Topologi terintegrasi hasil uji: endpoint/aset yang menjadi temuan diberi tanda.
	const graf = $derived(
		grafDasar ? tandaiGraf(grafDasar, petaTemuanTopologi(grafDasar, uji, temuan)) : null
	);
	const adaPeta = $derived(!!graf && graf.peristiwa > 0);
	const progres = $derived.by(() => {
		const jalan = baris.filter((b) => b.status !== 'tidak_berlaku' || b.durasi_ms !== undefined);
		const selesai = jalan.filter((b) => b.status !== 'antre' && b.status !== 'berjalan');
		return {
			total: jalan.length,
			selesai: selesai.length,
			persen: jalan.length ? Math.round((selesai.length / jalan.length) * 100) : 0
		};
	});
	const metodeTerkini = $derived(terkini ? indeksMetode.get(terkini) : null);

	// Pengujian yang sedang berjalan menampilkan mode live (animasi uji + log). Riwayat (selesai /
	// dihentikan) hanya menampilkan hasil: peta recon, daftar aset, dan tab hasil — tanpa animasi & log.
	const aktif = $derived(scan?.status === 'berjalan');

	// Tab: Topologi (hanya informasi topologi) · Operasi Uji (adegan pengujian, hanya saat berjalan) ·
	// Detail Analisis · Temuan · Ringkasan Hasil. Saat fase pengujian dimulai, tab berpindah otomatis ke
	// Operasi Uji sekali (pengguna tetap bebas kembali ke Topologi).
	type TabUtama = 'topologi' | 'uji' | 'detail' | 'temuan' | 'laporan';
	let tabUtama = $state<TabUtama>('topologi');
	let sudahPindahUji = false;
	$effect(() => {
		if (aktif && fase === 'pengujian' && !sudahPindahUji) {
			sudahPindahUji = true;
			if (tabUtama === 'topologi') tabUtama = 'uji';
		}
		if (!aktif && tabUtama === 'uji') tabUtama = 'topologi';
	});
	let sorotMetode = $state<string | null>(null);
	let ujiAktif = $state<string | null>(null);
	let ujiPilih = $state<string | null>(null);
	function rinciMetode(id: string) {
		sorotMetode = id;
		tabUtama = 'detail';
	}

	// Kendali kanvas graf penemuan (toolbar kartu).
	let visPeta = $state<ReturnType<typeof VisualisasiPenemuan>>();

	// Panel log: terbuka bila layar cukup tinggi agar kanvas tetap lega; di layar pendek otomatis
	// diminimalkan. Setelah pengguna menekan tombol minimize/tampilkan, pilihannya dipertahankan.
	const TINGGI_MIN_LOG = 860;
	let logCiut = $state(false);
	let logDiaturPengguna = false;
	$effect(() => {
		const sesuaikan = () => {
			if (!logDiaturPengguna) logCiut = window.innerHeight < TINGGI_MIN_LOG;
		};
		sesuaikan();
		window.addEventListener('resize', sesuaikan);
		return () => window.removeEventListener('resize', sesuaikan);
	});

	// Status DB langsung "dibatalkan"; worker berhenti di batas tahap berikutnya (sinyal via heartbeat).
	let menghentikan = $state(false);
	async function batalkan() {
		if (menghentikan) return;
		menghentikan = true;
		try {
			scan = await api.batalkanScan(scanId);
			toast.info('Pengujian dihentikan — worker berhenti pada tahap berikutnya.');
		} catch (e) {
			toast.error(e instanceof Error ? e.message : 'Gagal menghentikan pengujian');
		} finally {
			menghentikan = false;
		}
	}
	const bisaHentikan = $derived(
		!!scan &&
			!!app &&
			scan.status === 'berjalan' &&
			auth.bisaMenguji
	);

	const LABEL_STATUS_SCAN = {
		antre: 'antre',
		berjalan: 'berjalan',
		selesai: 'selesai',
		dibatalkan: 'dihentikan'
	} as const;
	const sistem = $derived(
		!storeWorker.status
			? { warna: 'bg-white/40', teks: 'Memeriksa sistem…' }
			: storeWorker.status.aktif > 0
				? { warna: 'bg-[#4ade80]', teks: 'Sistem Berjalan Normal' }
				: { warna: 'bg-[#ff7b6b]', teks: 'Worker pengujian tidak aktif' }
	);

	const TAB_UTAMA = $derived([
		{ k: 'topologi' as const, label: 'Topologi', Ikon: Network },
		...(aktif ? [{ k: 'uji' as const, label: 'Operasi Uji', Ikon: Play }] : []),
		{ k: 'detail' as const, label: 'Detail Analisis', Ikon: ClipboardList },
		{ k: 'temuan' as const, label: 'Temuan', Ikon: ShieldAlert, jumlah: temuan.length },
		{
			k: 'laporan' as const,
			label: aktif ? 'Laporan Sementara' : 'Ringkasan Hasil',
			Ikon: ChartColumn
		}
	]);
	const alatKanvas =
		'grid size-8 place-items-center rounded-md border border-white/10 bg-black/40 text-white/75 transition hover:bg-white/10 hover:text-white';
</script>

{#if !scan || !app}
	<Memuat />
{:else}
	<div
		class="dark flex flex-col gap-3 bg-[#0a0f0d] text-white lg:h-full lg:min-h-0 lg:overflow-y-auto lg:p-4"
	>
		<!-- Breadcrumb + judul + aksi -->
		<div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between lg:gap-6">
			<div class="min-w-0 flex-1">
				<nav class="flex items-center gap-1.5 text-xs text-white/55" aria-label="Breadcrumb">
					<a
						href="/aplikasi/{app.id}"
						class="grid size-5 place-items-center rounded hover:bg-white/10 hover:text-white"
						aria-label="Kembali ke berkas aplikasi"><ChevronLeft class="size-4" /></a
					>
					<a href="/dashboard" class="hover:text-white">Beranda</a>
					<ChevronRight class="size-3" />
					<a href="/aplikasi/{app.id}" class="hover:text-white">Pengujian</a>
					<ChevronRight class="size-3" />
					<span class="truncate text-white/85">Operasi {app.nama}</span>
				</nav>
				<div class="mt-2 flex items-center gap-3">
					<span
						class="grid size-11 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/5"
						><Box class="size-6 text-white/90" /></span
					>
					<div class="min-w-0">
						<h1 class="truncate text-xl font-semibold sm:text-[1.65rem]">Operasi {app.nama}</h1>
						<p class="truncate text-xs text-white/55">
							Analisis keamanan aplikasi dengan pendekatan {scan.pendekatan === 'blackbox'
								? 'Black Box'
								: 'Grey Box'} otomatis dan terintegrasi · {app.url_dasar} · {durasi(
								scan.dimulai_pada,
								scan.selesai_pada,
								sekarang
							)}
						</p>
					</div>
				</div>
			</div>

			<!-- Riwayat pengujian aplikasi + generate laporan untuk riwayat yang dipilih -->
			<div class="flex flex-wrap items-center gap-2 lg:shrink-0 lg:flex-nowrap">
				<PilihRiwayat {scan} {riwayat} />
				{#if bisaHentikan}
					<button
						type="button"
						onclick={batalkan}
						disabled={menghentikan}
						class="inline-flex h-10 items-center gap-2 rounded-xl bg-[#e0a526] px-4 text-[13.5px] font-semibold whitespace-nowrap text-black transition hover:bg-[#f0b53a] disabled:opacity-60"
					>
						<Square class="size-4 fill-current" />
						{menghentikan ? 'Menghentikan…' : 'Hentikan'}
					</button>
				{/if}
				{#if !aktif}
					<a
						href="/laporan/{scan.id}"
						title={scan.ai
							? 'Buka laporan tersimpan (riwayat terakhir)'
							: 'Susun laporan dengan AI untuk riwayat pengujian ini'}
						class="inline-flex h-10 items-center gap-2 rounded-xl bg-[#e0a526] px-4 text-[13.5px] font-semibold whitespace-nowrap text-black transition hover:bg-[#f0b53a]"
					>
						<FileText class="size-4" />
						{scan.ai ? 'Lihat Laporan' : 'Generate Laporan'}
					</a>
				{/if}
			</div>
		</div>

		<!-- Tab utama -->
		<div class="flex flex-wrap items-center gap-1 border-b border-white/10">
			{#each TAB_UTAMA as t (t.k)}
				<button
					type="button"
					onclick={() => (tabUtama = t.k)}
					aria-pressed={tabUtama === t.k}
					class={cn(
						'-mb-px inline-flex items-center gap-2 rounded-t-lg border-b-2 px-4 py-2.5 text-[13.5px] transition',
						tabUtama === t.k
							? 'border-[#4ade80] bg-[#4ade80]/[0.07] text-white'
							: 'border-transparent text-white/60 hover:text-white'
					)}
				>
					<t.Ikon class={cn('size-4', tabUtama === t.k && 'text-[#4ade80]')} />
					{t.label}
					{#if t.jumlah}
						<span
							class="grid h-4 min-w-4 place-items-center rounded-full bg-[#e5484d] px-1 text-[10px] font-semibold text-white"
							>{t.jumlah}</span
						>
					{/if}
				</button>
			{/each}
			{#if banner}
				<span
					class={cn(
						'ml-auto hidden max-w-96 items-center gap-1.5 truncate rounded-md border bg-black/40 px-2 py-1 font-mono text-[11px] md:inline-flex',
						WARNA_BANNER[banner.nada]
					)}
					title={banner.teks}
				>
					<Server class="size-3.5 shrink-0" />{banner.teks}
				</span>
			{/if}
		</div>

		<!-- Area utama -->
		<div
			class="grid min-h-0 gap-3 lg:min-h-[22rem] lg:flex-1 {tabUtama === 'topologi' ||
			tabUtama === 'uji'
				? 'lg:grid-cols-[minmax(0,1fr)_minmax(320px,26rem)]'
				: ''}"
		>
			{#if tabUtama === 'uji'}
				<!-- Adegan pengujian (hanya selama pengujian berjalan) -->
				<div
					class="relative h-[60vh] min-h-0 overflow-hidden rounded-xl border border-white/10 bg-[#0c1014] lg:h-auto"
				>
					<VisualisasiUji
						{uji}
						judul="Operasi uji"
						berjalan
						host={app.url_dasar}
						bind:dipilih={ujiPilih}
						bind:aktif={ujiAktif}
						polos
					/>
				</div>
				<div class="h-[50vh] min-h-0 lg:h-auto">
					<DaftarUji hasil={scan.hasil} aktif={ujiAktif} onpilih={(id) => (ujiPilih = id)} />
				</div>
			{:else if tabUtama === 'topologi'}
				<div
					class="relative h-[60vh] min-h-0 overflow-hidden rounded-xl border border-white/10 bg-[#0c1014] lg:h-auto"
				>
					{#if graf && adaPeta}
						{#if reconSumber}
							<p
								class="absolute right-3 bottom-3 z-20 rounded-md border border-white/10 bg-black/60 px-2.5 py-1 text-[11px] text-white/70"
								title="Pengujian ini memakai ulang hasil Recon & Discovery dari pengujian sebelumnya"
							>
								Recon dari pengujian
								<a href="/scan/{reconSumber.id}" class="text-[#4ade80] hover:underline"
									>#{reconSumber.id}</a
								>
								· {new Date(reconSumber.mulai).toLocaleDateString('id-ID', { dateStyle: 'medium' })}
							</p>
						{/if}
						<VisualisasiPenemuan
							bind:this={visPeta}
							{graf}
							berjalan={scan.status === 'berjalan'}
							host={app.url_dasar}
							bind:terpilih={asetTerpilih}
							polos
						/>
						<!-- toolbar kanvas -->
						<div class="absolute top-3 left-3 z-20 flex items-center gap-1.5">
							<button
								type="button"
								class={alatKanvas}
								onclick={() => visPeta?.perbesar()}
								aria-label="Perbesar"
								title="Perbesar"><ZoomIn class="size-4" /></button
							>
							<button
								type="button"
								class={alatKanvas}
								onclick={() => visPeta?.perkecil()}
								aria-label="Perkecil"
								title="Perkecil"><ZoomOut class="size-4" /></button
							>
							<button
								type="button"
								class={alatKanvas}
								onclick={() => visPeta?.paskan()}
								aria-label="Paskan ke layar"
								title="Paskan ke layar"><Paskan class="size-4" /></button
							>
							<button
								type="button"
								class={alatKanvas}
								onclick={() => visPeta?.pusatkan()}
								aria-label="Pusatkan"
								title="Pusatkan ke aset terpilih"><Crosshair class="size-4" /></button
							>
							<span class="mx-1 h-5 w-px bg-white/15"></span>
							<button
								type="button"
								onclick={() => visPeta?.aturUlang()}
								class="inline-flex h-8 items-center gap-1.5 rounded-md border border-white/10 bg-black/40 px-3 text-[13px] text-white/80 hover:bg-white/10 hover:text-white"
							>
								<RotateCcw class="size-3.5" /> Reset View
							</button>
						</div>
					{:else}
						<!-- Tanpa data recon (mode terarah, atau penemuan belum menghasilkan peta) -->
						<div class="grid h-full place-items-center p-6 text-center">
							<div class="max-w-sm">
								<Network class="mx-auto size-8 text-white/30" />
								<p class="mt-3 text-sm font-medium text-white/80">
									{aktif && fase === 'penemuan'
										? 'Memetakan topologi aplikasi…'
										: 'Tidak ada hasil Recon & Discovery'}
								</p>
								<p class="mt-1 text-xs text-white/50">
									{aktif && fase === 'penemuan'
										? 'Topologi tampil begitu fase penemuan menemukan aset.'
										: 'Pengujian ini dijalankan tanpa fase penemuan.'} Lihat hasil per metode di
									<button
										type="button"
										class="text-[#4ade80] hover:underline"
										onclick={() => (tabUtama = 'detail')}>Detail Analisis</button
									>.
								</p>
							</div>
						</div>
					{/if}
				</div>
				<div class="h-[50vh] min-h-0 lg:h-auto">
					{#if graf && adaPeta}
						<DaftarAset {graf} bind:terpilih={asetTerpilih} />
					{:else}
						<DaftarUji hasil={scan.hasil} aktif={ujiAktif} onpilih={(id) => (ujiPilih = id)} />
					{/if}
				</div>
			{:else}
				<div
					class="h-[70vh] min-h-0 overflow-hidden rounded-xl border border-white/10 bg-[#0f1412] lg:h-auto"
				>
					{#if tabUtama === 'detail'}
						<TabDetailAnalisis {baris} bind:sorot={sorotMetode} />
					{:else if tabUtama === 'temuan'}
						<TabTemuan {temuan} berjalan={scan.status === 'berjalan'} />
					{:else}
						<TabLaporanSementara {scan} {temuan} ondetail={() => (tabUtama = 'temuan')} />
					{/if}
				</div>
			{/if}
		</div>

		<!-- Panel log bawah: hanya saat pengujian berjalan (riwayat cukup menampilkan hasil) -->
		{#if aktif}
			<div class={cn('min-h-0 shrink-0', !logCiut && 'h-[45vh] lg:h-[30%] lg:min-h-48')}>
				<PanelLog
					bind:ciut={
						() => logCiut,
						(v) => {
							logCiut = v;
							logDiaturPengguna = true;
						}
					}
					log={scan.log}
					berjalan={scan.status === 'berjalan'}
					{temuan}
					onpilihTemuan={rinciMetode}
				>
					{#snippet info()}
						<dl class="grid gap-x-8 gap-y-2 text-[13px] sm:grid-cols-2 xl:grid-cols-3">
							{#each [['ID pengujian', `#${scan!.id}`], ['Aplikasi', app!.nama], ['Target', app!.url_dasar], ['Pendekatan', scan!.pendekatan === 'blackbox' ? 'Black Box (tanpa akun uji)' : 'Grey Box (dengan akun uji)'], ['Mode', scan!.mode === 'eksploratif' ? 'Eksploratif (penemuan otomatis)' : 'Terarah'], ['Profil', scan!.profil], ['Status', LABEL_STATUS_SCAN[scan!.status]], ['Dimulai', new Date(scan!.dimulai_pada).toLocaleString('id-ID')], ['Selesai', scan!.selesai_pada ? new Date(scan!.selesai_pada).toLocaleString('id-ID') : '—']] as [k, v] (k)}
								<div class="min-w-0">
									<dt class="text-[11px] tracking-wider text-white/45 uppercase">{k}</dt>
									<dd class="truncate text-white/85">{v}</dd>
								</div>
							{/each}
						</dl>
					{/snippet}
					{#snippet eksekusi()}
						<div class="grid gap-4 text-[13px] lg:grid-cols-[1.4fr_1fr]">
							<div>
								<p class="text-[11px] tracking-wider text-white/45 uppercase">Progres metode uji</p>
								<p class="mt-1 text-white/85">
									<span class="text-xl font-semibold tabular-nums">{progres.selesai}</span> / {progres.total}
									selesai ({progres.persen}%)
								</p>
								<div class="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
									<div
										class="h-full rounded-full bg-[#4ade80] transition-all"
										style:width="{progres.persen}%"
									></div>
								</div>
								<p class="mt-3 text-[11px] tracking-wider text-white/45 uppercase">
									Sedang dijalankan
								</p>
								<p class="mt-0.5 truncate text-white/85">
									{#if metodeTerkini}<span class="font-mono text-[#5bc8af]"
											>{metodeTerkini.metode.id}</span
										>
										— {metodeTerkini.metode.nama}
									{:else if scan!.status === 'berjalan'}{fase === 'penemuan'
											? 'Memetakan permukaan serangan (recon & discovery)…'
											: 'Menunggu metode berikutnya…'}
									{:else}—{/if}
								</p>
							</div>
							<div>
								<p class="text-[11px] tracking-wider text-white/45 uppercase">Worker & antrean</p>
								<p class="mt-1 text-white/85">
									{banner?.teks ??
										(scan!.status === 'berjalan'
											? 'Memeriksa worker…'
											: `Pengujian ${LABEL_STATUS_SCAN[scan!.status]}.`)}
								</p>
								<p class="mt-3 text-[11px] tracking-wider text-white/45 uppercase">Durasi</p>
								<p class="mt-0.5 text-white/85">
									{durasi(scan!.dimulai_pada, scan!.selesai_pada, sekarang)}
								</p>
							</div>
						</div>
					{/snippet}
				</PanelLog>
			</div>
		{/if}

		<!-- Bilah status -->
		<div
			class="flex items-center justify-between gap-3 border-t border-white/10 pt-2 text-xs text-white/55"
		>
			<span>TNI Angkatan Darat</span>
			<span class="flex items-center gap-2">
				<span class="flex items-center gap-1.5"
					><span class="size-2 rounded-full {sistem.warna}"></span>{sistem.teks}</span
				>
				<span class="text-white/20">|</span>
				<span class="font-mono tabular-nums">{jamWib} WIB</span>
			</span>
		</div>
	</div>
{/if}
