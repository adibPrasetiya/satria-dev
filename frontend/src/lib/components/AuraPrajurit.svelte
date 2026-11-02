<script lang="ts">
	import TerminalLatar from './TerminalLatar.svelte';

	// Latar login: foto prajurit + aura emas-api di sekeliling siluet.
	// Lapisan: foto -> terminal -> pendar siluet (CSS) -> lidah api & bara (canvas) -> prajurit tajam + rim light.
	// Semua lapisan memakai object-fit: cover dengan titik fokus yang sama (--fokus-x/--fokus-y)
	// sehingga potongan prajurit selalu sejajar dengan foto latar.
	const LEBAR_FOTO = 1672;
	const TINGGI_FOTO = 941;

	/** false: adegan sedang tidak tampil (mis. halaman daftar) → partikel api berhenti digambar. */
	let { aktif = true }: { aktif?: boolean } = $props();

	// Dibaca loop canvas tanpa memicu ulang efek utama. Dimatikan setelah adegan selesai memudar.
	let jalan = true;
	$effect(() => {
		if (aktif) {
			jalan = true;
			return;
		}
		const t = setTimeout(() => (jalan = false), 1100);
		return () => clearTimeout(t);
	});

	let wadah = $state<HTMLDivElement>();
	let kanvas = $state<HTMLCanvasElement>();

	interface Partikel {
		api: boolean; // true: lidah api besar; false: bara kecil
		x: number;
		y: number;
		vx: number;
		vy: number;
		umur: number;
		maks: number;
		r: number;
	}

	/** Sprite gradasi radial yang digambar ulang dengan drawImage (jauh lebih murah dari gradient per partikel). */
	function buatSprite(inti: string, tengah: string): HTMLCanvasElement {
		const s = document.createElement('canvas');
		s.width = s.height = 64;
		const g = s.getContext('2d')!;
		const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
		grad.addColorStop(0, inti);
		grad.addColorStop(0.35, tengah);
		grad.addColorStop(1, 'rgba(255,90,0,0)');
		g.fillStyle = grad;
		g.fillRect(0, 0, 64, 64);
		return s;
	}

	$effect(() => {
		if (!wadah || !kanvas) return;
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		const ctx = kanvas.getContext('2d');
		if (!ctx) return;

		const spriteApi = buatSprite('rgba(255,220,120,1)', 'rgba(255,120,10,0.6)');
		const spriteBara = buatSprite('rgba(255,250,220,1)', 'rgba(255,190,70,0.7)');

		const tepi: [number, number][] = []; // titik tepi atas siluet, koordinat foto
		let skala = 1;
		let ox = 0;
		let oy = 0;
		let target = { api: 160, bara: 70 };
		const partikel: Partikel[] = [];
		let raf = 0;
		let berhenti = false;

		// Ambil tepi atas siluet dari kanal alpha potongan (resolusi kecil sudah cukup).
		const img = new Image();
		img.src = '/login/prajurit.webp';
		img.onload = () => {
			const w = 300;
			const h = Math.round((w * TINGGI_FOTO) / LEBAR_FOTO);
			const c = document.createElement('canvas');
			c.width = w;
			c.height = h;
			const g = c.getContext('2d')!;
			g.drawImage(img, 0, 0, w, h);
			const data = g.getImageData(0, 0, w, h).data;
			for (let x = 0; x < w; x++) {
				for (let y = 0; y < h; y++) {
					if (data[(y * w + x) * 4 + 3] > 140) {
						if (y < h - 2) tepi.push([(x / w) * LEBAR_FOTO, (y / h) * TINGGI_FOTO]);
						break;
					}
				}
			}
			ukur();
			raf = requestAnimationFrame(langkah);
		};

		function ukur() {
			const dpr = Math.min(devicePixelRatio, 2);
			const W = wadah!.clientWidth;
			const H = wadah!.clientHeight;
			kanvas!.width = W * dpr;
			kanvas!.height = H * dpr;
			ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
			const gaya = getComputedStyle(wadah!);
			const fx = parseFloat(gaya.getPropertyValue('--fokus-x')) / 100;
			const fy = parseFloat(gaya.getPropertyValue('--fokus-y')) / 100;
			skala = Math.max(W / LEBAR_FOTO, H / TINGGI_FOTO);
			ox = (W - LEBAR_FOTO * skala) * fx;
			oy = (H - TINGGI_FOTO * skala) * fy;
			target = W < 640 ? { api: 70, bara: 30 } : { api: 160, bara: 70 };
		}

		function lahir(api: boolean): Partikel {
			const [x, y] = tepi[Math.floor(Math.random() * tepi.length)];
			// Ukuran mengikuti skala foto agar proporsional di layar besar/kecil.
			const k = skala * 1.6;
			return {
				api,
				x: ox + x * skala + (Math.random() - 0.5) * 8 * k,
				y: oy + y * skala + (api ? Math.random() * 10 * k : 0),
				vx: (Math.random() - 0.5) * (api ? 0.3 : 0.5),
				vy: -(api ? 0.6 + Math.random() * 1.1 : 0.5 + Math.random() * 1.4) * k,
				umur: Math.random() * 10,
				maks: api ? 35 + Math.random() * 35 : 100 + Math.random() * 120,
				r: (api ? 12 + Math.random() * 20 : 1.2 + Math.random() * 2.4) * k
			};
		}

		function langkah() {
			if (berhenti) return;
			const W = wadah!.clientWidth;
			const H = wadah!.clientHeight;
			ctx!.clearRect(0, 0, W, H);
			if (!jalan) partikel.length = 0;
			else if (tepi.length && !document.hidden) {
				let api = 0;
				for (const p of partikel) if (p.api) api++;
				for (let i = api; i < target.api; i++) partikel.push(lahir(true));
				for (let i = partikel.length - api; i < target.bara; i++) partikel.push(lahir(false));

				ctx!.globalCompositeOperation = 'lighter';
				for (let i = partikel.length - 1; i >= 0; i--) {
					const p = partikel[i];
					p.umur++;
					const t = p.umur / p.maks;
					if (t >= 1) {
						partikel.splice(i, 1);
						continue;
					}
					p.x += p.vx + Math.sin((p.umur + i * 7) * 0.08) * (p.api ? 0.35 : 0.25);
					p.y += p.vy;
					// Lidah api mengecil saat naik; bara tetap kecil dan berkedip.
					const r = p.api ? p.r * (1 - t * 0.75) : p.r;
					const a = p.api
						? (t < 0.2 ? t / 0.2 : 1 - (t - 0.2) / 0.8) * 0.5
						: (t < 0.1 ? t / 0.1 : 1 - t) * (0.6 + Math.random() * 0.4);
					ctx!.globalAlpha = a;
					ctx!.drawImage(p.api ? spriteApi : spriteBara, p.x - r, p.y - r * (p.api ? 1.4 : 1), r * 2, r * (p.api ? 2.8 : 2));
				}
				ctx!.globalAlpha = 1;
			}
			raf = requestAnimationFrame(langkah);
		}

		const ro = new ResizeObserver(ukur);
		ro.observe(wadah);
		return () => {
			berhenti = true;
			cancelAnimationFrame(raf);
			ro.disconnect();
		};
	});
</script>

<div
	bind:this={wadah}
	class="aura-wadah absolute inset-x-0 top-0 h-[64svh] overflow-hidden bg-[#141a12] lg:inset-0 lg:h-auto"
	aria-hidden="true"
>
	<div class="aura-gerak absolute inset-0">
		<img src="/login/latar.webp" alt="" class="lapisan latar" />
		<TerminalLatar />
		<img src="/login/prajurit.webp" alt="" class="lapisan aura-luar" />
		<img src="/login/prajurit.webp" alt="" class="lapisan aura-dalam" />
		<canvas bind:this={kanvas} class="absolute inset-0 size-full mix-blend-screen"></canvas>
		<img src="/login/prajurit.webp" alt="" class="lapisan prajurit" />
	</div>
</div>

<style>
	.aura-wadah {
		--fokus-x: 20%;
		--fokus-y: 0%;
	}
	@media (min-width: 1024px) {
		.aura-wadah {
			--fokus-x: 22%;
			--fokus-y: 30%;
		}
	}

	.lapisan {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: var(--fokus-x) var(--fokus-y);
		pointer-events: none;
		user-select: none;
	}

	/* Latar digelapkan dramatis agar prajurit & aura menonjol (efek sorot karakter). */
	.latar {
		filter: brightness(0.42) saturate(1.2) contrast(1.08);
	}

	/* Ken Burns pelan pada seluruh lapisan agar tetap sejajar. */
	.aura-gerak {
		transform-origin: 30% 30%;
		animation: kenburns 30s ease-in-out infinite alternate;
	}

	/* Siluet diwarnai emas-oranye, diburamkan, digoyang filter panas, lalu dibesarkan sedikit dari bawah. */
	/* Filter statis agar hasilnya di-cache GPU; gerak "kobar" hanya transform/opacity (murah).
	   Catatan: filter SVG turbulensi beranimasi sempat dicoba, tetapi menurunkan FPS ke ±19. */
	.aura-luar {
		filter: brightness(0) invert(1) sepia(1) saturate(12) hue-rotate(-24deg) blur(18px);
		transform: scale(1.05);
		will-change: transform, opacity;
		transform-origin: 30% 100%;
		mix-blend-mode: screen;
		opacity: 0;
		animation:
			muncul 1s 0.2s ease-out forwards,
			kobar 2.4s 1.2s ease-in-out infinite;
	}
	.aura-dalam {
		will-change: opacity;
		filter: brightness(0) invert(1) sepia(1) saturate(5) hue-rotate(-8deg) blur(5px);
		transform: scale(1.014);
		transform-origin: 30% 100%;
		mix-blend-mode: screen;
		opacity: 0;
		animation:
			muncul-dalam 1s 0.2s ease-out forwards,
			denyut-dalam 2.4s 1.2s ease-in-out infinite;
	}
	/* Rim light: tepi tubuh tersinari aura. */
	.prajurit {
		filter: drop-shadow(0 0 1.5px rgb(255 214 120 / 0.95)) drop-shadow(0 0 7px rgb(255 160 50 / 0.55));
	}

	@keyframes kenburns {
		from {
			transform: scale(1);
		}
		to {
			transform: scale(1.04);
		}
	}
	@keyframes muncul {
		to {
			opacity: 0.95;
		}
	}
	@keyframes muncul-dalam {
		to {
			opacity: 0.6;
		}
	}
	@keyframes kobar {
		0%,
		100% {
			opacity: 0.95;
			transform: scale(1.05, 1.05);
		}
		40% {
			opacity: 0.7;
			transform: scale(1.06, 1.075);
		}
		70% {
			opacity: 0.88;
			transform: scale(1.055, 1.06);
		}
	}
	@keyframes denyut-dalam {
		0%,
		100% {
			opacity: 0.6;
		}
		50% {
			opacity: 0.38;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.aura-gerak,
		.aura-luar,
		.aura-dalam {
			animation: none;
		}
		.aura-luar {
			opacity: 0.8;
		}
		.aura-dalam {
			opacity: 0.5;
		}
	}
</style>
