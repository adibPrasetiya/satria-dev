<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { indeksMetode } from '#lib/catalog.js';
	import { durasi } from '#lib/format.js';
	import type { Aplikasi, HasilMetode, Scan } from '#lib/types.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import VisualisasiOperasi from '#lib/components/VisualisasiOperasi.svelte';
	import VisualisasiPenemuan from '#lib/components/penemuan/VisualisasiPenemuan.svelte';
	import DaftarAset from '#lib/components/penemuan/DaftarAset.svelte';
	import KonsolLog from '#lib/components/penemuan/KonsolLog.svelte';
	import VisualisasiUji from '#lib/components/pengujian/VisualisasiUji.svelte';
	import DaftarUji from '#lib/components/pengujian/DaftarUji.svelte';
	import { bangunUji, type Uji } from '#lib/pengujian/uji.js';
	import { bangunGraf } from '#lib/penemuan/graf.js';
	import Memuat from '#lib/components/Memuat.svelte';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import Square from '@lucide/svelte/icons/square';
	import Server from '@lucide/svelte/icons/server';
	import { storeWorker, teksPerkiraan } from '#lib/stores/worker.svelte.js';
	import FileBarChart from '@lucide/svelte/icons/file-chart-column';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import PanelRightClose from '@lucide/svelte/icons/panel-right-close';
	import PanelRightOpen from '@lucide/svelte/icons/panel-right-open';
	import { onMount } from 'svelte';

	const scanId = $derived(page.params.scanId!);

	let scan = $state<Scan | null>(null);
	let app = $state<Aplikasi | null>(null);
	let terkini = $state<string | null>(null);
	// Entitas terpilih — dibagi antara graf penemuan & daftar aset.
	let asetTerpilih = $state<string | null>(null);

	$effect(() => {
		const sid = scanId;
		let berhenti = () => {};
		api.getScan(sid).then(async (s) => {
			scan = s;
			app = await api.getAplikasi(s.aplikasi_id);
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
		return () => berhenti();
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

	// Jam untuk durasi berjalan (Date.now() tidak reaktif).
	let sekarang = $state(Date.now());
	$effect(() => {
		if (scan?.status !== 'berjalan') return;
		const t = setInterval(() => (sekarang = Date.now()), 1000);
		return () => clearInterval(t);
	});

	const banner = $derived.by<{ nada: 'antre' | 'jalan' | 'putus' | 'mati'; teks: string } | null>(() => {
		if (!scan || scan.status !== 'berjalan') return null;
		const a = scan.antrean;
		if (storeWorker.status && storeWorker.status.aktif === 0) return { nada: 'mati', teks: 'Tidak ada worker aktif — pengujian tertahan sampai worker dinyalakan' };
		if (!a) return null;
		if (a.worker) return { nada: 'jalan', teks: `Dikerjakan ${a.worker.id}${a.worker.tahap ? ` · ${a.worker.tahap}` : ''}` };
		if (a.sedang_dikerjakan) return { nada: 'putus', teks: 'Worker terputus — menunggu worker lain mengambil alih' };
		return { nada: 'antre', teks: `Menunggu worker — antrean ke-${a.posisi} (${teksPerkiraan(a.perkiraan_tunggu_detik)})` };
	});
	const WARNA_BANNER = { antre: 'border-[#f5c451]/40 text-[#f5c451]', jalan: 'border-[#9fe08a]/40 text-[#9fe08a]', putus: 'border-[#ff7b6b]/40 text-[#ff7b6b]', mati: 'border-[#ff7b6b]/40 text-[#ff7b6b]' };

	const dijalankan = (h: HasilMetode) =>
		h.status === 'antre' || h.status === 'berjalan' || h.durasi_ms !== undefined || !!h.menunggu_tinjauan;

	const stat = $derived.by(() => {
		if (!scan) return null;
		const semua = Object.values(scan.hasil);
		const jalan = semua.filter(dijalankan);
		const selesai = jalan.filter((h) => h.status !== 'antre' && h.status !== 'berjalan');
		const hitung = (s: string) => semua.filter((h) => h.status === s).length;
		return {
			total: jalan.length,
			selesai: selesai.length,
			persen: jalan.length ? Math.round((selesai.length / jalan.length) * 100) : 100,
			lulus: hitung('lulus'),
			gagal: hitung('gagal'),
			tdv: hitung('tidak_dapat_diverifikasi'),
			tb: hitung('tidak_berlaku')
		};
	});

	// Fase operasi: penemuan (discovery) → pengujian → selesai. Diturunkan dari status + hasil.
	const fase = $derived.by<'penemuan' | 'pengujian' | 'selesai' | 'dihentikan'>(() => {
		if (!scan) return 'penemuan';
		if (scan.status === 'selesai') return 'selesai';
		if (scan.status === 'dibatalkan') return 'dihentikan';
		const adaUji = Object.keys(scan.hasil).some((k) => k !== '_discovery');
		return adaUji ? 'pengujian' : 'penemuan';
	});

	const metodeTerkini = $derived(terkini ? indeksMetode.get(terkini) : null);
	const sasaran = $derived(
		metodeTerkini ? `${metodeTerkini.metode.id} — ${metodeTerkini.metode.nama}` : fase === 'penemuan' && scan?.status === 'berjalan' ? 'Memetakan permukaan serangan…' : null
	);

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

	// Graf temuan penemuan, direkonstruksi dari peristiwa terstruktur pada log (live & setelah refresh).
	const graf = $derived(scan && app ? bangunGraf(scan.log, app.url_dasar) : null);
	const adaPeta = $derived(!!graf && graf.peristiwa > 0);
	// Adegan uji per fungsi (Autentikasi, Validasi Input), direkonstruksi dari peristiwa uji pada log.
	const ujiSemua = $derived(scan ? bangunUji(scan.log) : { daftar: [], per: new Map() });
	const ujiFungsi = (fungsi: string): Uji => {
		const daftar = ujiSemua.daftar.filter((m) => m.fungsi === fungsi);
		return { daftar, per: new Map(daftar.map((m) => [m.id, m])) };
	};
	const ujiAuth = $derived(ujiFungsi('AUTH'));
	const ujiInpv = $derived(ujiFungsi('INPV'));
	const ujiSess = $derived(ujiFungsi('SESS'));
	const ujiAccs = $derived(ujiFungsi('ACCS'));
	const adaAuth = $derived(!!scan && Object.keys(scan.hasil).some((k) => k.startsWith('AUTH-')));
	const adaInpv = $derived(!!scan && Object.keys(scan.hasil).some((k) => k.startsWith('INPV-')));
	const adaSess = $derived(!!scan && Object.keys(scan.hasil).some((k) => k.startsWith('SESS-')));
	const adaAccs = $derived(!!scan && Object.keys(scan.hasil).some((k) => k.startsWith('ACCS-')));
	let ujiAktif = $state<string | null>(null);
	let ujiPilih = $state<string | null>(null);

	// Tab visual: peta penemuan selama penemuan; adegan uji per fungsi saat pengujian (bila ada
	// metodenya); operasi uji (radar) untuk ringkasan. Peta tetap bisa dibuka.
	type Tab = 'peta' | 'uji' | 'inpv' | 'sess' | 'accs' | 'operasi';
	let tabPilihan = $state<Tab | null>(null);
	// Tab default mengikuti fungsi metode yang sedang berjalan, lalu fungsi mana pun yang punya hasil.
	const tabBerjalan = $derived<Tab | null>(
		terkini?.startsWith('INPV-') && adaInpv
			? 'inpv'
			: terkini?.startsWith('SESS-') && adaSess
				? 'sess'
				: terkini?.startsWith('ACCS-') && adaAccs
					? 'accs'
					: terkini?.startsWith('AUTH-') && adaAuth
						? 'uji'
						: null
	);
	const tabTersedia = $derived<Tab>(
		adaAuth ? 'uji' : adaInpv ? 'inpv' : adaSess ? 'sess' : adaAccs ? 'accs' : 'operasi'
	);
	const tab = $derived<Tab>(
		tabPilihan ??
			(fase === 'penemuan' && scan?.mode === 'eksploratif' ? 'peta' : (tabBerjalan ?? tabTersedia))
	);
	const DAFTAR_TAB = $derived(
		(
			[
				['peta', 'Recon & Discovery', adaPeta],
				['uji', 'Uji Autentikasi', adaAuth],
				['inpv', 'Uji Validasi Input', adaInpv],
				['sess', 'Uji Manajemen Sesi', adaSess],
				['accs', 'Uji Kontrol Akses', adaAccs],
				['operasi', 'Operasi Uji', true]
			] as const
		).filter(([, , ada]) => ada)
	);
	const tabUji = $derived(tab === 'uji' || tab === 'inpv' || tab === 'sess' || tab === 'accs');
	// Pemetaan tab uji → fungsi, data uji, dan judul adegan.
	const fungsiTab = $derived<'AUTH' | 'INPV' | 'SESS' | 'ACCS'>(
		tab === 'inpv' ? 'INPV' : tab === 'sess' ? 'SESS' : tab === 'accs' ? 'ACCS' : 'AUTH'
	);
	const ujiTab = $derived(tab === 'inpv' ? ujiInpv : tab === 'sess' ? ujiSess : tab === 'accs' ? ujiAccs : ujiAuth);
	const judulTab = $derived(
		{ uji: 'Uji autentikasi', inpv: 'Uji validasi input', sess: 'Uji manajemen sesi', accs: 'Uji kontrol akses' }[
			tab as 'uji' | 'inpv' | 'sess' | 'accs'
		] ?? 'Uji'
	);

	// Tata letak kanvas penuh (lg+): toolbar atas & panel kanan mengambang menutupi sebagian
	// kanvas; visualisasi diberi tahu `tepi` agar konten (fit graf, HUD) memakai area bebas.
	const ada = $derived(tabUji || (adaPeta && !!graf));
	const TOOLBAR = 48;
	const PANEL = 380;
	const KUNCI_PANEL = 'satya.panelScanCiut';
	let desktop = $state(false);
	let panelCiut = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(min-width: 1024px)');
		desktop = mq.matches;
		const ubah = (e: MediaQueryListEvent) => (desktop = e.matches);
		mq.addEventListener('change', ubah);
		try {
			panelCiut = localStorage.getItem(KUNCI_PANEL) === '1';
		} catch {
			/* penyimpanan tak tersedia */
		}
		return () => mq.removeEventListener('change', ubah);
	});
	function alihPanel() {
		panelCiut = !panelCiut;
		try {
			localStorage.setItem(KUNCI_PANEL, panelCiut ? '1' : '0');
		} catch {
			/* penyimpanan tak tersedia */
		}
	}
	// Dock terminal bawah: tinggi bisa diseret (diingat per browser), diciutkan ke bilah judul,
	// atau diperbesar sampai ±70% tinggi area.
	const KUNCI_DOCK = 'satya.tinggiDockLog';
	const JUDUL_DOCK = 36;
	let tinggiSimpan = $state(240);
	let dockCiut = $state(false);
	let dockMaks = $state(false);
	let tinggiArea = $state(800);
	const tinggiDock = $derived(dockCiut ? JUDUL_DOCK : dockMaks ? Math.round(tinggiArea * 0.7) : tinggiSimpan);
	onMount(() => {
		const ukur = () => (tinggiArea = window.innerHeight - 120);
		ukur();
		// Bawaan: ±30% tinggi area (120–260px) agar kanvas tetap lega di layar pendek.
		tinggiSimpan = Math.round(Math.min(260, Math.max(120, tinggiArea * 0.3)));
		try {
			const t = Number(localStorage.getItem(KUNCI_DOCK));
			if (t >= 120 && t <= 900) tinggiSimpan = t;
		} catch {
			/* penyimpanan tak tersedia */
		}
		window.addEventListener('resize', ukur);
		return () => window.removeEventListener('resize', ukur);
	});
	function alihMaksDock() {
		dockCiut = false;
		dockMaks = !dockMaks;
	}
	function mulaiSeret(e: PointerEvent) {
		const y0 = e.clientY;
		const t0 = tinggiDock;
		dockMaks = false;
		const gerak = (ev: PointerEvent) => {
			tinggiSimpan = Math.round(Math.min(tinggiArea * 0.8, Math.max(120, t0 + (y0 - ev.clientY))));
		};
		const lepas = () => {
			window.removeEventListener('pointermove', gerak);
			window.removeEventListener('pointerup', lepas);
			try {
				localStorage.setItem(KUNCI_DOCK, String(tinggiSimpan));
			} catch {
				/* penyimpanan tak tersedia */
			}
		};
		window.addEventListener('pointermove', gerak);
		window.addEventListener('pointerup', lepas);
	}
	const tepi = $derived(
		desktop ? { atas: TOOLBAR, kanan: ada && !panelCiut ? PANEL + 24 : 0, bawah: tinggiDock + 12 } : { atas: 0, kanan: 0, bawah: 0 }
	);

	const jumlahEndpoint = $derived.by(() => {
		if (!scan) return 0;
		if (graf?.hitung.endpoint) return graf.hitung.endpoint;
		let n = 0;
		for (const l of scan.log) {
			const m = l.pesan.match(/(\d+)\s+endpoint unik/i);
			if (m) n = Number(m[1]);
		}
		return n;
	});
</script>

{#if !scan || !app || !stat}
	<Memuat />
{:else}
	<!-- Ruang kerja operasi: kanvas penuh (lg+) dengan toolbar & panel kanan mengambang;
	     layar kecil → bertumpuk (toolbar, kanvas, panel). -->
	<div class="flex flex-col gap-4 lg:relative lg:block lg:h-full lg:w-full lg:overflow-hidden">
		<!-- Kanvas -->
		<div class="relative h-[62vh] overflow-hidden rounded-lg lg:absolute lg:inset-0 lg:h-auto lg:rounded-none">
			{#if tab === 'peta' && graf}
				<VisualisasiPenemuan {graf} berjalan={scan.status === 'berjalan'} host={app.url_dasar} bind:terpilih={asetTerpilih} {tepi} />
			{:else if tabUji}
				{#key tab}
					<VisualisasiUji
						uji={ujiTab}
						fungsi={fungsiTab}
						judul={judulTab}
						berjalan={scan.status === 'berjalan'}
						host={app.url_dasar}
						bind:dipilih={ujiPilih}
						bind:aktif={ujiAktif}
						{tepi}
					/>
				{/key}
			{:else}
				<VisualisasiOperasi
					{fase}
					berjalan={scan.status === 'berjalan'}
					persen={stat.persen}
					lulus={stat.lulus}
					gagal={stat.gagal}
					tdv={stat.tdv}
					total={stat.total}
					selesai={stat.selesai}
					endpoint={jumlahEndpoint}
					host={app.url_dasar}
					{sasaran}
					{tepi}
				/>
			{/if}
		</div>

		<!-- Toolbar -->
		<div class="order-first flex flex-wrap items-center gap-x-3 gap-y-2 lg:absolute lg:inset-x-0 lg:top-0 lg:z-30 lg:h-12 lg:flex-nowrap lg:border-b lg:border-gold/40 lg:bg-[#0c1014]/85 lg:px-3 lg:backdrop-blur-md">
			<a href="/aplikasi/{app.id}" class="inline-flex shrink-0 items-center gap-1 text-xs text-muted-foreground hover:text-foreground" title="Berkas aplikasi">
				<ChevronLeft class="size-4" /><span class="lg:hidden xl:inline">Berkas</span>
			</a>
			<div class="min-w-0">
				<p class="flex items-baseline gap-2">
					<span class="label-stensil hidden shrink-0 sm:inline">Operasi</span>
					<span class="truncate font-heading text-sm tracking-[0.08em] text-foreground uppercase">{app.nama}</span>
				</p>
				<p class="truncate font-mono text-[10px] text-muted-foreground">
					{app.url_dasar} · profil {scan.profil} · {scan.mode === 'eksploratif' ? 'eksploratif' : 'terarah'} · {durasi(scan.dimulai_pada, scan.selesai_pada, sekarang)}
				</p>
			</div>
			{#if DAFTAR_TAB.length > 1}
				<div class="flex shrink-0 gap-1">
					{#each DAFTAR_TAB as [k, l] (k)}
						<button
							type="button"
							onclick={() => (tabPilihan = k)}
							class={cn('rounded-sm border px-2.5 py-1 font-heading text-[10px] tracking-[0.2em] uppercase transition', tab === k ? 'border-[#9fe08a]/50 bg-[#9fe08a]/10 text-[#9fe08a]' : 'border-white/10 text-muted-foreground hover:text-foreground')}
						>{l}</button>
					{/each}
				</div>
			{/if}
			<div class="ml-auto flex shrink-0 items-center gap-2">
				{#if banner}
					<span class={cn('hidden max-w-80 items-center gap-1.5 truncate rounded-sm border bg-black/40 px-2 py-1 font-mono text-[10px] md:inline-flex', WARNA_BANNER[banner.nada])} title={banner.teks}>
						<Server class="size-3 shrink-0" />{banner.teks}
					</span>
				{/if}
				{#if scan.status === 'berjalan' && auth.pengguna?.id === app.pemilik_id}
					<Button size="sm" variant="destructive" onclick={batalkan} disabled={menghentikan}><Square /> {menghentikan ? 'Menghentikan…' : 'Hentikan'}</Button>
				{/if}
				{#if scan.status === 'selesai'}
					<Button size="sm" href="/laporan/{scan.id}" class="bg-gold text-gold-foreground hover:bg-gold/85"><FileBarChart /> Buka Laporan</Button>
				{/if}
				<Button
					size="icon-sm"
					variant="ghost"
					class="hidden text-muted-foreground hover:text-foreground lg:inline-flex"
					onclick={alihPanel}
					aria-label={panelCiut ? 'Tampilkan panel' : 'Sembunyikan panel'}
					title={panelCiut ? 'Tampilkan panel daftar & log' : 'Sembunyikan panel daftar & log'}
				>
					{#if panelCiut}<PanelRightOpen />{:else}<PanelRightClose />{/if}
				</Button>
			</div>
		</div>

		<!-- Panel kanan mengambang: daftar uji / daftar aset (setinggi area) -->
		{#if ada}
			<div
				class={cn('h-[45vh] min-h-0 min-w-0 lg:absolute lg:right-3 lg:z-20 lg:h-auto', panelCiut && 'lg:hidden')}
				style:top={desktop ? `${TOOLBAR + 12}px` : undefined}
				style:bottom={desktop ? '12px' : undefined}
				style:width={desktop ? `${PANEL}px` : undefined}
			>
				{#if tabUji}
					<DaftarUji
						fungsi={fungsiTab}
						hasil={scan.hasil}
						aktif={ujiAktif}
						onpilih={(id) => (ujiPilih = id)}
						mengambang={desktop}
					/>
				{:else if graf}
					<DaftarAset {graf} bind:terpilih={asetTerpilih} mengambang={desktop} />
				{/if}
			</div>
		{/if}

		<!-- Terminal log: dock bawah memanjang (lg+), bisa diubah tinggi, diciutkan & diperbesar -->
		<div
			class="h-[45vh] min-h-0 min-w-0 lg:absolute lg:left-3 lg:z-20 lg:h-auto"
			style:bottom={desktop ? '12px' : undefined}
			style:right={desktop ? `${ada && !panelCiut ? PANEL + 24 : 12}px` : undefined}
			style:height={desktop ? `${tinggiDock}px` : undefined}
		>
			{#if desktop && !dockCiut}
				<!-- pegangan ubah tinggi -->
				<div
					class="absolute inset-x-6 -top-1.5 z-10 h-3 cursor-ns-resize"
					role="separator"
					aria-orientation="horizontal"
					aria-label="Ubah tinggi terminal"
					onpointerdown={mulaiSeret}
				></div>
			{/if}
			<KonsolLog
				log={scan.log}
				berjalan={scan.status === 'berjalan'}
				durasi={durasi(scan.dimulai_pada, scan.selesai_pada, sekarang)}
				jalur="~/scan/{scan.id}"
				mengambang={desktop}
				ciut={desktop && dockCiut}
				onminimize={desktop ? () => (dockCiut = !dockCiut) : undefined}
				onmaximize={desktop ? alihMaksDock : undefined}
			/>
		</div>
	</div>
{/if}
