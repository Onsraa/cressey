import { useState } from "react";
import { LEGS, STATUS } from "@/lib/labels";
import {
	at,
	CELL,
	cellRect,
	type PerLeg,
	type Pt,
	perLeg,
	type Tri,
	weights,
} from "./geometry";
import { fmt, type Scored, tipOf } from "./run";
import { Letter, useAge } from "./ui";

export type Placed = Scored & { at: Pt };

export const GLIDE_MS = 600;
const RETICLE = (5 * CELL) / 2; // half the highlight's width
const DOT = CELL / 2;

// Where each label sits around its vertex, as in the design.
const LABEL = {
	P: "translate(-50%, calc(-100% - 14px))",
	O: "translate(-30%, 16px)",
	R: "translate(-70%, 16px)",
};

// Where the marker sits, as weights that survive a resize, and the scores it shows.
type Pose = { w: PerLeg; s: PerLeg };

const CENTRE: Pose = { w: perLeg(() => 1 / 3), s: perLeg(() => 0) };
const poseOf = (c?: Scored): Pose =>
	c ? { w: weights(c.legs), s: perLeg((k) => c.legs[k].score) } : CENTRE;
const mix = (a: Pose, b: Pose, e: number): Pose => ({
	w: perLeg((k) => a.w[k] + (b.w[k] - a.w[k]) * e),
	s: perLeg((k) => a.s[k] + (b.s[k] - a.s[k]) * e),
});
const easeOut = (k: number) => 1 - (1 - k) ** 3;

// The marker on the target call with its lines to the vertices, the landed calls' points,
// and the vertex labels with the marker's scores. A new target is reached in GLIDE_MS, from
// wherever the marker was.
export function Marker({
	w,
	h,
	t,
	calls,
	target,
	last,
}: {
	w: number;
	h: number;
	t: Tri;
	calls: Placed[];
	target?: Scored;
	last?: Scored;
}) {
	const n = target?.step.n ?? 0;
	const to = poseOf(target);
	const e = easeOut(Math.min(1, useAge(n, GLIDE_MS) / GLIDE_MS));
	const [way, setWay] = useState({ n, from: to, to });
	if (way.n !== n) setWay({ n, from: mix(way.from, way.to, e), to });
	const pose = mix(way.from, to, e);
	const p = at(t, pose.w);
	// Calls that land in the same cell share one point and one tooltip.
	const points = new Map<string, Placed[]>();
	for (const c of calls) {
		const k = `${Math.floor(c.at.x / CELL)},${Math.floor(c.at.y / CELL)}`;
		points.set(k, [...(points.get(k) ?? []), c]);
	}
	const box = {
		x: Math.round(p.x - RETICLE) + 0.5,
		y: Math.round(p.y - RETICLE) + 0.5,
		width: 2 * RETICLE,
		height: 2 * RETICLE,
	};
	return (
		<>
			<svg width={w} height={h} aria-hidden="true" className="absolute inset-0">
				{target && (
					<g pointerEvents="none">
						{LEGS.map((g) => {
							const width = 1.2 + 2.6 * pose.s[g.k];
							const line = { x1: p.x, y1: p.y, x2: t[g.k].x, y2: t[g.k].y };
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
								{/* A call waiting for a human pulses slowly (index.css). */}
								{group.some((c) => c.step.status === "held") && (
									<rect
										{...cellRect(q - 1, r - 1, 3)}
										className="beacon fill-held-bd"
									/>
								)}
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
				{target && (
					<g pointerEvents="none" fill="none">
						<rect {...box} className="stroke-surface" strokeWidth={4} />
						<rect {...box} className="stroke-ink" strokeWidth={1.6} />
						<rect
							x={Math.round(p.x - DOT / 2)}
							y={Math.round(p.y - DOT / 2)}
							width={DOT}
							height={DOT}
							className={
								target.step.held_until ? "fill-held-strong" : "fill-ink"
							}
						/>
					</g>
				)}
			</svg>
			{LEGS.map((g) => {
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
						<span className="font-pixel text-[20px] leading-none">
							{fmt(pose.s[g.k])}
						</span>
					</div>
				);
			})}
		</>
	);
}
