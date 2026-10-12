import gsap from "gsap";
import { still } from "@/lib/motion";
import { band, RAMP } from "./run";

// The design's fraud-triangle field, ported from its prototype (frame, drawEdges, drawHL):
// a canvas of 6 px cells, its noise drifting, calls landing as heat with a ring, the held
// call pulsing salmon, the cursor painting a fading trail, a click sending a shockwave, and
// a marker gliding to the latest (or hovered, or selected) call, leaving a trail. Each of
// the agent's thoughts lands too, and every landed dot is drawn as solid cells over the heat.
// New dots fire one after another in the order they were said or made, however they arrive.

const CELL = 6; // finer than the design's 10 px « medium » pixel: room for many dots
const STAGGER = 90; // ms between two dots firing
const HOT = "#EF7462";
const SALMON = "#FFD6CE";
const INK = "#1E1E1E";
const PAPER = "#FEFEFE";
const LC = { p: "#3D64D8", o: "#0E8F86", r: "#8A55D1" } as const;

export type P3 = { p: number; o: number; r: number };
type Pt = [number, number];
// The vertices, the side, the height, and the field's width.
export type Tri = { P: Pt; O: Pt; R: Pt; s: number; h: number; W: number };
// A scored call or thought, whether it was ever held, and where it sits in the run: a call's
// number, or k + 0.5 for a thought said after k calls.
export type Dot = { id: string; legs: P3; hold: boolean; at: number };
export type Scene = {
	calls: Dot[];
	thoughts: Dot[]; // every read thought, never held
	confirmed: Record<keyof P3, boolean>; // a side closes when both its legs are
	held: boolean; // a call waits for a human
	holdId?: string; // the held call, pending or decided
	pin?: string; // the hovered or selected call the marker goes to
};

// Room around the triangle for the vertex labels.
export function layout(W: number, H: number): Tri {
	const padX = 84;
	const top = 62;
	const bot = 60;
	const s = Math.max(
		140,
		Math.min(W - padX * 2, ((H - top - bot) * 2) / Math.sqrt(3)),
	);
	const h = (s * Math.sqrt(3)) / 2;
	return shape(W / 2, top + Math.max(0, (H - top - bot - h) / 2), s, W);
}

// An equilateral triangle of side s, apex up at (cx, y0).
function shape(cx: number, y0: number, s: number, W: number): Tri {
	const h = (s * Math.sqrt(3)) / 2;
	return {
		P: [cx, y0],
		O: [cx - s / 2, y0 + h],
		R: [cx + s / 2, y0 + h],
		s,
		h,
		W,
	};
}

// The layout k of the way from a to b, while the triangle glides to a new size.
export function mix(a: Tri, b: Tri, k: number): Tri {
	const m = (x: number, y: number) => x + (y - x) * k;
	return shape(m(a.P[0], b.P[0]), m(a.P[1], b.P[1]), m(a.s, b.s), b.W);
}

// Each vertex's share in a dot's place: its squared scores, eased 18 % toward equal shares,
// and only as far from equal as its strongest score, so a leg that grows walks its dots out.
// No score at all: equal shares, the centre (the design divides by zero there).
const EASE = 0.82; // how far a vertex's share can go from equal: never onto the vertex
function shares(legs: P3): P3 {
	const sq = { p: legs.p ** 2, o: legs.o ** 2, r: legs.r ** 2 };
	const s = sq.p + sq.o + sq.r;
	const m = 1 / 3;
	const far = Math.max(legs.p, legs.o, legs.r) * EASE;
	const at = (v: number) => (s ? m + (v / s - m) * far : m);
	return { p: at(sq.p), o: at(sq.o), r: at(sq.r) };
}

// Where a dot lands: its shares of the three vertices.
export function pos(T: Tri, legs: P3): Pt {
	const w = shares(legs);
	return [
		w.p * T.P[0] + w.o * T.O[0] + w.r * T.R[0],
		w.p * T.P[1] + w.o * T.O[1] + w.r * T.R[1],
	];
}

// How far (x, y) lies out on an apex-up triangle centred on 0: its inradius there, as hypot
// is a circle's radius. The outward normals of its sides: down, up-left, up-right.
const triNorm = (x: number, y: number) =>
	Math.max(y, -0.866 * x - 0.5 * y, 0.866 * x - 0.5 * y);

// The cells a landed dot fills: a thought one, a call two, one more for a strong score. Its
// centre is where the marker points.
function square(T: Tri, d: Dot, thought: boolean) {
	const [x, y] = pos(T, d.legs);
	const n =
		(thought ? 1 : 2) + Math.round(Math.max(d.legs.p, d.legs.o, d.legs.r));
	const x0 = Math.round(x / CELL - n / 2) * CELL;
	const y0 = Math.round(y / CELL - n / 2) * CELL;
	return { x0, y0, n, cx: x0 + (n * CELL) / 2, cy: y0 + (n * CELL) / 2 };
}

const rgb = (hex: string) =>
	[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const GREY = rgb(RAMP[2]);
const LEG_RGB = { p: rgb(LC.p), o: rgb(LC.o), r: rgb(LC.r) };

// A thought's colour: the legs' colours mixed in its shares of the triangle, from grey at the
// centre to a leg's own colour at its vertex.
function hue(legs: P3) {
	const w = shares(legs);
	const k = (Math.max(w.p, w.o, w.r) - 1 / 3) / ((2 / 3) * EASE); // 0 → 1, centre → vertex
	const ch = GREY.map((g, i) => {
		const leg = w.p * LEG_RGB.p[i] + w.o * LEG_RGB.o[i] + w.r * LEG_RGB.r[i];
		return Math.round(g + (leg - g) * k);
	});
	return `rgb(${ch.join(",")})`;
}

function bary(T: Tri, x: number, y: number) {
	const { P, O, R } = T;
	const d = (O[1] - R[1]) * (P[0] - R[0]) + (R[0] - O[0]) * (P[1] - R[1]);
	const a = ((O[1] - R[1]) * (x - R[0]) + (R[0] - O[0]) * (y - R[1])) / d;
	const b = ((R[1] - P[1]) * (x - R[0]) + (P[0] - R[0]) * (y - R[1])) / d;
	return [a, b, 1 - a - b];
}

const amp = (d: Dot) => Math.max(d.legs.p, d.legs.o, d.legs.r) * 0.95;
const THOUGHT = 0.55; // a thought's ring against a call's
const key = (d: Dot) => `${d.id}:${d.legs.p},${d.legs.o},${d.legs.r}:${d.hold}`;

type Wave = {
	x: number;
	y: number;
	b: number;
	pow: number;
	hot: boolean;
	life: number;
	rm: number;
	tri?: boolean; // a click's: a triangle, slow at first, then fast
};
// A call in flight; k is its eased progress.
type Probe = {
	x: number;
	y: number;
	lx: number | null;
	ly: number | null;
	k: number;
};
type Marker = {
	x: number;
	y: number;
	a: number;
	s: number;
	id: string | null;
	w: P3;
	lx: number | null;
	ly: number | null;
};

export class Pixels {
	private read: () => Scene = () => ({
		calls: [],
		thoughts: [],
		confirmed: { p: false, o: false, r: false },
		held: false,
	});
	private onLayout: (t: Tri) => void = () => {};
	private run = "";
	private cv: HTMLCanvasElement | null = null;
	private ctx: CanvasRenderingContext2D | null = null;
	private ro: ResizeObserver | null = null;
	private raf = 0;
	private timers: number[] = [];
	private rm = false; // reduced motion: the field stands still
	private S = Math.random() * 1000;
	private t = 0;
	private intro = 0;
	private l: number | null = null;
	private hb = -1e9;
	private shake = 0;
	private waves: Wave[] = [];
	private probes: Probe[] = []; // calls flying in from the left edge
	private pm: Pt | null = null;
	private holdPos: Pt | null = null;
	private hl: Marker | null = null;
	private seen = new Set<string>(); // dots fired, flying or landed
	private landed = new Set<string>();
	private drawn = ""; // the dots' scores the heat was last laid from
	private next = 0; // when the next dot may fire, in performance.now() time
	private DPR = 1;
	private W = 0;
	private H = 0;
	private cols = 0;
	private rows = 0;
	private tr = new Float32Array(0); // the cursor's and the marker's trail
	private acc = new Float32Array(0); // the calls' heat
	private pk = new Float32Array(0); // the salmon waves' peak
	private mask = new Uint8Array(0); // the triangle, its edge dithered
	private tri: Tri | null = null;
	private glide: gsap.core.Tween | null = null; // the triangle moving to a new size
	private reported = ""; // the layout last told to the page

	// One canvas at a time: a page switch detaches it, and the field keeps its texture and
	// its waves for the next one, as the design's.
	attach(
		cv: HTMLCanvasElement,
		run: string,
		read: () => Scene,
		onLayout: (t: Tri) => void,
	) {
		this.read = read;
		this.onLayout = onLayout;
		this.reported = "";
		this.rm = still();
		if (run !== this.run) {
			this.run = run;
			this.waves = [];
			this.holdPos = null;
			this.hl = null;
			// A run opened midway shows what it already has; only what comes next fires.
			const sc = read();
			const ids = [...sc.calls, ...sc.thoughts].map((d) => d.id);
			this.seen = new Set(ids);
			this.landed = new Set(ids);
			this.drawn = "";
		}
		this.cv = cv;
		this.ctx = cv.getContext("2d");
		cv.addEventListener("pointermove", this.move);
		cv.addEventListener("pointerleave", this.leave);
		cv.addEventListener("click", this.click);
		this.ro = new ResizeObserver(() => this.size());
		if (cv.parentElement) this.ro.observe(cv.parentElement);
		this.tri = null; // a canvas just attached is laid out at once
		this.size();
		this.raf = requestAnimationFrame(this.frame);
	}

	detach(cv: HTMLCanvasElement) {
		if (this.cv !== cv) return;
		cv.removeEventListener("pointermove", this.move);
		cv.removeEventListener("pointerleave", this.leave);
		cv.removeEventListener("click", this.click);
		this.ro?.disconnect();
		cancelAnimationFrame(this.raf);
		for (const t of this.timers) clearTimeout(t);
		this.timers = [];
		// Dots still waiting or flying would never land: they are there when the page returns.
		for (const id of this.seen) this.landed.add(id);
		this.drawn = "";
		for (const p of this.probes) gsap.killTweensOf(p);
		this.probes = [];
		this.glide?.kill();
		this.cv = null;
		this.ctx = null;
		this.pm = null;
	}

	// Each call or thought scored since the last look fires, in the run's order, one every
	// STAGGER ms; a landed dot whose scores changed has its heat laid again at once.
	sync() {
		if (!this.tri) return;
		const sc = this.read();
		const fresh = [
			...sc.calls.map((d) => ({ d, thought: false })),
			...sc.thoughts.map((d) => ({ d, thought: true })),
		]
			.filter(({ d }) => !this.seen.has(d.id))
			.sort((a, b) => a.d.at - b.d.at);
		for (const { d, thought } of fresh) {
			this.seen.add(d.id);
			if (this.rm) {
				this.flyIn(d, thought);
				continue;
			}
			const now = performance.now();
			this.next = Math.max(this.next, now);
			this.later(() => this.flyIn(d, thought), this.next - now);
			this.next += STAGGER;
		}
		if (this.drawn !== [...sc.calls, ...sc.thoughts].map(key).join())
			this.rebuild();
	}

	private size() {
		const cv = this.cv;
		const p = cv?.parentElement;
		if (!cv || !p || !this.ctx) return;
		const W = p.clientWidth;
		const H = p.clientHeight;
		if (!W || !H) return;
		const c = CELL;
		this.DPR = Math.min(window.devicePixelRatio, 2);
		cv.width = Math.round(W * this.DPR);
		cv.height = Math.round(H * this.DPR);
		cv.style.width = `${W}px`;
		cv.style.height = `${H}px`;
		this.W = W;
		this.H = H;
		this.cols = Math.ceil(W / c);
		this.rows = Math.ceil(H / c);
		const N = this.cols * this.rows;
		this.tr = new Float32Array(N);
		this.acc = new Float32Array(N);
		this.pk = new Float32Array(N);
		this.mask = new Uint8Array(N);
		const T = layout(W, H);
		const from = this.tri;
		this.glide?.kill();
		// A new gauge line or a banner resizes the field: the triangle glides there, never jumps.
		if (!from || this.rm) return this.place(T);
		const g = { k: 0 };
		this.place(from);
		this.glide = gsap.to(g, {
			k: 1,
			duration: 0.45,
			ease: "power3.out",
			onUpdate: () => this.place(mix(from, T, g.k)),
		});
	}

	// Lays the field out on T: the triangle's cells, the calls' heat, and the vertex labels.
	private place(T: Tri) {
		const c = CELL;
		this.tri = T;
		this.mask.fill(0);
		for (let r = 0; r < this.rows; r++)
			for (let q = 0; q < this.cols; q++) {
				const b = bary(T, (q + 0.5) * c, (r + 0.5) * c);
				const mn = Math.min(b[0], b[1], b[2]);
				if (mn >= 0)
					this.mask[r * this.cols + q] =
						mn * T.h > c * 1.6 || this.hsh(q, r) < 0.55 ? 1 : 0;
			}
		this.rebuild();
		const k = `${T.W}:${T.P}:${T.s}`;
		if (this.reported !== k) {
			this.reported = k;
			this.onLayout(T);
		}
	}

	private rebuild() {
		const T = this.tri;
		if (!T) return;
		this.acc.fill(0);
		const sc = this.read();
		const sg = this.sigC();
		// Only calls lay heat: a thought is its pixel, crisp on the paper.
		for (const d of sc.calls) {
			if (!this.landed.has(d.id)) continue;
			const [x, y] = pos(T, d.legs);
			this.dep(this.acc, x, y, amp(d), sg);
		}
		const he = sc.calls.find(
			(d) => d.id === sc.holdId && this.landed.has(d.id),
		);
		this.holdPos = he ? pos(T, he.legs) : null;
		this.drawn = [...sc.calls, ...sc.thoughts].map(key).join();
	}

	private hsh(c: number, r: number) {
		const n = Math.sin(c * 127.1 + r * 311.7 + this.S * 0.13) * 43758.5453;
		return n - Math.floor(n);
	}

	private base(nx0: number, ny0: number, tt: number) {
		const S = this.S;
		const nx = nx0 + Math.sin(ny0 * 5 + tt * 0.5 + S) * 0.05;
		const ny = ny0 + Math.cos(nx * 5 - tt * 0.4) * 0.05;
		const v =
			Math.sin(nx * 5.6 + S * 1.3 + tt * 0.3) *
				Math.cos(ny * 4.7 - S * 0.7 + tt * 0.22) +
			Math.sin((nx * 1.4 + ny * 1.7) * 4.1 - S + tt * 0.16) +
			Math.sin(ny * 9 + S * 2.1 + nx * 3) * 0.5 +
			Math.sin(nx * 13 - S * 1.7) * 0.28;
		return 0.5 + 0.5 * (v / 2.55);
	}

	// A blob's spread, in cells: small, so a long run's dots stay apart.
	private sigC() {
		return Math.max(0.75, ((this.tri?.s ?? 0) * 0.017) / CELL);
	}

	// Heat laid in a gaussian around (x, y).
	private dep(
		arr: Float32Array,
		x: number,
		y: number,
		amt: number,
		sig: number,
	) {
		const c = CELL;
		const cc = x / c;
		const cr = y / c;
		const R = Math.ceil(sig * 2.2);
		const inv = 1 / (2 * sig * sig);
		const q0 = Math.floor(cc);
		const r0 = Math.floor(cr);
		for (let dr = -R; dr <= R; dr++)
			for (let dq = -R; dq <= R; dq++) {
				const q = q0 + dq;
				const r = r0 + dr;
				if (q < 0 || r < 0 || q >= this.cols || r >= this.rows) continue;
				const dx = q + 0.5 - cc;
				const dy = r + 0.5 - cr;
				const w = Math.exp(-(dx * dx + dy * dy) * inv);
				if (w > 0.02) {
					const i = r * this.cols + q;
					arr[i] = Math.min(1, arr[i] + amt * w);
				}
			}
	}

	private wave(
		x: number,
		y: number,
		pow: number,
		hot: boolean,
		life = 1500,
		rm = 0,
	) {
		this.waves.push({ x, y, b: this.t, pow, hot, life, rm });
	}

	private later(fn: () => void, ms: number) {
		this.timers.push(window.setTimeout(fn, ms));
	}

	// A call flies in from the left edge, trailing heat, and lands: its heat, a ring, and for
	// a held call three salmon shockwaves and a shake. Its place is read when used, not when
	// it arrives: a banner or a new gauge line can reshape the field while it flies.
	private flyIn(d: Dot, thought = false) {
		const T = this.tri;
		if (!T) return;
		const at = () => pos(this.tri ?? T, d.legs);
		const k = thought ? THOUGHT : 1;
		const land = () => {
			const [tx, ty] = at();
			this.landed.add(d.id);
			if (!thought) this.dep(this.acc, tx, ty, amp(d), this.sigC());
			if (!this.rm) this.wave(tx, ty, k, false, 760, CELL * 6.5 * k);
			if (d.hold) {
				this.holdPos = [tx, ty];
				if (!this.rm) {
					this.wave(tx, ty, 1.3, true);
					this.later(() => this.wave(...at(), 1, true), 240);
					this.later(() => this.wave(...at(), 0.7, true), 480);
					this.shake = 0.55;
				}
			}
		};
		if (this.rm) return land();
		const [tx, ty] = at();
		const x0 = -8;
		const y0 = Math.min(
			this.H - 8,
			Math.max(8, ty + (this.hsh(tx, ty) - 0.5) * 120),
		);
		const pr: Probe = { x: x0, y: y0, lx: null, ly: null, k: 0 };
		this.probes.push(pr);
		gsap.to(pr, {
			k: 1,
			duration: thought ? 0.5 : 0.95,
			ease: "power3.out",
			onUpdate: () => {
				const [x, y] = at();
				pr.x = x0 + (x - x0) * pr.k;
				pr.y = y0 + (y - y0) * pr.k;
			},
			onComplete: () => {
				this.probes = this.probes.filter((p) => p !== pr);
				land();
			},
		});
	}

	private move = (e: PointerEvent) => {
		if (this.rm || !this.cv || !this.tri) return;
		const b = this.cv.getBoundingClientRect();
		const p: Pt = [e.clientX - b.left, e.clientY - b.top];
		const pm = this.pm;
		if (pm) {
			const n = Math.max(
				1,
				Math.min(
					48,
					Math.round(Math.hypot(p[0] - pm[0], p[1] - pm[1]) / (CELL * 0.8)),
				),
			);
			for (let i = 1; i <= n; i++)
				this.dep(
					this.tr,
					pm[0] + ((p[0] - pm[0]) * i) / n,
					pm[1] + ((p[1] - pm[1]) * i) / n,
					0.16,
					2.4,
				);
		}
		this.pm = p;
	};

	private leave = () => {
		this.pm = null;
	};

	private click = (e: MouseEvent) => {
		if (this.rm || !this.cv) return;
		const b = this.cv.getBoundingClientRect();
		const [x, y] = [e.clientX - b.left, e.clientY - b.top];
		this.waves.push({
			x,
			y,
			b: this.t,
			pow: 0.75,
			hot: false,
			life: 1500,
			rm: 0,
			tri: true,
		});
	};

	private frame = (ts: number) => {
		this.raf = requestAnimationFrame(this.frame);
		const cv = this.cv;
		const ctx = this.ctx;
		const T = this.tri;
		if (!cv || !ctx || !T || !cv.isConnected) {
			this.l = ts;
			return;
		}
		const dt = Math.min(64, ts - (this.l ?? ts));
		this.l = ts;
		const fixed = this.rm;
		this.t += dt;
		this.intro += dt / 1000;
		const tt = fixed ? 0 : this.t / 1000;
		const { W, H, cols, rows, tr, acc, pk, mask } = this;
		const c = CELL;
		for (let i = 0; i < tr.length; i++) {
			const a = tr[i] * 0.878;
			tr[i] = a < 0.003 ? 0 : a;
			const b = pk[i] * 0.93;
			pk[i] = b < 0.01 ? 0 : b;
		}
		for (const p of this.probes) {
			if (p.lx !== null && p.ly !== null) {
				const n = Math.max(
					1,
					Math.min(
						40,
						Math.round(Math.hypot(p.x - p.lx, p.y - p.ly) / (c * 0.8)),
					),
				);
				for (let j = 1; j <= n; j++)
					this.dep(
						tr,
						p.lx + ((p.x - p.lx) * j) / n,
						p.ly + ((p.y - p.ly) * j) / n,
						0.5,
						1.1,
					);
			}
			p.lx = p.x;
			p.ly = p.y;
		}
		ctx.setTransform(this.DPR, 0, 0, this.DPR, 0, 0);
		ctx.fillStyle = PAPER;
		ctx.fillRect(0, 0, W, H);
		if (this.shake > 0.01 && !fixed) {
			ctx.translate(
				(Math.random() - 0.5) * this.shake * 12,
				(Math.random() - 0.5) * this.shake * 12,
			);
			this.shake *= 0.9;
		} else this.shake = 0;
		ctx.strokeStyle = "#EFEFED";
		ctx.lineWidth = 1;
		ctx.beginPath();
		for (let x = 0; x <= W; x += c) {
			ctx.moveTo(x + 0.5, 0);
			ctx.lineTo(x + 0.5, H);
		}
		for (let y = 0; y <= H; y += c) {
			ctx.moveTo(0, y + 0.5);
			ctx.lineTo(W, y + 0.5);
		}
		ctx.stroke();
		this.waves = this.waves.filter((w) => this.t - w.b < w.life);
		const Rm = Math.hypot(W, H) * 0.62;
		const ws = this.waves.map((w) => {
			const a = (this.t - w.b) / 1000;
			if (w.tri) {
				const f = a / (w.life / 1000);
				return {
					x: w.x,
					y: w.y,
					R: Rm * 1.6 * f ** 3, // an ease-in: it crawls, then rushes out
					s2: 2 * (c * 2.4 * w.pow) ** 2,
					amp: (1 - f) * 1.1 * w.pow,
					hot: w.hot,
					tri: true,
				};
			}
			if (w.rm) {
				const f = a / (w.life / 1000);
				return {
					x: w.x,
					y: w.y,
					R: w.rm * (0.25 + 0.75 * f),
					s2: 2 * (c * 1.15 * w.pow) ** 2,
					amp: (1 - f) * 1.15 * w.pow,
					hot: w.hot,
				};
			}
			return {
				x: w.x,
				y: w.y,
				R: a * Rm,
				s2: 2 * (c * 2.4 * w.pow) ** 2,
				amp: (1 - a / 1.5) * 1.1 * w.pow,
				hot: w.hot,
			};
		});
		const sc = this.read();
		const hp = sc.held ? this.holdPos : null;
		const br =
			hp && !fixed ? 0.5 + 0.5 * Math.sin((this.t * Math.PI * 2) / 1900) : 0.5;
		const hr = hp ? this.sigC() * c * (1.8 + 1.1 * br) : 0;
		const intro = this.intro / 1.6;
		// While a call waits, its spot breathes and sends a salmon ring every 1.9 s.
		if (hp && !fixed && this.t - this.hb > 1900) {
			this.hb = this.t;
			this.waves.push({
				x: hp[0],
				y: hp[1],
				b: this.t,
				pow: 0.8,
				hot: true,
				life: 1800,
				rm: c * 7.5,
			});
		}
		for (let r = 0; r < rows; r++)
			for (let q = 0; q < cols; q++) {
				const i = r * cols + q;
				const x = (q + 0.5) * c;
				const y = (r + 0.5) * c;
				let v = acc[i] * 0.95 + tr[i] * 0.9;
				if (mask[i] && this.hsh(q * 1.7 + 11.3, r * 1.3 + 5.1) < intro)
					v +=
						0.08 +
						0.24 * this.base(x / W, y / H, tt) +
						(this.hsh(q, r) - 0.5) * 0.1 +
						(fixed ? 0 : Math.sin(q * 0.6 + r * 0.8 + tt * 1.7) * 0.03);
				let pv = pk[i];
				for (const w of ws) {
					const d =
						("tri" in w
							? triNorm(x - w.x, y - w.y)
							: Math.hypot(x - w.x, y - w.y)) - w.R;
					const val = w.amp * Math.exp(-(d * d) / w.s2);
					if (w.hot) {
						if (val > pv) pv = val;
					} else if (val > v) v = val;
				}
				pk[i] = pv;
				let col: string | null = null;
				if (pv > 0.32) col = HOT;
				else if (hp && v >= 0.62 && Math.hypot(x - hp[0], y - hp[1]) < hr)
					col = HOT;
				else {
					const b = band(v);
					if (b) col = RAMP[b];
				}
				if (col) {
					ctx.fillStyle = col;
					ctx.fillRect(q * c, r * c, c - 1, c - 1);
				}
			}
		this.drawEdges(ctx, T, sc);
		this.drawMarker(ctx, T, sc, dt);
	};

	// The landed dots as solid cells over the heat: a thought in its colour, a call in ink,
	// salmon once held, on top.
	private drawDots(ctx: CanvasRenderingContext2D, T: Tri, sc: Scene) {
		const put = (d: Dot, thought: boolean) => {
			if (!this.landed.has(d.id)) return;
			const { x0, y0, n } = square(T, d, thought);
			ctx.fillStyle = thought ? hue(d.legs) : d.hold ? HOT : INK;
			ctx.fillRect(x0, y0, n * CELL - 1, n * CELL - 1);
		};
		for (const d of sc.thoughts) put(d, true);
		for (const d of sc.calls) put(d, false);
	}

	// The sides as cells: dashed while open, ink once closed, salmon while a call waits; the
	// vertices as 3×3 blocks.
	private drawEdges(ctx: CanvasRenderingContext2D, T: Tri, sc: Scene) {
		const c = CELL;
		const sides = [
			["P", "O", "p", "o"],
			["O", "R", "o", "r"],
			["R", "P", "r", "p"],
		] as const;
		for (const [a, b, ka, kb] of sides) {
			const A = T[a];
			const B = T[b];
			const closed = sc.confirmed[ka] && sc.confirmed[kb];
			const n = Math.ceil(Math.hypot(B[0] - A[0], B[1] - A[1]) / (c * 0.5));
			ctx.fillStyle = sc.held ? HOT : closed ? INK : "#C9C9C6";
			let last = -1;
			for (let k = 0; k <= n; k++) {
				const q = Math.floor((A[0] + ((B[0] - A[0]) * k) / n) / c);
				const r = Math.floor((A[1] + ((B[1] - A[1]) * k) / n) / c);
				const id = r * this.cols + q;
				if (id === last) continue;
				last = id;
				if (!closed && !sc.held && (q + r) & 1) continue;
				ctx.fillRect(q * c, r * c, c - 1, c - 1);
			}
		}
		ctx.fillStyle = INK;
		for (const k of ["P", "O", "R"] as const) {
			const q = Math.floor(T[k][0] / c);
			const r = Math.floor(T[k][1] / c);
			ctx.fillRect((q - 1) * c, (r - 1) * c, c * 3 - 1, c * 3 - 1);
		}
	}

	// The marker glides to its call (fast when pinned), its lines to the vertices as thick as
	// the scores; it pops bigger on a new call, and pulses salmon on a waiting one.
	private drawMarker(
		ctx: CanvasRenderingContext2D,
		T: Tri,
		sc: Scene,
		dt: number,
	) {
		const c = CELL;
		const pin = sc.pin ? sc.calls.find((d) => d.id === sc.pin) : undefined;
		const e = pin ?? sc.calls.findLast((d) => this.landed.has(d.id));
		this.hl ??= {
			x: (T.P[0] + T.O[0] + T.R[0]) / 3,
			y: (T.P[1] + T.O[1] + T.R[1]) / 3,
			a: 0,
			s: 3,
			id: null,
			w: { p: 0, o: 0, r: 0 },
			lx: null,
			ly: null,
		};
		const M = this.hl;
		const fixed = this.rm;
		const k = fixed ? 1 : 1 - Math.exp(-(dt || 16) * (pin ? 0.012 : 0.0046));
		if (e) {
			const { cx: tx, cy: ty } = square(T, e, false);
			if (M.id !== e.id) {
				M.id = e.id;
				if (!fixed) M.s = 5;
			}
			M.x += (tx - M.x) * k;
			M.y += (ty - M.y) * k;
			M.a += (1 - M.a) * Math.min(1, k * 2.5);
			for (const q of ["p", "o", "r"] as const)
				M.w[q] += (e.legs[q] - M.w[q]) * k;
			if (!fixed && M.lx !== null && M.ly !== null && M.a > 0.6) {
				const n = Math.min(
					40,
					Math.round(Math.hypot(M.x - M.lx, M.y - M.ly) / (c * 0.7)),
				);
				for (let j = 1; j <= n; j++)
					this.dep(
						this.tr,
						M.lx + ((M.x - M.lx) * j) / n,
						M.ly + ((M.y - M.ly) * j) / n,
						0.42,
						1.05,
					);
			}
			M.lx = M.x;
			M.ly = M.y;
		} else {
			M.a += (0 - M.a) * k * 1.4;
			M.id = null;
			M.lx = null;
		}
		M.s += (3 - M.s) * k;
		if (M.a < 0.02) return this.drawDots(ctx, T, sc);
		const held = Boolean(e && sc.held && e.id === sc.holdId);
		const pu =
			held && !fixed ? 0.5 + 0.5 * Math.sin((this.t * Math.PI * 2) / 1900) : 0;
		const half = ((M.s + pu * 1.4) * c) / 2;
		ctx.save();
		ctx.globalAlpha = Math.min(1, M.a);
		ctx.lineCap = "butt";
		for (const [V, q] of [
			["P", "p"],
			["O", "o"],
			["R", "r"],
		] as const) {
			const [vx, vy] = T[V];
			const w = 1.2 + 2.6 * M.w[q];
			ctx.beginPath();
			ctx.moveTo(M.x, M.y);
			ctx.lineTo(vx, vy);
			ctx.strokeStyle = PAPER;
			ctx.lineWidth = w + 3;
			ctx.stroke();
			ctx.strokeStyle = LC[q];
			ctx.lineWidth = w;
			ctx.stroke();
		}
		ctx.restore();
		// The dots over the lines, under the square: a line never hides a dot.
		this.drawDots(ctx, T, sc);
		ctx.save();
		// Centred on the call, unrounded: the dots under it show through the fill.
		const sz = half * 2;
		const rx = M.x - half;
		const ry = M.y - half;
		const ink = held ? "#B8331C" : INK;
		const a = Math.min(1, M.a);
		ctx.globalAlpha = a * 0.35;
		ctx.fillStyle = held ? SALMON : PAPER;
		ctx.fillRect(rx, ry, sz, sz);
		ctx.globalAlpha = a * 0.6;
		ctx.lineWidth = 2.5;
		ctx.strokeStyle = PAPER;
		ctx.strokeRect(rx, ry, sz, sz);
		ctx.globalAlpha = a;
		ctx.lineWidth = 1.2;
		ctx.strokeStyle = ink;
		ctx.strokeRect(rx, ry, sz, sz);
		ctx.fillStyle = ink;
		const d = 4; // even, so it sits exactly on the centre
		ctx.fillRect(M.x - d / 2, M.y - d / 2, d, d);
		ctx.restore();
	}
}
