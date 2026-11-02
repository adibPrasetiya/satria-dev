<script lang="ts">
	// Input seed TOTP: ketik base32 / tempel URI otpauth, ATAU scan QR (kamera, unggah, tempel gambar).
	// Semua diproses lokal di browser. Pratinjau kode live untuk dicocokkan dengan authenticator.
	import jsQR from 'jsqr';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import Field from '#lib/components/Field.svelte';
	import {
		kodeTotp,
		normalisasiSecret,
		parameterStandar,
		parseOtpauth,
		secretValid,
		type AlgoritmaTotp
	} from '#lib/totp.js';
	import { toast } from 'svelte-sonner';
	import ScanQrCode from '@lucide/svelte/icons/scan-qr-code';
	import Camera from '@lucide/svelte/icons/camera';
	import ImageUp from '@lucide/svelte/icons/image-up';
	import ClipboardPaste from '@lucide/svelte/icons/clipboard-paste';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';

	let {
		id,
		secret = $bindable(''),
		digits = $bindable(6),
		period = $bindable(30),
		algoritma = $bindable<AlgoritmaTotp>('SHA1')
	}: {
		id: string;
		secret?: string;
		digits?: number;
		period?: number;
		algoritma?: AlgoritmaTotp;
	} = $props();

	const terisi = $derived(!!secret?.trim());
	const valid = $derived(secretValid(secret));
	const standar = $derived(parameterStandar({ digits, period, algoritma }));

	// ---- ketik / tempel teks: URI otpauth langsung di-parse ----
	function terapkanUri(teks: string): boolean {
		const h = parseOtpauth(teks);
		if (!h) return false;
		secret = h.secret;
		digits = h.digits;
		period = h.period;
		algoritma = h.algoritma;
		toast.success(`Seed TOTP terbaca${h.issuer ? ` (${h.issuer})` : ''}`);
		return true;
	}
	// URI diterapkan saat ditempel atau saat kolom dikonfirmasi (blur/Enter) — bukan per ketikan,
	// karena URI setengah jadi (mis. `…?secret=J`) sudah ter-parse dan akan menimpa ketikan.
	// Yang belum lengkap/salah cukup ditandai inline.
	function saatKonfirmasi(e: Event) {
		const v = (e.currentTarget as HTMLInputElement).value;
		if (/^otpauth:\/\//i.test(v.trim())) terapkanUri(v);
	}
	const sepertiUri = $derived(/^otpauth:\/\//i.test(secret?.trim() ?? ''));
	const uriSiap = $derived(sepertiUri && parseOtpauth(secret ?? '') !== null);
	function saatTombol(e: KeyboardEvent) {
		if (e.key === 'Enter' && sepertiUri) {
			e.preventDefault();
			saatKonfirmasi(e);
		}
	}
	function resetParameter() {
		digits = 6;
		period = 30;
		algoritma = 'SHA1';
	}

	// ---- pratinjau kode live ----
	let kode = $state('');
	let sisa = $state(0);
	$effect(() => {
		if (!valid) {
			kode = '';
			return;
		}
		const s = normalisasiSecret(secret);
		const p = { digits, period, algoritma };
		let aktif = true;
		const segarkan = () =>
			kodeTotp(s, p)
				.then((r) => {
					if (!aktif) return;
					kode = r.kode;
					sisa = r.sisaDetik;
				})
				.catch(() => aktif && (kode = ''));
		segarkan();
		const t = setInterval(segarkan, 1000);
		return () => {
			aktif = false;
			clearInterval(t);
		};
	});
	const kodeTampil = $derived(kode.length > 4 ? `${kode.slice(0, Math.ceil(kode.length / 2))} ${kode.slice(Math.ceil(kode.length / 2))}` : kode);

	// ---- scan QR ----
	let dlgScan = $state(false);
	let galatScan = $state('');
	let kameraJalan = $state(false);
	let video = $state<HTMLVideoElement>();
	let fileEl = $state<HTMLInputElement>();
	let stream: MediaStream | null = null;
	let raf = 0;
	const kameraTersedia =
		typeof window !== 'undefined' && window.isSecureContext && !!navigator.mediaDevices?.getUserMedia;

	function terimaQr(data: string) {
		if (terapkanUri(data)) {
			dlgScan = false;
		} else {
			galatScan = 'QR terbaca, tetapi bukan kode TOTP (otpauth://totp).';
		}
	}

	function dekode(sumber: CanvasImageSource, w: number, h: number, pindaiInversi: boolean): string | null {
		const skala = Math.min(1, 1600 / Math.max(w, h));
		const cw = Math.max(1, Math.round(w * skala));
		const ch = Math.max(1, Math.round(h * skala));
		const kanvas = document.createElement('canvas');
		kanvas.width = cw;
		kanvas.height = ch;
		const ctx = kanvas.getContext('2d', { willReadFrequently: true });
		if (!ctx) return null;
		ctx.drawImage(sumber, 0, 0, cw, ch);
		const img = ctx.getImageData(0, 0, cw, ch);
		return jsQR(img.data, cw, ch, { inversionAttempts: pindaiInversi ? 'attemptBoth' : 'dontInvert' })?.data ?? null;
	}

	async function dariGambar(blob: Blob) {
		galatScan = '';
		try {
			const bmp = await createImageBitmap(blob);
			const data = dekode(bmp, bmp.width, bmp.height, true);
			bmp.close();
			if (data) terimaQr(data);
			else galatScan = 'QR tidak terdeteksi pada gambar. Pastikan QR utuh & cukup jelas.';
		} catch {
			galatScan = 'Gambar tidak dapat dibaca.';
		}
	}

	function gambarDariClipboard(e: ClipboardEvent): Blob | null {
		for (const item of e.clipboardData?.items ?? []) {
			if (item.type.startsWith('image/')) return item.getAsFile();
		}
		return null;
	}
	function saatTempel(e: ClipboardEvent) {
		const blob = gambarDariClipboard(e);
		if (blob) {
			e.preventDefault();
			dlgScan = true;
			dariGambar(blob);
			return;
		}
		const teks = e.clipboardData?.getData('text') ?? '';
		if (/^otpauth:\/\//i.test(teks.trim())) {
			e.preventDefault();
			if (!terapkanUri(teks)) toast.error('URI otpauth tidak valid atau bukan TOTP.');
			else dlgScan = false;
		}
	}

	async function mulaiKamera() {
		galatScan = '';
		try {
			stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
			if (!video) return hentikanKamera();
			video.srcObject = stream;
			await video.play();
			kameraJalan = true;
			const pindai = () => {
				if (!kameraJalan || !video) return;
				if (video.readyState >= 2 && video.videoWidth) {
					const data = dekode(video, video.videoWidth, video.videoHeight, false);
					if (data) {
						hentikanKamera();
						terimaQr(data);
						return;
					}
				}
				raf = requestAnimationFrame(pindai);
			};
			raf = requestAnimationFrame(pindai);
		} catch (err) {
			hentikanKamera();
			const nama = (err as DOMException)?.name;
			galatScan =
				nama === 'NotAllowedError'
					? 'Izin kamera ditolak. Izinkan kamera di browser, atau unggah/tempel gambar QR.'
					: nama === 'NotFoundError'
						? 'Kamera tidak ditemukan. Unggah atau tempel gambar QR.'
						: 'Kamera tidak dapat dibuka.';
		}
	}

	function hentikanKamera() {
		kameraJalan = false;
		cancelAnimationFrame(raf);
		stream?.getTracks().forEach((t) => t.stop());
		stream = null;
		if (video) video.srcObject = null;
	}

	// Tutup dialog → pastikan kamera mati.
	$effect(() => {
		if (!dlgScan) hentikanKamera();
		else galatScan = '';
	});
</script>

<div class="grid gap-2">
<Field label="Secret TOTP (MFA)" {id} bantuan="Opsional. Ketik seed base32, tempel URI otpauth://, atau scan QR dari halaman aktivasi MFA aplikasi target.">
	<div class="flex gap-2">
		<Input
			{id}
			class="h-9 flex-1 font-mono"
			autocomplete="off"
			spellcheck={false}
			placeholder="mis. JBSWY3DPEHPK3PXP"
			aria-invalid={terisi && !valid && !uriSiap}
			bind:value={secret}
			onchange={saatKonfirmasi}
			onkeydown={saatTombol}
			onpaste={saatTempel}
		/>
		<Button type="button" variant="outline" class="h-9 shrink-0" onclick={() => (dlgScan = true)}>
			<ScanQrCode /> Scan QR
		</Button>
	</div>
</Field>

{#if uriSiap}
	<p class="text-xs text-info">URI otpauth terdeteksi — tekan Enter atau pindah kolom untuk menerapkan.</p>
{:else if terisi && !valid}
	<p class="text-xs text-critical">
		{sepertiUri ? 'URI otpauth belum lengkap, tidak valid, atau bukan TOTP.' : 'Seed bukan base32 yang valid (huruf A–Z & angka 2–7).'}
	</p>
{/if}

{#if valid}
	<div class="flex items-center gap-3 rounded-md border border-black/40 bg-[#0d120c] px-3 py-2">
		<div class="min-w-0 flex-1">
			<p class="font-heading text-[9px] tracking-[0.2em] text-white/50 uppercase">Kode saat ini</p>
			<p class="font-mono text-xl tracking-[0.25em] text-[#9fe08a] tabular-nums">{kodeTampil || '······'}</p>
			<div class="mt-1 h-1 overflow-hidden rounded-full bg-white/10">
				<span class="block h-full bg-[#9fe08a]/70 transition-[width] duration-1000 ease-linear" style="width: {period ? (sisa / period) * 100 : 0}%"></span>
			</div>
		</div>
		<div class="text-right">
			<p class="font-stencil text-lg text-[#9fe08a]/80 tabular-nums">{sisa}s</p>
			{#if !standar}
				<button type="button" onclick={resetParameter} title="Kembalikan ke 6 digit · 30 dtk · SHA1" class="inline-flex items-center gap-1 rounded-sm border border-[#f5c451]/40 px-1.5 py-px font-heading text-[9px] tracking-wide text-[#f5c451] uppercase hover:bg-[#f5c451]/10">
					{digits} digit · {period} dtk · {algoritma} <RotateCcw class="size-2.5" />
				</button>
			{/if}
		</div>
	</div>
	<p class="text-[11px] text-muted-foreground">Cocokkan dengan kode di aplikasi authenticator Anda.</p>
{/if}
</div>

<Dialog.Root bind:open={dlgScan}>
	<Dialog.Content class="max-h-[92svh] overflow-y-auto sm:max-w-md" onpaste={saatTempel}>
		<Dialog.Header>
			<Dialog.Title>Scan QR TOTP</Dialog.Title>
			<Dialog.Description>Arahkan kamera ke QR aktivasi MFA, unggah gambarnya, atau tempel screenshot (Ctrl+V).</Dialog.Description>
		</Dialog.Header>

		<div class="sudut-taktis relative grid aspect-[4/3] max-h-[45svh] w-full place-items-center overflow-hidden rounded-lg border bg-[#0d120c]">
			<!-- svelte-ignore a11y_media_has_caption -->
			<video bind:this={video} class={kameraJalan ? 'size-full object-cover' : 'hidden'} playsinline muted></video>
			{#if kameraJalan}
				<div class="pointer-events-none absolute inset-[18%] rounded-md border-2 border-[#9fe08a]/70 shadow-[0_0_0_9999px_rgb(0_0_0/0.35)]"></div>
				<div class="pointer-events-none absolute inset-x-[18%] top-1/2 h-px animate-pulse bg-[#9fe08a]"></div>
			{:else}
				<div class="grid place-items-center gap-2 p-6 text-center text-white/60">
					<ScanQrCode class="size-10 text-[#9fe08a]/70" />
					<p class="text-xs">Kamera belum aktif.</p>
					<p class="flex items-center gap-1 text-[11px] text-white/40"><ClipboardPaste class="size-3" /> Tempel screenshot QR di sini (Ctrl+V)</p>
				</div>
			{/if}
		</div>

		{#if galatScan}<p class="text-xs text-critical">{galatScan}</p>{/if}

		<div class="grid grid-cols-2 gap-2">
			{#if kameraJalan}
				<Button type="button" variant="outline" onclick={hentikanKamera}><Camera /> Hentikan kamera</Button>
			{:else}
				<Button type="button" variant="outline" onclick={mulaiKamera} disabled={!kameraTersedia} title={kameraTersedia ? '' : 'Kamera butuh HTTPS atau localhost'}>
					<Camera /> Buka kamera
				</Button>
			{/if}
			<Button type="button" variant="outline" onclick={() => fileEl?.click()}><ImageUp /> Unggah gambar</Button>
		</div>
		{#if !kameraTersedia}
			<p class="text-[11px] text-muted-foreground">Kamera hanya tersedia pada koneksi aman (HTTPS/localhost). Unggah atau tempel gambar tetap bisa.</p>
		{/if}
		<input
			bind:this={fileEl}
			type="file"
			accept="image/*"
			class="sr-only"
			tabindex="-1"
			aria-label="Unggah gambar QR"
			onchange={(e) => {
				const f = (e.currentTarget as HTMLInputElement).files?.[0];
				if (f) dariGambar(f);
				(e.currentTarget as HTMLInputElement).value = '';
			}}
		/>
	</Dialog.Content>
</Dialog.Root>
