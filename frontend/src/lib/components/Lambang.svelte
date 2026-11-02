<script lang="ts">
	// Lambang SATYA: perisai bergaris emas, bintang, dan tanda centang (kelaikan).
	// Desain orisinal aplikasi — bukan lambang resmi satuan mana pun.
	let { class: className = '' }: { class?: string } = $props();
	const id = `lambang-${Math.random().toString(36).slice(2, 8)}`;
</script>

<svg viewBox="0 0 64 72" class={className} role="img" aria-label="Lambang SATYA">
	<defs>
		<linearGradient id="{id}-emas" x1="0" y1="0" x2="0" y2="1">
			<stop offset="0" stop-color="#f3d77a" />
			<stop offset="0.55" stop-color="#c99a2e" />
			<stop offset="1" stop-color="#8a6516" />
		</linearGradient>
		<linearGradient id="{id}-isi" x1="0" y1="0" x2="0" y2="1">
			<stop offset="0" stop-color="#4b5a2c" />
			<stop offset="1" stop-color="#253419" />
		</linearGradient>
		<pattern id="{id}-loreng" width="64" height="72" patternUnits="userSpaceOnUse">
			<image href="/loreng.svg" width="96" height="96" opacity="0.55" />
		</pattern>
	</defs>
	<!-- Perisai -->
	<path
		d="M32 2 L60 10 V34 C60 52 47 64 32 70 C17 64 4 52 4 34 V10 Z"
		fill="url(#{id}-emas)"
	/>
	<path
		d="M32 6.5 L56 13.4 V34 C56 49.5 45 60 32 65.5 C19 60 8 49.5 8 34 V13.4 Z"
		fill="url(#{id}-isi)"
	/>
	<path
		d="M32 6.5 L56 13.4 V34 C56 49.5 45 60 32 65.5 C19 60 8 49.5 8 34 V13.4 Z"
		fill="url(#{id}-loreng)"
	/>
	<!-- Pita atas -->
	<path d="M8.5 26 H55.5" stroke="#c99a2e" stroke-width="1.5" />
	<!-- Bintang -->
	<path
		d="M32 9.5 l2.35 4.8 5.3.77 -3.83 3.73 .9 5.27 -4.72-2.48 -4.72 2.48 .9-5.27 -3.83-3.73 5.3-.77 Z"
		fill="url(#{id}-emas)"
		transform="translate(0 -1) scale(1) "
	/>
	<!-- Centang kelaikan -->
	<path
		d="M20 40 L28.5 48.5 L45 31"
		fill="none"
		stroke="url(#{id}-emas)"
		stroke-width="6"
		stroke-linecap="square"
		stroke-linejoin="miter"
	/>
	<path
		d="M20 40 L28.5 48.5 L45 31"
		fill="none"
		stroke="#1b1d18"
		stroke-width="1"
		stroke-opacity="0.35"
	/>
</svg>
