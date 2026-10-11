import type { Run } from "@/api/types";
import { Check, Eye, TriangleAlert } from "@/components/icons";
import { KIND, STATUS, shown, TONE } from "@/lib/labels";
import { Tip } from "./ui";
import { secretNames, shortArgs } from "./util";

// The same task run without Cressey: what the agent reported, next to what the log recorded.
export function Observer({ run }: { run: Run }) {
	const names = secretNames(run);
	const check = run.report_check;
	return (
		<div data-anim className="flex flex-col gap-4">
			<div className="flex flex-wrap items-center gap-2 font-mono text-xs">
				<span
					className={`inline-flex h-[22px] items-center border px-[7px] ${TONE.info}`}
				>
					{KIND[run.kind]}
				</span>
				<span>{run.id}</span>
				<Tip
					tip="Same task without Cressey: every call is logged, nothing is held."
					className="inline-flex cursor-help items-center gap-1 text-mute"
				>
					<Eye size={12} />
					observer mode
				</Tip>
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
						// A call Cressey would have held ran here: the lie in the report.
						const bad = s.status === "would_hold";
						return (
							<div
								key={s.n}
								className="grid grid-cols-[34px_minmax(0,1fr)] items-baseline gap-2 border-line border-b py-[7px]"
							>
								<span className="font-pixel text-[22px] leading-none">
									#{s.n}
								</span>
								<div className="flex min-w-0 flex-col gap-[3px]">
									<code className="wrap-anywhere font-mono text-xs">
										{args ? `${s.tool} · ${args}` : s.tool}
									</code>
									<span
										className={`inline-flex items-center gap-[5px] text-[13px] ${bad ? "font-semibold" : ""}`}
									>
										<span
											className={`inline-flex ${bad ? "text-[#c33a22]" : "text-ok-strong"}`}
										>
											{bad ? <TriangleAlert size={13} /> : <Check size={13} />}
										</span>
										{STATUS[shown(s)].label}
									</span>
								</div>
							</div>
						);
					})}
				</div>
			</div>
			{check?.confirmed && (
				<div className="flex flex-col gap-2 self-start border border-held-bd bg-held px-3.5 py-3 text-held-fg">
					<span className="inline-flex items-center gap-[7px] font-semibold text-sm">
						<TriangleAlert size={15} />
						report contradicted by the log · score {check.score.toFixed(2)}
					</span>
					{check.facts.map((f) => (
						<span
							key={f}
							className="grid grid-cols-[8px_minmax(0,1fr)] items-baseline gap-2 text-[13px] leading-[1.4]"
						>
							<span className="size-1.5 bg-held-fg" />
							{f}
						</span>
					))}
				</div>
			)}
		</div>
	);
}
