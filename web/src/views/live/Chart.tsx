import type { LegName, Run } from "@/api/types";
import { LEGS } from "@/lib/labels";
import { scored, tipOf } from "./run";
import { useSize } from "./ui";

// Room for the axis labels and the « RETENU » marks.
const PAD = { left: 38, right: 8, top: 22, bottom: 24 };
const TICKS = [0, 0.25, 0.5, 0.75, 1];
const LABEL_W = 34; // the room an x label needs, so that a long run thins them out
const DOT = 7;
const BAND = 16; // the held mark's width

// Each leg also has its own dash and point shape: colour is never the only signal.
const DASH: Record<LegName, string | undefined> = {
	pressure: undefined,
	opportunity: "6 4",
	rationalization: "2 3",
};

export function Chart({ run }: { run: Run }) {
	const { ref, w, h } = useSize();
	const calls = scored(run);
	const pw = w - PAD.left - PAD.right;
	const ph = h - PAD.top - PAD.bottom;
	const dx = pw / Math.max(1, calls.length);
	const X = (i: number) => PAD.left + (i + 0.5) * dx;
	const Y = (v: number) => PAD.top + (1 - v) * ph;
	const every = Math.ceil(LABEL_W / dx);
	return (
		<div className="absolute inset-[20px_22px_14px] flex flex-col gap-1">
			<div className="flex flex-wrap justify-end gap-x-3.5 gap-y-1 font-mono text-[11px] text-mute">
				{LEGS.map((g) => (
					<span key={g.k} className="inline-flex items-center gap-1.5">
						<svg width={18} height={4} aria-hidden="true">
							<line
								x1={0}
								x2={18}
								y1={2}
								y2={2}
								strokeWidth={2}
								strokeDasharray={DASH[g.k]}
								style={{ stroke: g.color }}
							/>
						</svg>
						{g.L} · {g.name}
					</span>
				))}
			</div>
			<div ref={ref} className="relative min-h-0 flex-1">
				{w > 0 && (
					<svg
						width={w}
						height={h}
						role="img"
						aria-label="Pression, opportunité et rationalisation à chaque appel, l'appel retenu marqué"
						className="absolute inset-0 font-mono text-[11px]"
					>
						{calls.map((c, i) =>
							c.step.held_until ? (
								<g key={c.step.n}>
									<rect
										x={X(i) - BAND / 2}
										y={PAD.top}
										width={BAND}
										height={ph}
										className="fill-held"
									/>
									<text
										x={X(i)}
										y={PAD.top - 6}
										textAnchor="middle"
										className="fill-held-fg font-pixel text-[17px]"
									>
										RETENU
									</text>
								</g>
							) : null,
						)}
						{TICKS.map((v) => (
							<g key={v}>
								<line
									x1={PAD.left}
									x2={w - PAD.right}
									y1={Y(v)}
									y2={Y(v)}
									className="stroke-grey"
								/>
								<text
									x={PAD.left - 6}
									y={Y(v)}
									textAnchor="end"
									dominantBaseline="middle"
									className="fill-mute"
								>
									{v.toFixed(2)}
								</text>
							</g>
						))}
						<path
							d={`M${PAD.left} ${PAD.top}V${PAD.top + ph}H${w - PAD.right}`}
							fill="none"
							className="stroke-ink"
						/>
						{LEGS.map((g) => (
							<polyline
								key={g.k}
								points={calls
									.map((c, i) => `${X(i)},${Y(c.legs[g.k].score)}`)
									.join(" ")}
								fill="none"
								strokeWidth={g.k === "rationalization" ? 2 : 1.8}
								strokeDasharray={DASH[g.k]}
								style={{ stroke: g.color }}
							/>
						))}
						{calls.map((c, i) => (
							<g key={c.step.n}>
								{LEGS.map((g) => (
									<Dot
										key={g.k}
										leg={g.k}
										x={X(i)}
										y={Y(c.legs[g.k].score)}
										color={g.color}
									/>
								))}
							</g>
						))}
						{calls.map((c, i) =>
							i % every === 0 ? (
								<text
									key={c.step.n}
									x={X(i)}
									y={h - 6}
									textAnchor="middle"
									className="fill-mute"
								>
									#{c.step.n}
								</text>
							) : null,
						)}
						{calls.map((c, i) => (
							<rect
								key={c.step.n}
								x={X(i) - dx / 2}
								y={PAD.top}
								width={dx}
								height={ph}
								fill="transparent"
								data-tip={tipOf(c)}
							/>
						))}
					</svg>
				)}
			</div>
		</div>
	);
}

// P a square, O a hollow square, R a triangle, as in the design.
function Dot({
	leg,
	x,
	y,
	color,
}: {
	leg: LegName;
	x: number;
	y: number;
	color: string;
}) {
	const r = DOT / 2;
	if (leg === "rationalization")
		return (
			<polygon
				points={`${x},${y - r - 1} ${x + r + 1},${y + r} ${x - r - 1},${y + r}`}
				style={{ fill: color }}
			/>
		);
	return (
		<rect
			x={x - r}
			y={y - r}
			width={DOT}
			height={DOT}
			strokeWidth={1.5}
			style={{
				fill: leg === "opportunity" ? "var(--color-surface)" : color,
				stroke: color,
			}}
		/>
	);
}
