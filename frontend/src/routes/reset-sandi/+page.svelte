<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import { SYARAT_SANDI } from '#lib/validasi.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import AuthShell from '#lib/components/AuthShell.svelte';
	import FieldAuth from '#lib/components/FieldAuth.svelte';
	import TombolLihatSandi from '#lib/components/TombolLihatSandi.svelte';
	import { cn } from '#lib/utils.js';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import Check from '@lucide/svelte/icons/check';
	import Circle from '@lucide/svelte/icons/circle';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';

	const token = $derived(page.url.searchParams.get('token') ?? '');

	let password = $state('');
	let ulang = $state('');
	let lihat = $state(false);
	let disentuh = $state({ password: false, ulang: false });
	let memuat = $state(false);
	let selesai = $state(false);
	let galatServer = $state<string | null>(null);
	let refSandi = $state<HTMLInputElement | null>(null);
	let refUlang = $state<HTMLInputElement | null>(null);

	const galatSandi = $derived(SYARAT_SANDI.every((s) => s.cek(password)) ? null : 'Kata sandi belum memenuhi syarat.');
	const galatUlang = $derived(!ulang ? 'Ulangi kata sandi.' : ulang !== password ? 'Kata sandi tidak sama.' : null);

	$effect(() => {
		if (refSandi && matchMedia('(pointer: fine)').matches) refSandi.focus();
	});

	async function kirim(e: SubmitEvent) {
		e.preventDefault();
		galatServer = null;
		if (galatSandi || galatUlang) {
			disentuh = { password: true, ulang: true };
			(galatSandi ? refSandi : refUlang)?.focus();
			return;
		}
		memuat = true;
		try {
			await api.resetSandi(token, password);
			selesai = true;
		} catch (err) {
			galatServer = (err as Error).message;
		} finally {
			memuat = false;
		}
	}
</script>

<svelte:head><title>Atur ulang kata sandi — SATYA</title></svelte:head>

{#if !token}
	<AuthShell judul="Tautan tidak valid" keterangan="Tautan atur ulang kata sandi tidak lengkap atau sudah tidak berlaku.">
		<Button href="/lupa-sandi" class="h-10 w-full bg-gold font-heading tracking-[0.12em] text-gold-foreground uppercase hover:bg-gold/90">
			Minta tautan baru
		</Button>
	</AuthShell>
{:else if selesai}
	<AuthShell judul="Kata sandi diperbarui" keterangan="Semua sesi lama telah dikeluarkan. Silakan masuk dengan kata sandi baru.">
		<div class="mb-5 flex justify-center"><ShieldCheck class="size-10 text-[#9fe08a]" /></div>
		<Button href="/login" class="h-10 w-full bg-gold font-heading tracking-[0.12em] text-gold-foreground uppercase hover:bg-gold/90">
			Masuk
		</Button>
	</AuthShell>
{:else}
	<AuthShell judul="Atur ulang kata sandi" keterangan="Buat kata sandi baru untuk akun Anda.">
		<form class="grid gap-4" onsubmit={kirim} novalidate>
			<FieldAuth id="password" label="Kata sandi baru" ikon={KeyRound} type={lihat ? 'text' : 'password'} autocomplete="new-password"
				bind:value={password} bind:ref={refSandi} galat={disentuh.password ? galatSandi : null}
				onblur={() => (disentuh.password ||= !!password)} oninput={() => (galatServer = null)}>
				{#snippet kanan()}<TombolLihatSandi bind:lihat />{/snippet}
				{#snippet bawah()}
					{#if password || disentuh.password}
						<ul class="grid w-full grid-cols-2 gap-x-3 gap-y-0.5">
							{#each SYARAT_SANDI as s (s.label)}
								{@const ok = s.cek(password)}
								<li class={cn('flex items-center gap-1.5', ok ? 'text-[#9fe08a]' : 'text-white/45')}>
									{#if ok}<Check class="size-3" />{:else}<Circle class="size-3" />{/if}{s.label}
								</li>
							{/each}
						</ul>
					{/if}
				{/snippet}
			</FieldAuth>
			<FieldAuth id="ulang" label="Ulangi kata sandi baru" ikon={KeyRound} type={lihat ? 'text' : 'password'} autocomplete="new-password"
				bind:value={ulang} bind:ref={refUlang} galat={disentuh.ulang ? galatUlang : null}
				onblur={() => (disentuh.ulang ||= !!ulang)} oninput={() => (galatServer = null)} />

			{#if galatServer}
				<div class="flex items-start gap-2 rounded-md border border-red-400/35 bg-red-500/10 px-3 py-2.5 text-sm text-red-200" role="alert">
					<CircleAlert class="mt-0.5 size-4 shrink-0" />
					<div>
						<p>{galatServer}</p>
						<a href="/lupa-sandi" class="text-xs font-medium text-gold hover:underline">Minta tautan baru</a>
					</div>
				</div>
			{/if}

			<Button type="submit" aria-disabled={memuat} class="mt-2 h-10 bg-gold font-heading text-[15px] tracking-[0.12em] text-gold-foreground uppercase hover:bg-gold/90">
				{#if memuat}<LoaderCircle class="animate-spin" /> Menyimpan…{:else}Simpan kata sandi{/if}
			</Button>
		</form>
		<p class="mt-5 text-center text-sm text-white/60">
			<a href="/login" class="inline-flex items-center gap-1 font-medium text-gold hover:underline">
				<ArrowLeft class="size-3.5" /> Kembali ke halaman masuk
			</a>
		</p>
	</AuthShell>
{/if}
