import { useCallback, useLayoutEffect, useRef, useState } from "react";
import type { LegName } from "@/api/types";
import { LEGS } from "@/lib/labels";
import { type P3, Pixels, pos, type Scene, type Tri } from "./pixels";
import { type Agg, fmt } from "./run";
import { Letter } from "./ui";

// The design keeps one field for the page: its texture and its waves outlive a page switch.
const sim = new Pixels();

// Where each label sits around its vertex.
const AT = {
	P: "translate(-50%, calc(-100% - 14px))",
	O: "translate(-30%, 16px)",
	R: "translate(-70%, 16px)",
};

export type Hover = { n: number; tool: string; legs: P3 };

// The canvas, the three vertex labels with the gauges' scores, and the hovered call's tip.
export function Field({
	run,
	scene,
	agg,
	score,
	hover,
}: {
	run: string;
	scene: Scene;
	agg: Agg;
	score: Record<LegName, number>;
	hover?: Hover;
}) {
	const [tri, setTri] = useState<Tri | null>(null);
	const latest = useRef(scene);
	const ref = useCallback(
		(cv: HTMLCanvasElement | null) => {
			if (!cv) return;
			sim.attach(cv, run, () => latest.current, setTri);
			return () => sim.detach(cv);
		},
		[run],
	);
	useLayoutEffect(() => {
		latest.current = scene;
		sim.sync();
	});
	const at = hover && tri ? pos(tri, hover.legs) : null;
	// The tip sits right of the call, or left of it near the right edge.
	const right = !at || !tri || at[0] < tri.W * 0.6;
	return (
		<>
			<canvas
				ref={ref}
				data-pane
				role="img"
				aria-label={`Fraud triangle: ${scene.calls.length} calls placed by pressure, opportunity and rationalization.`}
				className="absolute inset-0 block cursor-crosshair [image-rendering:pixelated]"
			/>
			{tri &&
				LEGS.map((g) => {
					const on = agg[g.k].confirmed;
					return (
						<div
							key={g.k}
							data-tip={`${g.name} · ${on ? "confirmed by facts" : "not confirmed"}`}
							className="absolute flex items-center gap-[7px] whitespace-nowrap border-[1.2px] border-ink bg-surface py-0.5 pr-2 pl-0.5"
							style={{
								left: Math.round(tri[g.L][0]),
								top: Math.round(tri[g.L][1]),
								transform: AT[g.L],
							}}
						>
							<Letter g={g} on={on} size={22} />
							<span className="font-medium text-[13.5px]">{g.name}</span>
							<span className="ml-0.5 font-pixel text-[22px] leading-[0.8]">
								{fmt(score[g.k])}
							</span>
						</div>
					);
				})}
			{hover && at && (
				<div
					className="pointer-events-none absolute whitespace-nowrap bg-ink px-2 py-1.5 font-mono text-[11.5px] text-surface leading-[1.4] shadow-[0_10px_24px_-10px_rgba(30,30,30,.45)]"
					style={{
						left: Math.round(at[0] + (right ? 18 : -18)),
						top: Math.round(at[1] - 10),
						transform: right
							? "translate(0, -100%)"
							: "translate(-100%, -100%)",
					}}
				>
					<div className="font-medium">
						#{hover.n} {hover.tool}
					</div>
					<div>
						P {fmt(hover.legs.p)} · O {fmt(hover.legs.o)} · R{" "}
						{fmt(hover.legs.r)}
					</div>
				</div>
			)}
		</>
	);
}
