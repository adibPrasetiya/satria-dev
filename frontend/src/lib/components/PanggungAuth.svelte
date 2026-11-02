<script lang="ts" module>
	export type Adegan = 'login' | 'daftar' | 'lupa';

	/** Adegan latar per halaman publik; null bila bukan halaman publik. */
	export function adeganDari(path: string | undefined): Adegan | null {
		if (!path) return null;
		if (path.startsWith('/daftar')) return 'daftar';
		// Lupa & atur ulang kata sandi satu alur pemulihan: kartu di tengah, dua prajurit mengapit.
		if (path.startsWith('/lupa-sandi') || path.startsWith('/reset-sandi')) return 'lupa';
		if (path.startsWith('/login')) return 'login';
		return null;
	}
</script>

<script lang="ts">
	// Panggung halaman publik: latar tetap hidup saat berpindah halaman, sehingga pergantian
	// adegan bisa dianimasikan seperti menu game:
	// - latar: transisi CSS (login: prajurit hijau kiri; daftar: prajurit hitam kanan;
	//   lupa: keduanya bergeser mengapit kartu di tengah);
	// - kartu: View Transitions API (kartu lama keluar, kartu baru meluncur ke posisinya; gaya di layout.css).
	import type { Snippet } from 'svelte';
	import { onNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import AuraPrajurit from './AuraPrajurit.svelte';
	import LatarKopassus from './LatarKopassus.svelte';

	let { children }: { children: Snippet } = $props();

	const adegan = $derived(adeganDari(page.url.pathname) ?? 'login');
	const lupa = $derived(adegan === 'lupa');

	onNavigate((nav) => {
		const dari = adeganDari(nav.from?.url.pathname);
		const ke = adeganDari(nav.to?.url.pathname);
		if (!dari || !ke || dari === ke || !document.startViewTransition) return;
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

		const akar = document.documentElement;
		// Mis. "login-daftar", "login-lupa"; tiap pasangan punya animasi kartu sendiri (layout.css).
		akar.dataset.arahAuth = `${dari}-${ke}`;
		return new Promise((selesai) => {
			const vt = document.startViewTransition(async () => {
				selesai();
				await nav.complete;
			});
			vt.finished.finally(() => delete akar.dataset.arahAuth);
		});
	});
</script>

<div class="relative isolate flex min-h-svh flex-col overflow-x-hidden bg-[#0d110c] text-white">
	<div class={['adegan', adegan !== 'daftar' && 'aktif', lupa && 'kanan']}>
		<AuraPrajurit aktif={adegan !== 'daftar'} />
		<!-- Gradasi keterbacaan: gelap dari kanan (desktop, kartu di kanan) dan dari bawah (ponsel). -->
		<div
			class="gradasi pointer-events-none absolute inset-0 bg-gradient-to-t from-[#0b0f09] from-40% via-[#0b0f09]/80 via-55% to-transparent to-70% lg:bg-gradient-to-l lg:from-[#0b0f09]/90 lg:from-0% lg:via-[#0b0f09]/45 lg:via-40% lg:to-transparent lg:to-65%"
		></div>
	</div>

	<div class={['adegan adegan-daftar', adegan !== 'login' && 'aktif', lupa && 'kiri']}>
		<LatarKopassus aktif={adegan !== 'login'} />
		<!-- Kartu daftar di kiri: gradasi dari kiri (desktop) dan dari bawah (ponsel). -->
		<div
			class="gradasi pointer-events-none absolute inset-0 bg-gradient-to-t from-[#0b0d0c] from-40% via-[#0b0d0c]/80 via-55% to-transparent to-70% lg:bg-gradient-to-r lg:from-[#0b0d0c]/92 lg:from-0% lg:via-[#0b0d0c]/50 lg:via-40% lg:to-transparent lg:to-65%"
		></div>
	</div>

	<!-- Adegan lupa: gelap di tengah tempat kartu, kedua prajurit tetap terlihat di sisi. -->
	<div class={['gradasi-tengah pointer-events-none absolute inset-0', lupa && 'aktif']}></div>

	{@render children()}
</div>

<style>
	.adegan {
		position: absolute;
		inset: 0;
		pointer-events: none;
		opacity: 0;
		visibility: hidden;
		/* Keluar: bergeser ke kanan sambil memudar. */
		transform: translateX(12%);
		transition:
			transform 0.8s cubic-bezier(0.5, 0, 0.75, 0),
			opacity 0.6s 0.1s ease-in,
			visibility 0s 0.8s;
	}
	/* Masuk: kembali ke posisinya dari kanan, sedikit setelah adegan lama mulai keluar. */
	.adegan.aktif {
		opacity: 1;
		visibility: visible;
		transform: none;
		transition:
			transform 1s 0.15s cubic-bezier(0.16, 1, 0.3, 1),
			opacity 0.5s 0.15s ease-out,
			visibility 0s;
	}
	/* Adegan daftar mengatur geser prajuritnya sendiri (parallax), jadi wadahnya cukup memudar. */
	.adegan-daftar,
	.adegan-daftar.aktif {
		transform: none;
	}
	.gradasi {
		transition: opacity 0.6s;
	}

	.gradasi-tengah {
		opacity: 0;
		transition: opacity 0.8s 0.1s;
		background:
			radial-gradient(ellipse 32% 70% at 50% 50%, rgb(11 15 9 / 0.85), transparent 75%),
			linear-gradient(to top, rgb(11 15 9 / 0.85), transparent 45%);
	}

	@media (min-width: 1024px) {
		/* Adegan lupa: prajurit hijau bergeser ke kanan, prajurit hitam ke kiri; tepi dalam dipudarkan
		   agar keduanya menyatu di belakang kartu. */
		.adegan.aktif.kanan {
			transform: translateX(52%);
			mask-image: linear-gradient(to right, transparent, #000 12%);
		}
		.adegan-daftar.aktif.kiri {
			transform: translateX(-48%);
			mask-image: linear-gradient(to left, transparent, #000 12%);
		}
		.kanan .gradasi,
		.kiri .gradasi {
			opacity: 0;
		}
		.gradasi-tengah.aktif {
			opacity: 1;
		}
	}
	/* Ponsel: layar terlalu sempit untuk dibelah; adegan lupa memakai latar login saja. */
	@media (max-width: 1023px) {
		.adegan.kiri {
			opacity: 0;
			visibility: hidden;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.adegan,
		.adegan.aktif,
		.adegan.aktif.kanan,
		.adegan-daftar.aktif.kiri {
			transition:
				opacity 0.3s,
				visibility 0s 0.3s;
		}
		.adegan.aktif {
			transition: opacity 0.3s;
		}
	}
</style>
