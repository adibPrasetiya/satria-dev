<script lang="ts">
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import { SYARAT_SANDI } from '#lib/validasi.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import LayarAuthPenuh from '#lib/components/LayarAuthPenuh.svelte';
	import FieldAuth from '#lib/components/FieldAuth.svelte';
	import TombolLihatSandi from '#lib/components/TombolLihatSandi.svelte';
	import SyaratSandi from '#lib/components/SyaratSandi.svelte';
	import Lock from '@lucide/svelte/icons/lock';
	import LockKeyhole from '@lucide/svelte/icons/lock-keyhole';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import LinkOff from '@lucide/svelte/icons/link-2-off';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';

	const token = $derived(page.url.searchParams.get('token') ?? '');

	let password = $state('');
	let ulang = $state('');
	let lihat = $state(false);
	let disentuh = $state({ password: false, ulang: false });
	let memuat = $state(false);
	let selesai = $state(false);
	let goyang = $state(false);
	let galatServer = $state<string | null>(null);
	let refSandi = $state<HTMLInputElement | null>(null);
	let refUlang = $state<HTMLInputElement | null>(null);

	const galatSandi = $derived(
		SYARAT_SANDI.every((s) => s.cek(password)) ? null : 'Kata sandi belum memenuhi syarat.'
	);
	const galatUlang = $derived(
		!ulang ? 'Ulangi kata sandi.' : ulang !== password ? 'Kata sandi tidak sama.' : null
	);

	$effect(() => {
		if (refSandi && matchMedia('(pointer: fine)').matches) refSandi.focus();
	});

	function getar() {
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		goyang = true;
		setTimeout(() => (goyang = false), 350);
	}

	async function kirim(e: SubmitEvent) {
		e.preventDefault();
		if (memuat) return;
		galatServer = null;
		if (galatSandi || galatUlang) {
			disentuh = { password: true, ulang: true };
			(galatSandi ? refSandi : refUlang)?.focus();
			getar();
			return;
		}
		memuat = true;
		try {
			await api.resetSandi(token, password);
			selesai = true;
		} catch (err) {
			galatServer = (err as Error).message;
			getar();
		} finally {
			memuat = false;
		}
	}
</script>

<svelte:head><title>Atur ulang kata sandi — SATRIA</title></svelte:head>

{#snippet hasil(
	Ikon: typeof ShieldCheck,
	judul: string,
	keterangan: string,
	href: string,
	tombol: string,
	nada: 'sukses' | 'galat'
)}
	<div class="flex flex-col items-center gap-4 text-center">
		<span
			class={nada === 'sukses'
				? 'grid size-16 place-items-center rounded-full border border-gold/40 bg-gold/10 text-gold'
				: 'grid size-16 place-items-center rounded-full border border-red-400/35 bg-red-500/10 text-red-300'}
		>
			<Ikon class="size-8" />
		</span>
		<div>
			<h1 class="font-heading text-2xl font-semibold">{judul}</h1>
			<p class="mx-auto mt-2 max-w-md text-sm text-white/65">{keterangan}</p>
		</div>
	</div>
	<div class="mt-8 flex justify-center">
		<Button
			{href}
			class="group/lanjut h-11 bg-gold px-6 font-medium text-gold-foreground hover:bg-gold/90"
		>
			{tombol}
			<ArrowRight class="transition-transform group-hover/lanjut:translate-x-0.5" />
		</Button>
	</div>
{/snippet}

{#if !token}
	<LayarAuthPenuh label="Tautan tidak valid">
		{@render hasil(
			LinkOff,
			'Tautan Tidak Valid',
			'Tautan atur ulang kata sandi tidak lengkap atau sudah tidak berlaku. Silakan minta tautan baru.',
			'/lupa-sandi',
			'Minta tautan baru',
			'galat'
		)}
	</LayarAuthPenuh>
{:else if selesai}
	<LayarAuthPenuh label="Kata sandi diperbarui">
		{@render hasil(
			ShieldCheck,
			'Kata Sandi Diperbarui',
			'Semua sesi lama telah dikeluarkan. Silakan masuk dengan kata sandi baru Anda.',
			'/login',
			'Masuk',
			'sukses'
		)}
	</LayarAuthPenuh>
{:else}
	<LayarAuthPenuh label="Atur ulang kata sandi" {goyang}>
		<form class="grid gap-5" onsubmit={kirim} novalidate>
			<!-- Kepala: ikon + judul + keterangan (selaras dengan langkah "Buat Kata Sandi"). -->
			<div class="flex items-center gap-4">
				<span class="grid size-12 shrink-0 place-items-center rounded-full bg-gold/12 text-gold">
					<Lock class="size-6" />
				</span>
				<div class="min-w-0">
					<h1 class="font-heading text-[1.6rem] leading-tight font-semibold tracking-normal">
						Atur Ulang Kata Sandi
					</h1>
					<p class="mt-0.5 text-sm text-white/55">Buat kata sandi baru yang kuat untuk akun Anda</p>
				</div>
			</div>

			<FieldAuth
				id="password"
				label="Kata Sandi Baru"
				ikon={Lock}
				type={lihat ? 'text' : 'password'}
				autocomplete="new-password"
				placeholder="Minimal 8 karakter"
				bind:value={password}
				bind:ref={refSandi}
				galat={disentuh.password ? galatSandi : null}
				onblur={() => (disentuh.password ||= !!password)}
				oninput={() => (galatServer = null)}
			>
				{#snippet kanan()}<TombolLihatSandi bind:lihat />{/snippet}
			</FieldAuth>
			<FieldAuth
				id="ulang"
				label="Konfirmasi Kata Sandi"
				ikon={LockKeyhole}
				type={lihat ? 'text' : 'password'}
				autocomplete="new-password"
				placeholder="Ulangi kata sandi"
				bind:value={ulang}
				bind:ref={refUlang}
				galat={disentuh.ulang ? galatUlang : null}
				onblur={() => (disentuh.ulang ||= !!ulang)}
				oninput={() => (galatServer = null)}
			>
				{#snippet kanan()}<TombolLihatSandi bind:lihat />{/snippet}
			</FieldAuth>
			<SyaratSandi sandi={password} class="-mt-1" />

			{#if galatServer}
				<div
					class="flex items-start gap-2 rounded-md border border-red-400/35 bg-red-500/10 px-3 py-2.5 text-sm text-red-200"
					role="alert"
				>
					<CircleAlert class="mt-0.5 size-4 shrink-0" />
					<div>
						<p>{galatServer}</p>
						<a href="/lupa-sandi" class="text-xs font-medium text-gold hover:underline">
							Minta tautan baru
						</a>
					</div>
				</div>
			{/if}

			<div class="mt-3 flex items-center justify-between gap-4">
				<a
					href="/login"
					class="group/mundur flex w-fit items-center gap-2 text-sm text-white/60 transition-colors hover:text-white"
				>
					<ArrowLeft class="size-4 transition-transform group-hover/mundur:-translate-x-0.5" /> Kembali
				</a>
				<Button
					type="submit"
					aria-disabled={memuat}
					class="group/lanjut h-11 min-w-[150px] border border-gold/40 bg-gold px-6 text-[15px] font-medium text-gold-foreground hover:bg-gold/90"
				>
					{#if memuat}<LoaderCircle class="animate-spin" /> Menyimpan…
					{:else}Simpan Kata Sandi
						<ArrowRight class="transition-transform group-hover/lanjut:translate-x-0.5" />{/if}
				</Button>
			</div>
		</form>
	</LayarAuthPenuh>
{/if}
