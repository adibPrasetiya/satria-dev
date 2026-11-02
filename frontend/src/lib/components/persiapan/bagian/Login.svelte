<script lang="ts">
	import type { Aplikasi, PersiapanAuth } from '#lib/types.js';
	import { alamatSalah } from '#lib/persiapan/bagian.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import Field from '#lib/components/Field.svelte';
	import NativeSelect from '#lib/components/NativeSelect.svelte';
	import InputAlamat from '#lib/components/persiapan/InputAlamat.svelte';

	let { p = $bindable(), app }: { p: PersiapanAuth; app: Aplikasi } = $props();
</script>

{#snippet pesan(v: string)}
	{#if alamatSalah(v)}<p class="text-xs text-critical">Tulis alamat lengkap, mis. https://aplikasi.mil.id/login</p>{/if}
{/snippet}

<div class="grid items-start gap-4 sm:grid-cols-2">
	<div class="sm:col-span-2">
		<Field label="Alamat halaman login" tandaJenis="frontend" id="login-halaman" wajib info="Alamat yang dibuka pengguna di browser untuk login.">
			<InputAlamat id="login-halaman" urlDasar={app.url_dasar} bind:value={p.login.jalur_halaman} placeholder="/login" invalid={alamatSalah(p.login.jalur_halaman)} />
			{@render pesan(p.login.jalur_halaman)}
		</Field>
	</div>
	<div class="grid grid-cols-[minmax(0,1fr)_96px] items-start gap-2 sm:col-span-2">
		<Field label="Alamat penerima data login" tandaJenis="backend" id="login-aksi" wajib info="Alamat server (endpoint API) yang menerima data saat tombol Masuk ditekan. Boleh berbeda domain/subdomain dari aplikasi. Tanyakan ke pengembang bila belum tahu.">
			<InputAlamat id="login-aksi" urlDasar={app.url_dasar} bind:value={p.login.jalur_aksi} placeholder="https://api.satuan.mil.id/auth/login" invalid={alamatSalah(p.login.jalur_aksi)} />
			{@render pesan(p.login.jalur_aksi)}
		</Field>
		<Field label="Cara kirim" id="login-metode" info="Hampir selalu POST.">
			<NativeSelect id="login-metode" class="h-9" bind:value={p.login.metode_http} opsi={[{ value: 'POST', label: 'POST' }, { value: 'GET', label: 'GET' }]} />
		</Field>
	</div>
	<Field label="Nama kolom isian username/email" id="login-user" wajib info="Nama teknis kolom (atribut name) tempat pengguna mengetik username atau email.">
		<Input id="login-user" class="h-9 font-mono" bind:value={p.login.field_username} placeholder="email" />
	</Field>
	<Field label="Nama kolom isian kata sandi" id="login-pass" wajib info="Nama teknis kolom (atribut name) tempat pengguna mengetik kata sandi.">
		<Input id="login-pass" class="h-9 font-mono" bind:value={p.login.field_password} placeholder="password" />
	</Field>
	<Field label="Tanda login berhasil" id="login-ok" info="Halaman tujuan atau tulisan yang muncul setelah berhasil masuk.">
		<Input id="login-ok" class="h-9" bind:value={p.login.penanda_berhasil} placeholder="/dashboard" />
	</Field>
	<Field label="Pesan saat login gagal" id="login-gagal" info="Potongan pesan yang muncul bila kata sandi salah.">
		<Input id="login-gagal" class="h-9" bind:value={p.login.penanda_gagal} placeholder="Email atau kata sandi salah" />
	</Field>
	<div class="sm:col-span-2">
		<Field label="Halaman khusus pengguna terdaftar" tandaJenis="frontend" id="login-terbatas" wajib info="Halaman yang hanya boleh dibuka setelah login, mis. profil atau dasbor.">
			<InputAlamat id="login-terbatas" urlDasar={app.url_dasar} bind:value={p.login.jalur_terbatas} placeholder="/profil" invalid={alamatSalah(p.login.jalur_terbatas)} />
			{@render pesan(p.login.jalur_terbatas)}
		</Field>
	</div>
</div>
