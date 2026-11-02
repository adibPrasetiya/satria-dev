<script lang="ts">
	// Latar halaman daftar: prajurit berseragam hitam membidik, di sisi kanan layar.
	// Lapisan: foto (digelapkan) -> terminal -> kabut bergerak -> potongan prajurit tajam + rim light dingin.
	// Potongan memakai object-fit & titik fokus yang sama dengan foto agar selalu sejajar.
	// Saat `aktif` berubah, latar & prajurit bergeser dengan jarak berbeda (parallax) — lihat PanggungAuth.
	import TerminalLatar from './TerminalLatar.svelte';

	let { aktif }: { aktif: boolean } = $props();
</script>

<div class={['latar-kopassus absolute inset-x-0 top-0 h-[64svh] overflow-hidden bg-[#0b0d0c] lg:inset-0 lg:h-auto', aktif && 'aktif']} aria-hidden="true">
	<div class="gerak absolute inset-0">
		<img src="/login/latar-daftar.webp" alt="" class="lapisan latar" />
		<!-- Cermin adegan login: blok terminal di sisi kartu (kiri), di belakang prajurit. -->
		<TerminalLatar desktop={[{ x: 2, y: 5, w: 48, h: 90 }]} />
		<div class="kabut absolute inset-0"></div>
		<img src="/login/prajurit-daftar.webp" alt="" class="lapisan prajurit" />
	</div>
</div>

<style>
	.latar-kopassus {
		--fokus-x: 74%;
		--fokus-y: 15%;
	}
	@media (min-width: 1024px) {
		.latar-kopassus {
			--fokus-x: 70%;
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

	.latar {
		filter: brightness(0.5) saturate(0.85) contrast(1.1);
		transform: translateX(4%) scale(1.06);
		transition: transform 1.2s cubic-bezier(0.2, 0.8, 0.2, 1);
	}
	/* Rim light dingin agar siluet hitam terpisah dari langit mendung. */
	.prajurit {
		filter: drop-shadow(0 0 1.5px rgb(210 225 240 / 0.7)) drop-shadow(0 0 10px rgb(120 160 200 / 0.3));
		opacity: 0;
		transform: translateX(14%);
		transition:
			transform 0.7s cubic-bezier(0.4, 0, 1, 1),
			opacity 0.5s ease-in;
	}
	/* Masuk: latar bergeser pelan, prajurit menyusul lebih jauh & lebih cepat (parallax). */
	.aktif .latar {
		transform: translateX(0) scale(1.02);
	}
	.aktif .prajurit {
		opacity: 1;
		transform: translateX(0);
		transition:
			transform 1s 0.15s cubic-bezier(0.16, 1, 0.3, 1),
			opacity 0.6s 0.15s ease-out;
	}

	.kabut {
		background:
			radial-gradient(60% 40% at 20% 70%, rgb(200 205 210 / 0.1), transparent 70%),
			radial-gradient(50% 35% at 60% 85%, rgb(200 205 210 / 0.08), transparent 70%);
		animation: kabut 18s ease-in-out infinite alternate;
	}

	.gerak {
		transform-origin: 70% 30%;
		animation: kenburns 30s ease-in-out infinite alternate;
	}
	@keyframes kenburns {
		to {
			transform: scale(1.04);
		}
	}
	@keyframes kabut {
		to {
			transform: translateX(6%);
			opacity: 0.6;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.gerak,
		.kabut {
			animation: none;
		}
		.latar,
		.prajurit,
		.aktif .latar,
		.aktif .prajurit {
			transform: none;
			transition: opacity 0.3s;
		}
	}
</style>
