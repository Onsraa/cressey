import { useLive } from "@/api/live";
import type { Incident, Run, Source } from "@/api/types";
import { ArrowRight, Search, Triangle } from "@/components/icons";
import { LEGS } from "@/lib/labels";
import { Box, Pending } from "./ui";
import { argPath, secretNames, unmask } from "./util";

const HOW: { k: Source["how"]; label: string; tip: string }[] = [
	{ k: "exact", label: "exact", tip: "Value found as is" },
	{ k: "lowercase", label: "lowercase", tip: "Value found in lowercase" },
	{ k: "base64", label: "base64", tip: "Value found base64-encoded" },
	{ k: "hex", label: "hex", tip: "Value found hex-encoded" },
	{ k: "url", label: "URL", tip: "Value found URL-encoded" },
];

export function Overview({
	incident: i,
	run,
}: {
	incident: Incident;
	run?: Run;
}) {
	const { go, focusMode } = useLive();
	const names = secretNames(run);
	return (
		<div
			data-anim
			className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] items-start gap-4"
		>
			<Box Icon={Search} title="SOURCE">
				<div className="flex flex-col divide-y divide-line">
					{i.sources.map((s) => {
						const path = argPath(s.args);
						// The secret's line in what that call returned.
						const line = run?.steps
							.find((x) => x.n === s.step)
							?.secrets.find((x) => (x.name ?? x.kind) === s.secret)?.line;
						const where = path ? `in ${path} ` : "";
						return (
							<div
								key={`${s.step}-${s.how}-${s.value}`}
								className="flex flex-col gap-4 p-5"
							>
								<span className="text-pretty font-medium text-lg leading-[1.3] tracking-[-0.01em]">
									{`${s.secret ?? unmask(s.value, names)} read ${where}at step ${s.step}`}
								</span>
								<div className="grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-3.5 gap-y-1.5 font-mono text-[12.5px]">
									{!focusMode && (
										<>
											<span className="text-[11px] text-mute-2">tool</span>
											<span>{s.tool}</span>
											{path && (
												<>
													<span className="text-[11px] text-mute-2">file</span>
													<span>{line ? `${path}, line ${line}` : path}</span>
												</>
											)}
											{!path && line !== undefined && (
												<>
													<span className="text-[11px] text-mute-2">line</span>
													<span>{line}</span>
												</>
											)}
										</>
									)}
									<span className="text-[11px] text-mute-2">match</span>
									<span className="flex flex-wrap gap-[3px]">
										{HOW.map((h) => {
											const on = h.k === s.how;
											return (
												<span
													key={h.k}
													data-tip={on ? `${h.tip} · this match` : h.tip}
													className={`inline-flex h-5 items-center border px-1.5 text-[11px] ${on ? "border-ink bg-ink text-surface" : "border-[#d6d6d3] bg-surface text-mute-3"}`}
												>
													{h.label}
												</span>
											);
										})}
									</span>
								</div>
								{run ? (
									<button
										type="button"
										onClick={() => go("live", { run: i.run_id, step: s.step })}
										className="btn btn-dark h-8 gap-1.5 self-start px-3 text-[13px]"
									>
										Go to step {s.step}
										<ArrowRight size={14} />
									</button>
								) : (
									<span className="font-mono text-[11px] text-mute-2">
										Archived run · step {s.step} is in the event log
									</span>
								)}
							</div>
						);
					})}
					{!i.sources.length &&
						(i.tracing ? (
							<div className="p-5">
								<Pending>Tracing where the values came from…</Pending>
							</div>
						) : (
							<p className="p-5 text-[13px] text-mute">
								No value in the held call comes from an earlier read.
							</p>
						))}
				</div>
			</Box>
			<Box Icon={Triangle} title="LEGS INVOLVED">
				{LEGS.map((g) => {
					const leg = i.legs[g.k];
					return (
						<div
							key={g.k}
							className="grid grid-cols-[24px_minmax(0,1fr)] gap-2.5 border-line border-b px-[18px] py-3.5"
						>
							<span
								className="inline-flex size-6 items-center justify-center border-[1.2px] font-pixel text-[19px] leading-none"
								style={
									leg.confirmed
										? {
												background: g.color,
												borderColor: g.color,
												color: "var(--color-surface)",
											}
										: {
												background: "var(--color-surface)",
												borderColor: "#d6d6d3",
												color: "var(--color-mute-3)",
											}
								}
							>
								{g.L}
							</span>
							<div className="flex min-w-0 flex-col gap-1">
								<span className="flex flex-wrap items-baseline gap-2">
									<span className="font-medium text-sm">{g.name}</span>
									<span className="font-mono text-[11px] text-mute-2">
										{leg.confirmed ? "confirmed by facts" : "not involved"}
									</span>
								</span>
								{leg.facts.map((f) => (
									<span
										key={f}
										className="grid grid-cols-[8px_minmax(0,1fr)] items-baseline gap-2 text-[12.5px] leading-[1.4]"
									>
										<span className="size-1.5 bg-ink" />
										{f}
									</span>
								))}
							</div>
						</div>
					);
				})}
			</Box>
		</div>
	);
}
