import type { EvalFile } from "@/api/types";
import { Strip } from "./charts";
import { num, sample, signed } from "./format";
import type { Decision, JudgedSet, Latency } from "./read";
import { Aside, Head, type Tile, Tiles } from "./ui";

const CALL: Record<Latency["call"], string> = {
	label: "labels",
	judgment: "judgment",
	report: "report",
};

const usd = (v: number) =>
	v.toLocaleString("en-US", {
		style: "currency",
		currency: "USD",
		maximumFractionDigits: 3,
	});

// Accuracy at the threshold, with the margin and the calibration error.
const judged = (s: JudgedSet) => ({
	value: s.accuracy.replace("/", " / "),
	sub: `threshold ${s.threshold.toLocaleString("en-US")} · margin ${signed(s.margin, 2)} · ECE ${num(s.ece, 3)}`,
});

function SetStrip({ title, set }: { title: string; set: JudgedSet }) {
	return (
		<div className="flex min-w-0 flex-col gap-1">
			<span className="font-mono text-[11px] text-mute">
				{title} · n = {set.n}
			</span>
			<Strip
				scores={set.scores}
				threshold={set.threshold}
				label={`${title}: the score of each labelled case, yes against no, threshold ${set.threshold.toLocaleString("en-US")}`}
			/>
		</div>
	);
}

export function DecisionTab({ file, d }: { file: EvalFile; d: Decision }) {
	// The largest shift the injected text caused, with its sign.
	const shift = d.attack
		.flatMap((a) => a.deltas)
		.reduce((m, x) => (Math.abs(x) > Math.abs(m) ? x : m), 0);
	const held = d.attack.filter((a) => a.floorHeld).length;
	const p50 = d.latency.map((l) => l.p50_ms);
	const tiles: Tile[] = [
		{
			label: "Write judgment",
			...judged(d.write),
			reading: "good, higher is better",
		},
		{
			label: "Report check",
			...judged(d.report),
			reading: "to watch, higher is better",
			watch: true,
		},
		{
			label: "Under our attack",
			value: signed(shift, 2),
			sub: `largest score shift · floor held ${held} / ${d.attack.length}`,
			reading: "to watch, closer to 0 is better",
			watch: true,
		},
		{
			label: "Latency per call · p50",
			value: `${num(Math.min(...p50))}–${num(Math.max(...p50))} ms`,
			sub: `${d.latency.map((l) => `${CALL[l.call]} ${num(l.p50_ms)}`).join(" · ")} · ${sample([...new Set(d.latency.map((l) => l.n))].join(" / "))}`,
			reading: "good, lower is better",
		},
		{
			label: "Price · million input tokens",
			value: usd(d.price),
			sub: `${d.model}'s list price, not a measure`,
			reading: "good, lower is better",
			price: true,
		},
	];

	return (
		<>
			<Tiles file={file} tiles={tiles} />
			<section className="panel rise flex-none">
				<Head>
					<span>SCORES BY CASE</span>
					<Aside>{file.split} · the team's labels</Aside>
					<div className="flex-1" />
					<Aside>
						<span className="size-2.5 bg-held-strong" />
						yes: to flag
					</Aside>
					<Aside>
						<span className="size-2.5 rounded-full border-[1.6px] border-ok-strong" />
						no: to let through
					</Aside>
					<Aside>
						<span className="w-4 border-ink border-t-2 border-dashed" />
						threshold
					</Aside>
				</Head>
				<div className="grid grid-cols-[repeat(auto-fit,minmax(320px,1fr))] gap-x-8 gap-y-3 px-3.5 py-3">
					<SetStrip title="Write judgment" set={d.write} />
					<SetStrip title="Report check" set={d.report} />
				</div>
			</section>
		</>
	);
}
