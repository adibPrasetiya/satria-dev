<script lang="ts" module>
	export type Adegan = 'login' | 'daftar' | 'lupa';

	/** Adegan latar per halaman publik; null bila bukan halaman publik. */
	export function adeganDari(path: string | undefined): Adegan | null {
		if (!path) return null;
		if (path.startsWith('/daftar')) return 'daftar';
		// Lupa & atur ulang kata sandi satu alur pemulihan (latar bersih seperti pendaftaran).
		if (path.startsWith('/lupa-sandi') || path.startsWith('/reset-sandi')) return 'lupa';
		if (path.startsWith('/login')) return 'login';
		return null;
	}
</script>

<script lang="ts">
	// Panggung halaman publik: latar tetap hidup saat berpindah halaman, sehingga pergantian
	// adegan bisa dianimasikan:
	// - latar: transisi CSS antara dua latar — prajurit (masuk) dan polos bertekstur topografi
	//   (daftar, lupa & atur ulang kata sandi);
	// - isian: View Transitions API (lama keluar, baru meluncur ke posisinya; gaya di layout.css).
	import type { Snippet } from 'svelte';
	import { onNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import AuraPrajurit from './AuraPrajurit.svelte';

	let { children }: { children: Snippet } = $props();

	const adegan = $derived(adeganDari(page.url.pathname) ?? 'login');
	const masuk = $derived(adegan === 'login');

	onNavigate((nav) => {
		const dari = adeganDari(nav.from?.url.pathname);
		const ke = adeganDari(nav.to?.url.pathname);
		if (!dari || !ke || dari === ke || !document.startViewTransition) return;
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

		const akar = document.documentElement;
		// Mis. "login-daftar", "login-lupa"; tiap pasangan punya animasi sendiri (layout.css).
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
	<!-- Adegan masuk: foto prajurit (panel isian di kanan). -->
	<div class={['adegan', masuk && 'aktif']}>
		<AuraPrajurit />
		<!-- Gradasi keterbacaan: gelap dari kanan (desktop) dan dari bawah (ponsel). -->
		<div
			class="pointer-events-none absolute inset-0 bg-gradient-to-t from-[#0b0f09] from-40% via-[#0b0f09]/80 via-55% to-transparent to-70% lg:bg-gradient-to-l lg:from-[#0b0f09]/90 lg:from-0% lg:via-[#0b0f09]/45 lg:via-40% lg:to-transparent lg:to-65%"
		></div>
	</div>

	<!-- Adegan daftar & lupa/atur ulang sandi: latar polos bersih bertekstur topografi. -->
	<div class={['adegan adegan-bersih', !masuk && 'aktif']}>
		<div class="absolute inset-0 bg-[#0a0d09]"></div>
		<div
			class="absolute inset-0 opacity-70"
			style="background-image:url('/topo.webp');background-size:512px"
		></div>
		<div
			class="absolute inset-0 bg-[radial-gradient(ellipse_70%_60%_at_50%_45%,transparent_0%,rgb(5_7_4/0.55)_70%,rgb(5_7_4/0.85)_100%)]"
		></div>
	</div>

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
	/* Latar bersih cukup memudar (tanpa geser). */
	.adegan-bersih,
	.adegan-bersih.aktif {
		transform: none;
	}

	@media (prefers-reduced-motion: reduce) {
		.adegan,
		.adegan.aktif {
			transition:
				opacity 0.3s,
				visibility 0s 0.3s;
		}
		.adegan.aktif {
			transition: opacity 0.3s;
		}
	}
</style>
