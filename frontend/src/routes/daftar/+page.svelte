<script lang="ts">
	import { tick } from 'svelte';
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { api } from '#lib/api/client.js';
	import { galatEmail as cekEmail, bukanEmailDinas, SYARAT_SANDI } from '#lib/validasi.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import AuthShell from '#lib/components/AuthShell.svelte';
	import FieldAuth from '#lib/components/FieldAuth.svelte';
	import ComboboxAuth from '#lib/components/ComboboxAuth.svelte';
	import StepperAuth from '#lib/components/StepperAuth.svelte';
	import TombolLihatSandi from '#lib/components/TombolLihatSandi.svelte';
	import { cn } from '#lib/utils.js';
	import User from '@lucide/svelte/icons/user';
	import IdCard from '@lucide/svelte/icons/id-card';
	import Building from '@lucide/svelte/icons/building-2';
	import Mail from '@lucide/svelte/icons/mail';
	import KeyRound from '@lucide/svelte/icons/key-round';
	import Check from '@lucide/svelte/icons/check';
	import Circle from '@lucide/svelte/icons/circle';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import MailCheck from '@lucide/svelte/icons/mail-check';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';

	type Kolom = 'nama' | 'nrp' | 'email' | 'satuan_id' | 'password' | 'ulang';

	// Pendaftaran bertahap: identitas (+ cek NRP/NIP) -> email dinas (+ cek email) -> satuan -> kata sandi.
	const LANGKAH = [
		{ label: 'Identitas', kolom: ['nama', 'nrp'] },
		{ label: 'Email', kolom: ['email'] },
		{ label: 'Satuan', kolom: ['satuan_id'] },
		{ label: 'Kata sandi', kolom: ['password', 'ulang'] }
	] as const satisfies readonly { label: string; kolom: readonly Kolom[] }[];

	let f = $state<Record<Kolom, string>>({ nama: '', nrp: '', email: '', satuan_id: '', password: '', ulang: '' });
	let disentuh = $state<Record<Kolom, boolean>>({
		nama: false,
		nrp: false,
		email: false,
		satuan_id: false,
		password: false,
		ulang: false
	});
	let langkah = $state(0);
	/** 1 = maju (isi baru masuk dari kanan), -1 = mundur. */
	let arah = $state(1);
	let lihatSandi = $state(false);
	let memeriksa = $state(false);
	let memuat = $state(false);
	let terkirim = $state(false);
	let goyang = $state(false);
	let galatServer = $state<string | null>(null);

	// Hasil cek ketersediaan dari server; nilai yang sudah lolos tidak dicek ulang (hemat rate limit).
	let terpakai = $state<{ nrp: string | null; email: string | null }>({ nrp: null, email: null });
	const lolosCek = $state({ nrp: '', email: '' });

	// Diisi null (bukan kosong) karena bind:ref ke prop yang punya nilai bawaan tidak boleh undefined.
	const ref = $state<Record<Exclude<Kolom, 'satuan_id'>, HTMLInputElement | null>>({
		nama: null,
		nrp: null,
		email: null,
		password: null,
		ulang: null
	});
	let refSatuan = $state<HTMLInputElement | null>(null);
	const fokus = (k: Kolom) => (k === 'satuan_id' ? refSatuan : ref[k])?.focus();

	// Satuan/instansi dicari di backend sambil mengetik (daftarnya bisa ribuan), lalu dipilih dari hasilnya.
	let namaSatuan = $state('');
	const cariSatuan = async (kata: string) =>
		(await api.cariSatuan(kata)).map((s) => ({ value: s.id, label: s.nama }));

	const galat = $derived<Record<Kolom, string | null>>({
		nama: f.nama.trim().length < 3 ? 'Nama lengkap wajib diisi.' : null,
		nrp: !/^\d{6,18}$/.test(f.nrp.trim()) ? 'NRP/NIP berupa 6–18 digit angka.' : null,
		email: cekEmail(f.email),
		satuan_id: !f.satuan_id ? 'Ketik lalu pilih satuan dari daftar.' : null,
		password: SYARAT_SANDI.every((s) => s.cek(f.password)) ? null : 'Kata sandi belum memenuhi syarat.',
		ulang: !f.ulang ? 'Ulangi kata sandi.' : f.ulang !== f.password ? 'Kata sandi tidak sama.' : null
	});
	const tampil = (k: Kolom) => (disentuh[k] ? galat[k] : null) ?? (k === 'nrp' || k === 'email' ? terpakai[k] : null);
	const sentuh = (k: Kolom) => () => (disentuh[k] ||= !!f[k]);

	const reduksiGerak = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
	const durasi = (ms: number) => (reduksiGerak() ? 0 : ms);

	function getar() {
		if (reduksiGerak()) return;
		goyang = true;
		setTimeout(() => (goyang = false), 350);
	}

	async function pindah(ke: number) {
		arah = ke > langkah ? 1 : -1;
		langkah = ke;
		galatServer = null;
		await tick();
		fokus(LANGKAH[ke].kolom[0]);
	}

	/** Cek NRP/NIP atau email belum terdaftar. false = berhenti di langkah ini. */
	async function cekTersedia(k: 'nrp' | 'email'): Promise<boolean> {
		const nilai = f[k].trim();
		if (lolosCek[k] === nilai) return true;
		memeriksa = true;
		try {
			const tersedia = await api.cekKetersediaan(k === 'nrp' ? { nrp: nilai } : { email: nilai });
			if (tersedia) {
				lolosCek[k] = nilai;
				return true;
			}
			terpakai[k] = k === 'nrp' ? 'NRP/NIP ini sudah terdaftar.' : 'Email ini sudah terdaftar.';
		} catch (err) {
			galatServer = (err as Error).message;
		} finally {
			memeriksa = false;
		}
		fokus(k);
		getar();
		return false;
	}

	async function lanjut(e: SubmitEvent) {
		e.preventDefault();
		if (memeriksa || memuat) return;
		galatServer = null;
		const { kolom } = LANGKAH[langkah];
		const salah = kolom.find((k) => galat[k]);
		if (salah) {
			for (const k of kolom) disentuh[k] = true;
			fokus(salah);
			getar();
			return;
		}
		if (langkah === 0 && !(await cekTersedia('nrp'))) return;
		if (langkah === 1 && !(await cekTersedia('email'))) return;
		if (langkah < LANGKAH.length - 1) return pindah(langkah + 1);

		memuat = true;
		try {
			await api.daftar({
				nama: f.nama.trim(),
				nrp: f.nrp.trim(),
				satuan_id: f.satuan_id,
				email: f.email.trim(),
				password: f.password
			});
			terkirim = true;
		} catch (err) {
			galatServer = (err as Error).message;
			getar();
		} finally {
			memuat = false;
		}
	}
</script>

<svelte:head><title>Daftar — SATYA</title></svelte:head>

{#if terkirim}
	<AuthShell judul="Pendaftaran terkirim" keterangan="Akun akan aktif setelah disetujui administrator.">
		<div class="flex flex-col items-center gap-4 rounded-md border border-success/30 bg-success/10 p-5 text-center">
			<MailCheck class="size-8 text-[#9fe08a]" />
			<p class="text-sm text-white/75">
				Pemberitahuan persetujuan akan dikirim ke <b class="text-white">{f.email}</b>.
			</p>
		</div>
		<Button href="/login" class="mt-6 h-11 w-full bg-gold font-heading tracking-[0.12em] text-gold-foreground uppercase hover:bg-gold/90">
			<ArrowLeft /> Kembali ke halaman masuk
		</Button>
	</AuthShell>
{:else}
	<AuthShell judul="Daftar akun" {goyang}>
		<StepperAuth langkah={langkah} label={LANGKAH.map((l) => l.label)} onpilih={pindah} />

		<form class="mt-5 grid gap-4" onsubmit={lanjut} novalidate>
			<!-- Isi langkah bergeser horizontal; lama & baru ditumpuk di sel grid yang sama selama transisi. -->
			<div class="-mx-1 grid overflow-x-clip px-1">
				{#key langkah}
					<div
						class="grid gap-2 [grid-area:1/1]"
						in:fly={{ x: 36 * arah, duration: durasi(320), delay: durasi(130), easing: cubicOut }}
						out:fly={{ x: -36 * arah, duration: durasi(130) }}
					>
						{#if langkah === 0}
							<div class="grid gap-2">
								<FieldAuth id="nama" label="Nama lengkap & pangkat" ikon={User} autocomplete="name" placeholder="Kapten Czi. Nama Lengkap"
									bind:value={f.nama} bind:ref={ref.nama} galat={tampil('nama')} onblur={sentuh('nama')} />
								<FieldAuth id="nrp" label="NRP / NIP" ikon={IdCard} inputmode="numeric" placeholder="11080012345"
									bind:value={f.nrp} bind:ref={ref.nrp} galat={tampil('nrp')} onblur={sentuh('nrp')}
									oninput={() => (terpakai.nrp = null)}>
									{#snippet kanan()}
										{#if lolosCek.nrp && lolosCek.nrp === f.nrp.trim()}
											<Check class="absolute top-1/2 right-3.5 size-4 -translate-y-1/2 text-[#9fe08a]" aria-label="NRP/NIP tersedia" />
										{/if}
									{/snippet}
									{#snippet bawah()}
										{#if terpakai.nrp}
											<span class="text-white/55">
												Sudah punya akun? <a href="/login" class="font-medium text-gold hover:underline">Masuk</a> ·
												<a href="/lupa-sandi" class="font-medium text-gold hover:underline">Lupa kata sandi</a>
											</span>
										{/if}
									{/snippet}
								</FieldAuth>
							</div>
						{:else if langkah === 1}
							<FieldAuth id="email" label="Email dinas" ikon={Mail} type="email" inputmode="email" autocomplete="email" spellcheck={false}
								placeholder="nama@satuan.mil.id" bind:value={f.email} bind:ref={ref.email} galat={tampil('email')}
								petunjuk={disentuh.email && bukanEmailDinas(f.email) ? 'Disarankan memakai email dinas (.mil.id / .go.id).' : null}
								onblur={sentuh('email')} oninput={() => (terpakai.email = null)}>
								{#snippet bawah()}
									{#if terpakai.email}
										<span class="text-white/55">
											Sudah punya akun? <a href="/login" class="font-medium text-gold hover:underline">Masuk</a> ·
											<a href="/lupa-sandi" class="font-medium text-gold hover:underline">Lupa kata sandi</a>
										</span>
									{/if}
								{/snippet}
							</FieldAuth>
						{:else if langkah === 2}
							<ComboboxAuth id="satuan" label="Satuan / instansi" ikon={Building} cari={cariSatuan}
								placeholder="Ketik nama satuan…" bind:value={f.satuan_id} bind:terpilih={namaSatuan} bind:ref={refSatuan}
								galat={tampil('satuan_id')} />
						{:else}
							<FieldAuth id="password" label="Kata sandi" ikon={KeyRound} type={lihatSandi ? 'text' : 'password'} autocomplete="new-password"
								bind:value={f.password} bind:ref={ref.password} galat={tampil('password')} onblur={sentuh('password')}>
								{#snippet kanan()}<TombolLihatSandi bind:lihat={lihatSandi} />{/snippet}
								{#snippet bawah()}
									<ul class="grid w-full grid-cols-2 gap-x-3 gap-y-0.5">
										{#each SYARAT_SANDI as s (s.label)}
											{@const ok = s.cek(f.password)}
											<li class={cn('flex items-center gap-1.5 transition-colors', ok ? 'text-[#9fe08a]' : 'text-white/45')}>
												{#if ok}<Check class="size-3" />{:else}<Circle class="size-3" />{/if}{s.label}
											</li>
										{/each}
									</ul>
								{/snippet}
							</FieldAuth>
							<FieldAuth id="ulang" label="Ulangi kata sandi" ikon={KeyRound} type={lihatSandi ? 'text' : 'password'} autocomplete="new-password"
								bind:value={f.ulang} bind:ref={ref.ulang} galat={tampil('ulang')} onblur={sentuh('ulang')} />
							<!-- Ringkasan data langkah sebelumnya sebelum dikirim. -->
							<dl class="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs">
								<dt class="text-white/45">Nama</dt><dd class="truncate text-white/80">{f.nama.trim()} · {f.nrp.trim()}</dd>
								<dt class="text-white/45">Email</dt><dd class="truncate text-white/80">{f.email.trim()}</dd>
								<dt class="text-white/45">Satuan</dt><dd class="truncate text-white/80">{namaSatuan}</dd>
							</dl>
						{/if}
					</div>
				{/key}
			</div>

			{#if galatServer}
				<p class="flex items-center gap-2 rounded-md border border-red-400/35 bg-red-500/10 px-3 py-2.5 text-sm text-red-200" role="alert">
					<CircleAlert class="size-4 shrink-0" />{galatServer}
				</p>
			{/if}

			<div class="flex gap-2">
				{#if langkah > 0}
					<Button type="button" variant="outline" onclick={() => pindah(langkah - 1)}
						class="h-11 border-white/15 bg-transparent px-4 text-white/80 hover:bg-white/5 hover:text-white">
						<ArrowLeft /> Kembali
					</Button>
				{/if}
				<Button type="submit" aria-disabled={memeriksa || memuat}
					class="group/lanjut h-11 flex-1 bg-gold font-heading text-[15px] tracking-[0.12em] text-gold-foreground uppercase hover:bg-gold/90">
					{#if memeriksa}<LoaderCircle class="animate-spin" /> Memeriksa…
					{:else if memuat}<LoaderCircle class="animate-spin" /> Mengirim…
					{:else if langkah === LANGKAH.length - 1}Daftar <Check />
					{:else}Lanjut <ArrowRight class="transition-transform group-hover/lanjut:translate-x-0.5" />{/if}
				</Button>
			</div>
		</form>

		<p class="mt-6 text-center text-sm text-white/60">
			Sudah punya akun? <a href="/login" class="font-medium text-gold hover:underline">Masuk</a>
		</p>
	</AuthShell>
{/if}
