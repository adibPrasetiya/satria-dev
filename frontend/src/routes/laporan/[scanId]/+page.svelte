<script lang="ts">
	// Laporan Hasil Asesmen (dokumen A4, siap cetak/PDF): Sampul · Daftar Isi · 1 Ringkasan Eksekutif ·
	// 2 Metode Uji · 3 Cakupan & Ruang Lingkup · 4 Temuan · 5 Rekomendasi Temuan · 6 Detail Seluruh
	// Pengujian · Pengesahan. Ringkasan eksekutif & rekomendasi disusun AI dari konteks yang disamarkan.
	// Laporan riwayat TERAKHIR tersimpan di backend; riwayat lain selalu di-generate saat dibuka.
	import { page } from '$app/state';
	import { api } from '#lib/api/client.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { katalog, LABEL_PUTUSAN, LABEL_STATUS, nilaiKelaikan } from '#lib/catalog.js';
	import { durasi } from '#lib/format.js';
	import type { Aplikasi, Scan } from '#lib/types.js';
	import {
		barisMetode,
		daftarTemuan,
		WARNA_SEVERITY,
		type BarisMetode
	} from '#lib/operasi/ringkas.js';
	import { bangunGraf } from '#lib/penemuan/graf.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import Memuat from '#lib/components/Memuat.svelte';
	import Kosong from '#lib/components/Kosong.svelte';
	import { cn } from '#lib/utils.js';
	import { toast } from 'svelte-sonner';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import Printer from '@lucide/svelte/icons/printer';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import Database from '@lucide/svelte/icons/database';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import ClipboardCheck from '@lucide/svelte/icons/clipboard-check';

	const scanId = $derived(page.params.scanId!);

	let scan = $state<Scan | null>(null);
	let app = $state<Aplikasi | null>(null);
	let galat = $state<string | null>(null);
	let menyusun = $state(false);
	let galatAi = $state<string | null>(null);

	async function generate() {
		if (!scan || menyusun) return;
		menyusun = true;
		galatAi = null;
		try {
			const s = await api.analisisAi(scan.id);
			if (scan && s.id === scan.id) scan.ai = s.ai;
			toast.success(
				s.ai?.disimpan
					? 'Laporan disusun & disimpan'
					: 'Laporan disusun (tidak disimpan — bukan riwayat terakhir)'
			);
		} catch (e) {
			galatAi = e instanceof Error ? e.message : 'AI gagal menyusun laporan';
		} finally {
			menyusun = false;
		}
	}

	$effect(() => {
		const sid = scanId;
		scan = null;
		galat = null;
		galatAi = null;
		api
			.getScan(sid)
			.then(async (s) => {
				app = await api.getAplikasi(s.aplikasi_id);
				scan = s;
				// Laporan tersimpan hanya untuk riwayat terakhir; selain itu (atau belum ada) → generate dulu.
				if (!s.ai && s.status !== 'berjalan') void generate();
			})
			.catch((e) => (galat = e.message));
	});

	// --- Data turunan ---
	const nilai = $derived(scan ? nilaiKelaikan(scan.hasil) : null);
	const baris = $derived(scan ? barisMetode(scan) : []);
	const temuan = $derived(daftarTemuan(baris));
	const graf = $derived(scan && app ? bangunGraf(scan.log, app.url_dasar) : null);
	const blackbox = $derived(scan?.pendekatan === 'blackbox');
	const nomor = $derived(
		scan
			? `LAP/SATRIA/${String(scan.id)
					.replace(/^scan-/, '')
					.toUpperCase()}/${new Date(scan.dimulai_pada).getFullYear()}`
			: ''
	);
	const tgl = (iso?: string) =>
		iso
			? new Date(iso).toLocaleDateString('id-ID', {
					day: 'numeric',
					month: 'long',
					year: 'numeric'
				})
			: '—';
	const waktu = (iso?: string) =>
		iso ? new Date(iso).toLocaleString('id-ID', { dateStyle: 'long', timeStyle: 'short' }) : '—';

	const SEV = ['kritis', 'tinggi', 'sedang', 'rendah'] as const;
	const perSev = $derived(
		SEV.map((s) => ({ s, n: temuan.filter((t) => t.severity === s).length }))
	);
	const rekomendasiPer = $derived(
		new Map((scan?.ai?.rekomendasi ?? []).map((r) => [r.metode_id, r]))
	);
	const perFungsiBaris = $derived.by(() => {
		const per = new Map<string, { id: string; nama: string; baris: BarisMetode[] }>();
		for (const b of baris) {
			const g = per.get(b.fungsi) ?? { id: b.fungsi, nama: b.namaFungsi, baris: [] };
			g.baris.push(b);
			per.set(b.fungsi, g);
		}
		return [...per.values()];
	});
	const fungsiDiuji = $derived(
		(nilai?.perFungsi ?? []).filter(
			(f) => f.hitungan.lulus + f.hitungan.gagal + f.hitungan.tidak_dapat_diverifikasi > 0
		)
	);

	const KLASIFIKASI = { biasa: 'BIASA', terbatas: 'TERBATAS', rahasia: 'RAHASIA' } as const;
	const klasifikasi = $derived(app ? KLASIFIKASI[app.klasifikasi_data] : 'TERBATAS');
	const WARNA_PUTUSAN = {
		laik: '#15803d',
		laik_bersyarat: '#b45309',
		tidak_laik: '#b91c1c'
	} as const;
	const PRIORITAS = {
		segera: 'Segera',
		tinggi: 'Tinggi',
		sedang: 'Sedang',
		rendah: 'Rendah'
	} as const;
	const WARNA_STATUS_CETAK: Record<string, string> = {
		lulus: '#15803d',
		gagal: '#b91c1c',
		tidak_dapat_diverifikasi: '#b45309',
		tidak_berlaku: '#6b7280',
		antre: '#6b7280',
		berjalan: '#0369a1'
	};

	const BAB = [
		[
			'ringkasan',
			'Ringkasan Eksekutif',
			'Kondisi keamanan, putusan kelaikan, dan prioritas tindak lanjut.'
		],
		['metode', 'Metode Uji', 'Pendekatan, tahapan, acuan, dan aturan penilaian.'],
		[
			'cakupan',
			'Cakupan & Ruang Lingkup',
			'Sasaran, periode, fungsi keamanan yang diuji, dan batasan.'
		],
		['temuan', 'Temuan', 'Daftar dan rincian metode uji yang tidak terpenuhi.'],
		[
			'rekomendasi',
			'Rekomendasi Temuan',
			'Langkah perbaikan per temuan dan rekomendasi strategis.'
		],
		['detail', 'Detail Informasi Seluruh Pengujian', 'Hasil setiap metode uji per fungsi keamanan.']
	] as const;
</script>

<svelte:head>
	<title>Laporan {app?.nama ?? ''} — SATRIA</title>
	<!-- Aturan halaman cetak: A4, nomor halaman & penanda klasifikasi di margin (Chrome 131+). -->
	{@html `<style>
		@page { size: A4; margin: 18mm 16mm 20mm;
			@top-right { content: "${klasifikasi}"; font: 700 8pt ui-sans-serif, system-ui; letter-spacing: .2em; color: #b91c1c; }
			@bottom-left { content: "SATRIA · ${nomor}"; font: 8pt ui-sans-serif, system-ui; color: #6b7280; }
			@bottom-right { content: "Halaman " counter(page) " dari " counter(pages); font: 8pt ui-sans-serif, system-ui; color: #6b7280; }
		}
		@page :first { margin: 0; @top-right { content: none } @bottom-left { content: none } @bottom-right { content: none } }
	</style>`}
</svelte:head>

{#if galat}
	<Kosong judul="Laporan tidak ditemukan" pesan={galat} />
{:else if !scan || !app || !nilai}
	<Memuat />
{:else}
	<!-- Bilah aksi (tidak tercetak) -->
	<div class="no-print mb-5 flex flex-wrap items-center gap-3">
		<a
			href="/scan/{scan.id}"
			class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
		>
			<ChevronLeft class="size-4" /> Operasi pengujian
		</a>
		<div class="ml-auto flex flex-wrap items-center gap-2">
			{#if scan.ai}
				<span
					class={cn(
						'inline-flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs',
						scan.ai.disimpan
							? 'border-success/40 bg-success/10 text-success'
							: 'border-warning/40 bg-warning/10 text-warning-foreground'
					)}
					title={scan.ai.disimpan
						? 'Laporan riwayat terakhir tersimpan di server'
						: 'Bukan riwayat pengujian terakhir — laporan disusun ulang setiap dibuka dan tidak disimpan'}
				>
					<Database class="size-3.5" />
					{scan.ai.disimpan ? 'Tersimpan (riwayat terakhir)' : 'Tidak disimpan'}
				</span>
			{/if}
			{#if auth.punya('asesor', 'admin') && nilai.hitungan.tidak_dapat_diverifikasi}
				<Button variant="outline" size="sm" href="/asesor/tinjau/{scan.id}"
					><ClipboardCheck /> Tinjau Manual</Button
				>
			{/if}
			<Button variant="outline" size="sm" onclick={generate} disabled={menyusun}>
				{#if menyusun}<LoaderCircle class="animate-spin" />{:else}<RefreshCw />{/if} Generate ulang
			</Button>
			<Button size="sm" onclick={() => window.print()} disabled={menyusun}
				><Printer /> Cetak / Unduh PDF</Button
			>
		</div>
	</div>

	{#if menyusun}
		<div
			class="no-print mb-5 flex items-start gap-3 rounded-lg border border-gold/40 bg-gold/10 px-4 py-3 text-sm"
		>
			<Sparkles class="mt-0.5 size-4 shrink-0 animate-pulse text-gold" />
			<div>
				<p class="font-medium">AI sedang menyusun ringkasan eksekutif & rekomendasi…</p>
				<p class="text-xs text-muted-foreground">
					Biasanya 30–60 detik. Data yang dikirim ke AI telah disamarkan (tanpa nama aplikasi,
					satuan, URL, akun, maupun token).
				</p>
			</div>
		</div>
	{:else if galatAi}
		<div
			class="no-print mb-5 flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm"
		>
			<TriangleAlert class="mt-0.5 size-4 shrink-0 text-destructive" />
			<div class="flex-1">
				<p class="font-medium">Ringkasan & rekomendasi AI belum tersedia</p>
				<p class="text-xs text-muted-foreground">{galatAi}</p>
			</div>
			<Button size="sm" variant="outline" onclick={generate}>Coba lagi</Button>
		</div>
	{/if}

	<div class="dokumen">
		<!-- ================= SAMPUL ================= -->
		<section class="lembar sampul">
			<div class="sampul-pita">
				<img src="/satria-lambang.png" alt="" class="size-16" />
				<div>
					<p class="sampul-label">Sistem Asesmen Kelaikan Keamanan Aplikasi</p>
					<p class="sampul-merek">SATRIA</p>
				</div>
				<span class="cap-klasifikasi">{klasifikasi}</span>
			</div>
			<div class="sampul-isi">
				<p class="sampul-jenis">Laporan Hasil Asesmen</p>
				<h1 class="sampul-judul">Kelaikan Keamanan Aplikasi Berbasis Web</h1>
				<div class="garis-emas"></div>
				<p class="sampul-aplikasi">{app.nama}</p>
				<p class="sampul-satuan">{app.satuan}</p>

				<dl class="sampul-meta">
					<dt>Nomor</dt>
					<dd>{nomor}</dd>
					<dt>Tanggal pengujian</dt>
					<dd>{tgl(scan.dimulai_pada)}</dd>
					<dt>Metode uji</dt>
					<dd>
						{blackbox ? 'Black Box' : 'Grey Box'} · {scan.mode === 'eksploratif'
							? 'eksploratif'
							: 'terarah'}
					</dd>
					<dt>Acuan</dt>
					<dd>{katalog.sumber.peraturan}</dd>
				</dl>

				<div class="sampul-putusan" style="--w:{WARNA_PUTUSAN[nilai.putusan]}">
					<span>Putusan{scan.status === 'selesai' ? '' : ' sementara'}</span>
					<strong>{LABEL_PUTUSAN[nilai.putusan]}</strong>
				</div>
			</div>
			<div class="sampul-kaki">
				Dokumen ini berklasifikasi <b>{klasifikasi}</b>. Dilarang menggandakan atau menyebarluaskan
				tanpa izin pemilik aplikasi.
				<span
					>Disusun otomatis oleh SATRIA{scan.ai
						? ` · ringkasan & rekomendasi dibantu AI (${scan.ai.model})`
						: ''}.</span
				>
			</div>
		</section>

		<!-- ================= DAFTAR ISI ================= -->
		<section class="lembar">
			<h2 class="judul-bab tanpa-nomor">Daftar Isi</h2>
			<ol class="daftar-isi">
				{#each BAB as [id, judul, ket], i (id)}
					<li>
						<a href="#{id}">
							<span class="di-nomor">{i + 1}</span>
							<span class="di-judul">{judul}<small>{ket}</small></span>
							<span class="di-titik"></span>
						</a>
					</li>
				{/each}
				<li>
					<a href="#pengesahan"
						><span class="di-nomor">—</span><span class="di-judul">Pengesahan</span><span
							class="di-titik"
						></span></a
					>
				</li>
			</ol>
		</section>

		<!-- ================= 1. RINGKASAN EKSEKUTIF ================= -->
		<section class="lembar" id="ringkasan">
			<h2 class="judul-bab"><span>1</span> Ringkasan Eksekutif</h2>
			<div class="kpi">
				<div class="kpi-putusan" style="--w:{WARNA_PUTUSAN[nilai.putusan]}">
					<small>Putusan kelaikan</small>
					<strong>{LABEL_PUTUSAN[nilai.putusan]}</strong>
				</div>
				<div><small>Skor kepatuhan</small><strong>{nilai.skor}%</strong></div>
				<div><small>Cakupan pengujian</small><strong>{nilai.cakupan}%</strong></div>
				<div><small>Jumlah temuan</small><strong>{temuan.length}</strong></div>
			</div>
			<div class="sebaran">
				{#each perSev as { s, n } (s)}
					<span><i style="background:{WARNA_SEVERITY[s]}"></i>{s} <b>{n}</b></span>
				{/each}
			</div>

			{#if scan.ai?.ringkasan_eksekutif}
				{#each scan.ai.ringkasan_eksekutif.split(/\n\s*\n/) as p, i (i)}
					<p class="paragraf">{p.replaceAll('**', '')}</p>
				{/each}
			{:else}
				<p class="paragraf">
					Pengujian {blackbox ? 'black box' : 'grey box'} terhadap aplikasi <b>{app.nama}</b>
					menghasilkan putusan
					<b>{LABEL_PUTUSAN[nilai.putusan]}</b> dengan skor kepatuhan {nilai.skor}% dan cakupan {nilai.cakupan}%.
					{#each nilai.alasan as a, i (i)}{a}
					{/each}
				</p>
				<p class="catatan no-print">
					{menyusun
						? 'Ringkasan naratif sedang disusun AI…'
						: 'Ringkasan naratif AI belum tersedia.'}
				</p>
			{/if}
		</section>

		<!-- ================= 2. METODE UJI ================= -->
		<section class="lembar" id="metode">
			<h2 class="judul-bab"><span>2</span> Metode Uji</h2>
			<h3>2.1 Pendekatan</h3>
			<table class="tabel kv">
				<tbody>
					<tr
						><th>Pendekatan</th><td
							><b>{blackbox ? 'Black Box' : 'Grey Box'}</b> — {blackbox
								? 'pengujian dari sudut pandang penyerang eksternal tanpa akun uji maupun informasi internal.'
								: 'pengujian dengan akses terbatas: memakai akun uji yang disediakan pemilik aplikasi.'}</td
						></tr
					>
					<tr
						><th>Mode</th><td
							>{scan.mode === 'eksploratif'
								? 'Eksploratif — permukaan aplikasi dipetakan otomatis (recon & discovery) sebelum pengujian.'
								: 'Terarah — titik uji dipetakan oleh pemilik aplikasi.'}</td
						></tr
					>
					<tr
						><th>Profil</th><td class="capitalize"
							>{scan.profil}
							{scan.profil === 'aman' ? '(tanpa uji yang berpotensi mengganggu layanan)' : ''}</td
						></tr
					>
					<tr><th>Acuan</th><td>{katalog.sumber.peraturan} — {katalog.sumber.bagian}</td></tr>
				</tbody>
			</table>
			<h3>2.2 Tahapan Pengujian</h3>
			<ol class="tahapan">
				{#if scan.mode === 'eksploratif'}
					<li>
						<b>Recon & Discovery.</b> Pemetaan halaman, endpoint API, spesifikasi API, dan aset statis
						aplikasi secara otomatis (hanya membaca).
					</li>
				{/if}
				<li>
					<b>Pengujian otomatis.</b> Setiap metode uji katalog dijalankan terhadap titik uji yang relevan;
					hasil dan buktinya direkam.
				</li>
				<li>
					<b>Evaluasi.</b> Hasil tiap metode dibandingkan dengan kriteria lulusnya; status kontrol diagregasi
					dari metodenya.
				</li>
				<li>
					<b>Penilaian kelaikan.</b> Putusan ditetapkan dari status kontrol menurut aturan di bawah.
				</li>
			</ol>
			<h3>2.3 Aturan Penilaian</h3>
			<table class="tabel">
				<thead><tr><th>Putusan</th><th>Kriteria</th></tr></thead>
				<tbody>
					<tr
						><td style="color:{WARNA_PUTUSAN.tidak_laik}"><b>Tidak Laik</b></td><td
							>Ada kontrol berseverity kritis atau tinggi yang tidak terpenuhi.</td
						></tr
					>
					<tr
						><td style="color:{WARNA_PUTUSAN.laik_bersyarat}"><b>Laik Bersyarat</b></td><td
							>Ada kontrol sedang/rendah yang gagal, kontrol yang belum terverifikasi, atau skor
							&lt; 100%.</td
						></tr
					>
					<tr
						><td style="color:{WARNA_PUTUSAN.laik}"><b>Laik</b></td><td
							>Seluruh kontrol yang berlaku terpenuhi.</td
						></tr
					>
				</tbody>
			</table>
			<p class="catatan">
				Skor kepatuhan = kontrol lulus ÷ (lulus + gagal). Cakupan = kontrol teruji ÷ kontrol yang
				berlaku.
			</p>
			{#if blackbox}
				<p class="catatan">
					Keterbatasan: pada black box, metode yang memerlukan login berstatus belum terverifikasi
					sehingga putusan tertinggi adalah Laik Bersyarat.
				</p>
			{/if}
		</section>

		<!-- ================= 3. CAKUPAN & RUANG LINGKUP ================= -->
		<section class="lembar" id="cakupan">
			<h2 class="judul-bab"><span>3</span> Cakupan & Ruang Lingkup</h2>
			<h3>3.1 Sasaran Pengujian</h3>
			<table class="tabel kv">
				<tbody>
					<tr><th>Aplikasi</th><td>{app.nama}</td></tr>
					<tr><th>Satuan / pemilik</th><td>{app.satuan} · PIC {app.pic_nama}</td></tr>
					<tr><th>URL sasaran</th><td class="mono">{app.url_dasar}</td></tr>
					<tr><th>Lingkungan</th><td class="capitalize">{app.lingkungan}</td></tr>
					<tr><th>Klasifikasi data</th><td class="capitalize">{app.klasifikasi_data}</td></tr>
					<tr
						><th>Teknologi</th><td
							>{[
								app.teknologi.frontend,
								app.teknologi.backend,
								app.teknologi.database,
								app.teknologi.server
							]
								.filter(Boolean)
								.join(' · ') || '—'}</td
						></tr
					>
					<tr
						><th>Periode pengujian</th><td
							>{waktu(scan.dimulai_pada)} — {waktu(scan.selesai_pada)} ({durasi(
								scan.dimulai_pada,
								scan.selesai_pada
							)})</td
						></tr
					>
				</tbody>
			</table>
			{#if graf && graf.peristiwa > 0}
				<h3>3.2 Hasil Recon & Discovery</h3>
				<div class="kpi kecil">
					<div><small>Halaman/URL</small><strong>{graf.hitung.halaman}</strong></div>
					<div><small>Endpoint API</small><strong>{graf.hitung.endpoint}</strong></div>
					<div><small>Aset JavaScript</small><strong>{graf.hitung.aset}</strong></div>
					<div><small>Titik uji terdeteksi</small><strong>{graf.hitung.titik}</strong></div>
				</div>
			{/if}
			<h3>{graf && graf.peristiwa > 0 ? '3.3' : '3.2'} Fungsi Keamanan yang Diuji</h3>
			<table class="tabel">
				<thead
					><tr
						><th>Fungsi keamanan</th><th class="angka">Lulus</th><th class="angka">Gagal</th><th
							class="angka">Belum terverifikasi</th
						><th class="angka">Skor</th></tr
					></thead
				>
				<tbody>
					{#each fungsiDiuji as f (f.fungsi.id)}
						<tr>
							<td><span class="mono">{f.fungsi.id}</span> {f.fungsi.nama}</td>
							<td class="angka">{f.hitungan.lulus}</td>
							<td class="angka">{f.hitungan.gagal}</td>
							<td class="angka">{f.hitungan.tidak_dapat_diverifikasi}</td>
							<td class="angka"><b>{f.skor === null ? '—' : `${f.skor}%`}</b></td>
						</tr>
					{/each}
				</tbody>
			</table>
			<p class="catatan">
				Di luar cakupan: {nilai.hitungan.tidak_berlaku} kontrol tidak berlaku untuk aplikasi ini. {nilai
					.hitungan.tidak_dapat_diverifikasi}
				kontrol belum dapat diverifikasi secara otomatis dan memerlukan bukti dokumen atau tinjauan asesor.
			</p>
		</section>

		<!-- ================= 4. TEMUAN ================= -->
		<section class="lembar" id="temuan">
			<h2 class="judul-bab"><span>4</span> Temuan</h2>
			{#if !temuan.length}
				<p class="paragraf">Tidak ditemukan metode uji yang gagal pada pengujian ini.</p>
			{:else}
				<h3>4.1 Daftar Temuan</h3>
				<table class="tabel">
					<thead
						><tr><th class="angka">No.</th><th>Kode</th><th>Temuan</th><th>Severity</th></tr></thead
					>
					<tbody>
						{#each temuan as t, i (t.id)}
							<tr>
								<td class="angka">{i + 1}</td>
								<td class="mono">{t.id}</td>
								<td>{t.nama}</td>
								<td
									><span class="sev" style="--s:{WARNA_SEVERITY[t.severity]}">{t.severity}</span
									></td
								>
							</tr>
						{/each}
					</tbody>
				</table>
				<h3>4.2 Rincian Temuan</h3>
				{#each temuan as t, i (t.id)}
					<article class="kartu-temuan" style="--s:{WARNA_SEVERITY[t.severity]}">
						<header>
							<span class="t-no">T-{String(i + 1).padStart(2, '0')}</span>
							<span class="t-judul">{t.nama}</span>
							<span class="sev" style="--s:{WARNA_SEVERITY[t.severity]}">{t.severity}</span>
						</header>
						<dl>
							<dt>Kode metode</dt>
							<dd class="mono">{t.id}</dd>
							<dt>Fungsi / kontrol</dt>
							<dd>{t.fungsi}{t.namaFungsi ? ` — ${t.namaFungsi}` : ''} · kontrol {t.kontrol}</dd>
							<dt>Hasil pengujian</dt>
							<dd>{t.ringkasan || '—'}</dd>
							<dt>Kriteria lulus</dt>
							<dd>{t.kriteria || '—'}</dd>
						</dl>
					</article>
				{/each}
			{/if}
		</section>

		<!-- ================= 5. REKOMENDASI ================= -->
		<section class="lembar" id="rekomendasi">
			<h2 class="judul-bab"><span>5</span> Rekomendasi Temuan</h2>
			{#if !scan.ai}
				<p class="paragraf">
					{menyusun
						? 'Rekomendasi sedang disusun AI…'
						: 'Rekomendasi AI belum tersedia. Gunakan tombol "Generate ulang" untuk menyusunnya.'}
				</p>
			{:else}
				{#if temuan.length}
					<h3>5.1 Rekomendasi per Temuan</h3>
					{#each temuan as t, i (t.id)}
						{@const r = rekomendasiPer.get(t.id)}
						<article class="kartu-rek">
							<header>
								<span class="t-no">T-{String(i + 1).padStart(2, '0')}</span>
								<span class="t-judul">{r?.judul ?? t.nama}</span>
								{#if r?.prioritas}<span class="prioritas p-{r.prioritas}"
										>Prioritas {PRIORITAS[r.prioritas]}</span
									>{/if}
							</header>
							{#if r}
								{#if r.penjelasan}<p>{r.penjelasan}</p>{/if}
								{#if r.langkah.length}
									<p class="sub">Langkah perbaikan</p>
									<ol>
										{#each r.langkah as l, j (j)}<li>{l}</li>{/each}
									</ol>
								{/if}
								{#if r.verifikasi}<p class="sub">Verifikasi</p>
									<p>{r.verifikasi}</p>{/if}
							{:else}
								<p>Perbaiki implementasi agar memenuhi kriteria lulus: {t.kriteria}</p>
							{/if}
						</article>
					{/each}
				{/if}
				{#if scan.ai.rekomendasi_umum?.length}
					<h3>{temuan.length ? '5.2' : '5.1'} Rekomendasi Umum</h3>
					<ol class="tahapan">
						{#each scan.ai.rekomendasi_umum as r, i (i)}<li>{r}</li>{/each}
					</ol>
				{/if}
				<p class="catatan">
					Rekomendasi disusun dengan bantuan AI ({scan.ai.provider ?? 'AI'} · {scan.ai.model}, {waktu(
						scan.ai.dibuat_pada
					)}) dari data pengujian yang telah disamarkan, dan perlu ditelaah oleh tim teknis sebelum
					diterapkan.
				</p>
			{/if}
		</section>

		<!-- ================= 6. DETAIL SELURUH PENGUJIAN ================= -->
		<section class="lembar" id="detail">
			<h2 class="judul-bab"><span>6</span> Detail Informasi Seluruh Pengujian</h2>
			<p class="paragraf">
				Total {baris.length} metode uji. Status: lulus {nilai.hitungan.lulus}, gagal {nilai.hitungan
					.gagal}, belum terverifikasi {nilai.hitungan.tidak_dapat_diverifikasi}, tidak berlaku {nilai
					.hitungan.tidak_berlaku} (hitungan per kontrol).
			</p>
			{#each perFungsiBaris as g (g.id)}
				<h3><span class="mono">{g.id}</span> {g.nama}</h3>
				<table class="tabel rapat">
					<thead
						><tr
							><th>Kode</th><th>Metode uji & hasil</th><th>Severity</th><th>Status</th><th
								class="angka">Durasi</th
							></tr
						></thead
					>
					<tbody>
						{#each g.baris as b (b.id)}
							<tr>
								<td class="mono">{b.id}</td>
								<td
									>{b.nama}{#if b.ringkasan}<small>{b.ringkasan}</small>{/if}</td
								>
								<td class="capitalize">{b.severity}</td>
								<td style="color:{WARNA_STATUS_CETAK[b.status]}">{LABEL_STATUS[b.status]}</td>
								<td class="angka"
									>{b.durasi_ms !== undefined ? `${(b.durasi_ms / 1000).toFixed(1)} dtk` : '—'}</td
								>
							</tr>
						{/each}
					</tbody>
				</table>
			{/each}
		</section>

		<!-- ================= PENGESAHAN ================= -->
		<section class="lembar" id="pengesahan">
			<h2 class="judul-bab tanpa-nomor">Pengesahan</h2>
			<p class="paragraf">
				Laporan ini disusun berdasarkan hasil pengujian otomatis SATRIA pada {tgl(
					scan.dimulai_pada
				)} dan berlaku untuk kondisi aplikasi pada saat pengujian. Perubahan aplikasi setelah tanggal
				tersebut memerlukan pengujian ulang.
			</p>
			<div class="ttd">
				<div>
					<p>Pemilik Aplikasi</p>
					<div class="ruang"></div>
					<p class="nama">{app.pic_nama}</p>
					<p class="jab">{app.satuan}</p>
				</div>
				<div>
					<p>Asesor</p>
					<div class="ruang"></div>
					<p class="nama">(.................................)</p>
					<p class="jab">NRP/NIP ...........................</p>
				</div>
			</div>
		</section>
	</div>
{/if}

<style>
	/* Dokumen bergaya kertas (terang) apa pun tema aplikasi; persona: hijau zaitun + emas SATRIA. */
	.dokumen {
		--tinta: #1f2a1f;
		--redup: #5b6658;
		--garis: #d9ded5;
		--zaitun: #2f3d24;
		--emas: #b8902f;
		color: var(--tinta);
		font-family: ui-sans-serif, system-ui, sans-serif;
		display: grid;
		gap: 24px;
		justify-items: center;
		background: #e7e9e3;
		margin: 0 -1rem;
		padding: 24px 1rem 48px;
		border-radius: 12px;
	}
	.lembar {
		width: min(210mm, 100%);
		min-height: 297mm;
		background: #fff;
		padding: 18mm 16mm;
		box-shadow:
			0 2px 4px rgb(0 0 0 / 0.06),
			0 12px 32px rgb(0 0 0 / 0.1);
		font-size: 10.5pt;
		line-height: 1.55;
	}
	/* --- sampul --- */
	.sampul {
		padding: 0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	.sampul-pita {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 14mm 16mm 10mm;
		background: linear-gradient(135deg, #253219, #3a4a2a);
		color: #f2efe2;
		print-color-adjust: exact;
		-webkit-print-color-adjust: exact;
	}
	.sampul-label {
		font-size: 8.5pt;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		opacity: 0.8;
	}
	.sampul-merek {
		font-family: var(--font-heading, inherit);
		font-size: 22pt;
		letter-spacing: 0.25em;
		font-weight: 700;
		color: #e6c46a;
	}
	.cap-klasifikasi {
		margin-left: auto;
		border: 2px solid #f87171;
		color: #fca5a5;
		padding: 4px 12px;
		font-weight: 800;
		letter-spacing: 0.25em;
		transform: rotate(-4deg);
	}
	.sampul-isi {
		flex: 1;
		padding: 22mm 16mm 10mm;
	}
	.sampul-jenis {
		font-size: 10pt;
		letter-spacing: 0.3em;
		text-transform: uppercase;
		color: var(--emas);
		font-weight: 700;
	}
	.sampul-judul {
		font-family: var(--font-heading, inherit);
		font-size: 26pt;
		line-height: 1.15;
		font-weight: 700;
		text-transform: uppercase;
		margin-top: 4mm;
		color: var(--zaitun);
	}
	.garis-emas {
		width: 70mm;
		height: 5px;
		margin: 7mm 0;
		background: repeating-linear-gradient(-60deg, var(--emas) 0 8px, transparent 8px 13px);
		print-color-adjust: exact;
		-webkit-print-color-adjust: exact;
	}
	.sampul-aplikasi {
		font-size: 18pt;
		font-weight: 700;
	}
	.sampul-satuan {
		font-size: 12pt;
		color: var(--redup);
	}
	.sampul-meta {
		display: grid;
		grid-template-columns: 42mm 1fr;
		gap: 2mm 6mm;
		margin-top: 14mm;
		font-size: 10.5pt;
	}
	.sampul-meta dt {
		color: var(--redup);
	}
	.sampul-meta dd {
		font-weight: 600;
	}
	.sampul-putusan {
		margin-top: 14mm;
		display: inline-flex;
		flex-direction: column;
		border: 3px solid var(--w);
		padding: 4mm 8mm;
		color: var(--w);
	}
	.sampul-putusan span {
		font-size: 8.5pt;
		letter-spacing: 0.2em;
		text-transform: uppercase;
	}
	.sampul-putusan strong {
		font-family: var(--font-heading, inherit);
		font-size: 22pt;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	.sampul-kaki {
		padding: 6mm 16mm 12mm;
		border-top: 1px solid var(--garis);
		font-size: 8.5pt;
		color: var(--redup);
		display: grid;
		gap: 1mm;
	}
	/* --- judul & isi --- */
	.judul-bab {
		display: flex;
		align-items: center;
		gap: 10px;
		font-family: var(--font-heading, inherit);
		font-size: 17pt;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--zaitun);
		padding-bottom: 3mm;
		margin-bottom: 6mm;
		border-bottom: 2px solid var(--zaitun);
	}
	.judul-bab span {
		display: grid;
		place-items: center;
		width: 10mm;
		height: 10mm;
		background: var(--zaitun);
		color: #e6c46a;
		font-size: 13pt;
		print-color-adjust: exact;
		-webkit-print-color-adjust: exact;
	}
	h3 {
		font-weight: 700;
		font-size: 11.5pt;
		margin: 7mm 0 3mm;
		color: var(--zaitun);
	}
	.paragraf {
		margin: 0 0 3mm;
		text-align: justify;
	}
	.catatan {
		font-size: 9pt;
		color: var(--redup);
		margin-top: 3mm;
	}
	.mono {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 9pt;
	}
	.capitalize {
		text-transform: capitalize;
	}
	/* --- daftar isi --- */
	.daftar-isi {
		display: grid;
		gap: 4mm;
		margin-top: 4mm;
	}
	.daftar-isi a {
		display: grid;
		grid-template-columns: 10mm 1fr auto;
		align-items: baseline;
		gap: 4mm;
		color: inherit;
		text-decoration: none;
	}
	.di-nomor {
		font-weight: 700;
		color: var(--emas);
		font-size: 13pt;
	}
	.di-judul {
		font-weight: 600;
		font-size: 11.5pt;
	}
	.di-judul small {
		display: block;
		font-weight: 400;
		font-size: 9pt;
		color: var(--redup);
	}
	.di-titik {
		width: 30mm;
		border-bottom: 1px dotted var(--redup);
	}
	/* --- KPI --- */
	.kpi {
		display: grid;
		grid-template-columns: 1.4fr 1fr 1fr 1fr;
		gap: 3mm;
		margin-bottom: 4mm;
	}
	.kpi.kecil {
		grid-template-columns: repeat(4, 1fr);
	}
	.kpi > div {
		border: 1px solid var(--garis);
		padding: 3mm 4mm;
	}
	.kpi small {
		display: block;
		font-size: 8pt;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--redup);
	}
	.kpi strong {
		font-size: 17pt;
		font-weight: 700;
	}
	.kpi-putusan {
		border-left: 4px solid var(--w) !important;
	}
	.kpi-putusan strong {
		color: var(--w);
		text-transform: uppercase;
		font-size: 14pt;
	}
	.sebaran {
		display: flex;
		flex-wrap: wrap;
		gap: 6mm;
		margin-bottom: 6mm;
		font-size: 9.5pt;
		text-transform: capitalize;
	}
	.sebaran i {
		display: inline-block;
		width: 9px;
		height: 9px;
		border-radius: 50%;
		margin-right: 5px;
		print-color-adjust: exact;
		-webkit-print-color-adjust: exact;
	}
	/* --- tabel --- */
	.tabel {
		width: 100%;
		border-collapse: collapse;
		font-size: 9.5pt;
	}
	.tabel th,
	.tabel td {
		border-bottom: 1px solid var(--garis);
		padding: 2mm 2.5mm;
		text-align: left;
		vertical-align: top;
	}
	.tabel thead th {
		background: #eef1ea;
		font-size: 8.5pt;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--zaitun);
		print-color-adjust: exact;
		-webkit-print-color-adjust: exact;
	}
	.tabel.kv th {
		width: 40mm;
		color: var(--redup);
		font-weight: 500;
	}
	.tabel.rapat td {
		padding: 1.4mm 2mm;
	}
	.tabel td small {
		display: block;
		color: var(--redup);
		font-size: 8.5pt;
	}
	.tabel .angka {
		text-align: right;
		white-space: nowrap;
	}
	.tabel tr {
		break-inside: avoid;
	}
	.tahapan {
		list-style: decimal;
		padding-left: 6mm;
		display: grid;
		gap: 2mm;
	}
	.sev {
		display: inline-block;
		padding: 0.5mm 2mm;
		border: 1px solid var(--s);
		color: var(--s);
		font-size: 8pt;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	/* --- kartu temuan / rekomendasi --- */
	.kartu-temuan,
	.kartu-rek {
		border: 1px solid var(--garis);
		border-left: 4px solid var(--s, var(--zaitun));
		padding: 3.5mm 4mm;
		margin-bottom: 4mm;
		break-inside: avoid;
	}
	.kartu-temuan header,
	.kartu-rek header {
		display: flex;
		align-items: baseline;
		gap: 3mm;
		margin-bottom: 2mm;
	}
	.t-no {
		font-weight: 700;
		color: var(--emas);
	}
	.t-judul {
		font-weight: 700;
		flex: 1;
	}
	.kartu-temuan dl {
		display: grid;
		grid-template-columns: 34mm 1fr;
		gap: 1.2mm 4mm;
		font-size: 9.5pt;
	}
	.kartu-temuan dt {
		color: var(--redup);
	}
	.kartu-rek p {
		margin: 0 0 2mm;
		font-size: 9.8pt;
	}
	.kartu-rek .sub {
		font-size: 8.5pt;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--redup);
		font-weight: 600;
		margin-top: 2.5mm;
	}
	.kartu-rek ol {
		list-style: decimal;
		padding-left: 5mm;
		font-size: 9.8pt;
		display: grid;
		gap: 1mm;
	}
	.prioritas {
		font-size: 8pt;
		font-weight: 700;
		padding: 0.5mm 2mm;
		text-transform: uppercase;
		border: 1px solid;
	}
	.p-segera {
		color: #b91c1c;
	}
	.p-tinggi {
		color: #c2410c;
	}
	.p-sedang {
		color: #a16207;
	}
	.p-rendah {
		color: #1d4ed8;
	}
	/* --- pengesahan --- */
	.ttd {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20mm;
		margin-top: 18mm;
		text-align: center;
	}
	.ttd .ruang {
		height: 26mm;
	}
	.ttd .nama {
		border-top: 1px solid var(--tinta);
		padding-top: 2mm;
		font-weight: 600;
	}
	.ttd .jab {
		font-size: 9pt;
		color: var(--redup);
	}

	@media (max-width: 640px) {
		.lembar {
			padding: 10mm 6mm;
			min-height: 0;
		}
		.kpi {
			grid-template-columns: 1fr 1fr;
		}
		.sampul-meta,
		.kartu-temuan dl {
			grid-template-columns: 1fr;
		}
	}
	@media print {
		.dokumen {
			display: block;
			background: none;
			margin: 0;
			padding: 0;
		}
		.lembar {
			width: auto;
			min-height: 0;
			box-shadow: none;
			padding: 0;
			break-before: page;
		}
		.lembar:first-child {
			break-before: auto;
		}
		.sampul {
			height: 297mm;
		}
		.sampul-isi {
			padding: 22mm 16mm 10mm;
		}
	}
</style>
