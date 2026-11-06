<script lang="ts">
	import { tick } from 'svelte';
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { api } from '#lib/api/client.js';
	import type { StatusKepegawaian } from '#lib/types.js';
	import { galatEmail as cekEmail, bukanEmailDinas, SYARAT_SANDI } from '#lib/validasi.js';
	import { cariPangkat, PANGKAT } from '#lib/data/pangkat.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import LayarAuthPenuh from '#lib/components/LayarAuthPenuh.svelte';
	import FieldAuth from '#lib/components/FieldAuth.svelte';
	import ComboboxAuth from '#lib/components/ComboboxAuth.svelte';
	import StepperAuth from '#lib/components/StepperAuth.svelte';
	import TombolLihatSandi from '#lib/components/TombolLihatSandi.svelte';
	import SyaratSandi from '#lib/components/SyaratSandi.svelte';
	import { cn } from '#lib/utils.js';
	import User from '@lucide/svelte/icons/user';
	import UserRound from '@lucide/svelte/icons/user-round';
	import Medal from '@lucide/svelte/icons/medal';
	import IdCard from '@lucide/svelte/icons/id-card';
	import Building from '@lucide/svelte/icons/building-2';
	import Mail from '@lucide/svelte/icons/mail';
	import Lock from '@lucide/svelte/icons/lock';
	import LockKeyhole from '@lucide/svelte/icons/lock-keyhole';
	import Check from '@lucide/svelte/icons/check';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import MailCheck from '@lucide/svelte/icons/mail-check';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';

	type Kolom = 'nama' | 'status' | 'pangkat' | 'nrp' | 'satuan_id' | 'email' | 'password' | 'ulang';
	type Isian = Record<Exclude<Kolom, 'status'>, string> & { status: StatusKepegawaian };

	let f = $state<Isian>({
		nama: '',
		status: 'TNI',
		pangkat: '',
		nrp: '',
		satuan_id: '',
		email: '',
		password: '',
		ulang: ''
	});

	const pns = $derived(f.status === 'PNS');

	// Pendaftaran bertahap; NRP/NIP & email dicek ketersediaannya sebelum lanjut.
	const LANGKAH = $derived([
		{
			label: 'Identitas',
			kolom: ['nama', 'status'],
			ikon: UserRound,
			judul: 'Identitas Diri',
			sub: 'Masukkan informasi identitas Anda'
		},
		{
			label: 'Pangkat',
			kolom: ['pangkat'],
			ikon: Medal,
			judul: pns ? 'Golongan' : 'Pangkat',
			sub: pns ? 'Pilih golongan ruang Anda sebagai PNS' : 'Pilih pangkat Anda saat ini'
		},
		{
			label: 'NIP/NRP',
			kolom: ['nrp'],
			ikon: IdCard,
			judul: pns ? 'Nomor Induk Pegawai' : 'Nomor Registrasi Pokok',
			sub: pns ? 'Masukkan NIP Anda (18 digit)' : 'Masukkan NRP Anda'
		},
		{
			label: 'Satuan',
			kolom: ['satuan_id'],
			ikon: Building,
			judul: 'Satuan / Instansi',
			sub: 'Pilih satuan tempat Anda bertugas'
		},
		{
			label: 'Email',
			kolom: ['email'],
			ikon: Mail,
			judul: 'Email Dinas',
			sub: 'Pemberitahuan persetujuan akun dikirim ke email ini'
		},
		{
			label: 'Password',
			kolom: ['password', 'ulang'],
			ikon: Lock,
			judul: 'Buat Kata Sandi',
			sub: 'Buat kata sandi yang kuat untuk akun Anda'
		}
	] satisfies { label: string; kolom: Kolom[]; ikon: typeof User; judul: string; sub: string }[]);

	let disentuh = $state<Record<Kolom, boolean>>({
		nama: false,
		status: false,
		pangkat: false,
		nrp: false,
		satuan_id: false,
		email: false,
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

	const ref = $state<
		Record<'nama' | 'nrp' | 'email' | 'password' | 'ulang', HTMLInputElement | null>
	>({
		nama: null,
		nrp: null,
		email: null,
		password: null,
		ulang: null
	});
	let refPangkat = $state<HTMLInputElement | null>(null);
	let refSatuan = $state<HTMLInputElement | null>(null);
	let refStatus = $state<HTMLInputElement | null>(null);
	function fokus(k: Kolom) {
		if (k === 'status') return refStatus?.focus();
		if (k === 'pangkat') return refPangkat?.focus();
		if (k === 'satuan_id') return refSatuan?.focus();
		ref[k]?.focus();
	}

	// Satuan dicari di backend sambil mengetik (bisa ribuan); pangkat/golongan dari daftar lokal.
	let namaSatuan = $state('');
	let namaPangkat = $state('');
	const cariSatuan = async (kata: string) =>
		(await api.cariSatuan(kata)).map((s) => ({ value: s.id, label: s.nama }));
	const cariPangkatSesuaiStatus = async (kata: string) => cariPangkat(f.status, kata);

	// Ganti status → pangkat yang bukan milik status baru dikosongkan; NRP/NIP dicek ulang.
	function gantiStatus(s: StatusKepegawaian) {
		if (f.status === s) return;
		f.status = s;
		if (f.pangkat && !PANGKAT[s].includes(f.pangkat)) {
			f.pangkat = '';
			namaPangkat = '';
			disentuh.pangkat = false;
		}
		lolosCek.nrp = '';
		terpakai.nrp = null;
	}

	const galat = $derived<Record<Kolom, string | null>>({
		nama: f.nama.trim().length < 3 ? 'Nama lengkap wajib diisi (minimal 3 karakter).' : null,
		status: f.status !== 'TNI' && f.status !== 'PNS' ? 'Pilih status kepegawaian.' : null,
		pangkat: !f.pangkat
			? pns
				? 'Pilih golongan dari daftar.'
				: 'Pilih pangkat dari daftar.'
			: null,
		nrp: pns
			? !/^\d{18}$/.test(f.nrp.trim())
				? 'NIP berupa 18 digit angka.'
				: null
			: !/^\d{6,18}$/.test(f.nrp.trim())
				? 'NRP berupa 6–18 digit angka.'
				: null,
		satuan_id: !f.satuan_id ? 'Ketik lalu pilih satuan dari daftar.' : null,
		email: cekEmail(f.email),
		password: SYARAT_SANDI.every((s) => s.cek(f.password))
			? null
			: 'Kata sandi belum memenuhi syarat.',
		ulang: !f.ulang
			? 'Ulangi kata sandi.'
			: f.ulang !== f.password
				? 'Kata sandi tidak sama.'
				: null
	});
	const tampil = (k: Kolom) =>
		(disentuh[k] ? galat[k] : null) ?? (k === 'nrp' || k === 'email' ? terpakai[k] : null);
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
			terpakai[k] =
				k === 'nrp' ? `${pns ? 'NIP' : 'NRP'} ini sudah terdaftar.` : 'Email ini sudah terdaftar.';
		} catch (err) {
			galatServer = (err as Error).message;
		} finally {
			memeriksa = false;
		}
		fokus(k);
		getar();
		return false;
	}

	const L_NRP = 2;
	const L_EMAIL = 4;

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
		if (langkah === L_NRP && !(await cekTersedia('nrp'))) return;
		if (langkah === L_EMAIL && !(await cekTersedia('email'))) return;
		if (langkah < LANGKAH.length - 1) return pindah(langkah + 1);

		memuat = true;
		try {
			await api.daftar({
				nama: f.nama.trim(),
				status_kepegawaian: f.status,
				pangkat: f.pangkat,
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

	const sekarang = $derived(LANGKAH[langkah]);
	const terakhir = $derived(langkah === LANGKAH.length - 1);
</script>

<svelte:head><title>Daftar — SATRIA</title></svelte:head>

{#snippet tombolKembali()}
	{#if langkah > 0}
		<button
			type="button"
			onclick={() => pindah(langkah - 1)}
			class="group/mundur flex items-center gap-2 text-sm text-white/60 transition-colors hover:text-white"
		>
			<ArrowLeft class="size-4 transition-transform group-hover/mundur:-translate-x-0.5" /> Kembali
		</button>
	{:else}
		<a
			href="/login"
			class="group/mundur flex w-fit items-center gap-2 text-sm text-white/60 transition-colors hover:text-white"
		>
			<ArrowLeft class="size-4 transition-transform group-hover/mundur:-translate-x-0.5" /> Kembali
		</a>
	{/if}
{/snippet}

{#if terkirim}
	<LayarAuthPenuh label="Pendaftaran terkirim">
		<div class="flex flex-col items-center gap-4 text-center">
			<span class="grid size-16 place-items-center rounded-full border border-gold/40 bg-gold/10">
				<MailCheck class="size-8 text-gold" />
			</span>
			<div>
				<h1 class="font-heading text-2xl font-semibold">Pendaftaran terkirim</h1>
				<p class="mt-2 text-sm text-white/65">
					Akun akan aktif setelah disetujui administrator. Pemberitahuan dikirim ke
					<b class="text-white">{f.email}</b>.
				</p>
			</div>
		</div>
		<div class="mt-8 flex justify-center">
			<Button
				href="/login"
				class="h-11 bg-gold px-6 font-medium text-gold-foreground hover:bg-gold/90"
			>
				<ArrowLeft /> Kembali ke halaman masuk
			</Button>
		</div>
	</LayarAuthPenuh>
{:else}
	<LayarAuthPenuh label="Daftar akun SATRIA" {goyang}>
		<div>
			<StepperAuth {langkah} label={LANGKAH.map((l) => l.label)} onpilih={pindah} />
		</div>

		<form class="mt-8 grid" onsubmit={lanjut} novalidate>
			<!-- Isi langkah bergeser horizontal; lama & baru ditumpuk di sel grid yang sama selama transisi. -->
			<div class="-mx-1 grid overflow-x-clip px-1">
				{#key langkah}
					<div
						class="grid gap-5 [grid-area:1/1]"
						in:fly={{ x: 36 * arah, duration: durasi(320), delay: durasi(130), easing: cubicOut }}
						out:fly={{ x: -36 * arah, duration: durasi(130) }}
					>
						<!-- Kepala langkah: ikon + judul + keterangan. -->
						<div class="flex items-center gap-4">
							<span
								class="grid size-12 shrink-0 place-items-center rounded-full bg-gold/12 text-gold"
							>
								<sekarang.ikon class="size-6" />
							</span>
							<div class="min-w-0">
								<h1 class="font-heading text-[1.6rem] leading-tight font-semibold tracking-normal">
									{sekarang.judul}
								</h1>
								<p class="mt-0.5 text-sm text-white/55">{sekarang.sub}</p>
							</div>
						</div>

						{#if langkah === 0}
							<FieldAuth
								id="nama"
								label="Nama Lengkap"
								ikon={User}
								autocomplete="name"
								placeholder="Masukkan nama lengkap"
								bind:value={f.nama}
								bind:ref={ref.nama}
								galat={tampil('nama')}
								onblur={sentuh('nama')}
							/>

							<fieldset class="grid gap-2.5">
								<legend class="mb-2.5 text-sm font-medium text-white/85">Status</legend>
								<div class="flex gap-10" role="radiogroup" aria-label="Status kepegawaian">
									{#each ['TNI', 'PNS'] as const as s, i (s)}
										{@const pilih = f.status === s}
										<label
											class="group/radio flex cursor-pointer items-center gap-2.5 text-[15px] select-none"
										>
											{#if i === 0}
												<input
													type="radio"
													name="status"
													value={s}
													checked={pilih}
													onchange={() => gantiStatus(s)}
													bind:this={refStatus}
													class="peer sr-only"
												/>
											{:else}
												<input
													type="radio"
													name="status"
													value={s}
													checked={pilih}
													onchange={() => gantiStatus(s)}
													class="peer sr-only"
												/>
											{/if}
											<span
												class={cn(
													'grid size-5 place-items-center rounded-full border transition-colors peer-focus-visible:ring-3 peer-focus-visible:ring-gold/30',
													pilih
														? 'border-gold'
														: 'border-white/30 group-hover/radio:border-white/55'
												)}
											>
												<span
													class={cn(
														'size-2.5 rounded-full bg-gold transition-transform',
														pilih ? 'scale-100' : 'scale-0'
													)}
												></span>
											</span>
											<span class={pilih ? 'text-white' : 'text-white/70'}>{s}</span>
										</label>
									{/each}
								</div>
							</fieldset>
						{:else if langkah === 1}
							{#key f.status}
								<ComboboxAuth
									id="pangkat"
									label={pns ? 'Golongan' : 'Pangkat'}
									ikon={Medal}
									cari={cariPangkatSesuaiStatus}
									placeholder={pns
										? 'Ketik golongan, mis. Penata (III/c)…'
										: 'Ketik pangkat, mis. Kapten…'}
									bind:value={f.pangkat}
									bind:terpilih={namaPangkat}
									bind:ref={refPangkat}
									galat={tampil('pangkat')}
								/>
							{/key}
						{:else if langkah === 2}
							<FieldAuth
								id="nrp"
								label={pns ? 'NIP' : 'NRP'}
								ikon={IdCard}
								inputmode="numeric"
								placeholder={pns ? '18 digit, mis. 198501012010011001' : 'Mis. 11080012345'}
								bind:value={f.nrp}
								bind:ref={ref.nrp}
								galat={tampil('nrp')}
								onblur={sentuh('nrp')}
								oninput={() => (terpakai.nrp = null)}
							>
								{#snippet kanan()}
									{#if lolosCek.nrp && lolosCek.nrp === f.nrp.trim()}
										<Check
											class="absolute top-1/2 right-3.5 size-4 -translate-y-1/2 text-[#9fe08a]"
											aria-label="{pns ? 'NIP' : 'NRP'} tersedia"
										/>
									{/if}
								{/snippet}
								{#snippet bawah()}
									{#if terpakai.nrp}
										<span class="text-white/55">
											Sudah punya akun? <a
												href="/login"
												class="font-medium text-gold hover:underline">Masuk</a
											>
											·
											<a href="/lupa-sandi" class="font-medium text-gold hover:underline"
												>Lupa kata sandi</a
											>
										</span>
									{/if}
								{/snippet}
							</FieldAuth>
						{:else if langkah === 3}
							<ComboboxAuth
								id="satuan"
								label="Satuan / Instansi"
								ikon={Building}
								cari={cariSatuan}
								placeholder="Ketik nama satuan…"
								bind:value={f.satuan_id}
								bind:terpilih={namaSatuan}
								bind:ref={refSatuan}
								galat={tampil('satuan_id')}
							/>
						{:else if langkah === 4}
							<FieldAuth
								id="email"
								label="Email Dinas"
								ikon={Mail}
								type="email"
								inputmode="email"
								autocomplete="email"
								spellcheck={false}
								placeholder="nama@satuan.mil.id"
								bind:value={f.email}
								bind:ref={ref.email}
								galat={tampil('email')}
								petunjuk={disentuh.email && bukanEmailDinas(f.email)
									? 'Disarankan memakai email dinas (.mil.id / .go.id).'
									: null}
								onblur={sentuh('email')}
								oninput={() => (terpakai.email = null)}
							>
								{#snippet bawah()}
									{#if terpakai.email}
										<span class="text-white/55">
											Sudah punya akun? <a
												href="/login"
												class="font-medium text-gold hover:underline">Masuk</a
											>
											·
											<a href="/lupa-sandi" class="font-medium text-gold hover:underline"
												>Lupa kata sandi</a
											>
										</span>
									{/if}
								{/snippet}
							</FieldAuth>
						{:else}
							<FieldAuth
								id="password"
								label="Kata Sandi"
								ikon={Lock}
								type={lihatSandi ? 'text' : 'password'}
								autocomplete="new-password"
								placeholder="Minimal 8 karakter"
								bind:value={f.password}
								bind:ref={ref.password}
								galat={tampil('password')}
								onblur={sentuh('password')}
							>
								{#snippet kanan()}<TombolLihatSandi bind:lihat={lihatSandi} />{/snippet}
							</FieldAuth>
							<FieldAuth
								id="ulang"
								label="Konfirmasi Kata Sandi"
								ikon={LockKeyhole}
								type={lihatSandi ? 'text' : 'password'}
								autocomplete="new-password"
								placeholder="Ulangi kata sandi"
								bind:value={f.ulang}
								bind:ref={ref.ulang}
								galat={tampil('ulang')}
								onblur={sentuh('ulang')}
							>
								{#snippet kanan()}<TombolLihatSandi bind:lihat={lihatSandi} />{/snippet}
							</FieldAuth>
							<SyaratSandi sandi={f.password} class="-mt-1" />
						{/if}
					</div>
				{/key}
			</div>

			{#if galatServer}
				<p
					class="mt-5 flex items-center gap-2 rounded-md border border-red-400/35 bg-red-500/10 px-3 py-2.5 text-sm text-red-200"
					role="alert"
				>
					<CircleAlert class="size-4 shrink-0" />{galatServer}
				</p>
			{/if}

			<div class={cn('mt-8 flex', terakhir ? 'items-center justify-between gap-4' : 'justify-end')}>
				{#if terakhir}{@render tombolKembali()}{/if}
				<Button
					type="submit"
					aria-disabled={memeriksa || memuat}
					class="group/lanjut h-11 min-w-[150px] border border-gold/40 bg-gold px-6 text-[15px] font-medium text-gold-foreground hover:bg-gold/90"
				>
					{#if memeriksa}<LoaderCircle class="animate-spin" /> Memeriksa…
					{:else if memuat}<LoaderCircle class="animate-spin" /> Mengirim…
					{:else}{terakhir ? 'Daftar Sekarang' : 'Selanjutnya'}
						<ArrowRight class="transition-transform group-hover/lanjut:translate-x-0.5" />{/if}
				</Button>
			</div>
		</form>

		{#if !terakhir}
			<div class="mt-5">{@render tombolKembali()}</div>
		{/if}
	</LayarAuthPenuh>
{/if}
