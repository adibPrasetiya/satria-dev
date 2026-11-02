<script lang="ts">
	// Efek terminal "operasi siber" sebagai latar dekoratif. Satu canvas, dibatasi ±24 fps,
	// berhenti saat tab tersembunyi; statis bila prefers-reduced-motion.
	// Isi baris diambil dari katalog kontrol BSSN agar relevan dengan SATYA (bukan perintah serangan).
	import { semuaMetode } from '#lib/catalog.js';

	interface Blok {
		x: number;
		y: number;
		w: number;
		h: number;
	}

	let {
		// Blok kiri-bawah sempat dicoba, tetapi tertutup penuh oleh tubuh prajurit.
		desktop = [{ x: 50, y: 5, w: 48, h: 90 }],
		ponsel = [{ x: 3, y: 4, w: 94, h: 92 }]
	}: { desktop?: Blok[]; ponsel?: Blok[] } = $props();

	let kanvas = $state<HTMLCanvasElement>();

	const HIJAU = '#9fe08a';
	const REDUP = '#5f8f54';
	const EMAS = '#f5c451';
	const MERAH = '#ff7b6b';
	const PUTIH = '#e6f2df';

	type Segmen = [teks: string, warna: string];
	interface Baris {
		seg: Segmen[];
		panjang: number;
	}

	const acak = (n: number) => Math.floor(Math.random() * n);
	const pilih = <T,>(a: T[]) => a[acak(a.length)];
	const hex = (n: number) =>
		Array.from({ length: n }, () => acak(256).toString(16).padStart(2, '0')).join('');
	const ip = () => `10.${acak(255)}.${acak(255)}.${acak(254) + 1}`;

	function baris(seg: Segmen[]): Baris {
		return { seg, panjang: seg.reduce((n, [t]) => n + t.length, 0) };
	}

	const PERINTAH = [
		() => `satya scan --profil aman --target ${ip()}`,
		() => `satya verify --dns _satya.app-${hex(2)}.mil.id`,
		() => `sslyze --regular ${ip()}:443`,
		() => `nuclei -t exposures/ -t misconfiguration/ -silent -u https://${ip()}`,
		() => `zap-cli quick-scan --spider -r https://${ip()}/`,
		() => `playwright run auth.reset.token_single_use_expiry`,
		() => `satya report --format pdf --scan scan-${hex(3)}`
	];

	const STATUS = [
		() => `>> handshake TLSv1.3 ${pilih(['TLS_AES_256_GCM_SHA384', 'TLS_CHACHA20_POLY1305_SHA256'])} ... OK`,
		() => `>> sha256 ${hex(16)}`,
		() => `>> token sesi: ${hex(8)}… entropi ${96 + acak(64)} bit`,
		() => `>> HSTS max-age=31536000; includeSubDomains`,
		() => `>> sertifikat valid s.d. ${2027 + acak(2)}-${String(acak(12) + 1).padStart(2, '0')}-${String(acak(28) + 1).padStart(2, '0')}`,
		() => `>> redaksi data AI: aktif · ${acak(40) + 8} entitas disamarkan`
	];

	function barisBerikut(): Baris {
		const r = Math.random();
		if (r < 0.12) return baris([['$ ', EMAS], [pilih(PERINTAH)(), PUTIH]]);
		if (r < 0.55) {
			const { metode } = pilih(semuaMetode);
			const lulus = Math.random() < 0.8;
			const kiri = `[${metode.id}] ${metode.check_id} `;
			const titik = '.'.repeat(Math.max(3, 52 - kiri.length));
			return baris([
				[`[${metode.id}] `, REDUP],
				[`${metode.check_id} `, HIJAU],
				[titik + ' ', REDUP],
				lulus ? ['LULUS', HIJAU] : [`GAGAL (${metode.severity})`, MERAH]
			]);
		}
		if (r < 0.72) return baris([[`0x${hex(3)}  `, REDUP], [hex(8).replace(/(..)/g, '$1 '), HIJAU]]);
		if (r < 0.84) {
			const p = acak(101);
			const isi = Math.round(p / 10);
			return baris([
				['[', REDUP],
				['#'.repeat(isi), EMAS],
				['.'.repeat(10 - isi), REDUP],
				[`] ${String(p).padStart(3)}%  `, HIJAU],
				[pilih(semuaMetode).fungsi.nama.toLowerCase(), REDUP]
			]);
		}
		return baris([[pilih(STATUS)(), HIJAU]]);
	}

	$effect(() => {
		const c = kanvas;
		if (!c) return;
		const ctx = c.getContext('2d');
		if (!ctx) return;
		const diam = matchMedia('(prefers-reduced-motion: reduce)').matches;

		let W = 0;
		let H = 0;
		let font = 13;
		let lebarHuruf = 8;
		let tinggiBaris = 19;
		let blok: { r: Blok; isi: Baris[]; aktif: Baris; ketik: number; jeda: number; kapasitas: number }[] = [];

		function siapkan() {
			const dpr = Math.min(devicePixelRatio, 1.5);
			W = c!.clientWidth;
			H = c!.clientHeight;
			c!.width = W * dpr;
			c!.height = H * dpr;
			ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
			const kecil = W < 1024;
			font = kecil ? 10.5 : W > 1700 ? 14 : 12.5;
			tinggiBaris = Math.round(font * 1.5);
			ctx!.font = `${font}px ui-monospace, "Cascadia Mono", Consolas, monospace`;
			ctx!.textBaseline = 'top';
			lebarHuruf = ctx!.measureText('M').width;
			blok = (kecil ? ponsel : desktop).map((b) => {
				const r = { x: (b.x / 100) * W, y: (b.y / 100) * H, w: (b.w / 100) * W, h: (b.h / 100) * H };
				const kapasitas = Math.max(3, Math.floor(r.h / tinggiBaris) - 1);
				// Isi awal agar terminal tidak kosong saat halaman dibuka.
				const isi = Array.from({ length: kapasitas }, barisBerikut);
				return { r, isi, aktif: barisBerikut(), ketik: 0, jeda: 0, kapasitas };
			});
		}

		function gambarBaris(b: Baris, x: number, y: number, maksKolom: number, batas: number) {
			let kol = 0;
			for (const [teks, warna] of b.seg) {
				if (kol >= batas || kol >= maksKolom) break;
				const potong = teks.slice(0, Math.min(batas, maksKolom) - kol);
				ctx!.fillStyle = warna;
				ctx!.fillText(potong, x + kol * lebarHuruf, y);
				kol += potong.length;
			}
			return kol;
		}

		let kedip = 0;
		function gambar() {
			ctx!.clearRect(0, 0, W, H);
			kedip++;
			for (const b of blok) {
				const maksKolom = Math.floor(b.r.w / lebarHuruf);
				// Baris lama memudar ke atas (pengganti mask-image).
				for (let i = 0; i < b.isi.length; i++) {
					ctx!.globalAlpha = Math.min(1, (i + 1) / 5);
					gambarBaris(b.isi[i], b.r.x, b.r.y + i * tinggiBaris, maksKolom, Infinity);
				}
				ctx!.globalAlpha = 1;
				const y = b.r.y + b.isi.length * tinggiBaris;
				const kol = gambarBaris(b.aktif, b.r.x, y, maksKolom, b.ketik);
				if (Math.floor(kedip / 8) % 2 === 0) {
					ctx!.fillStyle = HIJAU;
					ctx!.fillRect(b.r.x + kol * lebarHuruf + 1, y + 1, lebarHuruf * 0.8, font);
				}
			}
		}

		function maju() {
			for (const b of blok) {
				if (b.jeda > 0) {
					b.jeda--;
					continue;
				}
				b.ketik += 2 + acak(4);
				if (b.ketik >= b.aktif.panjang) {
					b.isi.push(b.aktif);
					if (b.isi.length > b.kapasitas) b.isi.shift();
					b.aktif = barisBerikut();
					b.ketik = 0;
					// Perintah ($) diberi jeda lebih lama, seolah menunggu proses.
					b.jeda = b.isi[b.isi.length - 1].seg[0][0] === '$ ' ? 10 + acak(14) : acak(4);
				}
			}
		}

		siapkan();
		gambar();
		if (diam) return;

		let raf = 0;
		let terakhir = 0;
		const INTERVAL = 1000 / 24;
		function loop(t: number) {
			raf = requestAnimationFrame(loop);
			if (document.hidden || t - terakhir < INTERVAL) return;
			terakhir = t;
			maju();
			gambar();
		}
		raf = requestAnimationFrame(loop);

		const ro = new ResizeObserver(() => {
			siapkan();
			gambar();
		});
		ro.observe(c);
		return () => {
			cancelAnimationFrame(raf);
			ro.disconnect();
		};
	});
</script>

<canvas bind:this={kanvas} class="terminal absolute inset-0 size-full" aria-hidden="true"></canvas>
<div class="scanline pointer-events-none absolute inset-0" aria-hidden="true"></div>

<style>
	.terminal {
		opacity: 0.25;
		pointer-events: none;
	}
	@media (min-width: 1024px) {
		.terminal {
			opacity: 0.38;
		}
	}
	/* Garis scanline CRT statis — tanpa biaya animasi. */
	.scanline {
		background: repeating-linear-gradient(
			to bottom,
			rgb(0 0 0 / 0.16) 0 1px,
			transparent 1px 3px
		);
	}
</style>
