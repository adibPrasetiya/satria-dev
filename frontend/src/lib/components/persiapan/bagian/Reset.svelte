<script lang="ts">
	import type { Aplikasi, PersiapanAuth } from '#lib/types.js';
	import { alamatSalah } from '#lib/persiapan/bagian.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import Field from '#lib/components/Field.svelte';
	import InputAlamat from '#lib/components/persiapan/InputAlamat.svelte';

	let { p = $bindable(), app }: { p: PersiapanAuth; app: Aplikasi } = $props();
</script>

<div class="grid items-start gap-4 sm:grid-cols-2">
	<div class="sm:col-span-2">
		<Field label="Alamat halaman lupa kata sandi" tandaJenis="frontend" id="reset-halaman" wajib>
			<InputAlamat id="reset-halaman" urlDasar={app.url_dasar} bind:value={p.reset.jalur_halaman} placeholder="/lupa-sandi" invalid={alamatSalah(p.reset.jalur_halaman)} />
			{#if alamatSalah(p.reset.jalur_halaman)}<p class="text-xs text-critical">Tulis alamat lengkap, mis. https://aplikasi.mil.id/lupa-sandi</p>{/if}
		</Field>
	</div>
	<div class="sm:col-span-2">
		<Field label="Alamat penerima data reset" tandaJenis="backend" id="reset-aksi" wajib info="Endpoint server yang menerima permintaan reset saat tombol ditekan (mis. /auth/forgot-password). Boleh beda domain.">
			<InputAlamat id="reset-aksi" urlDasar={app.url_dasar} bind:value={p.reset.jalur_aksi} placeholder="https://api.satuan.mil.id/auth/forgot-password" invalid={alamatSalah(p.reset.jalur_aksi)} />
			{#if alamatSalah(p.reset.jalur_aksi)}<p class="text-xs text-critical">Tulis alamat lengkap, mis. https://aplikasi.mil.id/auth/forgot-password</p>{/if}
		</Field>
	</div>
	<Field label="Kolom username/email" id="reset-id" wajib info="Nama teknis kolom (atribut name) tempat pengguna mengetik email atau username.">
		<Input id="reset-id" class="h-9 font-mono" bind:value={p.reset.field_identitas} placeholder="email" />
	</Field>
	<Field label="Email akun uji" id="reset-email" wajib info="Kotak masuk yang bisa dibuka asesor untuk mengambil tautan pemulihan.">
		<Input id="reset-email" class="h-9" type="email" bind:value={p.reset.email_akun_uji} placeholder="uji.satya@satuan.mil.id" />
	</Field>
</div>
