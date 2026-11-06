<script lang="ts">
	// Kartu halaman publik (login, daftar, lupa kata sandi) di atas latar PanggungAuth.
	// Kartu hanya berisi: logo & nama aplikasi, judul + keterangan, lalu isi (form).
	// Adegan login: kartu di kanan; daftar: kartu di kiri (prajurit di kanan); lupa: kartu di tengah.
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { adeganDari } from './PanggungAuth.svelte';
	import LogoSatria from './LogoSatria.svelte';
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
		'relative flex flex-1 items-end justify-center pt-[30svh] lg:items-stretch lg:p-0 lg:pt-0',
		{ daftar: 'lg:justify-start', lupa: 'lg:justify-center', login: 'lg:justify-end' }[adegan]
	)}
>
	<!-- Desktop: panel solid setinggi layar menempel ke tepi (bukan kartu melayang) → bagi 2 dengan latar. -->
	<section
		class={cn(
			'kartu-auth relative w-full rounded-t-2xl border border-b-0 border-gold/30 px-6 pt-6 pb-6 shadow-[0_-10px_50px_rgb(0_0_0/0.6)] sm:px-8',
			'lg:flex lg:min-h-svh lg:flex-col lg:justify-center lg:rounded-none lg:border-t-0 lg:border-r-0 lg:border-l lg:border-gold/25 lg:px-0 lg:py-16 lg:shadow-[-30px_0_80px_rgb(0_0_0/0.55)]',
			adegan === 'daftar'
				? 'bg-[#0e1110]/95 lg:w-[45vw] lg:max-w-[640px] lg:bg-[#0c0f0b]'
				: 'bg-[#10150e]/95 lg:w-[41vw] lg:max-w-[560px] lg:bg-[#0a0d08]',
			adegan !== 'login' && 'sudut-taktis',
			goyang && 'goyang'
		)}
		style:view-transition-name="kartu-{adegan}"
		aria-labelledby="judul-auth"
	>
		{#if adegan === 'login'}
			<!-- Tekstur topografi (pattern seamless, diulang — bukan gambar diperbesar). -->
			<div
				class="pointer-events-none absolute inset-0 z-0 hidden bg-repeat opacity-80 lg:block"
				style="background-image:url('/topo.webp');background-size:512px"
				aria-hidden="true"
			></div>
			<!-- Dekorasi HUD taktis (desktop): garis hijau bertingkat di pojok kanan-atas + bracket
			     bawah-kanan, meniru dekorasi pada mockup. -->
			<svg
				class="pointer-events-none absolute top-0 right-0 z-20 hidden h-[60px] w-[300px] lg:block"
				viewBox="0 0 300 60"
				fill="none"
				aria-hidden="true"
			>
				<path
					d="M4 44 L40 28 L198 28 L220 14"
					stroke="var(--gold)"
					stroke-width="1.75"
					stroke-opacity="0.7"
				/>
				<path d="M220 14 L300 14" stroke="oklch(0.8 0.13 128)" stroke-width="4" />
			</svg>
			<svg
				class="pointer-events-none absolute right-0 bottom-0 z-20 hidden h-[74px] w-[260px] lg:block"
				viewBox="0 0 260 74"
				fill="none"
				aria-hidden="true"
			>
				<path
					d="M260 56 L214 56 L190 72"
					stroke="var(--gold)"
					stroke-width="1.5"
					stroke-opacity="0.55"
				/>
				<path
					d="M260 44 L224 44"
					stroke="oklch(0.8 0.13 128)"
					stroke-width="3.5"
					stroke-opacity="0.85"
				/>
			</svg>
		{/if}

		<div class="relative z-10 lg:mx-auto lg:w-full lg:max-w-[400px]">
			<LogoSatria
				class="flex w-fit [--logo-h:3rem] sm:[--logo-h:3.5rem] lg:mx-auto lg:[--logo-h:5.5rem]"
			/>

			<div class="mt-5 mb-4 lg:mt-7 lg:mb-6">
				<h1
					id="judul-auth"
					class="font-heading text-xl font-semibold tracking-normal lg:text-[2rem] lg:leading-tight"
				>
					{judul}
				</h1>
				{#if keterangan}<p class="mt-1 text-sm text-white/60 lg:mt-2 lg:text-[15px]">
						{keterangan}
					</p>{/if}
			</div>

			{@render children()}
		</div>
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
