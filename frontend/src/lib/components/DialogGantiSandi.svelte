<script lang="ts">
	// Pop-up ganti kata sandi akun yang sedang masuk (POST /auth/change-password).
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import FieldAuth from './FieldAuth.svelte';
	import TombolLihatSandi from './TombolLihatSandi.svelte';
	import { SYARAT_SANDI } from '#lib/validasi.js';
	import { api } from '#lib/api/client.js';
	import { GalatApi } from '#lib/api/http.js';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import LockKeyhole from '@lucide/svelte/icons/lock-keyhole';
	import Check from '@lucide/svelte/icons/check';
	import Circle from '@lucide/svelte/icons/circle';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	let { open = $bindable(false) }: { open?: boolean } = $props();

	let f = $state({ lama: '', baru: '', ulang: '' });
	let disentuh = $state({ lama: false, baru: false, ulang: false });
	let lihat = $state(false);
	let menyimpan = $state(false);
	let refLama = $state<HTMLInputElement | null>(null);
	// Galat dari server per kolom (mis. kata sandi lama salah); hilang saat kolomnya diubah.
	let galatServer = $state<{ lama: string | null; baru: string | null }>({ lama: null, baru: null });

	const galat = $derived({
		lama: !f.lama ? 'Isi kata sandi saat ini.' : null,
		baru: !SYARAT_SANDI.every((s) => s.cek(f.baru))
			? 'Kata sandi baru belum memenuhi syarat.'
			: f.baru === f.lama
				? 'Kata sandi baru harus berbeda dari yang lama.'
				: null,
		ulang: !f.ulang ? 'Ulangi kata sandi baru.' : f.ulang !== f.baru ? 'Kata sandi tidak sama.' : null
	});
	// Galat server (mis. "Kata sandi saat ini salah") didahulukan sampai kolomnya diubah.
	const tampil = (k: keyof typeof f) =>
		(k === 'ulang' ? null : galatServer[k]) ?? (disentuh[k] ? galat[k] : null);

	// Setiap kali dibuka, mulai dari form kosong.
	$effect(() => {
		if (!open) return;
		f = { lama: '', baru: '', ulang: '' };
		disentuh = { lama: false, baru: false, ulang: false };
		galatServer = { lama: null, baru: null };
		lihat = false;
	});

	async function simpan(e: SubmitEvent) {
		e.preventDefault();
		disentuh = { lama: true, baru: true, ulang: true };
		if (galat.lama || galat.baru || galat.ulang) return;
		menyimpan = true;
		try {
			await api.gantiSandi(f.lama, f.baru);
			toast.success('Kata sandi berhasil diubah. Sesi di perangkat lain telah dikeluarkan.');
			open = false;
		} catch (err) {
			const kolom = err instanceof GalatApi ? err.errors?.[0]?.field : undefined;
			if (kolom === 'passwordLama') {
				galatServer.lama = (err as Error).message;
				f.lama = '';
				refLama?.focus();
			} else if (kolom === 'passwordBaru') galatServer.baru = err instanceof GalatApi ? err.errors![0].message : null;
			else toast.error((err as Error).message);
		} finally {
			menyimpan = false;
		}
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content
		class="dark sudut-taktis gap-0 overflow-hidden rounded-none border-gold/35 bg-[#10150e] p-0 text-white sm:max-w-md"
		onOpenAutoFocus={(e) => {
			e.preventDefault();
			refLama?.focus();
		}}
	>
		<div class="bg-loreng flex items-center gap-3 border-b border-gold/30 px-5 py-4">
			<span class="grid size-10 place-items-center rounded-sm border border-gold/60 bg-black/40 text-gold">
				<LockKeyhole class="size-5" />
			</span>
			<Dialog.Header class="gap-0.5 text-left">
				<Dialog.Title class="font-heading text-lg tracking-[0.06em] uppercase">Ganti Password</Dialog.Title>
				<Dialog.Description class="text-xs text-white/60">Gunakan kata sandi kuat yang belum pernah dipakai.</Dialog.Description>
			</Dialog.Header>
		</div>

		<form class="grid gap-3 px-5 pt-4 pb-5" onsubmit={simpan} novalidate>
			<FieldAuth id="sandi-lama" label="Kata sandi saat ini" ikon={KeyRound} type={lihat ? 'text' : 'password'}
				autocomplete="current-password" bind:value={f.lama} bind:ref={refLama} galat={tampil('lama')}
				oninput={() => (galatServer.lama = null)}
				onblur={() => (disentuh.lama ||= !!f.lama)}>
				{#snippet kanan()}<TombolLihatSandi bind:lihat />{/snippet}
			</FieldAuth>
			<FieldAuth id="sandi-baru" label="Kata sandi baru" ikon={KeyRound} type={lihat ? 'text' : 'password'}
				autocomplete="new-password" bind:value={f.baru} galat={tampil('baru')}
				oninput={() => (galatServer.baru = null)}
				onblur={() => (disentuh.baru ||= !!f.baru)}>
				{#snippet bawah()}
					<ul class="grid w-full grid-cols-2 gap-x-3 gap-y-0.5">
						{#each SYARAT_SANDI as s (s.label)}
							{@const ok = s.cek(f.baru)}
							<li class={cn('flex items-center gap-1.5 transition-colors', ok ? 'text-[#9fe08a]' : 'text-white/45')}>
								{#if ok}<Check class="size-3" />{:else}<Circle class="size-3" />{/if}{s.label}
							</li>
						{/each}
					</ul>
				{/snippet}
			</FieldAuth>
			<FieldAuth id="sandi-ulang" label="Ulangi kata sandi baru" ikon={KeyRound} type={lihat ? 'text' : 'password'}
				autocomplete="new-password" bind:value={f.ulang} galat={tampil('ulang')}
				onblur={() => (disentuh.ulang ||= !!f.ulang)} />

			<div class="mt-2 flex justify-end gap-2">
				<Button type="button" variant="outline" class="border-white/15 bg-transparent text-white/80 hover:bg-white/5 hover:text-white"
					onclick={() => (open = false)}>Batal</Button>
				<Button type="submit" aria-disabled={menyimpan}
					class="bg-gold font-heading tracking-[0.1em] text-gold-foreground uppercase hover:bg-gold/90">
					{#if menyimpan}<LoaderCircle class="animate-spin" /> Menyimpan…{:else}Simpan{/if}
				</Button>
			</div>
		</form>
	</Dialog.Content>
</Dialog.Root>
