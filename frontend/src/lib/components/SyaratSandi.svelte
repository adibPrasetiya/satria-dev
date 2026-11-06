<script lang="ts">
	// Checklist syarat kata sandi (kebijakan BSSN, sama dengan validasi backend) bergaya bulatan
	// centang. Empat aturan SYARAT_SANDI diringkas jadi tiga baris.
	import { SYARAT_SANDI } from '#lib/validasi.js';
	import { cn } from '#lib/utils.js';
	import Circle from '@lucide/svelte/icons/circle';
	import CircleCheck from '@lucide/svelte/icons/circle-check';

	let { sandi, class: kelas = '' }: { sandi: string; class?: string } = $props();

	const [panjang, hurufBesarKecil, angka, simbol] = SYARAT_SANDI;
	const syarat = $derived([
		{ label: 'Minimal 8 karakter', ok: panjang.cek(sandi) },
		{ label: 'Mengandung huruf besar & kecil', ok: hurufBesarKecil.cek(sandi) },
		{ label: 'Mengandung angka & simbol', ok: angka.cek(sandi) && simbol.cek(sandi) }
	]);
</script>

<ul class={cn('grid gap-1.5 text-sm', kelas)} aria-label="Syarat kata sandi">
	{#each syarat as s (s.label)}
		<li
			class={cn(
				'flex items-center gap-2.5 transition-colors',
				s.ok ? 'text-white/80' : 'text-white/45'
			)}
		>
			{#if s.ok}
				<CircleCheck class="size-[18px] shrink-0 fill-gold text-[#0d100c]" />
			{:else}
				<Circle class="size-[18px] shrink-0 text-white/25" />
			{/if}
			{s.label}
			<span class="sr-only">{s.ok ? '(terpenuhi)' : '(belum)'}</span>
		</li>
	{/each}
</ul>
