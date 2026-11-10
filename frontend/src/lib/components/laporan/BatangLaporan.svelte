<script lang="ts">
	// Bar chart horizontal statis untuk laporan cetak (tanpa interaksi). Magnitude per kategori:
	// tiap baris diberi LABEL teks + nilai, jadi identitas tak bergantung warna saja (aman untuk CVD/cetak).
	// Warna mengikuti palet status/severity laporan (warna status bersifat reserved + berlabel).
	let {
		judul,
		data,
		satuan = ''
	}: { judul: string; data: { label: string; nilai: number; warna: string }[]; satuan?: string } = $props();

	const maks = $derived(Math.max(1, ...data.map((d) => d.nilai)));
</script>

<figure class="batang">
	<figcaption>{judul}</figcaption>
	{#each data as d (d.label)}
		<div class="baris">
			<span class="label">{d.label}</span>
			<span class="track">
				<span class="fill" style="width:{(d.nilai / maks) * 100}%;background:{d.warna}"></span>
			</span>
			<span class="nilai">{d.nilai}{satuan}</span>
		</div>
	{/each}
</figure>

<style>
	.batang {
		margin: 0 0 4mm;
		break-inside: avoid;
	}
	figcaption {
		font-size: 9pt;
		font-weight: 600;
		color: var(--tinta, #1f2a1f);
		margin-bottom: 1.5mm;
	}
	.baris {
		display: grid;
		grid-template-columns: 34mm 1fr 10mm;
		align-items: center;
		gap: 2mm;
		margin-bottom: 1mm;
	}
	.label {
		font-size: 8.5pt;
		color: var(--redup, #5b6658);
		text-transform: capitalize;
		text-align: right;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.track {
		height: 3.2mm;
		background: #eef0ea;
		border-radius: 1mm;
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		min-width: 0.6mm;
		border-radius: 1mm;
		print-color-adjust: exact;
		-webkit-print-color-adjust: exact;
	}
	.nilai {
		font-size: 8.5pt;
		font-weight: 600;
		color: var(--tinta, #1f2a1f);
		font-variant-numeric: tabular-nums;
		text-align: right;
	}
</style>
