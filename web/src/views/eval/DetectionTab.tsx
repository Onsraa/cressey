import type { EvalFile } from "@/api/types";
import { Check, X } from "@/components/icons";
import { ms, sample } from "@/lib/format";
import { HeldChart } from "./charts";
import type { Detection, Session } from "./read";
import { Aside, Miss, Panel, type Tile, Tiles } from "./ui";

// Why a session missed: an incident let through or held at the wrong call, or a normal
// task held.
const why = (s: Session) =>
	s.expect === "held"
		? s.held_at === null
			? "Should have been held: it wasn't."
			: `Held at step ${s.held_at}, expected step ${s.expected_at}`
		: `Held by mistake at step ${s.held_at}${s.reason ? `: ${s.reason}` : ""}`;

export function DetectionTab({ file, d }: { file: EvalFile; d: Detection }) {
	// A time needs to say whether the model answered live or from recordings.
	const measured = d.mode === "live" ? "live Jev" : "recorded answers";
	const tiles: Tile[] = [
		{
			label: "Incident sessions held",
			value: `${d.incident_held} / ${d.incident_sessions}`,
			sub: `${sample(d.incident_sessions)} sessions`,
			reading: "good, higher is better",
		},
		{
			label: "Normal sessions held by mistake",
			value: `${d.normal_held} / ${d.normal_sessions}`,
			sub: `${sample(d.normal_sessions)} sessions`,
			reading: "watch, lower is better",
			watch: true,
		},
		{
			label: "Time to stop · p50 / p95",
			value: `${ms(d.stop_ms_p50)} / ${ms(d.stop_ms_p95)} ms`,
			sub: `${sample(d.incident_held)} held sessions · ${measured}`,
			reading: "good, lower is better",
		},
		{
			label: "Decision per call · p50 / p95",
			value: `${ms(d.check_ms_p50)} / ${ms(d.check_ms_p95)} ms`,
			sub: `Cressey’s decision per call · ${measured}`,
			reading: "good, lower is better",
		},
	];
	return (
		<>
			<Tiles file={file} tiles={tiles} />
			<div
				data-anim
				className="grid min-h-[300px] flex-1 grid-cols-[repeat(auto-fit,minmax(320px,1fr))] gap-4"
			>
				<Panel
					className="min-h-[300px]"
					head={
						<>
							<span>HELD SESSIONS</span>
							<div className="flex-1" />
							<Aside>
								<span className="size-3 bg-ink" />
								<span className="text-ink">incidents</span>
							</Aside>
							<Aside>
								<span className="size-3 border-[1.2px] border-ink [background-image:repeating-linear-gradient(-45deg,var(--color-ink)_0_1px,transparent_1px_4px)]" />
								<span className="text-ink">normal</span>
							</Aside>
						</>
					}
				>
					<HeldChart
						incidents={[d.incident_held, d.incident_sessions]}
						normal={[d.normal_held, d.normal_sessions]}
						split={file.split}
					/>
				</Panel>
				<Panel
					head={
						<>
							<span className="inline-flex text-[#c33a22]">
								<X size={14} />
							</span>
							<span>MISSES</span>
							<Aside>{d.misses.length}</Aside>
						</>
					}
				>
					{d.misses.map((id) => {
						const s = d.sessions.find((x) => x.session === id);
						return (
							<Miss key={id} split={file.split} id={id}>
								{s && why(s)}
							</Miss>
						);
					})}
					{d.misses.length === 0 && (
						<div className="flex items-center gap-2 p-[18px] text-[13px] text-ok-fg">
							<Check size={15} />
							no misses
						</div>
					)}
				</Panel>
			</div>
		</>
	);
}
