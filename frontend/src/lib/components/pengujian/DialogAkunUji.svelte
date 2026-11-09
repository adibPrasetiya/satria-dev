<script lang="ts" module>
	import type { AlgoritmaTotp } from '#lib/totp.js';

	export type AkunForm = {
		username: string;
		password: string;
		totp_secret: string;
		totp_digits: number;
		totp_period: number;
		totp_algoritma: AlgoritmaTotp;
	};

	export const akunKosong = (): AkunForm => ({
		username: '',
		password: '',
		totp_secret: '',
		totp_digits: 6,
		totp_period: 30,
		totp_algoritma: 'SHA1'
	});
</script>

<script lang="ts">
	// Form buat / ubah satu akun uji grey box (username, kata sandi, seed TOTP opsional).
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import Field from '#lib/components/Field.svelte';
	import InputTotp from '#lib/components/InputTotp.svelte';
	import { secretValid } from '#lib/totp.js';
	import UserPlus from '@lucide/svelte/icons/user-plus';
	import Eye from '@lucide/svelte/icons/eye';
	import EyeOff from '@lucide/svelte/icons/eye-off';

	let {
		open = $bindable(false),
		awal,
		nomor,
		usernameLain,
		onsimpan
	}: {
		open?: boolean;
		/** Akun yang diubah; null = buat akun baru. */
		awal: AkunForm | null;
		/** Nomor urut akun (1 = utama). */
		nomor: number;
		/** Username akun lain (cegah duplikat). */
		usernameLain: string[];
		onsimpan: (a: AkunForm) => void;
	} = $props();

	let f = $state<AkunForm>(akunKosong());
	let lihat = $state(false);
	let dicoba = $state(false);

	$effect(() => {
		if (open) {
			f = awal ? { ...awal } : akunKosong();
			lihat = false;
			dicoba = false;
		}
	});

	const galatUser = $derived(
		!f.username.trim()
			? 'Username wajib diisi'
			: usernameLain.some((u) => u.trim().toLowerCase() === f.username.trim().toLowerCase())
				? 'Username sudah dipakai akun lain'
				: null
	);
	const galatSandi = $derived(!f.password ? 'Kata sandi wajib diisi' : null);
	const galatTotp = $derived(f.totp_secret.trim() && !secretValid(f.totp_secret) ? 'Seed TOTP tidak valid' : null);

	function simpan(e: SubmitEvent) {
		e.preventDefault();
		dicoba = true;
		if (galatUser || galatSandi || galatTotp) return;
		onsimpan({ ...f, username: f.username.trim() });
		open = false;
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="gap-0 p-0 sm:max-w-lg">
		<Dialog.Header class="border-b px-5 py-4 text-left">
			<div class="flex items-center gap-3">
				<span class="flex size-9 items-center justify-center rounded-md border border-gold/40 bg-gold/10">
					<UserPlus class="size-4 text-gold" />
				</span>
				<div>
					<Dialog.Title class="font-heading tracking-wide uppercase">{awal ? 'Ubah' : 'Buat'} akun uji {nomor}</Dialog.Title>
					<Dialog.Description class="text-xs text-muted-foreground">
						{nomor === 1 ? 'Akun utama — dipakai untuk login & menelusuri aplikasi.' : 'Akun pembanding — dipakai menguji akses lintas akun.'}
					</Dialog.Description>
				</div>
			</div>
		</Dialog.Header>
		<form onsubmit={simpan} class="grid gap-4 px-5 py-4" autocomplete="off">
			<Field label="Username / email" id="akun-baru-user" wajib>
				<Input id="akun-baru-user" class="h-9" autocomplete="off" bind:value={f.username} />
				{#if dicoba && galatUser}<p class="mt-1 text-xs text-destructive">{galatUser}</p>{/if}
			</Field>
			<Field label="Kata sandi" id="akun-baru-pass" wajib>
				<div class="relative">
					<Input id="akun-baru-pass" class="h-9 pr-9" type={lihat ? 'text' : 'password'} autocomplete="new-password" bind:value={f.password} />
					<button
						type="button"
						onclick={() => (lihat = !lihat)}
						class="absolute top-1/2 right-2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
						aria-label={lihat ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
					>
						{#if lihat}<EyeOff class="size-4" />{:else}<Eye class="size-4" />{/if}
					</button>
				</div>
				{#if dicoba && galatSandi}<p class="mt-1 text-xs text-destructive">{galatSandi}</p>{/if}
			</Field>
			<InputTotp
				id="akun-baru-totp"
				bind:secret={f.totp_secret}
				bind:digits={f.totp_digits}
				bind:period={f.totp_period}
				bind:algoritma={f.totp_algoritma}
			/>
			{#if dicoba && galatTotp}<p class="-mt-2 text-xs text-destructive">{galatTotp}</p>{/if}
			<div class="flex justify-end gap-2 border-t pt-4">
				<Button type="button" variant="outline" onclick={() => (open = false)}>Batal</Button>
				<Button type="submit" class="bg-gold text-gold-foreground hover:bg-gold/85">{awal ? 'Simpan perubahan' : 'Tambahkan akun'}</Button>
			</div>
		</form>
	</Dialog.Content>
</Dialog.Root>
