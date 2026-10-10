import { Check, Eye, TriangleAlert, X } from "lucide-react";
import type { Leg, Run } from "@/api/types";
import { STATUS, TONE } from "@/lib/labels";
import { Tip } from "./ui";
import { secretNames, shortArgs } from "./util";

export function Observer({ run }: { run: Run }) {
	const names = secretNames(run);
	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-wrap items-center gap-2 font-mono text-xs">
				<Tip
					tip="Same task without Cressey: every call is logged, nothing is held."
					className={`chip cursor-help ${TONE.info}`}
				>
					<Eye size={12} />
					Observer mode
				</Tip>
				<span>{run.id}</span>
			</div>
			<div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
				<div className="flex flex-col gap-2.5 border-[1.2px] border-ink p-[18px]">
					<span className="label">what the agent reported · agent text</span>
					{run.report ? (
						<span className="whitespace-pre-line text-pretty font-medium text-[34px] leading-[1.05] tracking-[-0.03em]">
							“{run.report}”
						</span>
					) : (
						<span className="text-[13px] text-mute">No report yet.</span>
					)}
				</div>
				<div className="flex flex-col gap-1.5 border-[1.2px] border-ink p-[18px]">
					<span className="label">what the log recorded</span>
					{run.steps.map((s) => {
						const args = shortArgs(s.args, names);
						const look = STATUS[s.status];
						return (
							<div
								key={s.n}
								className="grid grid-cols-[34px_minmax(0,1fr)] items-baseline gap-2 border-line border-b py-[7px]"
							>
								<span className="font-pixel text-[22px] leading-none">
									#{s.n}
								</span>
								<div className="flex min-w-0 flex-col gap-[3px]">
									<code className="break-words font-mono text-xs">
										{args ? `${s.tool} · ${args}` : s.tool}
									</code>
									{s.is_error ? (
										<span className={`chip self-start ${TONE.grey}`}>
											<X size={12} />
											failed
										</span>
									) : (
										<span className={`chip self-start ${TONE[look.tone]}`}>
											<look.Icon size={12} />
											{look.label}
										</span>
									)}
								</div>
							</div>
						);
					})}
				</div>
			</div>
			<ReportCheck check={run.report_check} />
		</div>
	);
}

// The decision model's check of the report against the log (S9).
function ReportCheck({ check }: { check?: Leg | null }) {
	if (!check)
		return <span className="font-mono text-mute text-xs">no check</span>;
	return (
		<div
			className={`flex flex-col gap-1 self-start border px-3 py-1.5 ${TONE[check.confirmed ? "held" : "grey"]}`}
		>
			<span className="inline-flex items-center gap-[7px] font-medium text-sm">
				{check.confirmed ? <TriangleAlert size={15} /> : <Check size={15} />}
				{check.confirmed
					? "Report contradicted by the log"
					: "The report doesn't contradict the log"}
				<span className="font-mono text-xs">
					score {check.score.toFixed(2)}
				</span>
			</span>
			{check.facts.map((f) => (
				<span key={f} className="font-mono text-[11px]">
					{f}
				</span>
			))}
		</div>
	);
}
