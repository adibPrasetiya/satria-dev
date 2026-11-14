<script lang="ts">
	// Peta Indeks Ketahanan Keamanan Siber Indonesia: batas provinsi (SVG, tanpa tile online), pendar per
	// satuan (hijau = tangguh → merah = rawan), indeks nasional di tengah atas, sorotan provinsi bergilir
	// di kanan (provinsinya ikut disorot di peta), label Kotama, skala, legenda, zoom/geser, layar penuh.
	// Selalu bertema gelap (panel taktis) apa pun tema aplikasi.
	import type { Snippet } from 'svelte';
	import { Tween } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';
	import { PETA, kmPerSatuan, kodeBentuk, proyeksi } from '#lib/peta/proyeksi.js';
	import type { Kotama, SebaranTingkat, TitikSebaran } from '#lib/peta/tipe.js';
	import type { RingkasProvinsi } from '#lib/peta/agregat.js';
	import { statusIndeks, warnaIndeks as warna } from '#lib/peta/warna.js';
	import { labelJenis, namaProvinsi } from '#lib/data/satuan.js';
	import PanelSorotan from './PanelSorotan.svelte';
	import PanelNasional from './PanelNasional.svelte';
	import PanelKerentanan from './PanelKerentanan.svelte';
	import { cn } from '#lib/utils.js';
	import Crosshair from '@lucide/svelte/icons/crosshair';
	import Plus from '@lucide/svelte/icons/plus';
	import Minus from '@lucide/svelte/icons/minus';
	import Maximize from '@lucide/svelte/icons/maximize';
	import Minimize from '@lucide/svelte/icons/minimize';

	let {
		titik,
		kotama,
		provinsi,
		nasional,
		sebaranNasional = null,
		kosong
	}: {
		titik: TitikSebaran[];
		kotama: Kotama[];
		/** Ringkasan per provinsi (urutan = urutan sorotan). */
		provinsi: RingkasProvinsi[];
		/** Indeks ketahanan rata-rata nasional. */
		nasional: number | null;
		/** Sebaran severity temuan secara nasional (dari ringkasan peta). */
		sebaranNasional?: SebaranTingkat | null;
		/** Pesan di tengah peta saat belum ada titik (memuat / galat / belum ada data). */
		kosong?: Snippet;
	} = $props();

	// ---------------------------------------------------------------------------
	// Layar penuh: Fullscreen API pada elemen peta (menyembunyikan sidebar, header, & bilah browser).
	// Bila API tidak tersedia/ditolak, peta menutupi jendela lewat CSS (fixed inset-0).
	let wadah = $state<HTMLDivElement>();
	let layarPenuh = $state(false);
	let penuhCss = $state(false);
	$effect(() => {
		const ubah = () => (layarPenuh = document.fullscreenElement === wadah);
		document.addEventListener('fullscreenchange', ubah);
		return () => document.removeEventListener('fullscreenchange', ubah);
	});
	$effect(() => {
		if (!penuhCss) return;
		const esc = (e: KeyboardEvent) => e.key === 'Escape' && (penuhCss = false);
		document.addEventListener('keydown', esc);
		return () => document.removeEventListener('keydown', esc);
	});
	async function alihLayarPenuh() {
		if (layarPenuh) return void document.exitFullscreen();
		if (penuhCss) return void (penuhCss = false);
		try {
			if (!wadah?.requestFullscreen) throw new Error('tidak didukung');
			await wadah.requestFullscreen({ navigationUI: 'hide' });
		} catch {
			penuhCss = true;
		}
	}
	const modePenuh = $derived(layarPenuh || penuhCss);

	// ---------------------------------------------------------------------------
	// Kamera: g[transform] = translate(tx, ty) scale(k). Ukuran kontainer dari bind:client*.
	let W = $state(0);
	let H = $state(0);
	let k = $state(1);
	let tx = $state(0);
	let ty = $state(0);
	let k0 = $state(1);
	/** Pengguna sudah menggeser/zoom: jangan reset kamera saat ukuran berubah. */
	let diubah = false;

	/** Lebar yang dipakai panel sorotan di kanan (layar lebar saja). */
	const ruangKanan = $derived(W >= 1024 ? 372 : 0);

	function pas() {
		if (!W || !H) return;
		const lebar = W - ruangKanan;
		// Sisakan ruang untuk indeks nasional (atas) & kontrol (bawah).
		k0 = Math.min(lebar / PETA.lebar, (H - 190) / PETA.tinggi) * 0.95;
		k = k0;
		tx = (lebar - PETA.lebar * k) / 2;
		ty = (H - PETA.tinggi * k) / 2 + 36;
		diubah = false;
	}
	$effect(() => {
		void [W, H, ruangKanan];
		if (!diubah) pas();
	});

	const K_MIN = () => k0 * 0.8;
	const K_MAKS = () => k0 * 14;
	function zoomDi(faktor: number, cx = W / 2, cy = H / 2) {
		const baru = Math.min(K_MAKS(), Math.max(K_MIN(), k * faktor));
		tx = cx - ((cx - tx) * baru) / k;
		ty = cy - ((cy - ty) * baru) / k;
		k = baru;
		diubah = true;
	}

	let svgEl = $state<SVGSVGElement>();
	let petunjukZoom = $state(false);
	let timerPetunjuk: ReturnType<typeof setTimeout> | undefined;
	// Di halaman, gulir biasa tetap menggulir halaman (ke konten di bawah peta); zoom = Ctrl/⌘ + gulir
	// (pinch touchpad juga mengirim ctrlKey). Dalam mode layar penuh gulir langsung mem-zoom.
	$effect(() => {
		const el = svgEl;
		if (!el) return;
		const roda = (e: WheelEvent) => {
			if (!modePenuh && !e.ctrlKey && !e.metaKey) {
				petunjukZoom = true;
				clearTimeout(timerPetunjuk);
				timerPetunjuk = setTimeout(() => (petunjukZoom = false), 1400);
				return;
			}
			e.preventDefault();
			petunjukZoom = false;
			const r = el.getBoundingClientRect();
			zoomDi(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
		};
		el.addEventListener('wheel', roda, { passive: false });
		return () => el.removeEventListener('wheel', roda);
	});

	let seret: { x: number; y: number; tx: number; ty: number; id: number } | null = null;
	let menyeret = $state(false);
	/** Tombol dilepas setelah menggeser: klik berikutnya bukan "pilih provinsi". */
	let barusDigeser = false;
	function turun(e: PointerEvent) {
		if (e.button !== 0) return;
		seret = { x: e.clientX, y: e.clientY, tx, ty, id: e.pointerId };
		barusDigeser = false;
	}
	function catatKursor(e: PointerEvent) {
		const r = svgEl?.getBoundingClientRect();
		if (r) kursor = { x: e.clientX - r.left, y: e.clientY - r.top };
	}
	function gerak(e: PointerEvent) {
		catatKursor(e);
		if (!seret || seret.id !== e.pointerId) return;
		const dx = e.clientX - seret.x;
		const dy = e.clientY - seret.y;
		if (!menyeret && Math.hypot(dx, dy) < 4) return;
		if (!menyeret) svgEl?.setPointerCapture(e.pointerId);
		menyeret = true;
		barusDigeser = true;
		tx = seret.tx + dx;
		ty = seret.ty + dy;
		diubah = true;
	}
	function naik(e: PointerEvent) {
		if (seret?.id === e.pointerId) seret = null;
		menyeret = false;
	}

	// ---------------------------------------------------------------------------
	// Data terproyeksi.
	const titikPeta = $derived(
		titik.map((t) => {
			const [x, y] = proyeksi(t.lng, t.lat);
			return { ...t, x, y };
		})
	);
	/**
	 * Indeks per BENTUK provinsi di peta (34 provinsi). Provinsi pemekaran yang berbagi bentuk induk
	 * (mis. Papua + Papua Selatan/Tengah/Pegunungan) digabung, tertimbang jumlah sistem informasi.
	 */
	const indeksBentuk = $derived.by(() => {
		const m = new Map<string, { total: number; bobot: number }>();
		for (const p of provinsi) {
			const kode = kodeBentuk(p.kode);
			const v = m.get(kode) ?? { total: 0, bobot: 0 };
			v.total += p.indeks * p.aplikasi;
			v.bobot += p.aplikasi;
			m.set(kode, v);
		}
		return new Map([...m].filter(([, v]) => v.bobot).map(([kode, v]) => [kode, v.total / v.bobot]));
	});
	const kotamaPeta = $derived(
		kotama.map((q) => {
			const [x, y] = proyeksi(q.lng, q.lat);
			const anggota = titik.filter((t) => t.kotama === q.id);
			const rata = anggota.length
				? Math.round(anggota.reduce((s, t) => s + t.kekuatan, 0) / anggota.length)
				: null;
			return { ...q, x, y, rata };
		})
	);
	const provinsiPerKode = $derived(new Map(provinsi.map((p) => [p.kode, p])));

	const layar = (x: number, y: number) => ({ x: x * k + tx, y: y * k + ty });
	const batasKanan = $derived(W - ruangKanan);

	// Label Kotama hanya muncul saat titik satuannya disorot kursor (peta bersih secara default).
	// Tidak tampil di balik panel.
	let sorotKotama = $state<string | null>(null);
	const label = $derived(
		kotamaPeta
			.filter((q) => sorotKotama === q.id)
			.map((q) => {
				const p = layar(q.x, q.y);
				// Kotak label di kanan-atas titik; pindah ke kiri di tepi kanan, ke bawah di separuh bawah
				// atau bila akan menabrak blok indeks di atas.
				const kanan = p.x > batasKanan * 0.72;
				const bawah = p.y > H * 0.58 || p.y - 58 < 150;
				const ujungX = p.x + (kanan ? -34 : 34);
				const ly = p.y + (bawah ? 34 : -58);
				return { ...q, p, ujungX, ly, kanan };
			})
			.filter((q) => q.p.x > -50 && q.p.x < batasKanan - 8 && q.p.y > -50 && q.p.y < H + 50)
	);

	// ---------------------------------------------------------------------------
	// Sorotan provinsi (dari panel bergilir atau klik provinsi di peta).
	let sorotKode = $state<string | null>(null);
	// Kode provinsi hasil pemekaran digambar dengan bentuk provinsi induknya (lihat kodeBentuk).
	const sorotJalur = $derived(
		sorotKode ? PETA.provinsi.find((p) => p.kode === kodeBentuk(sorotKode!))?.d : undefined
	);
	const luarSorotan = (kode: string | null) =>
		!!sorotKode && (!kode || kodeBentuk(kode) !== kodeBentuk(sorotKode));
	/** Klik bentuk provinsi / titik: sorot provinsi itu (atau provinsi pecahannya yang punya data). */
	function pilihProvinsi(kode: string | null) {
		if (barusDigeser || !kode) return;
		const cocok = provinsiPerKode.has(kode)
			? kode
			: provinsi.find((p) => kodeBentuk(p.kode) === kodeBentuk(kode))?.kode;
		if (cocok) sorotKode = cocok;
	}

	// ---------------------------------------------------------------------------
	// Indeks nasional (angka berhitung saat data diperbarui).
	const angkaNasional = new Tween(0, { duration: 900, easing: cubicOut });
	$effect(() => {
		if (nasional !== null) angkaNasional.target = nasional;
	});

	// ---------------------------------------------------------------------------
	// Tooltip & skala.
	let kursor = $state({ x: 0, y: 0 });
	let sorotTitik = $state<(typeof titikPeta)[number] | null>(null);
	let sorotProv = $state<string | null>(null);

	// Skala: panjang "bulat" terbesar yang muat ±170 px pada zoom sekarang.
	const skala = $derived.by(() => {
		const kmPerPx = kmPerSatuan(-2) / k;
		const pilihan = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000];
		const km = [...pilihan].reverse().find((v) => v / kmPerPx <= 170) ?? pilihan[0];
		return { km, px: km / kmPerPx };
	});
	const angka = (n: number) => n.toLocaleString('id-ID');
</script>

<div
	bind:this={wadah}
	class={cn(
		'peta relative h-full w-full overflow-hidden bg-[#050806] text-white select-none',
		penuhCss && 'fixed inset-0 z-50 h-svh'
	)}
	bind:clientWidth={W}
	bind:clientHeight={H}
>
	<!-- Latar: kisi halus + vinyet agar terasa seperti layar taktis. -->
	<div class="kisi pointer-events-none absolute inset-0" aria-hidden="true"></div>

	<svg
		bind:this={svgEl}
		width={W}
		height={H}
		class={cn('absolute inset-0 touch-none', menyeret ? 'cursor-grabbing' : 'cursor-grab')}
		role="img"
		aria-label="Peta indeks ketahanan keamanan siber per satuan di Indonesia"
		onpointerdown={turun}
		onpointermove={gerak}
		onpointerup={naik}
		onpointercancel={naik}
		onpointerleave={() => ((sorotTitik = null), (sorotProv = null))}
		ondblclick={(e) => {
			const r = svgEl!.getBoundingClientRect();
			zoomDi(e.shiftKey ? 0.5 : 2, e.clientX - r.left, e.clientY - r.top);
		}}
	>
		<defs>
			<filter id="peta-pendar-pantai" x="-5%" y="-5%" width="110%" height="110%">
				<feGaussianBlur stdDeviation="1.6" />
			</filter>
			<!-- Topeng peredup: seluruh daratan kecuali provinsi yang disorot. -->
			<mask id="peta-topeng-sorot" maskUnits="userSpaceOnUse">
				<rect x={-tx / k} y={-ty / k} width={W / k} height={H / k} fill="white" />
				{#if sorotJalur}<path d={sorotJalur} fill="black" />{/if}
			</mask>
		</defs>

		<g transform="translate({tx} {ty}) scale({k})" style="will-change: transform">
			<!-- Pendar garis pantai -->
			<g filter="url(#peta-pendar-pantai)" opacity="0.55">
				{#each PETA.provinsi as p (p.kode)}
					<path d={p.d} fill="none" stroke="#3f8f4a" stroke-width={2.2 / k} />
				{/each}
			</g>

			<!-- Daratan per provinsi, diwarnai penuh sesuai indeks provinsinya (tanpa data = gelap netral).
			     Klik = sorot provinsi itu di panel. -->
			{#each PETA.provinsi as p (p.kode)}
				{@const nilai = indeksBentuk.get(p.kode)}
				<path
					d={p.d}
					class="provinsi"
					fill={nilai === undefined
						? sorotProv === p.kode
							? '#16241a'
							: '#0c1510'
						: warna(nilai, sorotProv === p.kode ? 0.9 : 0.72)}
					stroke="rgb(4 7 5 / 0.85)"
					stroke-width="0.8"
					vector-effect="non-scaling-stroke"
					onpointerenter={(e) => ((sorotProv = p.kode), catatKursor(e))}
					onpointerleave={() => sorotProv === p.kode && (sorotProv = null)}
					onclick={() => pilihProvinsi(p.kode)}
					role="presentation"
				/>
			{/each}

			<!-- Titik satuan: penanda kecil netral (warna peta = warna provinsi), tooltip saat disorot. -->
			{#each titikPeta as t (t.id)}
				<circle
					cx={t.x}
					cy={t.y}
					r={(t.jenis === 'KOTAMA' ? 2.6 : 1.8) / k}
					fill="rgb(255 255 255 / 0.9)"
					stroke="rgb(0 0 0 / 0.55)"
					stroke-width={0.8 / k}
					class="titik"
					role="presentation"
					onpointerenter={(e) => ((sorotTitik = t), (sorotKotama = t.kotama), catatKursor(e))}
					onpointerleave={() => ((sorotTitik = null), (sorotKotama = null))}
				/>
				<!-- Area sentuh lebih besar dari titiknya -->
				<circle
					cx={t.x}
					cy={t.y}
					r={9 / k}
					fill="transparent"
					role="presentation"
					onpointerenter={(e) => ((sorotTitik = t), (sorotKotama = t.kotama), catatKursor(e))}
					onpointerleave={() => ((sorotTitik = null), (sorotKotama = null))}
					onclick={() => pilihProvinsi(t.provinsi_kode)}
				/>
			{/each}

			<!-- Sorotan provinsi: provinsi aktif tetap dengan warna aslinya; semua di luarnya (daratan lain,
			     pendar, titik, laut) diredupkan oleh satu lapisan bertopeng. Garis tepi netral tipis
			     hanya untuk mempertegas batasnya. -->
			{#if sorotJalur}
				<rect
					x={-tx / k}
					y={-ty / k}
					width={W / k}
					height={H / k}
					fill="rgb(4 7 5 / 0.55)"
					mask="url(#peta-topeng-sorot)"
					class="redup pointer-events-none"
				/>
				{#key sorotKode}
					<path
						d={sorotJalur}
						fill="none"
						stroke="rgb(255 255 255 / 0.7)"
						stroke-width="1"
						vector-effect="non-scaling-stroke"
						class="garis-sorot pointer-events-none"
					/>
				{/key}
			{/if}
		</g>

		<!-- Garis penunjuk label Kotama (koordinat layar) -->
		{#each label as q (q.id)}
			<g class={cn('penunjuk pointer-events-none', luarSorotan(q.provinsi_kode) && 'redup-label')}>
				<polyline
					points="{q.p.x},{q.p.y} {q.ujungX},{q.ly + 19}"
					fill="none"
					stroke="rgb(200 240 190 / 0.55)"
					stroke-width="1"
				/>
				<circle cx={q.p.x} cy={q.p.y} r="5" fill="none" stroke="rgb(200 240 190 / 0.7)" />
			</g>
		{/each}
	</svg>

	<!-- Label Kotama -->
	{#each label as q (q.id)}
		<div
			class={cn(
				'label pointer-events-none absolute w-max min-w-28 rounded-md border border-white/15 bg-black/55 px-2.5 py-1.5 backdrop-blur-sm',
				luarSorotan(q.provinsi_kode) && 'redup-label'
			)}
			style="left: {q.ujungX}px; top: {q.ly}px; transform: translateX({q.kanan ? '-100%' : '0'})"
		>
			<p class="flex items-center gap-1.5 text-[12px] leading-tight font-semibold">
				<span
					class="size-1.5 shrink-0 rounded-full"
					style="background: {q.rata === null ? '#9fe08a' : warna(q.rata)}"
				></span>
				{q.nama}
			</p>
			{#if q.sebutan}<p class="pl-3 text-[10.5px] whitespace-nowrap text-white/60 uppercase">
					({q.sebutan})
				</p>{/if}
		</div>
	{/each}

	<!-- Indeks nasional (tengah atas, di tengah area peta — bukan di balik panel) -->
	<div
		class="pointer-events-none absolute top-0 flex flex-col items-center pt-5 text-center"
		style="left: 0; width: {batasKanan}px"
	>
		<p class="text-[10.5px] font-semibold tracking-[0.28em] text-white/55 uppercase sm:text-[11px]">
			Indeks Ketahanan Keamanan Siber Nasional
		</p>
		{#if nasional !== null}
			<!-- Angka indeks & sebaran severity nasional berdampingan, ditengahkan terhadap judul. -->
			<div class="mt-3 flex items-center justify-center gap-5">
				<div class="flex flex-col items-center">
					<!-- Level kerawanan di atas angka: satu blok solid berwarna level. -->
					<span
						class="rounded-md px-3.5 py-1.5 text-[11px] leading-none font-bold tracking-[0.16em] uppercase transition-colors duration-500"
						style="color: #0a0d0b; background: {warna(nasional)}"
					>
						{statusIndeks(nasional)}
					</span>
					<p
						class="mt-2.5 font-heading text-5xl leading-none font-semibold tabular-nums sm:text-6xl"
						style="color: {warna(nasional)}"
					>
						{angkaNasional.current.toFixed(1)}
					</p>
				</div>
				{#if sebaranNasional && ruangKanan}
					<div class="pointer-events-auto w-[340px] text-left">
						<PanelNasional sebaran={sebaranNasional} />
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Kiri atas: layar penuh -->
	<div class="absolute top-4 left-4 sm:top-5 sm:left-6">
		{#if modePenuh}
			<button
				type="button"
				class="flex h-[30px] items-center gap-1.5 rounded-md border border-white/12 bg-black/50 px-2.5 text-xs font-medium text-white/80 backdrop-blur hover:bg-white/10 hover:text-white"
				onclick={alihLayarPenuh}
			>
				<Minimize class="size-3.5" /> Keluar layar penuh
				<kbd class="ml-0.5 rounded border border-white/20 px-1 font-mono text-[10px] text-white/50"
					>Esc</kbd
				>
			</button>
		{:else}
			<button
				type="button"
				class="grid size-[30px] place-items-center rounded-md border border-white/12 bg-black/50 text-white/70 backdrop-blur hover:bg-white/10 hover:text-white"
				onclick={alihLayarPenuh}
				aria-label="Layar penuh"
				title="Layar penuh"
			>
				<Maximize class="size-3.5" />
			</button>
		{/if}
	</div>

	<!-- Kanan: sorotan provinsi bergilir (layar lebar) -->
	{#if ruangKanan}
		<div
			class="absolute top-5 right-6 bottom-36 flex w-[340px] flex-col justify-start gap-3 overflow-y-auto"
		>
			<PanelSorotan daftar={provinsi} bind:kode={sorotKode} />
			<PanelKerentanan />
		</div>
	{/if}

	<!-- Kontrol kamera & skala -->
	<div class="absolute bottom-4 left-4 flex items-end gap-4 sm:bottom-6 sm:left-6">
		<div
			class="flex flex-col overflow-hidden rounded-md border border-white/12 bg-black/50 backdrop-blur"
		>
			<button type="button" class="kendali" onclick={() => zoomDi(1.6)} aria-label="Perbesar"
				><Plus class="size-4" /></button
			>
			<button
				type="button"
				class="kendali border-y border-white/10"
				onclick={() => zoomDi(1 / 1.6)}
				aria-label="Perkecil"><Minus class="size-4" /></button
			>
			<button
				type="button"
				class="kendali"
				onclick={pas}
				aria-label="Kembali ke seluruh Indonesia"
				title="Seluruh Indonesia"><Crosshair class="size-4" /></button
			>
		</div>
		<div
			class="pb-0.5 text-[10.5px] text-white/60 tabular-nums"
			aria-label="Skala {angka(skala.km)} kilometer"
		>
			<div class="relative h-2.5 border-x border-b border-white/50" style="width: {skala.px}px">
				<span class="absolute top-0 left-1/2 h-1.5 border-l border-white/50"></span>
			</div>
			<div class="relative mt-1" style="width: {skala.px}px">
				<span class="absolute left-0 -translate-x-1/2">0</span>
				<span class="absolute left-1/2 -translate-x-1/2">{angka(skala.km / 2)}</span>
				<span class="absolute right-0 translate-x-1/2 whitespace-nowrap">{angka(skala.km)} km</span>
			</div>
		</div>
	</div>

	<!-- Legenda & atribusi -->
	<div class="absolute right-4 bottom-4 flex flex-col items-end gap-2 sm:right-6 sm:bottom-6">
		{#if !ruangKanan}
			<!-- Layar sempit: intel kerentanan cukup sebagai tautan ringkas di atas legenda -->
			<PanelKerentanan ringkas />
		{/if}
		<div class="rounded-md border border-white/12 bg-black/50 px-3 py-2 backdrop-blur">
			<p class="mb-1.5 text-[10.5px] font-semibold tracking-wider text-white/60 uppercase">
				Indeks ketahanan
			</p>
			<div
				class="h-1.5 w-44 rounded-full"
				style="background: linear-gradient(90deg, {warna(0)}, {warna(35)}, {warna(55)}, {warna(
					75
				)}, {warna(100)})"
			></div>
			<div class="mt-1 flex justify-between text-[10.5px] text-white/55">
				<span>Rawan</span><span>Waspada</span><span>Tangguh</span>
			</div>
		</div>
		<p class="text-[10px] text-white/35">
			Batas wilayah © OpenStreetMap contributors (ODbL) · geoBoundaries
		</p>
	</div>

	{#if petunjukZoom}
		<div
			class="pointer-events-none absolute inset-x-0 top-1/2 flex justify-center"
			aria-hidden="true"
		>
			<p class="rounded-md bg-black/75 px-3 py-1.5 text-sm text-white/85 backdrop-blur">
				Tahan <kbd class="rounded border border-white/25 px-1 text-xs">Ctrl</kbd> sambil menggulir untuk
				memperbesar peta
			</p>
		</div>
	{/if}

	{#if !titik.length && kosong}
		<div
			class="pointer-events-none absolute top-1/2 flex -translate-y-1/2 justify-center"
			style="left: 0; width: {batasKanan}px"
		>
			<div
				class="rounded-lg border border-white/10 bg-black/70 px-5 py-4 text-center backdrop-blur"
			>
				{@render kosong()}
			</div>
		</div>
	{/if}

	<!-- Tooltip -->
	{#if sorotTitik && !menyeret}
		{@const t = sorotTitik}
		<div
			class="tooltip"
			style="left: {Math.min(kursor.x + 14, W - 236)}px; top: {Math.min(kursor.y + 14, H - 150)}px"
		>
			<p class="text-sm font-semibold">{t.nama}</p>
			<p class="text-[11px] text-white/55">
				{[labelJenis(t.jenis), kotama.find((q) => q.id === t.kotama)?.sebutan]
					.filter(Boolean)
					.join(' · ')} · {namaProvinsi(t.provinsi_kode) ?? '—'}
			</p>
			<div class="mt-2 flex items-center gap-2">
				<div class="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
					<div
						class="h-full rounded-full"
						style="width: {t.kekuatan}%; background: {warna(t.kekuatan)}"
					></div>
				</div>
				<span class="text-xs font-semibold tabular-nums" style="color: {warna(t.kekuatan)}"
					>{t.kekuatan}</span
				>
			</div>
			<p class="mt-1 text-[11px] text-white/55">
				{t.jumlah_aplikasi} sistem informasi
			</p>
		</div>
	{:else if sorotProv && !menyeret}
		{@const v = provinsiPerKode.get(sorotProv)}
		<div
			class="tooltip"
			style="left: {Math.min(kursor.x + 14, W - 236)}px; top: {Math.min(kursor.y + 14, H - 110)}px"
		>
			<p class="text-sm font-semibold">{namaProvinsi(sorotProv) ?? sorotProv}</p>
			{#if v}
				<p class="text-[11px] text-white/55">{v.satuan} satuan · {v.aplikasi} sistem informasi</p>
				<p class="mt-1 text-xs">
					Indeks ketahanan <b class="tabular-nums" style="color: {warna(v.indeks)}"
						>{v.indeks.toFixed(1)}</b
					>
				</p>
				<p class="mt-1 text-[10.5px] text-white/40">Klik untuk menyorot</p>
			{:else}
				<p class="text-[11px] text-white/55">Belum ada satuan terdata</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	.kisi {
		background-image:
			radial-gradient(ellipse at center, transparent 45%, rgb(0 0 0 / 0.65) 100%),
			linear-gradient(rgb(120 180 120 / 0.045) 1px, transparent 1px),
			linear-gradient(90deg, rgb(120 180 120 / 0.045) 1px, transparent 1px);
		background-size:
			100% 100%,
			48px 48px,
			48px 48px;
	}
	.provinsi {
		transition: fill 150ms;
		cursor: pointer;
	}
	.titik {
		cursor: pointer;
	}
	/* Peredupan & garis tepi muncul halus saat sorotan berpindah. */
	.redup {
		animation: muncul 450ms ease-out;
	}
	.garis-sorot {
		animation: muncul 450ms ease-out;
	}
	.redup-label {
		opacity: 0.3;
	}
	.label,
	.penunjuk {
		transition: opacity 300ms;
	}
	@keyframes muncul {
		from {
			opacity: 0;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.redup,
		.garis-sorot {
			animation: none;
		}
	}
	.kendali {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		color: rgb(255 255 255 / 0.7);
	}
	.kendali:hover {
		background: rgb(255 255 255 / 0.08);
		color: white;
	}
	.label {
		box-shadow:
			0 0 0 1px rgb(0 0 0 / 0.3),
			0 8px 24px rgb(0 0 0 / 0.45);
	}
	.tooltip {
		position: absolute;
		z-index: 10;
		width: 222px;
		pointer-events: none;
		border-radius: 0.5rem;
		border: 1px solid rgb(255 255 255 / 0.14);
		background: rgb(8 12 9 / 0.92);
		padding: 0.6rem 0.75rem;
		box-shadow: 0 12px 32px rgb(0 0 0 / 0.55);
		backdrop-filter: blur(6px);
	}
</style>
