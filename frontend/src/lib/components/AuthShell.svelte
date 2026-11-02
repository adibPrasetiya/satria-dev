<script lang="ts">
	// Kartu halaman publik (login, daftar, lupa kata sandi) di atas latar PanggungAuth.
	// Kartu hanya berisi: logo & nama aplikasi, judul + keterangan, lalu isi (form).
	// Adegan login: kartu di kanan; daftar: kartu di kiri (prajurit di kanan); lupa: kartu di tengah.
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import Lambang from './Lambang.svelte';
	import { adeganDari } from './PanggungAuth.svelte';
	import { cn } from '#lib/utils.js';

	let {
		judul,
		keterangan,
		goyang = false,
		children
	}: { judul: string; keterangan?: string; goyang?: boolean; children: Snippet } = $props();

	const adegan = $derived(adeganDari(page.url.pathname) ?? 'login');
</script>

<main
	class={cn(
		'relative flex flex-1 items-end justify-center pt-[30svh] lg:items-center lg:px-[7vw] lg:py-10',
		{ daftar: 'lg:justify-start', lupa: 'lg:justify-center', login: 'lg:justify-end' }[adegan]
	)}
>
	<section
		class={cn(
			'kartu-auth sudut-taktis w-full rounded-t-2xl border border-b-0 border-gold/30 px-6 pt-6 pb-6 shadow-[0_-10px_50px_rgb(0_0_0/0.6)] sm:px-8 lg:rounded-none lg:border-b lg:shadow-[0_24px_70px_rgb(0_0_0/0.65)]',
			adegan === 'daftar' ? 'bg-[#0e1110]/95 lg:max-w-[560px]' : 'bg-[#10150e]/95 lg:max-w-[400px]',
			goyang && 'goyang'
		)}
		style:view-transition-name="kartu-{adegan}"
		aria-labelledby="judul-auth"
	>
		<div class="flex items-center gap-3">
			<Lambang class="size-11 shrink-0 drop-shadow-[0_4px_10px_rgb(0_0_0/0.6)]" />
			<div class="leading-tight">
				<p class="font-stencil text-2xl tracking-[0.16em] text-gold">SATYA</p>
				<p class="text-xs text-white/55">Asesmen Kelaikan Keamanan Aplikasi</p>
			</div>
		</div>

		<div class="mt-5 mb-4">
			<h1 id="judul-auth" class="font-heading text-xl font-semibold tracking-normal">{judul}</h1>
			{#if keterangan}<p class="mt-1 text-sm text-white/60">{keterangan}</p>{/if}
		</div>

		{@render children()}
	</section>
</main>

<style>
	.kartu-auth {
		padding-bottom: max(1.5rem, env(safe-area-inset-bottom));
		animation: naik 0.6s 0.1s cubic-bezier(0.2, 0.8, 0.2, 1) both;
	}
	/* Saat berpindah login <-> daftar, kartu digerakkan View Transition (layout.css), bukan animasi naik. */
	:global(:root[data-arah-auth]) .kartu-auth {
		animation: none;
	}
	/* Ponsel: bentuk bottom sheet membulat, tanpa sudut taktis. */
	@media (max-width: 1023px) {
		.kartu-auth::before,
		.kartu-auth::after {
			display: none;
		}
	}
	.goyang {
		animation: goyang 0.35s ease-in-out;
	}
	@keyframes naik {
		from {
			opacity: 0;
			transform: translateY(12px);
		}
	}
	@keyframes goyang {
		20%,
		60% {
			transform: translateX(-6px);
		}
		40%,
		80% {
			transform: translateX(6px);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.kartu-auth,
		.goyang {
			animation: none;
		}
	}
</style>
