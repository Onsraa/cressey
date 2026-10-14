import type { EvalFile } from "@/api/types";
import { Triangle } from "@/components/icons";
import { ms, share, signed } from "@/lib/format";
import type { Ablation } from "./read";
import { Aside, Miss, Panel, type Tile, Tiles } from "./ui";

type Cell = { value: string; score?: number }; // a score draws the pixel cells

const held = (k: number, n: number): Cell => ({
	value: `${k} / ${n}`,
	score: share(k, n),
});

const CELLS = 20;

// The design's ablation bar: 20 cells, ink up to the share.
const Cells = ({ score }: { score: number }) => (
	<span
		aria-hidden="true"
		className="grid gap-px"
		style={{ gridTemplateColumns: `repeat(${CELLS}, minmax(0, 1fr))` }}
	>
		{Array.from({ length: CELLS }, (_, i) => (
			<span
				// biome-ignore lint/suspicious/noArrayIndexKey: a cell is its position
				key={i}
				className={`h-[7px] shadow-[inset_0_0_0_1px_#c4c4c4] transition-[background-color] duration-[350ms] ${i < Math.round(score * CELLS) ? "bg-ink" : "bg-surface"}`}
			/>
		))}
	</span>
);

export function AblationTab({ file, a }: { file: EvalFile; a: Ablation }) {
	const { floor: f, both: b } = a;
	const incidents = new Set(
		b.sessions.filter((s) => s.expect === "held").map((s) => s.session),
	);
	const gained = a.only_triangle.filter((id) => incidents.has(id)).length;
	const stop =
		f.stop_ms_p50 === null || b.stop_ms_p50 === null
			? "—"
			: `${signed(b.stop_ms_p50 - f.stop_ms_p50)} ms`;
	const tiles: Tile[] = [
		{
			label: "Incidents held by the triangle alone",
			value: signed(gained),
			sub: `${f.incident_held} → ${b.incident_held} / ${b.incident_sessions}`,
			reading: "good",
		},
		{
			label: "Extra false holds",
			value: signed(b.normal_held - f.normal_held),
			sub: `${f.normal_held} → ${b.normal_held} / ${b.normal_sessions}`,
			reading: "watch, the cost of the triangle",
			watch: true,
		},
		{
			label: "Time to stop · p50",
			value: stop,
			sub: `${ms(f.stop_ms_p50)} → ${ms(b.stop_ms_p50)} ms`,
			reading: "good, lower is better",
		},
	];
	const rows: { label: string; floor: Cell; both: Cell }[] = [
		{
			label: "Incident sessions held",
			floor: held(f.incident_held, f.incident_sessions),
			both: held(b.incident_held, b.incident_sessions),
		},
		{
			label: "Normal sessions held by mistake",
			floor: held(f.normal_held, f.normal_sessions),
			both: held(b.normal_held, b.normal_sessions),
		},
		{
			label: "Time to stop · p50",
			floor: { value: `${ms(f.stop_ms_p50)} ms` },
			both: { value: `${ms(b.stop_ms_p50)} ms` },
		},
	];
	const grid = "grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]";
	// The triangle's gain always shows; sessions the floor alone held, only if any.
	const lists = [
		{
			title: "HELD BY THE TRIANGLE ALONE",
			note: "Held only when the triangle may hold, with no floor touched.",
			ids: a.only_triangle,
		},
		...(a.only_floor.length
			? [
					{
						title: "HELD BY THE FLOOR ALONE",
						note: "Held by the floor alone, but not once the triangle is added.",
						ids: a.only_floor,
					},
				]
			: []),
	];
	return (
		<>
			<Tiles file={file} tiles={tiles} />
			<div
				data-anim
				className="grid grid-cols-[repeat(auto-fit,minmax(320px,1fr))] items-start gap-4"
			>
				<div className="border-[1.2px] border-ink bg-surface shadow-[0_1px_2px_rgba(30,30,30,.04),0_12px_28px_-18px_rgba(30,30,30,.22)]">
					<div
						className={`${grid} border-ink border-b-[1.2px] font-mono text-xs`}
					>
						<span className="px-3.5 py-2.5 text-mute-2">{file.split}</span>
						<span className="border-line border-l px-3.5 py-2.5">
							floor only
						</span>
						<span className="bg-ink px-3.5 py-2.5 text-surface">
							floor + triangle
						</span>
					</div>
					{rows.map((r) => (
						<div key={r.label} className={`${grid} border-line border-b`}>
							<span className="p-5 text-[13.5px] leading-[1.35]">
								{r.label}
							</span>
							{(["floor", "both"] as const).map((k) => {
								const { value, score } = r[k];
								return (
									<div
										key={k}
										className="flex flex-col gap-[7px] border-line border-l p-5"
									>
										<span className="whitespace-nowrap font-pixel text-[34px] leading-[0.8]">
											{value}
										</span>
										{score !== undefined && <Cells score={score} />}
									</div>
								);
							})}
						</div>
					))}
				</div>
				<div className="flex flex-col gap-4">
					{lists.map((l) => (
						<Panel
							key={l.title}
							head={
								<>
									<span className="inline-flex text-[#c33a22]">
										<Triangle size={14} />
									</span>
									<span>{l.title}</span>
									<Aside>{l.ids.length}</Aside>
								</>
							}
						>
							{l.ids.map((id) => (
								<Miss key={id} split={file.split} id={id}>
									{l.note}
								</Miss>
							))}
							{l.ids.length === 0 && (
								<p className="px-[18px] py-3.5 font-mono text-mute-2 text-xs">
									none
								</p>
							)}
						</Panel>
					))}
				</div>
			</div>
		</>
	);
}
