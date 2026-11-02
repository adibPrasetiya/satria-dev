<script lang="ts">
	// Input alamat lengkap (URL) dalam satu kolom, agar alamat panjang tetap terbaca utuh.
	// Boleh berbeda domain dari URL dasar aset (mis. backend di subdomain api.*). Bila pengguna hanya
	// menulis jalur ("/login"), saat keluar kolom otomatis dilengkapi dengan URL dasar aset.
	import { Input } from '#lib/components/ui/input/index.js';

	let {
		id,
		urlDasar,
		value = $bindable(''),
		placeholder = '/',
		invalid = false
	}: { id: string; urlDasar: string; value?: string; placeholder?: string; invalid?: boolean } = $props();

	const asal = $derived(urlDasar.replace(/\/+$/, ''));

	function lengkapi() {
		const v = value.trim();
		if (!v) return (value = '');
		if (v.startsWith('/')) value = asal + v;
		else if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(v)) value = 'https://' + v;
		else value = v;
	}
</script>

<Input
	{id}
	bind:value
	type="url"
	inputmode="url"
	spellcheck={false}
	autocomplete="off"
	class="h-9 font-mono text-[13px]"
	placeholder={placeholder.startsWith('/') ? asal + placeholder : placeholder}
	aria-invalid={invalid}
	title={value || undefined}
	onblur={lengkapi}
/>
