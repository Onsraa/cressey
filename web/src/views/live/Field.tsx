import { useEffect, useState } from "react";
import type { LegName, Run } from "@/api/types";
import { LEGS } from "@/lib/labels";
import {
	CELL,
	cellRect,
	edge,
	heat,
	type Pt,
	place,
	pulse,
	triangle,
} from "./geometry";
import { GLIDE_MS, Marker, type Placed } from "./Marker";
import { RAMP, scored } from "./run";
import { useAge, useSize } from "./ui";

const GRID = "#efefed"; // the design's faint grid
const OPEN = "#c9c9c6"; // a side not closed yet
const PULSE_MS = 1000;
// A landing pulse's ramps, palest first: amber for a call, salmon for a held one.
const WARM = ["#f3dfa6", "#ebc97f", "#e2b65c", "#d9a640"];
const HELD = ["#ffd6ce", "#f1a79a", "#e27865", "#b8331c"];

// The sides, each between two legs' vertices.
const SIDES: [LegName, LegName][] = [
	["pressure", "opportunity"],
	["opportunity", "rationalization"],
	["rationalization", "pressure"],
];

// The fraud triangle. A call scored since the last poll glides in (Marker) and lands
// GLIDE_MS later: its heat and its point appear then, with a pulse.
export function Field({ run, focus }: { run: Run; focus?: number }) {
	const { ref, w, h } = useSize();
	// Each run has its own texture, the same on every poll and tab switch.
	const seed = [...run.id].reduce(
		(s, c) => (s * 31 + c.charCodeAt(0)) % 1000,
		0,
	);
	const t = triangle(w, h);
	const all = scored(run);
	const landed = useLanded(all.at(-1)?.step.n ?? 0);
	const calls: Placed[] = all
		.filter((c) => c.step.n <= landed)
		.map((c) => ({ ...c, at: place(t, c.legs) }));
	const last = calls.at(-1);
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
				<>
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
						<Pulse
							n={landed}
							at={last?.at}
							held={Boolean(last?.step.held_until)}
						/>
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
					</svg>
					<Marker
						w={w}
						h={h}
						t={t}
						calls={calls}
						target={all.find((c) => c.step.n === focus) ?? all.at(-1)}
						last={last}
					/>
				</>
			)}
		</div>
	);
}

// The latest call that has landed. One scored since the last poll lands GLIDE_MS later, as
// the marker reaches it; at once with reduced motion.
function useLanded(n: number) {
	const [landed, setLanded] = useState(n);
	useEffect(() => {
		if (landed === n) return;
		const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		const id = setTimeout(() => setLanded(n), still ? 0 : GLIDE_MS);
		return () => clearTimeout(id);
	}, [landed, n]);
	return landed;
}

// A ring of heat leaves the call that landed last and cools away, in about a second.
function Pulse({ n, at, held }: { n: number; at?: Pt; held: boolean }) {
	const age = useAge(n, PULSE_MS);
	if (!at || age >= PULSE_MS) return null;
	const ramp = held ? HELD : WARM;
	return (
		<g shapeRendering="crispEdges">
			{pulse(at, age / PULSE_MS).map((c) => (
				<rect
					key={`${c.q},${c.r}`}
					{...cellRect(c.q, c.r)}
					fill={ramp[c.band]}
				/>
			))}
		</g>
	);
}
