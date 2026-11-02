<script lang="ts">
	import type { PersiapanAuth } from '#lib/types.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import Field from '#lib/components/Field.svelte';
	import InputTotp from '#lib/components/InputTotp.svelte';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';

	let { p = $bindable() }: { p: PersiapanAuth } = $props();

	// Data lama belum punya parameter TOTP; isi default agar bisa di-bind (6 digit · 30 dtk · SHA1).
	for (const k of ['utama', 'penguncian'] as const) {
		const a = p.akun_uji[k];
		a.totp_secret ??= '';
		a.totp_digits ??= 6;
		a.totp_period ??= 30;
		a.totp_algoritma ??= 'SHA1';
	}
</script>

{#snippet sandi(idInput: string, label: string, akun: 'utama' | 'penguncian')}
	<Field label={label} id={idInput} info={p.akun_uji[akun].terisi ? 'Sudah tersimpan. Kosongkan untuk tetap memakai kata sandi lama.' : undefined}>
		<Input
			id={idInput}
			class="h-9"
			type="password"
			autocomplete="new-password"
			placeholder={p.akun_uji[akun].terisi ? '•••••••• (tersimpan)' : ''}
			bind:value={p.akun_uji[akun].password}
		/>
	</Field>
{/snippet}

{#snippet totp(idInput: string, akun: 'utama' | 'penguncian')}
	<div class="sm:col-span-2">
		<InputTotp
			id={idInput}
			bind:secret={p.akun_uji[akun].totp_secret}
			bind:digits={p.akun_uji[akun].totp_digits}
			bind:period={p.akun_uji[akun].totp_period}
			bind:algoritma={p.akun_uji[akun].totp_algoritma}
		/>
	</div>
{/snippet}

<div class="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/5 px-3 py-2 text-xs text-warning-foreground">
	<TriangleAlert class="mt-0.5 size-3.5 shrink-0" />
	<p>Gunakan akun yang dibuat khusus untuk SATYA dengan hak akses biasa. Kata sandi akun ini bisa diganti oleh mesin uji saat menguji fitur ubah kata sandi.</p>
</div>
<div class="grid gap-4 rounded-md border p-4 sm:grid-cols-2">
	<p class="label-stensil text-[10px] sm:col-span-2">Akun uji utama</p>
	<Field label="Username / email" id="akun-utama-user" wajib>
		<Input id="akun-utama-user" class="h-9" autocomplete="off" bind:value={p.akun_uji.utama.username} />
	</Field>
	{@render sandi('akun-utama-pass', 'Kata sandi', 'utama')}
	{@render totp('akun-utama-totp', 'utama')}
</div>
<div class="grid gap-4 rounded-md border border-dashed p-4 sm:grid-cols-2">
	<p class="label-stensil text-[10px] sm:col-span-2">Akun uji cadangan <span class="tracking-normal text-muted-foreground normal-case">(opsional — boleh terkunci)</span></p>
	<Field label="Username / email" id="akun-kunci-user">
		<Input id="akun-kunci-user" class="h-9" autocomplete="off" bind:value={p.akun_uji.penguncian.username} />
	</Field>
	{@render sandi('akun-kunci-pass', 'Kata sandi', 'penguncian')}
	{@render totp('akun-kunci-totp', 'penguncian')}
	<p class="text-xs text-muted-foreground sm:col-span-2">Hanya dipakai untuk uji penguncian akun, bila izin uji berisiko diberikan.</p>
</div>
