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
		<Field label="Alamat halaman ubah kata sandi" tandaJenis="frontend" id="ubah-halaman" wajib>
			<InputAlamat id="ubah-halaman" urlDasar={app.url_dasar} bind:value={p.ubah_password.jalur_halaman} placeholder="/akun/kata-sandi" invalid={alamatSalah(p.ubah_password.jalur_halaman)} />
			{#if alamatSalah(p.ubah_password.jalur_halaman)}<p class="text-xs text-critical">Tulis alamat lengkap, mis. https://aplikasi.mil.id/akun/kata-sandi</p>{/if}
		</Field>
	</div>
	<div class="sm:col-span-2">
		<Field label="Alamat penerima data ubah sandi" tandaJenis="backend" id="ubah-aksi" wajib info="Endpoint server yang menerima perubahan kata sandi (mis. /auth/change-password). Boleh beda domain.">
			<InputAlamat id="ubah-aksi" urlDasar={app.url_dasar} bind:value={p.ubah_password.jalur_aksi} placeholder="https://api.satuan.mil.id/auth/change-password" invalid={alamatSalah(p.ubah_password.jalur_aksi)} />
			{#if alamatSalah(p.ubah_password.jalur_aksi)}<p class="text-xs text-critical">Tulis alamat lengkap, mis. https://aplikasi.mil.id/auth/change-password</p>{/if}
		</Field>
	</div>
	<Field label="Kolom kata sandi lama" id="ubah-lama" wajib>
		<Input id="ubah-lama" class="h-9 font-mono" bind:value={p.ubah_password.field_lama} placeholder="current_password" />
	</Field>
	<div class="grid grid-cols-2 items-start gap-2">
		<Field label="Kolom kata sandi baru" id="ubah-baru" wajib>
			<Input id="ubah-baru" class="h-9 font-mono" bind:value={p.ubah_password.field_baru} placeholder="new_password" />
		</Field>
		<Field label="Kolom ulangi kata sandi" id="ubah-konf">
			<Input id="ubah-konf" class="h-9 font-mono" bind:value={p.ubah_password.field_konfirmasi} placeholder="new_password_confirm" />
		</Field>
	</div>
</div>
