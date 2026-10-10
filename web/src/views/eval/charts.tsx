import { useEffect, useId, useRef, useState } from "react";
import { num } from "./format";
import type { Scored } from "./read";

export type Bar = {
	key: string;
	value: number; // 0 to 1
	text: string; // printed above the bar
	tip: string;
	fill?: string;
	hatch?: boolean; // the design's hatched bar, for the normal sessions
};

export type Group = { label: string; bars: Bar[] | null }; // null: not measured yet

const [L, R, T, B] = [48, 10, 26, 28];
const TICKS = [0, 0.25, 0.5, 0.75, 1];

// The box a chart fills, measured, so its text keeps its size on any screen.
function useBox() {
	const ref = useRef<HTMLDivElement>(null);
	const [box, setBox] = useState({ w: 0, h: 0 });
	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		const ro = new ResizeObserver(() =>
			setBox({ w: el.clientWidth, h: el.clientHeight }),
		);
		ro.observe(el);
		return () => ro.disconnect();
	}, []);
	return [ref, box] as const;
}

export function Bars({
	groups,
	label,
	percent,
}: {
	groups: Group[];
	label: string;
	percent?: boolean;
}) {
	const hatch = useId();
	const [ref, { w, h }] = useBox();
	const pw = w - L - R;
	const ph = h - T - B;
	const y = (v: number) => T + ph * (1 - v);
	const band = pw / groups.length;
	const inner = band * 0.62;
	return (
		<div ref={ref} className="relative mx-3.5 mt-3 mb-2.5 min-h-0 flex-1">
			{pw > 0 && ph > 0 && (
				<svg
					width={w}
					height={h}
					role="img"
					aria-label={label}
					className="absolute inset-0 font-mono"
				>
					<defs>
						<pattern
							id={hatch}
							width={6}
							height={6}
							patternUnits="userSpaceOnUse"
						>
							<rect width={6} height={6} fill="var(--color-surface)" />
							<path d="M0 6L6 0" stroke="var(--color-ink)" />
						</pattern>
					</defs>
					{TICKS.map((t) => (
						<g key={t}>
							<line
								x1={L}
								x2={w - R}
								y1={y(t)}
								y2={y(t)}
								stroke="var(--color-grey)"
							/>
							<text
								x={L - 7}
								y={y(t)}
								textAnchor="end"
								dominantBaseline="middle"
								fontSize={11}
								fill="var(--color-mute)"
							>
								{percent ? `${num(t * 100)}%` : t.toLocaleString("en-US")}
							</text>
						</g>
					))}
					{groups.map((g, i) => {
						const x0 = L + band * i;
						const slot = g.bars ? inner / g.bars.length : 0;
						return (
							<g key={g.label}>
								{g.bars ? (
									g.bars.map((b, j) => {
										const bw = slot * 0.72;
										const x =
											x0 + (band - inner) / 2 + slot * j + (slot - bw) / 2;
										return (
											<g key={b.key} data-tip={b.tip}>
												<rect
													x={x}
													y={y(b.value)}
													width={bw}
													height={ph * b.value}
													fill={b.hatch ? `url(#${hatch})` : b.fill}
													stroke="var(--color-ink)"
													strokeWidth={1.2}
												/>
												<text
													x={x + bw / 2}
													y={y(b.value) - 5}
													textAnchor="middle"
													fontSize={19}
													className="font-pixel"
													fill="var(--color-ink)"
												>
													{b.text}
												</text>
											</g>
										);
									})
								) : (
									<text
										x={x0 + band / 2}
										y={T + ph / 2}
										textAnchor="middle"
										fontSize={12}
										fill="var(--color-mute-2)"
									>
										not measured yet
									</text>
								)}
								<text
									x={x0 + band / 2}
									y={h - 9}
									textAnchor="middle"
									fontSize={12}
									fill="var(--color-ink)"
								>
									{g.label}
								</text>
							</g>
						);
					})}
					<path
						d={`M${L} ${T - 8}V${T + ph}H${w - R}`}
						fill="none"
						stroke="var(--color-ink)"
						strokeWidth={1.2}
					/>
				</svg>
			)}
		</div>
	);
}

const DOT = 9; // a dot's size, and the gap two dots need not to overlap
const LANE = ["yes", "no"] as const;

// Each case in its lane, yes above no; close scores stack up instead of hiding each other.
function stack(scores: Scored[], x: (score: number) => number) {
	const rows: number[][] = [];
	return [...scores]
		.sort((a, b) => a.score - b.score)
		.map((s) => {
			const at = x(s.score);
			let level = rows.findIndex((r) =>
				r.every((p) => Math.abs(p - at) >= DOT),
			);
			if (level < 0) level = rows.push([]) - 1;
			rows[level].push(at);
			return { ...s, x: at, level };
		});
}

export function Strip({
	scores,
	threshold,
	label,
}: {
	scores: Scored[];
	threshold: number;
	label: string;
}) {
	const [ref, { w }] = useBox();
	const pw = w - L - R;
	const x = (score: number) => L + pw * score;
	const lanes = LANE.map((l) =>
		stack(
			scores.filter((s) => s.label === l),
			x,
		),
	);
	const height = (dots: { level: number }[]) =>
		(Math.max(0, ...dots.map((d) => d.level)) + 1) * (DOT + 2) + 10;
	const base = [T + height(lanes[0]), T + height(lanes[0]) + height(lanes[1])];
	const axis = base[1] + 4;
	return (
		<div ref={ref} className="relative min-w-0" style={{ height: axis + 24 }}>
			{pw > 0 && (
				<svg
					width={w}
					height={axis + 24}
					role="img"
					aria-label={label}
					className="absolute inset-0 font-mono"
				>
					<line
						x1={L}
						x2={w - R}
						y1={base[0]}
						y2={base[0]}
						stroke="var(--color-line)"
					/>
					{LANE.map((l, i) => (
						<text
							key={l}
							x={L - 10}
							y={base[i] - DOT / 2 - 5}
							textAnchor="end"
							dominantBaseline="middle"
							fontSize={11}
							fill="var(--color-mute)"
						>
							{l}
						</text>
					))}
					{lanes.map((dots, i) =>
						dots.map((d) => {
							const cy = base[i] - 5 - d.level * (DOT + 2) - DOT / 2;
							const tip = `${d.id} · ${d.label} · ${num(d.score, 2)}`;
							return d.label === "yes" ? (
								<rect
									key={d.id}
									data-tip={tip}
									x={d.x - DOT / 2}
									y={cy - DOT / 2}
									width={DOT}
									height={DOT}
									fill="var(--color-held-strong)"
								/>
							) : (
								<circle
									key={d.id}
									data-tip={tip}
									cx={d.x}
									cy={cy}
									r={DOT / 2 - 0.8}
									fill="var(--color-surface)"
									stroke="var(--color-ok-strong)"
									strokeWidth={1.6}
								/>
							);
						}),
					)}
					<line
						x1={x(threshold)}
						x2={x(threshold)}
						y1={T - 8}
						y2={axis}
						stroke="var(--color-ink)"
						strokeDasharray="4 3"
					/>
					<text
						x={x(threshold) + 5}
						y={T - 12}
						fontSize={11}
						fill="var(--color-ink)"
						dominantBaseline="middle"
					>
						threshold {threshold.toLocaleString("en-US")}
					</text>
					<line
						x1={L}
						x2={w - R}
						y1={axis}
						y2={axis}
						stroke="var(--color-ink)"
						strokeWidth={1.2}
					/>
					{TICKS.map((t) => (
						<text
							key={t}
							x={x(t)}
							y={axis + 15}
							textAnchor="middle"
							fontSize={11}
							fill="var(--color-mute)"
						>
							{t.toLocaleString("en-US")}
						</text>
					))}
				</svg>
			)}
		</div>
	);
}
