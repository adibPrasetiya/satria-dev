<script lang="ts">
	import Eye from '@lucide/svelte/icons/eye';
	import EyeOff from '@lucide/svelte/icons/eye-off';

	let { lihat = $bindable(false) }: { lihat?: boolean } = $props();
</script>

<button
	type="button"
	class="absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-lg text-white/50 transition hover:text-white focus-visible:text-gold focus-visible:outline-none"
	onclick={() => (lihat = !lihat)}
	aria-label={lihat ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
	aria-pressed={lihat}
>
	{#if lihat}<EyeOff class="size-4" />{:else}<Eye class="size-4" />{/if}
</button>
