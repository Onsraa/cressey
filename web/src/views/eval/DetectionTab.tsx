import { X } from "lucide-react";
import type { EvalFile } from "@/api/types";
import { Bars, type Group } from "./charts";
import { ms, sample, share } from "./format";
import type { Detection, Session } from "./read";
import { Aside, Head, Split, type Tile, Tiles } from "./ui";

// Why a session missed: an incident let through, or a normal task held.
const why = (s: Session) =>
	s.expect === "held"
		? "Should have been held: it wasn't."
		: `Held by mistake at step ${s.held_at}${s.reason ? `: ${s.reason}` : ""}`;

export function DetectionTab({ file, d }: { file: EvalFile; d: Detection }) {
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
			reading: "to watch, lower is better",
			watch: true,
		},
		{
			label: "Time to stop · p50 / p95",
			value: `${ms(d.stop_ms_p50)} / ${ms(d.stop_ms_p95)} ms`,
			sub: `${sample(d.incident_held)} sessions held`,
			reading: "good, lower is better",
		},
		{
			label: "Cressey's decision per call · p50 / p95",
			value: `${ms(d.check_ms_p50)} / ${ms(d.check_ms_p95)} ms`,
			sub: `every call in ${d.incident_sessions + d.normal_sessions} sessions`,
			reading: "good, lower is better",
		},
	];
	const held = (k: number, n: number) => `${k}/${n}`;
	const groups: Group[] = [
		{
			label: file.split,
			bars: [
				{
					key: "incident",
					value: share(d.incident_held, d.incident_sessions),
					text: held(d.incident_held, d.incident_sessions),
					tip: `Incident sessions held: ${d.incident_held} / ${d.incident_sessions}`,
					fill: "var(--color-ink)",
				},
				{
					key: "normal",
					value: share(d.normal_held, d.normal_sessions),
					text: held(d.normal_held, d.normal_sessions),
					tip: `Normal sessions held by mistake: ${d.normal_held} / ${d.normal_sessions}`,
					hatch: true,
				},
			],
		},
	];
	if (file.split !== "held-out") groups.push({ label: "held-out", bars: null });

	return (
		<>
			<Tiles file={file} tiles={tiles} />
			<div className="rise grid min-h-[300px] flex-1 grid-cols-[repeat(auto-fit,minmax(320px,1fr))] gap-4">
				<section className="panel min-h-[300px]">
					<Head>
						<span>SESSIONS HELD</span>
						<div className="flex-1" />
						<Aside>
							<span className="size-3 bg-ink" />
							incident
						</Aside>
						<Aside>
							<span className="size-3 border-[1.2px] border-ink [background-image:repeating-linear-gradient(-45deg,var(--color-ink)_0_1px,transparent_1px_4px)]" />
							normal
						</Aside>
					</Head>
					<Bars
						groups={groups}
						percent
						label="Sessions held by split, incident against normal"
					/>
				</section>
				<section className="panel">
					<Head>
						<X size={14} className="text-held-strong" />
						<span>MISSES</span>
						<Aside>{d.misses.length}</Aside>
					</Head>
					{d.misses.length === 0 && (
						<p className="px-[18px] py-3.5 text-[13px] text-mute">No misses</p>
					)}
					{d.misses.map((id) => {
						const s = d.sessions.find((x) => x.session === id);
						return (
							<div
								key={id}
								className="flex flex-col gap-1 border-line border-b px-[18px] py-3.5"
							>
								<span className="flex items-center gap-1.5 font-mono text-[11px]">
									<Split split={file.split} />
									{id}
								</span>
								{s && (
									<span className="text-[13px] leading-[1.4]">{why(s)}</span>
								)}
							</div>
						);
					})}
				</section>
			</div>
		</>
	);
}
