<script lang="ts">
	// Tampilan saat data halaman dimuat: kerangka halaman diburamkan di belakang,
	// panel "MEMUAT" bergaya radar taktis di tengah area yang terlihat.
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';

	let { baris = 3, pesan = 'Memuat data' }: { baris?: number; pesan?: string } = $props();
</script>

<div class="memuat relative" role="status" aria-live="polite">
	<span class="sr-only">{pesan}…</span>

	<!-- Kerangka meniru tata letak halaman umum: kartu statistik lalu kartu daftar. -->
	<div class="pointer-events-none grid gap-6 opacity-60 blur-[6px] select-none" aria-hidden="true">
		<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
			{#each Array(4) as _, i (i)}
				<div class="sudut-taktis grid gap-3 rounded-none border bg-card p-4">
					<Skeleton class="h-3 w-2/3" />
					<Skeleton class="h-8 w-12" />
					<Skeleton class="h-3 w-1/2" />
				</div>
			{/each}
		</div>
		<div class="sudut-taktis rounded-none border bg-card">
			<div class="grid gap-2 border-b p-5">
				<Skeleton class="h-4 w-48" />
				<Skeleton class="h-3 w-64" />
			</div>
			{#each Array(baris) as _, i (i)}
				<div class="flex items-center gap-4 border-b px-5 py-4 last:border-b-0">
					<div class="grid flex-1 gap-2">
						<Skeleton class="h-4 w-2/5" />
						<Skeleton class="h-3 w-3/5" />
					</div>
					<Skeleton class="hidden h-3 w-28 sm:block" />
					<Skeleton class="h-5 w-16" />
				</div>
			{/each}
		</div>
	</div>

	<!-- Panel di tengah; sticky agar tetap terlihat di layar walau kerangkanya lebih tinggi. -->
	<div class="absolute inset-0 flex items-start justify-center pt-16 sm:pt-24" aria-hidden="true">
		<div class="panel sudut-taktis sticky top-[40vh] flex flex-col items-center gap-3 border border-gold/35 bg-background/70 px-8 py-6 shadow-[0_20px_60px_rgb(0_0_0/0.35)] backdrop-blur-md">
			<div class="radar relative size-14 rounded-full border border-gold/40">
				<span class="absolute inset-[22%] rounded-full border border-gold/25"></span>
				<span class="sapu absolute inset-0 rounded-full"></span>
				<span class="absolute top-1/2 left-1/2 size-1.5 -translate-1/2 rounded-full bg-gold shadow-[0_0_8px_var(--gold)]"></span>
			</div>
			<p class="font-stencil text-xl tracking-[0.3em] text-gold">
				MEMUAT<span class="titik">.</span><span class="titik">.</span><span class="titik">.</span>
			</p>
			<div class="pindai relative h-0.5 w-32 overflow-hidden rounded-full bg-gold/15">
				<span class="absolute inset-y-0 w-1/3 rounded-full bg-gold"></span>
			</div>
			<p class="label-stensil text-[10px] text-muted-foreground">{pesan}</p>
		</div>
	</div>
</div>

<style>
	/* Muncul setelah jeda singkat: loading yang selesai < 120 ms tidak sempat berkedip. */
	.memuat {
		animation: muncul 0.15s 0.12s ease-out both;
	}
	.sapu {
		background: conic-gradient(from 0deg, transparent 0deg 280deg, color-mix(in oklab, var(--gold) 70%, transparent) 360deg);
		animation: putar 1.6s linear infinite;
	}
	.titik {
		animation: kedip 1.2s infinite;
	}
	.titik:nth-child(2) {
		animation-delay: 0.2s;
	}
	.titik:nth-child(3) {
		animation-delay: 0.4s;
	}
	.pindai span {
		animation: pindai 1.4s ease-in-out infinite;
	}

	@keyframes muncul {
		from {
			opacity: 0;
		}
	}
	@keyframes putar {
		to {
			transform: rotate(360deg);
		}
	}
	@keyframes kedip {
		0%,
		100% {
			opacity: 0.15;
		}
		40% {
			opacity: 1;
		}
	}
	@keyframes pindai {
		from {
			left: -33%;
		}
		to {
			left: 100%;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.sapu,
		.titik,
		.pindai span {
			animation: none;
		}
		.titik {
			opacity: 1;
		}
		.pindai span {
			left: 33%;
		}
	}
</style>
