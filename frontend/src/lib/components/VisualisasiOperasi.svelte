<script lang="ts">
	// Visualisasi operasi gaya SOC/peretas: inti target, sapuan radar saat penemuan,
	// node endpoint/metode yang ter-scan, paket data mengalir, dan ledakan "temuan" (merah).
	// Kanvas + rAF; HUD di DOM. Menghormati prefers-reduced-motion.
	import { onMount } from 'svelte';
	import { cn } from '#lib/utils.js';
	import { AMBER, HIJAU, MERAH, SIAN, drawGrid, drawHex, hexA } from '#lib/penemuan/kanvas.js';

	let {
		fase,
		berjalan,
		persen,
		lulus,
		gagal,
		tdv,
		total,
		selesai,
		endpoint,
		host,
		sasaran,
		tepi = { atas: 0, kanan: 0 }
	}: {
		fase: 'penemuan' | 'pengujian' | 'selesai' | 'dihentikan';
		berjalan: boolean;
		persen: number;
		lulus: number;
		gagal: number;
		tdv: number;
		total: number;
		selesai: number;
		endpoint: number;
		host: string;
		sasaran: string | null;
		tepi?: { atas: number; kanan: number; bawah?: number };
	} = $props();

	type Node = {
		a: number; // sudut
		r: number; // radius sekarang
		tr: number; // radius target
		st: 'scan' | 'pass' | 'fail' | 'review';
		lahir: number;
		nadi: number;
		size: number;
	};
	type Partikel = { x: number; y: number; vx: number; vy: number; umur: number; max: number; w: string; s: number };
	type Paket = { node: number; t: number; kec: number; w: string };

	let kanvas = $state<HTMLCanvasElement>();
	let bungkus = $state<HTMLDivElement>();
	let reduced = false;

	// state animasi (tak reaktif)
	const nodes: Node[] = [];
	const partikel: Partikel[] = [];
	const paket: Paket[] = [];
	let sweep = 0;
	let waktu = 0;
	let spawnAkum = 0;
	let gagalSblm = 0;
	let flash = 0; // kilatan merah saat temuan
	let shake = 0;

	// nilai prop terkini untuk dibaca di loop rAF (derived → selalu mutakhir).
	const S = $derived({ fase, berjalan, persen, lulus, gagal, tdv, total, selesai, endpoint });

	function warnaNode(n: Node): string {
		return n.st === 'fail' ? MERAH : n.st === 'pass' ? HIJAU : n.st === 'review' ? AMBER : SIAN;
	}

	function targetJumlah(): number {
		if (S.fase === 'penemuan') return Math.min(Math.max(S.endpoint, S.berjalan ? 6 : 0), 26);
		return Math.min(Math.max(S.selesai + (S.berjalan ? 4 : 0), S.endpoint, 8), 44);
	}

	// Pilih state node baru agar proporsi mendekati hitungan nyata.
	let tampilPass = 0, tampilFail = 0, tampilReview = 0;
	function stateBaru(): Node['st'] {
		if (S.fase === 'penemuan') return 'scan';
		const defisit = (target: number, tampil: number) => (target <= 0 ? -1 : (target - tampil) / target);
		const dPass = defisit(S.lulus, tampilPass);
		const dFail = defisit(S.gagal, tampilFail);
		const dRev = defisit(S.tdv, tampilReview);
		const maks = Math.max(dPass, dFail, dRev);
		if (maks < 0) return 'scan';
		if (maks === dFail) { tampilFail++; return 'fail'; }
		if (maks === dRev) { tampilReview++; return 'review'; }
		tampilPass++; return 'pass';
	}

	function spawnNode() {
		const a = Math.random() * Math.PI * 2;
		const tr = 0.32 + Math.random() * 0.56; // fraksi dari radius maks
		nodes.push({ a, r: 0, tr, st: stateBaru(), lahir: waktu, nadi: Math.random() * Math.PI * 2, size: 2.2 + Math.random() * 2.4 });
	}

	function ledakan(x: number, y: number, w: string, kuat = 1) {
		const n = Math.round(14 * kuat);
		for (let i = 0; i < n; i++) {
			const ang = Math.random() * Math.PI * 2;
			const sp = (0.6 + Math.random() * 2.2) * kuat;
			partikel.push({ x, y, vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp, umur: 0, max: 40 + Math.random() * 40, w, s: 1 + Math.random() * 2 });
		}
	}

	onMount(() => {
		reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
		const ctx = kanvas!.getContext('2d')!;
		let w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
		const ro = new ResizeObserver(() => {
			if (!bungkus) return;
			const r = bungkus.getBoundingClientRect();
			w = r.width; h = r.height;
			kanvas!.width = Math.round(w * dpr);
			kanvas!.height = Math.round(h * dpr);
			kanvas!.style.width = w + 'px';
			kanvas!.style.height = h + 'px';
			ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		});
		ro.observe(bungkus!);

		let raf = 0;
		let last = performance.now();

		const gambar = (ts: number) => {
			const dt = Math.min(2, (ts - last) / 16.67);
			last = ts;
			waktu += dt;
			const cx = w / 2, cy = h / 2;
			const R = Math.min(w, h) * 0.42;
			const aktif = S.berjalan;

			// deteksi temuan baru → kilat + guncang + ledakan
			if (S.gagal > gagalSblm) {
				flash = 1; shake = 8;
				const cand = nodes.filter((n) => n.st !== 'fail');
				const t = cand[Math.floor(Math.random() * cand.length)];
				if (t) { t.st = 'fail'; tampilFail++; ledakan(cx + Math.cos(t.a) * t.r * R, cy + Math.sin(t.a) * t.r * R, MERAH, 1.6); }
				gagalSblm = S.gagal;
			}
			flash = Math.max(0, flash - 0.03 * dt);
			shake = Math.max(0, shake - 0.5 * dt);

			// spawn/kurangi node
			const tj = targetJumlah();
			spawnAkum += dt;
			if (nodes.length < tj && spawnAkum > 6 && !reduced) { spawnNode(); spawnAkum = 0; }
			else if (nodes.length < tj && reduced) { while (nodes.length < tj) spawnNode(); }
			if (nodes.length > tj) nodes.splice(tj);

			// --- gambar ---
			ctx.clearRect(0, 0, w, h);
			ctx.save();
			if (shake > 0.2) ctx.translate((Math.random() - 0.5) * shake, (Math.random() - 0.5) * shake);

			// latar grid perspektif
			drawGrid(ctx, w, h, waktu, reduced);

			// cincin konsentris
			ctx.lineWidth = 1;
			for (let i = 1; i <= 3; i++) {
				ctx.beginPath();
				ctx.arc(cx, cy, (R * i) / 3, 0, Math.PI * 2);
				ctx.strokeStyle = `rgba(159,224,138,${0.06 + i * 0.03})`;
				ctx.stroke();
			}
			// salib
			ctx.strokeStyle = 'rgba(159,224,138,0.08)';
			ctx.beginPath(); ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy); ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy + R); ctx.stroke();

			// sapuan radar (penemuan aktif)
			if (aktif && (S.fase === 'penemuan') && !reduced) {
				sweep += 0.03 * dt;
				const g = ctx.createConicGradient(sweep, cx, cy);
				g.addColorStop(0, 'rgba(127,233,216,0.28)');
				g.addColorStop(0.08, 'rgba(127,233,216,0.02)');
				g.addColorStop(1, 'rgba(127,233,216,0)');
				ctx.fillStyle = g;
				ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();
				// garis tepi sapuan
				ctx.strokeStyle = 'rgba(127,233,216,0.5)';
				ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(sweep) * R, cy + Math.sin(sweep) * R); ctx.stroke();
			}

			// node + tautan + nadi
			for (const n of nodes) {
				n.r += (n.tr - n.r) * 0.06 * dt;
				n.nadi += 0.08 * dt;
				const nx = cx + Math.cos(n.a) * n.r * R;
				const ny = cy + Math.sin(n.a) * n.r * R;
				const c = warnaNode(n);
				// tautan ke inti
				ctx.strokeStyle = hexA(c, n.st === 'scan' ? 0.14 : 0.22);
				ctx.lineWidth = 1;
				ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(nx, ny); ctx.stroke();
				// halo
				const pulse = 0.5 + 0.5 * Math.sin(n.nadi);
				ctx.beginPath(); ctx.arc(nx, ny, n.size + pulse * 2.5, 0, Math.PI * 2);
				ctx.fillStyle = hexA(c, 0.18); ctx.fill();
				// titik
				ctx.beginPath(); ctx.arc(nx, ny, n.size, 0, Math.PI * 2);
				ctx.fillStyle = c; ctx.shadowColor = c; ctx.shadowBlur = n.st === 'fail' ? 14 : 8; ctx.fill(); ctx.shadowBlur = 0;
				// cincin bahaya untuk fail
				if (n.st === 'fail') {
					ctx.strokeStyle = hexA(MERAH, 0.6 * pulse + 0.2);
					ctx.lineWidth = 1.4;
					ctx.beginPath(); ctx.arc(nx, ny, n.size + 4 + pulse * 3, 0, Math.PI * 2); ctx.stroke();
				}
			}

			// paket data mengalir ke node (saat aktif)
			if (aktif && !reduced) {
				if (Math.random() < 0.3 && nodes.length) {
					const idx = Math.floor(Math.random() * nodes.length);
					paket.push({ node: idx, t: 0, kec: 0.02 + Math.random() * 0.03, w: warnaNode(nodes[idx]) });
				}
				for (let i = paket.length - 1; i >= 0; i--) {
					const p = paket[i];
					const n = nodes[p.node];
					if (!n) { paket.splice(i, 1); continue; }
					p.t += p.kec * dt;
					if (p.t >= 1) {
						ledakan(cx + Math.cos(n.a) * n.r * R, cy + Math.sin(n.a) * n.r * R, p.w, 0.5);
						paket.splice(i, 1); continue;
					}
					const px = cx + Math.cos(n.a) * n.r * R * p.t;
					const py = cy + Math.sin(n.a) * n.r * R * p.t;
					ctx.beginPath(); ctx.arc(px, py, 1.8, 0, Math.PI * 2);
					ctx.fillStyle = p.w; ctx.shadowColor = p.w; ctx.shadowBlur = 8; ctx.fill(); ctx.shadowBlur = 0;
				}
			}

			// partikel ledakan
			for (let i = partikel.length - 1; i >= 0; i--) {
				const p = partikel[i];
				p.umur += dt; p.x += p.vx * dt; p.y += p.vy * dt; p.vx *= 0.96; p.vy *= 0.96;
				if (p.umur >= p.max) { partikel.splice(i, 1); continue; }
				const al = 1 - p.umur / p.max;
				ctx.beginPath(); ctx.arc(p.x, p.y, p.s * al, 0, Math.PI * 2);
				ctx.fillStyle = hexA(p.w, al); ctx.fill();
			}

			// inti target
			const coreP = 0.5 + 0.5 * Math.sin(waktu * 0.06);
			const coreC = S.gagal > 0 ? MERAH : S.fase === 'selesai' ? HIJAU : AMBER;
			ctx.save();
			ctx.translate(cx, cy);
			if (!reduced) ctx.rotate(waktu * 0.004);
			drawHex(ctx, 16 + coreP * 3, coreC, 2);
			ctx.rotate(-waktu * 0.008);
			drawHex(ctx, 26 + coreP * 4, hexA(coreC, 0.5), 1.4);
			ctx.restore();
			ctx.beginPath(); ctx.arc(cx, cy, 6 + coreP * 2, 0, Math.PI * 2);
			ctx.fillStyle = coreC; ctx.shadowColor = coreC; ctx.shadowBlur = 20 + coreP * 14; ctx.fill(); ctx.shadowBlur = 0;

			ctx.restore();

			// kilat temuan (overlay merah)
			if (flash > 0.01) {
				ctx.fillStyle = `rgba(255,123,107,${flash * 0.16})`;
				ctx.fillRect(0, 0, w, h);
			}

			raf = requestAnimationFrame(gambar);
		};
		raf = requestAnimationFrame(gambar);

		return () => { cancelAnimationFrame(raf); ro.disconnect(); };
	});

	const judulFase = $derived(
		fase === 'penemuan' ? 'PEMINDAIAN PERMUKAAN' : fase === 'pengujian' ? 'EKSPLOITASI TERKENDALI' : fase === 'selesai' ? 'OPERASI SELESAI' : 'OPERASI DIHENTIKAN'
	);
</script>

<div bind:this={bungkus} class={cn('relative h-full w-full overflow-hidden bg-[#070b06]', !(tepi.atas > 0) && 'sudut-taktis rounded-lg border border-[#9fe08a]/20')}>
	<canvas bind:this={kanvas} class="absolute inset-0"></canvas>
	<div class="vis-scan pointer-events-none absolute inset-0"></div>

	<!-- HUD -->
	<div class="pointer-events-none absolute inset-0 flex flex-col justify-between p-4" style:top="{tepi.atas}px" style:right="{tepi.kanan}px" style:bottom="{tepi.bawah ?? 0}px">
		<!-- atas -->
		<div class="flex items-start justify-between gap-3">
			<div>
				<p class="flex items-center gap-1.5 font-heading text-[11px] tracking-[0.25em] text-[#9fe08a] uppercase">
					{#if berjalan}<span class="size-1.5 animate-pulse rounded-full bg-[#9fe08a] shadow-[0_0_6px_#9fe08a]"></span>{/if}
					{judulFase}
				</p>
				<p class="mt-0.5 truncate font-mono text-[10px] text-[#9fe08a]/50">TARGET // {host}</p>
			</div>
			<div class="text-right">
				<p class="font-stencil text-sm {gagal > 0 ? 'text-[#ff7b6b]' : 'text-[#9fe08a]/60'}" class:animate-pulse={gagal > 0}>
					⚠ {gagal} ANCAMAN
				</p>
				<p class="font-mono text-[10px] text-[#7fe9d8]/70">{endpoint} ENDPOINT</p>
			</div>
		</div>

		<!-- tengah: persen besar -->
		<div class="flex flex-col items-center">
			<p class="font-stencil text-6xl leading-none text-[#9fe08a] drop-shadow-[0_0_18px_rgba(159,224,138,0.5)] tabular-nums">{persen}%</p>
			<p class="mt-1 font-heading text-[10px] tracking-[0.3em] text-white/60 uppercase">{selesai} / {total} metode</p>
			{#if sasaran && berjalan}
				<p class="vis-ket mt-2 max-w-[90%] truncate rounded border border-[#f5c451]/30 bg-black/40 px-2 py-0.5 font-mono text-[10px] text-[#f5c451]">» {sasaran}</p>
			{/if}
		</div>

		<!-- bawah: metrik -->
		<div class="grid grid-cols-4 gap-2">
			{#each [[lulus, 'LULUS', '#9fe08a'], [gagal, 'GAGAL', '#ff7b6b'], [tdv, 'TINJAU', '#f5c451'], [total - selesai, 'ANTRE', '#7fe9d8']] as [n, l, c] (l)}
				<div class="rounded-sm border border-white/5 bg-black/35 px-2 py-1.5 text-center backdrop-blur-[1px]">
					<p class="font-stencil text-lg tabular-nums" style="color:{c}">{n}</p>
					<p class="font-heading text-[8px] tracking-[0.2em] text-white/45 uppercase">{l}</p>
				</div>
			{/each}
		</div>
	</div>
</div>

<style>
	/* garis pindai CRT + flicker halus */
	.vis-scan {
		background:
			repeating-linear-gradient(0deg, rgba(0, 0, 0, 0) 0px, rgba(0, 0, 0, 0) 2px, rgba(0, 0, 0, 0.18) 3px, rgba(0, 0, 0, 0) 4px);
		mix-blend-mode: multiply;
		animation: vis-flick 4s steps(60) infinite;
	}
	.vis-scan::after {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(180deg, transparent, rgba(159, 224, 138, 0.06), transparent);
		height: 40%;
		animation: vis-sweep 6s linear infinite;
	}
	@keyframes vis-sweep {
		0% { transform: translateY(-120%); }
		100% { transform: translateY(320%); }
	}
	@keyframes vis-flick {
		0%, 100% { opacity: 0.9; }
		50% { opacity: 1; }
	}
	.vis-ket { animation: vis-blink 1.4s steps(2) infinite; }
	@keyframes vis-blink { 50% { opacity: 0.55; } }
	@media (prefers-reduced-motion: reduce) {
		.vis-scan, .vis-scan::after, .vis-ket { animation: none; }
	}
</style>
