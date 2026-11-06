<script lang="ts">
	// Layout halaman publik "layar penuh bersih" (mis. pendaftaran bertahap): TANPA kartu — isian
	// berada di kolom tengah di atas latar polos bertekstur topografi (PanggungAuth, adegan 'daftar').
	// Agar tidak monoton, latar diberi sentuhan dekorasi taktis kecil: garis HUD bertingkat,
	// faset sudut, dan penanda koordinat — semuanya samar & tidak mengganggu isian.
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { adeganDari } from './PanggungAuth.svelte';
	import LogoSatria from './LogoSatria.svelte';
	import { cn } from '#lib/utils.js';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';

	let {
		label,
		goyang = false,
		children
	}: {
		/** Nama aksesibel area isian. */
		label: string;
		goyang?: boolean;
		children: Snippet;
	} = $props();

	const adegan = $derived(adeganDari(page.url.pathname) ?? 'daftar');
</script>

<div class="relative flex min-h-svh flex-1 flex-col">
	<!-- ===================== Dekorasi latar (desktop/tablet) ===================== -->
	<div
		class="pointer-events-none absolute inset-0 hidden overflow-hidden md:block"
		aria-hidden="true"
	>
		<!-- Garis HUD bertingkat — kanan atas (sama seperti halaman masuk). -->
		<svg class="absolute top-0 right-0 h-[60px] w-[340px]" viewBox="0 0 340 60" fill="none">
			<path
				d="M4 44 L40 28 L228 28 L250 14"
				stroke="var(--gold)"
				stroke-width="1.5"
				stroke-opacity="0.6"
			/>
			<path d="M250 14 L340 14" stroke="oklch(0.8 0.13 128)" stroke-width="4" />
		</svg>

		<!-- Garis HUD bertingkat — kiri bawah (cermin). -->
		<svg
			class="absolute bottom-0 left-0 h-[60px] w-[340px] -scale-100"
			viewBox="0 0 340 60"
			fill="none"
		>
			<path
				d="M4 44 L40 28 L228 28 L250 14"
				stroke="var(--gold)"
				stroke-width="1.5"
				stroke-opacity="0.45"
			/>
			<path
				d="M250 14 L340 14"
				stroke="oklch(0.8 0.13 128)"
				stroke-width="3"
				stroke-opacity="0.8"
			/>
		</svg>

		<!-- Faset sudut kanan bawah. -->
		<svg class="absolute right-0 bottom-0 h-[150px] w-[300px]" viewBox="0 0 300 150" fill="none">
			<path d="M300 30 L300 150 L170 150 Z" fill="rgb(255 255 255 / 0.025)" />
			<path d="M300 78 L300 150 L222 150 Z" fill="rgb(255 255 255 / 0.04)" />
			<path d="M150 150 L300 8" stroke="var(--gold)" stroke-opacity="0.35" stroke-width="1.25" />
			<path d="M196 150 L300 52" stroke="rgb(255 255 255 / 0.08)" stroke-width="1" />
		</svg>

		<!-- Faset sudut kiri atas (di bawah kepala halaman). -->
		<svg class="absolute top-0 left-0 h-[120px] w-[220px]" viewBox="0 0 220 120" fill="none">
			<path d="M0 0 L120 0 L0 96 Z" fill="rgb(255 255 255 / 0.02)" />
			<path d="M0 120 L150 0" stroke="rgb(255 255 255 / 0.06)" stroke-width="1" />
		</svg>

		<!-- Penanda koordinat di tepi kiri & kanan (garis tik kecil). -->
		<div class="absolute top-1/2 left-6 flex -translate-y-1/2 flex-col gap-2.5">
			{#each Array(7) as _, i (i)}
				<span class={cn('h-px bg-white/15', i === 3 ? 'w-5 bg-gold/60' : 'w-2.5')}></span>
			{/each}
		</div>
		<div class="absolute top-1/2 right-6 flex -translate-y-1/2 flex-col items-end gap-2.5">
			{#each Array(7) as _, i (i)}
				<span class={cn('h-px bg-white/15', i === 3 ? 'w-5 bg-gold/60' : 'w-2.5')}></span>
			{/each}
		</div>
	</div>

	<!-- ===================== Isian di tengah ===================== -->
	<main class="relative z-10 flex flex-1 items-center justify-center px-5 py-10 sm:px-8">
		<section
			class={cn('layar-isian w-full max-w-[640px]', goyang && 'goyang')}
			style:view-transition-name="kartu-{adegan}"
			aria-label={label}
		>
			<!-- Kepala kolom isian: logo (kiri) + kembali ke login (kanan), tepat di atas stepper. -->
			<header class="mb-8 flex items-center justify-between gap-4">
				<a href="/login" class="shrink-0" aria-label="SATRIA — ke halaman masuk">
					<LogoSatria class="flex [--logo-h:2.75rem] sm:[--logo-h:3.5rem]" />
				</a>
				<a
					href="/login"
					class="group/kembali flex items-center gap-1.5 text-sm whitespace-nowrap text-white/65 transition-colors hover:text-white"
				>
					Kembali ke Login
					<ArrowRight class="size-4 transition-transform group-hover/kembali:translate-x-0.5" />
				</a>
			</header>

			{@render children()}
		</section>
	</main>
</div>

<style>
	.layar-isian {
		animation: naik 0.55s 0.1s cubic-bezier(0.2, 0.8, 0.2, 1) both;
	}
	/* Saat berpindah login <-> daftar, isian digerakkan View Transition (layout.css). */
	:global(:root[data-arah-auth]) .layar-isian {
		animation: none;
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
		.layar-isian,
		.goyang {
			animation: none;
		}
	}
</style>
