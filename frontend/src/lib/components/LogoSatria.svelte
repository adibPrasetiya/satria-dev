<script lang="ts">
	// Logo SATRIA = lambang + tulisan sebagai dua gambar terpisah, agar proporsi tulisan terhadap
	// lambang bisa diatur (tulisan ≈ 42% tinggi lambang). Ukuran diatur lewat variabel --logo-h
	// (tinggi lambang), mis. class="[--logo-h:3rem] lg:[--logo-h:5rem]".
	import { cn } from '#lib/utils.js';

	let { class: kelas = '' }: { class?: string } = $props();
</script>

<span
	role="img"
	aria-label="SATRIA"
	class={cn('inline-flex items-center gap-[calc(var(--logo-h)*0.2)] [--logo-h:3rem]', kelas)}
>
	<img
		src="/satria-lambang.png"
		alt=""
		width="94"
		height="138"
		draggable="false"
		class="h-[var(--logo-h)] w-auto drop-shadow-[0_4px_12px_rgb(0_0_0/0.55)] select-none"
	/>
	<img
		src="/satria-teks.png"
		alt=""
		width="222"
		height="38"
		draggable="false"
		class="h-[calc(var(--logo-h)*0.42)] w-auto drop-shadow-[0_2px_8px_rgb(0_0_0/0.5)] select-none"
	/>
</span>
