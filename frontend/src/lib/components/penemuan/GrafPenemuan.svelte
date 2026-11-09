<script lang="ts">
	// Graf entitas penemuan bergaya alat analisis tautan: target di tengah, entitas hub (Frontend,
	// Aset, Backend per origin, Upload, Docs, Sesi, Katana, ZAP) di cincin berslot, daun (URL,
	// berkas JS, endpoint) mengelilingi klasternya. Node = ikon entitas berwarna; tautan garis lurus
	// tipis berlabel (hijau = struktur temuan, abu putus = kontribusi sumber, merah = alert).
	// Layout force-directed (d3-force, ditick manual di rAF). Pan (seret), zoom (roda / tombol),
	// klik node → onpilih; perubahan `terpilih` dari luar memusatkan graf ke node itu.
	import { onMount } from 'svelte';
	import {
		forceCollide,
		forceLink,
		forceManyBody,
		forceSimulation,
		forceX,
		forceY,
		type SimulationLinkDatum,
		type SimulationNodeDatum
	} from 'd3-force';
	import { JENIS_HUB, type EdgeGraf, type Graf, type JenisNode, type NodeGraf } from '#lib/penemuan/graf.js';
	import { HIJAU, MERAH, UNGU, hexA } from '#lib/penemuan/kanvas.js';
	import { WARNA_RISIKO, gambarIkon } from '#lib/penemuan/ikon-entitas.js';
	import Plus from '@lucide/svelte/icons/plus';
	import Minus from '@lucide/svelte/icons/minus';
	import Maximize from '@lucide/svelte/icons/maximize';

	let {
		graf,
		berjalan,
		terpilih = null,
		onpilih,
		tepi = { atas: 0, kanan: 0 },
		kontrol = true
	}: {
		graf: Graf;
		berjalan: boolean;
		terpilih?: string | null;
		onpilih: (id: string | null) => void;
		/** Area kanvas yang tertutup toolbar (atas) & panel mengambang (kanan), px. */
		tepi?: { atas: number; kanan: number; bawah?: number };
		/** Tampilkan tombol zoom bawaan (matikan bila induk menyediakan toolbar sendiri). */
		kontrol?: boolean;
	} = $props();

	type SimNode = SimulationNodeDatum & { id: string; jenis: JenisNode; r: number; lahir: number; ref: NodeGraf; tx?: number; ty?: number };
	type SimLink = SimulationLinkDatum<SimNode> & { jenis: EdgeGraf['jenis']; label?: string; lahir: number };
	type Paket = { link: SimLink; t: number; kec: number };

	// Setengah ukuran ikon (px pada zoom 1).
	const RADIUS: Record<JenisNode, number> = {
		situs: 26, frontend: 21, aset: 18, backend: 21, upload: 18, docs: 18, sesi: 18, zap: 19, katana: 19,
		halaman: 9, js: 9, endpoint: 9, titik: 8, alur: 10
	};
	const MUATAN: Record<JenisNode, number> = {
		situs: -700, frontend: -420, aset: -260, backend: -420, upload: -260, docs: -280, sesi: -240, zap: -300, katana: -300,
		halaman: -60, js: -50, endpoint: -60, titik: -80, alur: -70
	};
	// Urutan slot hub di cincin (searah jarum jam dari atas): yang saling terkait bersebelahan.
	const URUT_HUB: JenisNode[] = ['frontend', 'aset', 'sesi', 'katana', 'zap', 'docs', 'backend', 'upload'];
	const LATAR = '#0c1014';
	const PUTUS = 'rgba(160,174,192,0.55)';
	let orbit = 200;

	let kanvas = $state<HTMLCanvasElement>();
	let bungkus = $state<HTMLDivElement>();
	let hover = $state<NodeGraf | null>(null);
	let posHover = $state({ x: 0, y: 0 });

	// --- state animasi (tak reaktif) ---
	const simNodes = new Map<string, SimNode>();
	const simLinks: SimLink[] = [];
	const antre: NodeGraf[] = [];
	const diantrekan = new Set<string>();
	const paket: Paket[] = [];
	let waktu = 0;
	let akumReveal = 0;
	let reduced = false;
	let view = { k: 1, x: 0, y: 0 }; // translasi relatif pusat kanvas
	let tujuan: { k: number; x: number; y: number } | null = null; // animasi fokus ke node
	let interaksi = false;
	let W = 0, H = 0;

	const hub = (n: SimNode) => JENIS_HUB.has(n.jenis);

	const sim = forceSimulation<SimNode, SimLink>([])
		.force('muatan', forceManyBody<SimNode>().strength((n) => MUATAN[n.jenis]).distanceMax(700))
		.force(
			'tautan',
			forceLink<SimNode, SimLink>([])
				.id((n) => n.id)
				.distance((l) => jarakTautan(l))
				.strength((l) => kuatTautan(l))
		)
		.force('tabrak', forceCollide<SimNode>((n) => n.r + (hub(n) ? 34 : 6)))
		.force('x', forceX<SimNode>(0).strength(0.02))
		.force('y', forceY<SimNode>(0).strength(0.02))
		.stop();

	// Tata letak radial: tiap hub punya slot sudut tetap di cincin; daun ditarik ringan ke arah
	// luar hub-nya sehingga klaster tidak saling menumpuk.
	function aturSlot() {
		const hubs = [...simNodes.values()]
			.filter((n) => hub(n) && n.jenis !== 'situs')
			.sort((a, b) => URUT_HUB.indexOf(a.jenis) - URUT_HUB.indexOf(b.jenis) || a.ref.urutan - b.ref.urutan);
		orbit = Math.max(190, hubs.length * 38);
		hubs.forEach((h, i) => {
			const a = -Math.PI / 2 + (i * Math.PI * 2) / hubs.length;
			h.tx = Math.cos(a) * orbit;
			h.ty = Math.sin(a) * orbit;
		});
		for (const n of simNodes.values()) {
			if (hub(n)) continue;
			let p: SimNode | undefined = n;
			for (let i = 0; i < 4 && p && !hub(p); i++) p = p.ref.induk ? simNodes.get(p.ref.induk) : undefined;
			const jauh = p && p.tx !== undefined ? 1.6 : 0;
			n.tx = (p?.tx ?? 0) * jauh;
			n.ty = (p?.ty ?? 0) * jauh;
		}
		const kuat = (n: SimNode) => (n.jenis === 'situs' ? 0 : hub(n) ? 0.6 : 0.05);
		(sim.force('x') as ReturnType<typeof forceX<SimNode>>).x((n) => n.tx ?? 0).strength(kuat);
		(sim.force('y') as ReturnType<typeof forceY<SimNode>>).y((n) => n.ty ?? 0).strength(kuat);
	}

	function jarakTautan(l: SimLink): number {
		const s = l.source as SimNode, t = l.target as SimNode;
		switch (l.jenis) {
			case 'alur': return 80;
			case 'upload': return 140;
			case 'sumber': return hub(t) ? orbit : 240;
			case 'alert': return 260;
			case 'sesi': return orbit;
		}
		if (s.jenis === 'situs') return orbit;
		if (hub(s) && !hub(t)) return 62 + (hashKecil(t.id) % 44);
		return 140;
	}
	function kuatTautan(l: SimLink): number {
		switch (l.jenis) {
			case 'alur': return 0.1;
			case 'upload':
			case 'alert': return 0.01;
			case 'sumber': return 0.02;
		}
		// Posisi hub ditentukan slot cincin; tautan pusat→hub cukup lemah.
		if ((l.source as SimNode).jenis === 'situs') return 0.15;
		return hub(l.target as SimNode) ? 0.3 : 0.4;
	}
	function hashKecil(s: string): number {
		let h = 0;
		for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
		return Math.abs(h);
	}

	// Sinkron model → antrean reveal (node baru) + perbarui ref node lama (label/alert/titik).
	$effect(() => {
		const baru: NodeGraf[] = [];
		for (const n of graf.nodes) {
			const s = simNodes.get(n.id);
			if (s) s.ref = n;
			else if (!diantrekan.has(n.id)) baru.push(n);
		}
		baru.sort((a, b) => a.urutan - b.urutan);
		for (const n of baru) {
			diantrekan.add(n.id);
			antre.push(n);
		}
		void graf.edges.length;
		sambungTautan();
	});

	// Pilihan dari luar (mis. daftar aset) → pusatkan graf ke node terpilih.
	let pilihanTerakhir: string | null = null;
	$effect(() => {
		const id = terpilih;
		if (!id || id === pilihanTerakhir) {
			pilihanTerakhir = id;
			return;
		}
		pilihanTerakhir = id;
		fokusKe(id);
	});

	function sambungTautan() {
		const ada = new Map(simLinks.map((l) => [`${(l.source as SimNode).id ?? l.source}>${(l.target as SimNode).id ?? l.target}`, l]));
		let berubah = false;
		for (const e of graf.edges) {
			const k = `${e.dari}>${e.ke}`;
			const lama = ada.get(k);
			if (lama) {
				lama.label = e.label;
				lama.jenis = e.jenis;
				continue;
			}
			const s = simNodes.get(e.dari), t = simNodes.get(e.ke);
			if (!s || !t) continue;
			simLinks.push({ source: s, target: t, jenis: e.jenis, label: e.label, lahir: waktu });
			berubah = true;
		}
		if (berubah) {
			(sim.force('tautan') as ReturnType<typeof forceLink<SimNode, SimLink>>).links(simLinks);
			sim.alpha(Math.max(sim.alpha(), 0.5));
		}
	}

	function munculkan(n: NodeGraf) {
		const induk = (n.induk && simNodes.get(n.induk)) || simNodes.get(graf.nodes[0]?.id ?? '');
		const sudut = (hashKecil(n.id) % 628) / 100;
		const jarak = induk ? (JENIS_HUB.has(n.jenis) ? 70 : 30) : 0;
		const s: SimNode = {
			id: n.id,
			jenis: n.jenis,
			r: RADIUS[n.jenis],
			lahir: reduced ? -999 : waktu,
			ref: n,
			x: (induk?.x ?? 0) + Math.cos(sudut) * jarak,
			y: (induk?.y ?? 0) + Math.sin(sudut) * jarak
		};
		if (n.jenis === 'situs' && simNodes.size === 0) {
			s.fx = 0;
			s.fy = 0;
		}
		simNodes.set(n.id, s);
		sim.nodes([...simNodes.values()]);
		aturSlot();
		sambungTautan();
		sim.alpha(Math.max(sim.alpha(), 0.45));
	}

	function warnaTautan(l: SimLink): string {
		switch (l.jenis) {
			case 'alert': return MERAH;
			case 'alur': return UNGU;
			case 'sumber': return PUTUS;
			case 'upload': return '#ffa94d';
			default: return HIJAU;
		}
	}

	// --- koordinat ---
	const keLayar = (x: number, y: number) => ({ x: W / 2 + view.x + x * view.k, y: H / 2 + view.y + y * view.k });
	const keDunia = (sx: number, sy: number) => ({ x: (sx - W / 2 - view.x) / view.k, y: (sy - H / 2 - view.y) / view.k });

	function cariNode(sx: number, sy: number): SimNode | null {
		const p = keDunia(sx, sy);
		let best: SimNode | null = null, bestD = Infinity;
		for (const n of simNodes.values()) {
			const d = Math.hypot((n.x ?? 0) - p.x, (n.y ?? 0) - p.y);
			const ambang = Math.max(n.r + 4, 10 / view.k);
			if (d < ambang && d < bestD) { best = n; bestD = d; }
		}
		return best;
	}

	export function zoom(f: number, sx = W / 2, sy = H / 2) {
		interaksi = true;
		tujuan = null;
		const sebelum = keDunia(sx, sy);
		view.k = Math.min(4, Math.max(0.15, view.k * f));
		const sesudah = keLayar(sebelum.x, sebelum.y);
		view.x += sx - sesudah.x;
		view.y += sy - sesudah.y;
	}
	export function pas() {
		interaksi = false;
		tujuan = null;
		paskan(1);
	}
	/** Pusatkan ke node terpilih; tanpa pilihan → paskan seluruh graf. */
	export function pusatkan() {
		if (terpilih && simNodes.has(terpilih)) fokusKe(terpilih);
		else pas();
	}
	function fokusKe(id: string) {
		const n = simNodes.get(id);
		if (!n || !W) return;
		interaksi = true;
		const k = Math.max(view.k, hub(n) ? 0.9 : 1.3);
		// Pusatkan di area bebas (di luar toolbar & panel mengambang).
		tujuan = { k, x: -n.x! * k - tepi.kanan / 2, y: -n.y! * k + (tepi.atas - (tepi.bawah ?? 0)) / 2 };
	}
	function paskan(laju: number) {
		if (!simNodes.size || !W) return;
		let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
		for (const n of simNodes.values()) {
			x0 = Math.min(x0, n.x! - n.r); y0 = Math.min(y0, n.y! - n.r);
			x1 = Math.max(x1, n.x! + n.r); y1 = Math.max(y1, n.y! + n.r);
		}
		// Area bebas: sisihkan HUD atas (~56px; +bilah status selama penemuan berjalan) & legenda
		// bawah (~40px); label menambah margin.
		const ATAS = tepi.atas + (berjalan && !graf.selesai ? 116 : 56), BAWAH = 40 + (tepi.bawah ?? 0), KANAN = tepi.kanan;
		const kT = Math.min(1.4, Math.max(0.15, Math.min((W - KANAN - 40) / (x1 - x0 + 140), (H - ATAS - BAWAH) / (y1 - y0 + 60))));
		const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
		view.k += (kT - view.k) * laju;
		view.x += (-cx * view.k - KANAN / 2 - view.x) * laju;
		view.y += (-cy * view.k + (ATAS - BAWAH) / 2 - view.y) * laju;
	}

	// --- interaksi pointer ---
	let tekan: { x: number; y: number; vx: number; vy: number } | null = null;
	let geser = false;
	function posLokal(e: PointerEvent | WheelEvent) {
		const r = kanvas!.getBoundingClientRect();
		return { x: e.clientX - r.left, y: e.clientY - r.top };
	}
	function onDown(e: PointerEvent) {
		const p = posLokal(e);
		tekan = { x: p.x, y: p.y, vx: view.x, vy: view.y };
		geser = false;
		kanvas!.setPointerCapture(e.pointerId);
	}
	function onMove(e: PointerEvent) {
		const p = posLokal(e);
		if (tekan) {
			if (!geser && Math.hypot(p.x - tekan.x, p.y - tekan.y) > 4) geser = true;
			if (geser) {
				interaksi = true;
				tujuan = null;
				view.x = tekan.vx + (p.x - tekan.x);
				view.y = tekan.vy + (p.y - tekan.y);
				return;
			}
		}
		const n = cariNode(p.x, p.y);
		hover = n?.ref ?? null;
		posHover = p;
		kanvas!.style.cursor = n ? 'pointer' : tekan ? 'grabbing' : 'grab';
	}
	function onUp(e: PointerEvent) {
		const p = posLokal(e);
		if (tekan && !geser) {
			const id = cariNode(p.x, p.y)?.id ?? null;
			pilihanTerakhir = id; // klik di kanvas tidak memicu pemusatan ulang
			onpilih(id);
		}
		tekan = null;
		geser = false;
	}
	function onWheel(e: WheelEvent) {
		e.preventDefault();
		const p = posLokal(e);
		zoom(e.deltaY < 0 ? 1.12 : 1 / 1.12, p.x, p.y);
	}

	// Teks dengan halo gelap agar terbaca di atas garis/kisi.
	function teksHalo(ctx: CanvasRenderingContext2D, teks: string, x: number, y: number, warna: string) {
		ctx.lineWidth = 3;
		ctx.strokeStyle = LATAR;
		ctx.lineJoin = 'round';
		ctx.strokeText(teks, x, y);
		ctx.fillStyle = warna;
		ctx.fillText(teks, x, y);
	}

	onMount(() => {
		reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
		const ctx = kanvas!.getContext('2d')!;
		const dpr = Math.min(window.devicePixelRatio || 1, 2);
		const ro = new ResizeObserver(() => {
			const r = bungkus!.getBoundingClientRect();
			W = r.width; H = r.height;
			kanvas!.width = Math.round(W * dpr);
			kanvas!.height = Math.round(H * dpr);
			kanvas!.style.width = W + 'px';
			kanvas!.style.height = H + 'px';
			ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		});
		ro.observe(bungkus!);
		kanvas!.addEventListener('wheel', onWheel, { passive: false });

		// Graf yang sudah ada saat dibuka (replay/refresh) dimunculkan cepat.
		const replay = antre.length > 12;

		let raf = 0, last = performance.now(), frame = 0;
		const gambar = (ts: number) => {
			const dt = Math.min(2, (ts - last) / 16.67);
			last = ts; waktu += dt; frame++;

			// reveal bergiliran: cepat saat antrean panjang
			akumReveal += dt;
			const jeda = reduced ? 0 : replay && frame < 120 ? 0.6 : antre.length > 30 ? 1.5 : antre.length > 8 ? 3 : 6;
			if (jeda === 0) while (antre.length) munculkan(antre.shift()!);
			else while (antre.length && akumReveal >= jeda) { munculkan(antre.shift()!); akumReveal -= jeda; }
			if (!antre.length) akumReveal = 0;

			// tick layout + kamera
			if (sim.alpha() > sim.alphaMin()) sim.tick(reduced ? 3 : 1);
			if (tujuan) {
				const a = reduced ? 1 : 0.15;
				view.k += (tujuan.k - view.k) * a;
				view.x += (tujuan.x - view.x) * a;
				view.y += (tujuan.y - view.y) * a;
				if (Math.abs(tujuan.x - view.x) < 0.5 && Math.abs(tujuan.y - view.y) < 0.5) tujuan = null;
			} else if (!interaksi && frame % 2 === 0) paskan(0.06);

			const sel = terpilih;
			const tetanggaSel = new Set<string>();
			if (sel) {
				for (const l of simLinks) {
					const s = (l.source as SimNode).id, t = (l.target as SimNode).id;
					if (s === sel) tetanggaSel.add(t);
					if (t === sel) tetanggaSel.add(s);
				}
			}
			const redup = (id: string) => !!sel && id !== sel && !tetanggaSel.has(id);

			// latar: kisi halus + kisi besar
			ctx.fillStyle = LATAR;
			ctx.fillRect(0, 0, W, H);
			for (const [jarak, alfa] of [[24, 0.035], [120, 0.07]] as const) {
				const sp = jarak * view.k;
				if (sp < 8) continue;
				const ox = ((W / 2 + view.x) % sp + sp) % sp, oy = ((H / 2 + view.y) % sp + sp) % sp;
				ctx.strokeStyle = `rgba(255,255,255,${alfa})`;
				ctx.lineWidth = 1;
				ctx.beginPath();
				for (let x = ox; x < W; x += sp) { ctx.moveTo(Math.round(x) + 0.5, 0); ctx.lineTo(Math.round(x) + 0.5, H); }
				for (let y = oy; y < H; y += sp) { ctx.moveTo(0, Math.round(y) + 0.5); ctx.lineTo(W, Math.round(y) + 0.5); }
				ctx.stroke();
			}

			// tautan: garis lurus tipis, memudar masuk; label di sepanjang garis
			const tampilLabelTautan = view.k >= 0.45;
			ctx.font = '9.5px ui-monospace, SFMono-Regular, Menlo, monospace';
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			for (const l of simLinks) {
				const s = l.source as SimNode, t = l.target as SimNode;
				const muncul = reduced ? 1 : Math.min(1, (waktu - Math.max(l.lahir, t.lahir)) / 18);
				if (muncul <= 0) continue;
				const p0 = keLayar(s.x!, s.y!), p1 = keLayar(t.x!, t.y!);
				const c = warnaTautan(l);
				const fokus = sel && (s.id === sel || t.id === sel);
				const daun = !hub(t) && l.jenis !== 'alert';
				const dasar = l.jenis === 'alert' ? 0.45 : l.jenis === 'sumber' ? 0.6 : daun ? 0.28 : 0.75;
				const alfa = (fokus ? 1 : redup(s.id) && redup(t.id) ? 0.06 : dasar) * muncul;
				ctx.strokeStyle = c.startsWith('rgba') ? c : hexA(c, alfa);
				ctx.globalAlpha = c.startsWith('rgba') ? alfa : 1;
				ctx.lineWidth = fokus ? 1.6 : daun ? 0.8 : 1.2;
				ctx.setLineDash(l.jenis === 'sumber' ? [5, 4] : l.jenis === 'alur' || l.jenis === 'upload' ? [3, 3] : []);
				ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.stroke();
				ctx.setLineDash([]);
				ctx.globalAlpha = 1;

				// Label: tautan antar-hub selalu (bila zoom cukup); tautan daun hanya saat difokus.
				if (l.label && (fokus || (tampilLabelTautan && !daun)) && !(redup(s.id) && redup(t.id))) {
					const panjang = Math.hypot(p1.x - p0.x, p1.y - p0.y);
					if (panjang > 70) {
						let sudut = Math.atan2(p1.y - p0.y, p1.x - p0.x);
						if (sudut > Math.PI / 2 || sudut < -Math.PI / 2) sudut += Math.PI; // teks selalu tegak
						ctx.save();
						ctx.translate((p0.x + p1.x) / 2, (p0.y + p1.y) / 2);
						ctx.rotate(sudut);
						teksHalo(ctx, l.label, 0, -6, l.jenis === 'sumber' ? 'rgba(210,218,230,0.85)' : hexA(c, 0.95));
						ctx.restore();
					}
				}
			}
			ctx.textBaseline = 'alphabetic';

			// paket data: hanya pada tautan antar-hub, jarang, selama penemuan berjalan
			if (!reduced && berjalan && simLinks.length && Math.random() < 0.06) {
				const l = simLinks[Math.floor(Math.random() * simLinks.length)];
				if (l.jenis === 'utama' && hub(l.source as SimNode)) paket.push({ link: l, t: 0, kec: 0.012 + Math.random() * 0.01 });
			}
			for (let i = paket.length - 1; i >= 0; i--) {
				const p = paket[i];
				p.t += p.kec * dt;
				if (p.t >= 1) { paket.splice(i, 1); continue; }
				const s = p.link.source as SimNode, t = p.link.target as SimNode;
				const q = keLayar(s.x! + (t.x! - s.x!) * p.t, s.y! + (t.y! - s.y!) * p.t);
				ctx.globalAlpha = Math.sin(p.t * Math.PI);
				ctx.beginPath(); ctx.arc(q.x, q.y, 1.6, 0, Math.PI * 2);
				ctx.fillStyle = HIJAU; ctx.fill();
				ctx.globalAlpha = 1;
			}

			// node: daun dulu, hub di atasnya
			const tampilLabelDaun = view.k >= 1.15;
			const urut = [...simNodes.values()].sort((a, b) => Number(hub(a)) - Number(hub(b)));
			for (const n of urut) {
				const p = keLayar(n.x!, n.y!);
				if (p.x < -90 || p.y < -90 || p.x > W + 90 || p.y > H + 90) continue;
				const umur = waktu - n.lahir;
				const masuk = reduced ? 1 : easeOutCubic(Math.min(1, umur / 14));
				const isHub = hub(n);
				const skala = isHub ? Math.max(0.7, Math.min(1.25, view.k)) : Math.max(0.8, Math.min(1.8, view.k));
				const r = n.r * skala * (0.6 + 0.4 * masuk);
				ctx.globalAlpha = (redup(n.id) ? 0.2 : 1) * masuk;

				// sorotan seleksi / hover (bingkai persegi bergaya alat analisis)
				if (n.id === sel || hover?.id === n.id) {
					ctx.strokeStyle = n.id === sel ? '#4dabf7' : 'rgba(255,255,255,0.35)';
					ctx.fillStyle = n.id === sel ? 'rgba(77,171,247,0.12)' : 'rgba(255,255,255,0.04)';
					ctx.lineWidth = 1.2;
					ctx.beginPath(); ctx.roundRect(p.x - r - 5, p.y - r - 5, (r + 5) * 2, (r + 5) * 2, 6); ctx.fill(); ctx.stroke();
				}

				const img = gambarIkon(n.jenis, n.ref.endpoint?.metode_http);
				if (img.complete && img.naturalWidth) {
					ctx.drawImage(img, p.x - r, p.y - r, r * 2, r * 2);
				} else {
					ctx.fillStyle = '#334155';
					ctx.beginPath(); ctx.roundRect(p.x - r, p.y - r, r * 2, r * 2, r * 0.25); ctx.fill();
				}

				// penanda: alert ZAP (segitiga risiko), upload, butuh login, titik uji
				const tanda = Math.max(4, r * 0.42);
				if (n.ref.alert?.length) {
					const w = WARNA_RISIKO[n.ref.alert[0].risk] ?? WARNA_RISIKO.Informational;
					const bx = p.x + r * 0.85, by = p.y - r * 0.85;
					ctx.fillStyle = w; ctx.strokeStyle = LATAR; ctx.lineWidth = 1.5;
					ctx.beginPath(); ctx.moveTo(bx, by - tanda); ctx.lineTo(bx + tanda, by + tanda * 0.8); ctx.lineTo(bx - tanda, by + tanda * 0.8); ctx.closePath();
					ctx.stroke(); ctx.fill();
				}
				if (n.ref.upload && n.jenis === 'endpoint') {
					const bx = p.x - r * 0.85, by = p.y - r * 0.85;
					ctx.fillStyle = '#ff922b'; ctx.strokeStyle = LATAR; ctx.lineWidth = 1.5;
					ctx.beginPath(); ctx.arc(bx, by, tanda * 0.75, 0, Math.PI * 2); ctx.stroke(); ctx.fill();
					ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.2;
					ctx.beginPath(); ctx.moveTo(bx, by + tanda * 0.4); ctx.lineTo(bx, by - tanda * 0.4); ctx.moveTo(bx - tanda * 0.3, by - tanda * 0.1); ctx.lineTo(bx, by - tanda * 0.4); ctx.lineTo(bx + tanda * 0.3, by - tanda * 0.1); ctx.stroke();
				}
				if (n.ref.endpoint?.butuh_autentikasi) {
					ctx.fillStyle = HIJAU; ctx.strokeStyle = LATAR; ctx.lineWidth = 1.5;
					ctx.beginPath(); ctx.arc(p.x + r * 0.85, p.y + r * 0.85, tanda * 0.6, 0, Math.PI * 2); ctx.stroke(); ctx.fill();
				}
				if (n.ref.titik?.length) {
					const bx = p.x - r * 0.85, by = p.y + r * 0.85, d = tanda * 0.75;
					ctx.fillStyle = '#ffd43b'; ctx.strokeStyle = LATAR; ctx.lineWidth = 1.5;
					ctx.beginPath(); ctx.moveTo(bx, by - d); ctx.lineTo(bx + d, by); ctx.lineTo(bx, by + d); ctx.lineTo(bx - d, by); ctx.closePath(); ctx.stroke(); ctx.fill();
				}

				// label di bawah ikon
				ctx.textAlign = 'center';
				if (isHub) {
					ctx.font = '600 11px ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif';
					teksHalo(ctx, potong(n.ref.label, 30), p.x, p.y + r + 15, 'rgba(236,240,245,0.95)');
					if (n.ref.sub && view.k > 0.4) {
						ctx.font = '9.5px ui-monospace, SFMono-Regular, Menlo, monospace';
						teksHalo(ctx, potong(n.ref.sub, 40), p.x, p.y + r + 28, 'rgba(160,174,192,0.9)');
					}
				} else if (tampilLabelDaun || n.id === sel || tetanggaSel.has(n.id) || hover?.id === n.id) {
					ctx.font = '9.5px ui-monospace, SFMono-Regular, Menlo, monospace';
					const teks = n.jenis === 'endpoint' ? n.ref.endpoint?.path_template ?? n.ref.label : n.ref.label;
					teksHalo(ctx, potong(teks, 42), p.x, p.y + r + 12, 'rgba(226,232,240,0.85)');
				}
				ctx.globalAlpha = 1;
			}

			raf = requestAnimationFrame(gambar);
		};
		raf = requestAnimationFrame(gambar);
		return () => {
			cancelAnimationFrame(raf);
			ro.disconnect();
			kanvas?.removeEventListener('wheel', onWheel);
			sim.stop();
		};
	});

	function easeOutCubic(t: number) {
		return 1 - Math.pow(1 - t, 3);
	}
	function potong(s: string, n: number) {
		return s.length > n ? s.slice(0, n - 1) + '…' : s;
	}

	const tooltip = $derived.by(() => {
		if (!hover) return null;
		const sumber = hover.sumber?.length ? ` · ${hover.sumber.join(', ')}` : '';
		if (hover.endpoint) return { judul: `${hover.endpoint.metode_http} ${hover.endpoint.path_template}`, sub: `${hover.endpoint.origin}${sumber}` };
		return { judul: hover.label, sub: `${hover.sub ?? ''}${sumber}` };
	});
</script>

<div bind:this={bungkus} class="absolute inset-0">
	<canvas
		bind:this={kanvas}
		class="absolute inset-0 touch-none"
		style="cursor: grab"
		onpointerdown={onDown}
		onpointermove={onMove}
		onpointerup={onUp}
		onpointerleave={() => (hover = null)}
		aria-label="Graf entitas penemuan; klik node untuk detail"
	></canvas>

	{#if tooltip && hover?.id !== terpilih}
		<div
			class="pointer-events-none absolute z-10 max-w-80 rounded border border-white/10 bg-[#0c1014]/95 px-2 py-1 font-mono text-[10px] text-white/85 shadow-lg"
			style="left: {posHover.x + 14}px; top: {posHover.y + 12}px"
		>
			<p class="truncate">{tooltip.judul}</p>
			{#if tooltip.sub}<p class="truncate text-white/45">{tooltip.sub}</p>{/if}
		</div>
	{/if}

	{#if kontrol}
		<div style:right="{tepi.kanan + 12}px" style:bottom="{(tepi.bawah ?? 0) + 12}px" class="absolute z-10 flex flex-col overflow-hidden rounded border border-white/10 bg-[#0c1014]/90 text-white/70">
			<button type="button" class="p-1.5 hover:bg-white/10 hover:text-white" onclick={() => zoom(1.25)} aria-label="Perbesar"><Plus class="size-3.5" /></button>
			<button type="button" class="p-1.5 hover:bg-white/10 hover:text-white" onclick={() => zoom(0.8)} aria-label="Perkecil"><Minus class="size-3.5" /></button>
			<button type="button" class="p-1.5 hover:bg-white/10 hover:text-white" onclick={pas} aria-label="Paskan ke layar"><Maximize class="size-3.5" /></button>
		</div>
	{/if}
</div>
