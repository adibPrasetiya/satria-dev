<script lang="ts">
	import type { Aplikasi, PersiapanAuth } from '#lib/types.js';
	import { alamatSalah } from '#lib/persiapan/bagian.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import Field from '#lib/components/Field.svelte';
	import InputAlamat from '#lib/components/persiapan/InputAlamat.svelte';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';

	let { p = $bindable(), app }: { p: PersiapanAuth; app: Aplikasi } = $props();
</script>

{#snippet pesan(v: string)}
	{#if alamatSalah(v)}<p class="text-xs text-critical">Tulis alamat lengkap, mis. https://aplikasi.mil.id/daftar</p>{/if}
{/snippet}

<div class="grid items-start gap-4 sm:grid-cols-2">
	<div class="sm:col-span-2">
		<Field label="Alamat halaman pendaftaran" tandaJenis="frontend" id="reg-halaman" wajib>
			<InputAlamat id="reg-halaman" urlDasar={app.url_dasar} bind:value={p.registrasi.jalur_halaman} placeholder="/daftar" invalid={alamatSalah(p.registrasi.jalur_halaman)} />
			{@render pesan(p.registrasi.jalur_halaman)}
		</Field>
	</div>
	<div class="sm:col-span-2">
		<Field label="Alamat penerima data pendaftaran" tandaJenis="backend" id="reg-aksi" wajib info="Alamat server (endpoint API) yang menerima data saat tombol Daftar ditekan. Boleh berbeda domain/subdomain dari aplikasi.">
			<InputAlamat id="reg-aksi" urlDasar={app.url_dasar} bind:value={p.registrasi.jalur_aksi} placeholder="https://api.satuan.mil.id/auth/register" invalid={alamatSalah(p.registrasi.jalur_aksi)} />
			{@render pesan(p.registrasi.jalur_aksi)}
		</Field>
	</div>
	<Field label="Kolom username/email" id="reg-id" wajib info="Nama teknis kolom (atribut name) untuk username atau email.">
		<Input id="reg-id" class="h-9 font-mono" bind:value={p.registrasi.field_identitas} placeholder="email" />
	</Field>
	<div class="grid grid-cols-2 items-start gap-2">
		<Field label="Kolom kata sandi" id="reg-pass" wajib>
			<Input id="reg-pass" class="h-9 font-mono" bind:value={p.registrasi.field_password} placeholder="password" />
		</Field>
		<Field label="Kolom ulangi kata sandi" id="reg-konf">
			<Input id="reg-konf" class="h-9 font-mono" bind:value={p.registrasi.field_konfirmasi} placeholder="password_confirm" />
		</Field>
	</div>
</div>
<div class="grid gap-2">
	<p class="text-sm font-medium">Kolom isian wajib lainnya <span class="font-normal text-muted-foreground">— beserta contoh isian yang dipakai mesin uji</span></p>
	{#each p.registrasi.field_lain as f, i (i)}
		<div class="grid grid-cols-[1fr_1fr_auto] gap-2">
			<Input class="h-9 font-mono text-xs" placeholder="nama_kolom" bind:value={f.nama} aria-label="Nama field {i + 1}" />
			<Input class="h-9" placeholder="contoh isian" bind:value={f.nilai} aria-label="Nilai field {i + 1}" />
			<Button type="button" variant="ghost" size="icon-sm" class="self-center text-muted-foreground hover:text-critical"
				onclick={() => p.registrasi.field_lain.splice(i, 1)} aria-label="Hapus field {f.nama || i + 1}"><Trash2 /></Button>
		</div>
	{/each}
	<Button type="button" variant="ghost" size="sm" class="justify-self-start text-gold"
		onclick={() => p.registrasi.field_lain.push({ nama: '', nilai: '' })}><Plus /> Tambah field</Button>
</div>
<Field label="Siapa yang menghapus akun uji?" id="reg-bersih" info="Bila aplikasi lemah, akun uji bisa ikut terbuat saat pengujian.">
	<Textarea id="reg-bersih" rows={2} bind:value={p.registrasi.catatan_pembersihan} placeholder="Mis. akun berawalan satya-uji- dihapus admin aplikasi setelah pengujian." />
</Field>
