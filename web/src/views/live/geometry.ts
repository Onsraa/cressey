import type { LegName, Legs } from "@/api/types";
import { band } from "./run";

export type Pt = { x: number; y: number };
// The vertices by leg: P at the top, O bottom left, R bottom right.
export type Tri = Record<LegName, Pt> & { h: number };

export const CELL = 10; // the design's medium pixel

// The design's layout: room around the triangle for the vertex labels.
const PAD_X = 84;
const PAD_TOP = 62;
const PAD_BOTTOM = 60;
const MIN_SIDE = 140;

export function triangle(w: number, h: number): Tri {
	const room = h - PAD_TOP - PAD_BOTTOM;
	const side = Math.max(
		MIN_SIDE,
		Math.min(w - 2 * PAD_X, (room * 2) / Math.sqrt(3)),
	);
	const th = (side * Math.sqrt(3)) / 2;
	const x = w / 2;
	const y = PAD_TOP + Math.max(0, (room - th) / 2);
	return {
		pressure: { x, y },
		opportunity: { x: x - side / 2, y: y + th },
		rationalization: { x: x + side / 2, y: y + th },
		h: th,
	};
}

const KEYS: LegName[] = ["pressure", "opportunity", "rationalization"];

export type PerLeg = Record<LegName, number>;
export const perLeg = (f: (k: LegName) => number): PerLeg => ({
	pressure: f("pressure"),
	opportunity: f("opportunity"),
	rationalization: f("rationalization"),
});

// A call's weights: its three scores, normalised. All zero: equal weights, the centre.
export function weights(legs: Legs): PerLeg {
	const sum = KEYS.reduce((s, k) => s + legs[k].score, 0);
	return perLeg((k) => (sum ? legs[k].score / sum : 1 / 3));
}

// The barycentre of the vertices under those weights.
export const at = (t: Tri, w: PerLeg): Pt => ({
	x: KEYS.reduce((x, k) => x + w[k] * t[k].x, 0),
	y: KEYS.reduce((y, k) => y + w[k] * t[k].y, 0),
});

// A call sits at the barycentre of the vertices, weighted by its three scores.
export const place = (t: Tri, legs: Legs): Pt => at(t, weights(legs));

export const cellRect = (q: number, r: number, span = 1) => ({
	x: q * CELL,
	y: r * CELL,
	width: span * CELL - 1,
	height: span * CELL - 1,
});

// The smallest barycentric coordinate of (x, y): ≥ 0 inside the triangle.
function inside(t: Tri, x: number, y: number) {
	const { pressure: P, opportunity: O, rationalization: R } = t;
	const d = (O.y - R.y) * (P.x - R.x) + (R.x - O.x) * (P.y - R.y);
	const a = ((O.y - R.y) * (x - R.x) + (R.x - O.x) * (y - R.y)) / d;
	const b = ((R.y - P.y) * (x - R.x) + (P.x - R.x) * (y - R.y)) / d;
	return Math.min(a, b, 1 - a - b);
}

// The design's drawField, frozen in time: a hash, a noise texture inside the triangle, and
// a blob of heat where each call lands, as strong as its highest score.
const hash = (q: number, r: number, seed: number) => {
	const n = Math.sin(q * 127.1 + r * 311.7 + seed * 0.13) * 43758.5453;
	return n - Math.floor(n);
};

function noise(nx: number, ny: number, s: number) {
	const x = nx + Math.sin(ny * 5 + s) * 0.05;
	const y = ny + Math.cos(x * 5) * 0.05;
	const v =
		Math.sin(x * 5.6 + s * 1.3) * Math.cos(y * 4.7 - s * 0.7) +
		Math.sin((x * 1.4 + y * 1.7) * 4.1 - s) +
		Math.sin(y * 9 + s * 2.1 + x * 3) * 0.5 +
		Math.sin(x * 13 - s * 1.7) * 0.28;
	return 0.5 + 0.5 * (v / 2.55);
}

export type Heat = { at: Pt; score: number; held: boolean };
export type Cell = { q: number; r: number; band: number; hot: boolean };

export function heat(
	t: Tri,
	w: number,
	h: number,
	calls: Heat[],
	seed: number,
): Cell[] {
	const cols = Math.ceil(w / CELL);
	const rows = Math.ceil(h / CELL);
	const sig = Math.max(
		1.5,
		((t.rationalization.x - t.opportunity.x) * 0.034) / CELL,
	); // a blob's spread, in cells
	const reach = Math.ceil(sig * 2.2);
	const acc = new Float32Array(cols * rows);
	for (const c of calls) {
		const cq = c.at.x / CELL;
		const cr = c.at.y / CELL;
		for (let r = Math.floor(cr) - reach; r <= Math.floor(cr) + reach; r++)
			for (let q = Math.floor(cq) - reach; q <= Math.floor(cq) + reach; q++) {
				if (q < 0 || r < 0 || q >= cols || r >= rows) continue;
				const d2 = (q + 0.5 - cq) ** 2 + (r + 0.5 - cr) ** 2;
				const i = r * cols + q;
				acc[i] = Math.min(
					1,
					acc[i] + c.score * 0.95 * Math.exp(-d2 / (2 * sig * sig)),
				);
			}
	}
	const out: Cell[] = [];
	for (let r = 0; r < rows; r++)
		for (let q = 0; q < cols; q++) {
			const x = (q + 0.5) * CELL;
			const y = (r + 0.5) * CELL;
			const m = inside(t, x, y);
			// The edge is dithered: a cell just inside it shows about half the time.
			const masked =
				m >= 0 && (m * t.h > CELL * 1.6 || hash(q, r, seed) < 0.55);
			const v =
				acc[r * cols + q] * 0.95 +
				(masked
					? 0.08 +
						0.24 * noise(x / w, y / h, seed) +
						(hash(q, r, seed) - 0.5) * 0.1
					: 0);
			const hot =
				v >= 0.62 &&
				calls.some(
					(c) =>
						c.held && Math.hypot(x - c.at.x, y - c.at.y) < sig * CELL * 2.3,
				);
			const b = band(v);
			if (hot || b) out.push({ q, r, band: b, hot });
		}
	return out;
}

// The cells along a side, from a to b; an open side is dashed.
export function edge(a: Pt, b: Pt, dashed: boolean) {
	const n = Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / (CELL / 2));
	const out: { q: number; r: number }[] = [];
	let last = "";
	for (let k = 0; k <= n; k++) {
		const q = Math.floor((a.x + ((b.x - a.x) * k) / n) / CELL);
		const r = Math.floor((a.y + ((b.y - a.y) * k) / n) / CELL);
		const id = `${q},${r}`;
		if (id === last) continue;
		last = id;
		if (!dashed || (q + r) % 2 === 0) out.push({ q, r });
	}
	return out;
}

const REACH = 5; // how far a landing pulse's front goes, in cells
const WIDTH = 2; // half its thickness, in cells

// The design's reactive landing, kept small: at age a (0 to 1), the cells lit by a ring of
// heat leaving the point of a call that just landed, each with its band in a four-step ramp
// (3 the hottest). The ring slows as it spreads, and cools away.
export function pulse(p: Pt, a: number) {
	const cq = p.x / CELL;
	const cr = p.y / CELL;
	const front = REACH * (1 - (1 - a) ** 3);
	const out: { q: number; r: number; band: number }[] = [];
	const R = REACH + WIDTH;
	for (let r = Math.floor(cr) - R; r <= Math.floor(cr) + R; r++)
		for (let q = Math.floor(cq) - R; q <= Math.floor(cq) + R; q++) {
			const d = Math.hypot(q + 0.5 - cq, r + 0.5 - cr);
			const v = (1 - a) * Math.max(0, 1 - Math.abs(d - front) / WIDTH);
			const b = Math.min(3, Math.floor(v * 5) - 1);
			if (b >= 0) out.push({ q, r, band: b });
		}
	return out;
}
