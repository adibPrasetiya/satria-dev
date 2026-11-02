<script lang="ts">
	// Jam format Date-Time Group militer, mis. "211430G OKT 26" (zona G = UTC+7 / WIB).
	const BULAN = ['JAN', 'FEB', 'MAR', 'APR', 'MEI', 'JUN', 'JUL', 'AGU', 'SEP', 'OKT', 'NOV', 'DES'];

	let kini = $state(new Date());

	$effect(() => {
		const t = setInterval(() => (kini = new Date()), 15_000);
		return () => clearInterval(t);
	});

	const dtg = $derived.by(() => {
		const wib = new Date(kini.getTime() + 7 * 3600_000);
		const dua = (n: number) => String(n).padStart(2, '0');
		return `${dua(wib.getUTCDate())}${dua(wib.getUTCHours())}${dua(wib.getUTCMinutes())}G ${BULAN[wib.getUTCMonth()]} ${String(wib.getUTCFullYear()).slice(2)}`;
	});
</script>

<span class="font-heading text-xs tracking-[0.15em] tabular-nums" title="Date-Time Group (WIB)">{dtg}</span>
