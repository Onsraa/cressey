import type { IconNode } from "lucide";
import {
	Activity as activity,
	ArrowDownWideNarrow as arrowDownWideNarrow,
	ArrowRight as arrowRight,
	Ban as ban,
	Bell as bell,
	BookOpen as bookOpen,
	Bot as bot,
	ChartColumn as chartColumn,
	Check as check,
	ChevronRight as chevronRight,
	ChevronsUp as chevronsUp,
	ChevronUp as chevronUp,
	CircleHelp as circleHelp,
	CirclePause as circlePause,
	CircleX as circleX,
	Clock as clock,
	Columns2 as columns2,
	Copy as copy,
	Cpu as cpu,
	DoorOpen as doorOpen,
	Eye as eye,
	FileCheck as fileCheck,
	FileText as fileText,
	Focus as focus,
	Gavel as gavel,
	GitMerge as gitMerge,
	Hash as hash,
	Hourglass as hourglass,
	Inbox as inbox,
	Info as info,
	Keyboard as keyboard,
	KeySquare as keySquare,
	LayoutDashboard as layoutDashboard,
	List as list,
	Lock as lock,
	MessageSquare as messageSquare,
	Minus as minus,
	MousePointerClick as mousePointerClick,
	PanelLeftClose as panelLeftClose,
	PanelLeftOpen as panelLeftOpen,
	Pause as pause,
	Pencil as pencil,
	Repeat as repeat,
	Search as search,
	Shield as shield,
	ShieldCheck as shieldCheck,
	SlidersHorizontal as slidersHorizontal,
	SquareCheck as squareCheck,
	Terminal as terminal,
	Trash2 as trash2,
	Triangle as triangle,
	TriangleAlert as triangleAlert,
	Unplug as unplug,
	Wrench as wrench,
	X as x,
} from "lucide";
import { createElement, type ReactNode } from "react";

// The design's lucide-straight.js (<lc-icon>): a Lucide icon with every curve straightened.
// Corner arcs and curves become sharp corners, large arcs and circles become facets, with
// square caps and mitred joins, so the icons match the pixel type and the square corners.

type Attrs = IconNode[number][1];
type Pt = [number, number];

const ARGS: Record<string, number> = {
	M: 2,
	L: 2,
	H: 1,
	V: 1,
	C: 6,
	S: 4,
	Q: 4,
	T: 2,
	A: 7,
	Z: 0,
};
const r2 = (n: number) => Math.round(n * 100) / 100;

// A path's commands with their numbers; it stops at the first malformed one, as the design.
function scan(d: string): [string, number[]][] {
	const out: [string, number[]][] = [];
	let i = 0;
	let cmd: string | null = null;
	const ws = () => {
		while (i < d.length && /[\s,]/.test(d[i])) i++;
	};
	const num = () => {
		ws();
		const m = /^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?/.exec(d.slice(i));
		if (!m) return null;
		i += m[0].length;
		return Number.parseFloat(m[0]);
	};
	const flag = () => {
		ws();
		const c = d[i];
		if (c !== "0" && c !== "1") return null;
		i++;
		return Number(c);
	};
	while (i < d.length) {
		ws();
		if (i >= d.length) break;
		const ch = d[i];
		if (/[a-zA-Z]/.test(ch)) {
			cmd = ch;
			i++;
			if (ch === "z" || ch === "Z") {
				out.push([ch, []]);
				cmd = null;
				continue;
			}
		} else if (cmd === null) break;
		const U = cmd.toUpperCase();
		const k = ARGS[U];
		if (k === undefined) break;
		const args: number[] = [];
		for (let j = 0; j < k; j++) {
			const v = U === "A" && (j === 3 || j === 4) ? flag() : num();
			if (v === null) return out;
			args.push(v);
		}
		out.push([cmd, args]);
		if (cmd === "M") cmd = "L";
		else if (cmd === "m") cmd = "l";
	}
	return out;
}

// An arc as straight segments: a small one (a rounded corner) keeps one sharp corner per
// quarter turn, a large one becomes eighths of a turn.
function arcPts(
	x1: number,
	y1: number,
	rx: number,
	ry: number,
	phi: number,
	fa: number,
	fs: number,
	x2: number,
	y2: number,
): Pt[] {
	if (!rx || !ry || (x1 === x2 && y1 === y2)) return [[x2, y2]];
	const rad = (phi * Math.PI) / 180;
	const sp = Math.sin(rad);
	const cp = Math.cos(rad);
	const dx = (x1 - x2) / 2;
	const dy = (y1 - y2) / 2;
	const xp = cp * dx + sp * dy;
	const yp = -sp * dx + cp * dy;
	let Rx = Math.abs(rx);
	let Ry = Math.abs(ry);
	const lam = (xp * xp) / (Rx * Rx) + (yp * yp) / (Ry * Ry);
	if (lam > 1) {
		const sq = Math.sqrt(lam);
		Rx *= sq;
		Ry *= sq;
	}
	const nu = Rx * Rx * Ry * Ry - Rx * Rx * yp * yp - Ry * Ry * xp * xp;
	const de = Rx * Rx * yp * yp + Ry * Ry * xp * xp;
	let co = de ? Math.sqrt(Math.max(0, nu / de)) : 0;
	if (fa === fs) co = -co;
	const cxp = (co * Rx * yp) / Ry;
	const cyp = (-co * Ry * xp) / Rx;
	const cx = cp * cxp - sp * cyp + (x1 + x2) / 2;
	const cy = sp * cxp + cp * cyp + (y1 + y2) / 2;
	const ang = (ux: number, uy: number, vx: number, vy: number) =>
		Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy);
	const t1 = ang(1, 0, (xp - cxp) / Rx, (yp - cyp) / Ry);
	let dt = ang(
		(xp - cxp) / Rx,
		(yp - cyp) / Ry,
		(-xp - cxp) / Rx,
		(-yp - cyp) / Ry,
	);
	if (!fs && dt > 0) dt -= 2 * Math.PI;
	else if (fs && dt < 0) dt += 2 * Math.PI;
	const small = Math.max(Rx, Ry) <= 2.6;
	const seg = small ? Math.PI / 2 : Math.PI / 4;
	const n = Math.max(1, Math.ceil(Math.abs(dt) / seg - 1e-6));
	const step = dt / n;
	const at = (t: number, k: number): Pt => {
		const ex = Rx * Math.cos(t) * k;
		const ey = Ry * Math.sin(t) * k;
		return [cp * ex - sp * ey + cx, sp * ex + cp * ey + cy];
	};
	const pts: Pt[] = [];
	for (let j = 1; j <= n; j++) {
		const ta = t1 + step * (j - 1);
		const tb = t1 + step * j;
		if (small) pts.push(at((ta + tb) / 2, 1 / Math.cos(step / 2)));
		pts.push(j === n ? [x2, y2] : at(tb, 1));
	}
	return pts;
}

// A cubic curve as the corner where its two tangents meet, else through its midpoint.
function cubicPts(
	x0: number,
	y0: number,
	x1: number,
	y1: number,
	x2: number,
	y2: number,
	x3: number,
	y3: number,
): Pt[] {
	let d1x = x1 - x0;
	let d1y = y1 - y0;
	let d2x = x3 - x2;
	let d2y = y3 - y2;
	if (Math.abs(d1x) + Math.abs(d1y) < 1e-6) {
		d1x = x2 - x0;
		d1y = y2 - y0;
	}
	if (Math.abs(d2x) + Math.abs(d2y) < 1e-6) {
		d2x = x3 - x1;
		d2y = y3 - y1;
	}
	const den = d1x * d2y - d1y * d2x;
	if (Math.abs(den) > 1e-6) {
		const t = ((x3 - x0) * d2y - (y3 - y0) * d2x) / den;
		const cx = x0 + d1x * t;
		const cy = y0 + d1y * t;
		const inX =
			cx >= Math.min(x0, x1, x2, x3) - 0.5 &&
			cx <= Math.max(x0, x1, x2, x3) + 0.5;
		const inY =
			cy >= Math.min(y0, y1, y2, y3) - 0.5 &&
			cy <= Math.max(y0, y1, y2, y3) + 0.5;
		if (t > 0 && inX && inY)
			return [
				[cx, cy],
				[x3, y3],
			];
	}
	const u = 0.5;
	return [
		[
			u * u * u * x0 + 3 * u * u * u * x1 + 3 * u * u * u * x2 + u * u * u * x3,
			u * u * u * y0 + 3 * u * u * u * y1 + 3 * u * u * u * y2 + u * u * u * y3,
		],
		[x3, y3],
	];
}

function polyD(d: string) {
	let x = 0;
	let y = 0;
	let sx = 0;
	let sy = 0;
	let lc: Pt | null = null; // the last cubic control point, for S
	let lq: Pt | null = null; // the last quadratic control point, for T
	let out = "";
	const L = (p: Pt) => {
		out += `L${r2(p[0])} ${r2(p[1])}`;
	};
	for (const [c, a] of scan(d)) {
		const U = c.toUpperCase();
		const rel = c !== U;
		const ox = rel ? x : 0;
		const oy = rel ? y : 0;
		if (U === "M") {
			x = ox + a[0];
			y = oy + a[1];
			sx = x;
			sy = y;
			out += `M${r2(x)} ${r2(y)}`;
			lc = lq = null;
		} else if (U === "L") {
			x = ox + a[0];
			y = oy + a[1];
			L([x, y]);
			lc = lq = null;
		} else if (U === "H") {
			x = ox + a[0];
			L([x, y]);
			lc = lq = null;
		} else if (U === "V") {
			y = oy + a[0];
			L([x, y]);
			lc = lq = null;
		} else if (U === "C" || U === "S") {
			let x1: number;
			let y1: number;
			let x2: number;
			let y2: number;
			let nx: number;
			let ny: number;
			if (U === "C") {
				x1 = ox + a[0];
				y1 = oy + a[1];
				x2 = ox + a[2];
				y2 = oy + a[3];
				nx = ox + a[4];
				ny = oy + a[5];
			} else {
				x1 = lc ? 2 * x - lc[0] : x;
				y1 = lc ? 2 * y - lc[1] : y;
				x2 = ox + a[0];
				y2 = oy + a[1];
				nx = ox + a[2];
				ny = oy + a[3];
			}
			cubicPts(x, y, x1, y1, x2, y2, nx, ny).forEach(L);
			lc = [x2, y2];
			lq = null;
			x = nx;
			y = ny;
		} else if (U === "Q" || U === "T") {
			let qx: number;
			let qy: number;
			let nx: number;
			let ny: number;
			if (U === "Q") {
				qx = ox + a[0];
				qy = oy + a[1];
				nx = ox + a[2];
				ny = oy + a[3];
			} else {
				qx = lq ? 2 * x - lq[0] : x;
				qy = lq ? 2 * y - lq[1] : y;
				nx = ox + a[0];
				ny = oy + a[1];
			}
			L([qx, qy]);
			L([nx, ny]);
			lq = [qx, qy];
			lc = null;
			x = nx;
			y = ny;
		} else if (U === "A") {
			const nx = ox + a[5];
			const ny = oy + a[6];
			arcPts(x, y, a[0], a[1], a[2], a[3], a[4], nx, ny).forEach(L);
			x = nx;
			y = ny;
			lc = lq = null;
		} else if (U === "Z") {
			out += "Z";
			x = sx;
			y = sy;
			lc = lq = null;
		}
	}
	return out;
}

// A circle or an ellipse: an octagon around it, or a square when it is a dot.
function circ(
	cx: number,
	cy: number,
	rx: number,
	ry: number,
	rest: Attrs,
): IconNode[number] {
	if (Math.max(rx, ry) < 3)
		return [
			"rect",
			{
				x: r2(cx - rx),
				y: r2(cy - ry),
				width: r2(2 * rx),
				height: r2(2 * ry),
				...rest,
			},
		];
	const k = 1 / Math.cos(Math.PI / 8);
	let d = "";
	for (let j = 0; j < 8; j++) {
		const t = Math.PI / 8 + (j * Math.PI) / 4;
		d += `${j ? "L" : "M"}${r2(cx + rx * k * Math.cos(t))} ${r2(cy + ry * k * Math.sin(t))}`;
	}
	return ["path", { d: `${d}Z`, ...rest }];
}

function conv([tag, attrs]: IconNode[number]): IconNode[number] {
	if (tag === "path")
		return ["path", { ...attrs, d: polyD(String(attrs.d ?? "")) }];
	if (tag === "rect") {
		const { rx: _rx, ry: _ry, ...rest } = attrs;
		return ["rect", rest];
	}
	if (tag === "circle") {
		const { cx, cy, r, ...rest } = attrs;
		const R = Number(r) || 0;
		return circ(Number(cx) || 0, Number(cy) || 0, R, R, rest);
	}
	if (tag === "ellipse") {
		const { cx, cy, rx, ry, ...rest } = attrs;
		return circ(
			Number(cx) || 0,
			Number(cy) || 0,
			Number(rx) || 0,
			Number(ry) || 0,
			rest,
		);
	}
	return [tag, attrs];
}

export type IconProps = {
	size?: number;
	strokeWidth?: number;
	className?: string;
};
export type IconType = (props: IconProps) => ReactNode;

// <lc-icon name size stroke>: an inline-flex box of the icon's size around a block svg.
function make(node: IconNode): IconType {
	const kids = node.map(conv);
	return ({ size = 16, strokeWidth = 2, className }) => (
		<span
			className={className}
			style={{
				display: "inline-flex",
				flex: "none",
				width: size,
				height: size,
				lineHeight: 0,
			}}
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width={size}
				height={size}
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth={strokeWidth}
				strokeLinecap="square"
				strokeLinejoin="miter"
				aria-hidden="true"
				focusable="false"
				style={{ display: "block" }}
			>
				{kids.map(([tag, a], i) => createElement(tag, { key: i, ...a }))}
			</svg>
		</span>
	);
}

export const Activity = make(activity);
export const ArrowDownWideNarrow = make(arrowDownWideNarrow);
export const ArrowRight = make(arrowRight);
export const Ban = make(ban);
export const Bell = make(bell);
export const BookOpen = make(bookOpen);
export const Bot = make(bot);
export const ChartColumn = make(chartColumn);
export const Check = make(check);
export const ChevronRight = make(chevronRight);
export const ChevronsUp = make(chevronsUp);
export const ChevronUp = make(chevronUp);
export const CircleHelp = make(circleHelp);
export const CirclePause = make(circlePause);
export const CircleX = make(circleX);
export const Clock = make(clock);
export const Columns2 = make(columns2);
export const Copy = make(copy);
export const Cpu = make(cpu);
export const DoorOpen = make(doorOpen);
export const Eye = make(eye);
export const FileCheck = make(fileCheck);
export const FileText = make(fileText);
export const Focus = make(focus);
export const Gavel = make(gavel);
export const GitMerge = make(gitMerge);
export const Hash = make(hash);
export const Hourglass = make(hourglass);
export const Inbox = make(inbox);
export const Info = make(info);
export const Keyboard = make(keyboard);
export const KeySquare = make(keySquare);
export const LayoutDashboard = make(layoutDashboard);
export const List = make(list);
export const Lock = make(lock);
export const MessageSquare = make(messageSquare);
export const Minus = make(minus);
export const MousePointerClick = make(mousePointerClick);
export const PanelLeftClose = make(panelLeftClose);
export const PanelLeftOpen = make(panelLeftOpen);
export const Pause = make(pause);
export const Pencil = make(pencil);
export const Repeat = make(repeat);
export const Search = make(search);
export const Shield = make(shield);
export const ShieldCheck = make(shieldCheck);
export const SlidersHorizontal = make(slidersHorizontal);
export const SquareCheck = make(squareCheck);
export const Terminal = make(terminal);
export const Trash2 = make(trash2);
export const Triangle = make(triangle);
export const TriangleAlert = make(triangleAlert);
export const Unplug = make(unplug);
export const Wrench = make(wrench);
export const X = make(x);
