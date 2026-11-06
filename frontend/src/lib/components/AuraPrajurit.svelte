<script lang="ts">
	// Latar login taktis yang TENANG: foto latar digelapkan + siluet prajurit tajam di atasnya.
	// Versi lama memakai aura "api emas" (lapisan filter + partikel canvas) dan log terminal scan;
	// keduanya dihapus demi bahasa desain clean / minimalist / tactical (aksen hijau satu-satunya warna).
</script>

<div
	class="aura-wadah absolute inset-x-0 top-0 h-[64svh] overflow-hidden bg-[#10140e] lg:inset-0 lg:h-auto"
	aria-hidden="true"
>
	<div class="aura-gerak absolute inset-0">
		<img src="/login/latar.webp" alt="" class="lapisan latar" />
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

	/* Latar digelapkan & sedikit didinginkan agar prajurit menonjol tanpa warna hangat. */
	.latar {
		filter: brightness(0.44) saturate(0.95) contrast(1.06);
	}
	/* Prajurit tajam dengan bayangan tepi halus (tanpa rim light emas). */
	.prajurit {
		filter: drop-shadow(0 2px 6px rgb(0 0 0 / 0.5));
	}

	/* Ken Burns sangat pelan agar terasa hidup tapi tetap tenang. */
	.aura-gerak {
		transform-origin: 30% 30%;
		animation: kenburns 40s ease-in-out infinite alternate;
	}
	@keyframes kenburns {
		from {
			transform: scale(1);
		}
		to {
			transform: scale(1.035);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.aura-gerak {
			animation: none;
		}
	}
</style>
