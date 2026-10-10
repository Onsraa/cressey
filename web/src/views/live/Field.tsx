import type { LegName, Run } from "@/api/types";
import { LEGS, STATUS } from "@/lib/labels";
import { CELL, edge, heat, type Pt, place, triangle } from "./geometry";
import { RAMP, type Scored, scored, tipOf } from "./run";
import { Letter, useSize } from "./ui";

const GRID = "#efefed"; // the design's faint grid
const OPEN = "#c9c9c6"; // a side not closed yet
const RETICLE = (5 * CELL) / 2; // half the highlight's width
const DOT = CELL / 2;

// Where each label sits around its vertex, as in the design.
const LABEL = {
	P: "translate(-50%, calc(-100% - 14px))",
	O: "translate(-30%, 16px)",
	R: "translate(-70%, 16px)",
};

// The sides, each between two legs' vertices.
const SIDES: [LegName, LegName][] = [
	["pressure", "opportunity"],
	["opportunity", "rationalization"],
	["rationalization", "pressure"],
];

const cellRect = (q: number, r: number, span = 1) => ({
	x: q * CELL,
	y: r * CELL,
	width: span * CELL - 1,
	height: span * CELL - 1,
});

type Placed = Scored & { at: Pt };

// The fraud triangle, drawn again on each poll but never animated: calm, and the same with
// reduced motion.
export function Field({ run, focus }: { run: Run; focus?: number }) {
	const { ref, w, h } = useSize();
	// Each run has its own texture, the same on every poll and tab switch.
	const seed = [...run.id].reduce(
		(s, c) => (s * 31 + c.charCodeAt(0)) % 1000,
		0,
	);
	const t = triangle(w, h);
	const calls: Placed[] = scored(run).map((c) => ({
		...c,
		at: place(t, c.legs),
	}));
	const last = calls.at(-1);
	const target = calls.find((c) => c.step.n === focus) ?? last;
	const box = target && {
		x: Math.round(target.at.x - RETICLE) + 0.5,
		y: Math.round(target.at.y - RETICLE) + 0.5,
		width: 2 * RETICLE,
		height: 2 * RETICLE,
	};
	const pending = run.steps.some((s) => s.status === "held");
	const cells = heat(
		t,
		w,
		h,
		calls.map((c) => ({
			at: c.at,
			score: Math.max(...LEGS.map((g) => c.legs[g.k].score)),
			held: Boolean(c.step.held_until),
		})),
		seed,
	);
	// Calls that land in the same cell share one point and one tooltip.
	const points = new Map<string, Placed[]>();
	for (const c of calls) {
		const k = `${Math.floor(c.at.x / CELL)},${Math.floor(c.at.y / CELL)}`;
		points.set(k, [...(points.get(k) ?? []), c]);
	}
	return (
		<div
			ref={ref}
			className="absolute inset-0"
			style={{
				backgroundImage: `linear-gradient(${GRID} 1px, transparent 1px), linear-gradient(90deg, ${GRID} 1px, transparent 1px)`,
				backgroundSize: `${CELL}px ${CELL}px`,
			}}
		>
			{w > 0 && (
				<svg
					width={w}
					height={h}
					role="img"
					aria-label={`Fraud triangle: ${calls.length} calls placed by their three scores`}
					className="absolute inset-0"
				>
					<g shapeRendering="crispEdges">
						{cells.map((c) => (
							<rect
								key={`${c.q},${c.r}`}
								{...cellRect(c.q, c.r)}
								fill={c.hot ? undefined : RAMP[c.band]}
								className={c.hot ? "fill-held-bd" : undefined}
							/>
						))}
					</g>
					{SIDES.map(([a, b]) => {
						// A side closes once the latest call confirms the legs at both its ends.
						const shut = Boolean(
							last?.legs[a].confirmed && last.legs[b].confirmed,
						);
						return (
							<g
								key={`${a}-${b}`}
								shapeRendering="crispEdges"
								fill={pending || shut ? undefined : OPEN}
								className={
									pending ? "fill-held-bd" : shut ? "fill-ink" : undefined
								}
							>
								{edge(t[a], t[b], !shut && !pending).map((c) => (
									<rect key={`${c.q},${c.r}`} {...cellRect(c.q, c.r)} />
								))}
							</g>
						);
					})}
					<g shapeRendering="crispEdges" className="fill-ink">
						{LEGS.map((g) => (
							<rect
								key={g.k}
								{...cellRect(
									Math.floor(t[g.k].x / CELL) - 1,
									Math.floor(t[g.k].y / CELL) - 1,
									3,
								)}
							/>
						))}
					</g>
					{target && (
						<g pointerEvents="none">
							{LEGS.map((g) => {
								const width = 1.2 + 2.6 * target.legs[g.k].score;
								const line = {
									x1: target.at.x,
									y1: target.at.y,
									x2: t[g.k].x,
									y2: t[g.k].y,
								};
								return (
									<g key={g.k}>
										<line
											{...line}
											className="stroke-surface"
											strokeWidth={width + 3}
										/>
										<line
											{...line}
											style={{ stroke: g.color }}
											strokeWidth={width}
										/>
									</g>
								);
							})}
						</g>
					)}
					<g shapeRendering="crispEdges">
						{[...points].map(([k, group]) => {
							const [q, r] = k.split(",").map(Number);
							const held = group.some((c) => c.step.held_until);
							return (
								<g
									key={k}
									data-tip={group
										.map((c) =>
											c.step.held_until
												? `${tipOf(c)} · ${STATUS[c.step.status].label}`
												: tipOf(c),
										)
										.join("\n")}
								>
									<rect
										x={q * CELL - 1}
										y={r * CELL - 1}
										width={CELL + 1}
										height={CELL + 1}
										className="fill-surface"
									/>
									<rect
										x={q * CELL + 1}
										y={r * CELL + 1}
										width={CELL - 3}
										height={CELL - 3}
										className={held ? "fill-held-strong" : "fill-ink"}
									/>
								</g>
							);
						})}
					</g>
					{target && box && (
						<g pointerEvents="none" fill="none">
							<rect {...box} className="stroke-surface" strokeWidth={4} />
							<rect {...box} className="stroke-ink" strokeWidth={1.6} />
							<rect
								x={Math.round(target.at.x - DOT / 2)}
								y={Math.round(target.at.y - DOT / 2)}
								width={DOT}
								height={DOT}
								className={
									target.step.held_until ? "fill-held-strong" : "fill-ink"
								}
							/>
						</g>
					)}
				</svg>
			)}
			{w > 0 &&
				LEGS.map((g) => {
					const on = Boolean(last?.legs[g.k].confirmed);
					return (
						<div
							key={g.k}
							data-tip={`${g.name} · ${on ? "confirmed by the facts" : "not confirmed"}`}
							className="absolute flex items-center gap-[7px] whitespace-nowrap border-[1.2px] border-ink bg-surface py-0.5 pr-2 pl-0.5"
							style={{ left: t[g.k].x, top: t[g.k].y, transform: LABEL[g.L] }}
						>
							<Letter g={g} on={on} size={22} />
							<span className="font-medium text-[13.5px]">{g.name}</span>
						</div>
					);
				})}
		</div>
	);
}
