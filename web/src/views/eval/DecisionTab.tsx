import type { EvalFile } from "@/api/types";
import { ShieldCheck, TriangleAlert } from "@/components/icons";
import { num, sample, signed } from "@/lib/format";
import { TONE } from "@/lib/labels";
import { BandChart } from "./charts";
import type { Attack, Decision, JudgedSet, Latency } from "./read";
import { Aside, Panel, type Tile, Tiles } from "./ui";

const CALL: Record<Latency["call"], string> = {
	label: "labels",
	judgment: "judgment",
	report: "report",
};

// Accuracy at the threshold, with the margin and the calibration error.
const judged = (s: JudgedSet) => ({
	value: s.accuracy.replace("/", " / "),
	sub: `margin ${signed(s.margin, 2)} · ECE ${num(s.ece, 3)}`,
});

// The largest shift the injected text caused, with its sign.
const largest = (a: Attack) =>
	a.deltas.reduce((m, x) => (Math.abs(x) > Math.abs(m) ? x : m), 0);

export function DecisionTab({ file, d }: { file: EvalFile; d: Decision }) {
	const p50 = d.latency.map((l) => l.p50_ms);
	const tiles: Tile[] = [
		{
			label: `Write judgement at ${d.write.threshold.toLocaleString("en-US")}`,
			...judged(d.write),
			reading: "good",
		},
		{
			label: `Report check at ${d.report.threshold.toLocaleString("en-US")}`,
			...judged(d.report),
			reading: "watch",
			watch: true,
		},
		{
			label: "Latency per call · p50",
			value: `${p50.map((v) => num(v)).join(" / ")} ms`,
			sub: `${d.latency.map((l) => CALL[l.call]).join(" / ")} · ${sample([...new Set(d.latency.map((l) => l.n))].join(" / "))}`,
			reading: "good, lower is better",
		},
	];
	return (
		<>
			<Tiles file={file} tiles={tiles} />
			<div
				data-anim
				className="grid min-h-[300px] flex-1 grid-cols-[repeat(auto-fit,minmax(320px,1fr))] items-stretch gap-4"
			>
				<Panel
					className="min-h-[300px]"
					head={
						<>
							<span>DECISION BAND</span>
							<Aside>
								{file.split} · {d.write.n} writes, {d.report.n} reports
							</Aside>
							<div className="flex-1" />
							<Aside>
								<span className="size-2.5 bg-ink" />
								<span className="text-ink">harmful</span>
							</Aside>
							<Aside>
								<span className="size-2.5 border-[1.4px] border-mute-3" />
								<span className="text-ink">benign</span>
							</Aside>
						</>
					}
				>
					<BandChart write={d.write} report={d.report} />
				</Panel>
				<Panel
					head={
						<>
							<ShieldCheck size={14} />
							<span>ATTACKS</span>
							<Aside>score under injected text</Aside>
						</>
					}
				>
					{d.attack.map((a) => {
						const shift = largest(a);
						return (
							<div
								key={a.id}
								className="flex flex-col gap-[7px] border-line border-b px-[18px] py-3.5"
							>
								<span className="text-pretty text-[13px] leading-[1.35]">
									{a.id}
								</span>
								<div className="flex flex-wrap items-center gap-2.5">
									<span className="inline-flex items-baseline gap-[5px] font-mono text-[11.5px] text-mute">
										largest shift
										<span className="font-pixel text-[20px] text-ink leading-[0.8]">
											{signed(shift, 2)}
										</span>
									</span>
									<span
										aria-hidden="true"
										className="relative h-2 min-w-20 flex-1 bg-paper shadow-[inset_0_0_0_1px_#d6d6d3]"
									>
										<span
											className="absolute inset-y-0 left-0 bg-[#5c5c5a]"
											style={{
												width: `${Math.min(1, Math.abs(shift)) * 100}%`,
											}}
										/>
									</span>
									<span
										className={`inline-flex h-[22px] items-center gap-1 border px-[7px] font-mono text-[11px] ${TONE[a.floorHeld ? "ok" : "held"]}`}
									>
										{a.floorHeld ? (
											<ShieldCheck size={11} />
										) : (
											<TriangleAlert size={11} />
										)}
										{a.floorHeld ? "floor holds" : "floor moved"}
									</span>
								</div>
							</div>
						);
					})}
				</Panel>
			</div>
		</>
	);
}
