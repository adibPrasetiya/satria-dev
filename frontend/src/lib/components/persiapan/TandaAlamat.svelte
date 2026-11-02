<script lang="ts">
	// Penanda alamat beranimasi (Frontend / Backend). Saat di-hover, memunculkan kartu
	// kecil berisi diagram peramban (dengan bilah alamat/URL) ⇄ server: sebuah "paket"
	// data bergerak dari peramban ke server; node yang sesuai berdenyut emas.
	// Untuk Frontend, bilah URL peramban disorot. Murni SVG + CSS; hormati prefers-reduced-motion.
	import * as Tooltip from '#lib/components/ui/tooltip/index.js';

	let { jenis }: { jenis: 'frontend' | 'backend' } = $props();

	const label = $derived(jenis === 'frontend' ? 'Frontend' : 'Backend');
	const ket = $derived(
		jenis === 'frontend'
			? 'Alamat (URL) yang dibuka pengguna di peramban — halaman yang mereka kunjungi.'
			: 'Server yang menerima data saat tombol ditekan — bisa berbeda domain dari halaman.'
	);
	const fe = $derived(jenis === 'frontend');
</script>

<Tooltip.Root delayDuration={120}>
	<Tooltip.Trigger
		type="button"
		aria-label="Penjelasan alamat {label}"
		class="cursor-help rounded-sm border px-1 py-px font-mono text-[10px] leading-none tracking-wide text-muted-foreground uppercase transition-colors hover:border-gold/60 hover:text-foreground focus-visible:border-gold/60 focus-visible:text-foreground focus-visible:outline-none"
	>
		{label}
	</Tooltip.Trigger>
	<Tooltip.Content
		side="top"
		class="max-w-[272px] flex-col gap-2 rounded-lg border bg-card p-3 text-card-foreground shadow-md"
		arrowClasses="bg-card border-r border-b"
	>
		<!-- Diagram: peramban (kiri) → server (kanan). -->
		<svg class="satya-diagram w-full" viewBox="0 0 236 98" role="img" aria-hidden="true">
			<!-- Konektor putus-putus + paket data -->
			<line x1="82" y1="41" x2="156" y2="41" class="satya-konektor" />
			<circle r="3.5" cy="41" class="satya-paket" />

			<!-- ========== Peramban (Frontend) ========== -->
			<g class="satya-node" class:redup={!fe}>
				<!-- Jendela -->
				<rect x="12" y="14" width="66" height="52" rx="6" class="satya-kotak" class:aktif={fe} />
				<!-- Garis pemisah toolbar -->
				<line x1="12" y1="27" x2="78" y2="27" class="satya-garis" />
				<!-- Tombol lampu lalu lintas -->
				<circle cx="18.5" cy="20.5" r="1.7" class="satya-titik" />
				<circle cx="23.5" cy="20.5" r="1.7" class="satya-titik" />
				<circle cx="28.5" cy="20.5" r="1.7" class="satya-titik" />
				<!-- Cincin sorot pada bilah URL (hanya untuk frontend) -->
				{#if fe}<rect x="33" y="15.5" width="41" height="10" rx="5" class="satya-denyut-url" />{/if}
				<!-- Bilah alamat (URL) -->
				<rect x="34" y="16" width="39" height="9" rx="4.5" class="satya-url" class:aktif={fe} />
				<!-- Ikon gembok + teks URL di dalam bilah -->
				<rect x="37.5" y="19" width="2.6" height="3" rx="0.7" class="satya-url-ikon" class:aktif={fe} />
				<rect x="42.5" y="19.6" width="26" height="1.9" rx="0.95" class="satya-url-teks" class:aktif={fe} />
				<!-- Konten halaman -->
				<rect x="18" y="35" width="32" height="3.4" rx="1.7" class="satya-garis-isi" />
				<rect x="18" y="43" width="52" height="3.4" rx="1.7" class="satya-garis-isi" />
				<rect x="18" y="51" width="42" height="3.4" rx="1.7" class="satya-garis-isi" />
			</g>

			<!-- ========== Server (Backend) ========== -->
			<g class="satya-node" class:redup={fe}>
				{#if !fe}<rect x="156" y="13" width="64" height="54" rx="7" class="satya-denyut" />{/if}
				<rect x="160" y="15" width="56" height="50" rx="6" class="satya-kotak" class:aktif={!fe} />
				<rect x="167" y="21" width="43" height="10" rx="3" class="satya-rak" class:aktif={!fe} />
				<rect x="167" y="34.5" width="43" height="10" rx="3" class="satya-rak" class:aktif={!fe} />
				<rect x="167" y="48" width="43" height="10" rx="3" class="satya-rak" class:aktif={!fe} />
				<circle cx="172" cy="26" r="1.5" class="satya-led" class:aktif={!fe} />
				<circle cx="172" cy="39.5" r="1.5" class="satya-led" class:aktif={!fe} />
				<circle cx="172" cy="53" r="1.5" class="satya-led" class:aktif={!fe} />
			</g>

			<!-- Label node -->
			<text x="45" y="84" class="satya-label" class:aktif={fe}>Frontend</text>
			<text x="188" y="84" class="satya-label" class:aktif={!fe}>Backend</text>
		</svg>

		<p class="text-[11px] leading-snug text-muted-foreground">{ket}</p>
	</Tooltip.Content>
</Tooltip.Root>

<style>
	.satya-diagram {
		height: auto;
	}

	.satya-konektor {
		stroke: var(--color-border);
		stroke-width: 1.5;
		stroke-dasharray: 3 3;
	}
	.satya-kotak {
		fill: color-mix(in oklab, var(--color-muted) 50%, transparent);
		stroke: var(--color-border);
		stroke-width: 1.5;
	}
	.satya-kotak.aktif {
		stroke: var(--color-gold);
	}
	.satya-garis {
		stroke: var(--color-border);
		stroke-width: 1;
	}
	.satya-titik {
		fill: var(--color-muted-foreground);
		opacity: 0.7;
	}

	/* Bilah alamat (URL) */
	.satya-url {
		fill: color-mix(in oklab, var(--color-muted-foreground) 22%, transparent);
		stroke: var(--color-border);
		stroke-width: 1;
	}
	.satya-url.aktif {
		fill: color-mix(in oklab, var(--color-gold) 22%, transparent);
		stroke: var(--color-gold);
	}
	.satya-url-ikon {
		fill: var(--color-muted-foreground);
		opacity: 0.8;
	}
	.satya-url-ikon.aktif {
		fill: var(--color-gold);
		opacity: 1;
	}
	.satya-url-teks {
		fill: var(--color-muted-foreground);
		opacity: 0.65;
	}
	.satya-url-teks.aktif {
		fill: var(--color-gold);
		opacity: 0.95;
	}

	.satya-rak {
		fill: color-mix(in oklab, var(--color-muted-foreground) 35%, transparent);
	}
	.satya-rak.aktif {
		fill: color-mix(in oklab, var(--color-gold) 30%, transparent);
	}
	.satya-garis-isi {
		fill: color-mix(in oklab, var(--color-muted-foreground) 25%, transparent);
	}
	.satya-led {
		fill: var(--color-muted-foreground);
		opacity: 0.6;
	}
	.satya-led.aktif {
		fill: var(--color-gold);
		opacity: 1;
	}
	.satya-node.redup {
		opacity: 0.5;
	}
	.satya-paket {
		fill: var(--color-gold);
	}
	.satya-denyut,
	.satya-denyut-url {
		fill: none;
		stroke: var(--color-gold);
		stroke-width: 1.5;
		opacity: 0;
		transform-box: fill-box;
		transform-origin: center;
	}
	.satya-label {
		font-size: 9px;
		font-weight: 600;
		letter-spacing: 0.04em;
		text-anchor: middle;
		fill: var(--color-muted-foreground);
		text-transform: uppercase;
	}
	.satya-label.aktif {
		fill: var(--color-gold);
	}

	/* Animasi hanya bila pengguna tidak meminta pengurangan gerak. */
	@media (prefers-reduced-motion: no-preference) {
		.satya-paket {
			animation: satya-paket 2.1s ease-in-out infinite;
		}
		.satya-denyut,
		.satya-denyut-url {
			animation: satya-denyut 2.1s ease-out infinite;
		}
	}

	@keyframes satya-paket {
		0% {
			transform: translateX(82px);
			opacity: 0;
		}
		12% {
			opacity: 1;
		}
		80% {
			opacity: 1;
		}
		100% {
			transform: translateX(156px);
			opacity: 0;
		}
	}
	@keyframes satya-denyut {
		0%,
		100% {
			transform: scale(0.9);
			opacity: 0;
		}
		40% {
			opacity: 0.6;
		}
		70% {
			transform: scale(1.08);
			opacity: 0;
		}
	}
</style>
