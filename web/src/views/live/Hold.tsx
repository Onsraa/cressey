import { ArrowRight, Check, DoorOpen, KeyRound, Lock, X } from "lucide-react";
import type { Focus, View } from "@/api/live";
import type { Incident, Run, Step } from "@/api/types";
import { LEGS, SEVERITY, STATUS, TONE, time } from "@/lib/labels";
import type { Decision } from "./decide";
import { argsText } from "./run";
import { Code, FitCells, Labeled } from "./ui";

// The held call: the countdown and the decision while it waits, then the outcome.
export function Hold({
	run,
	step,
	incident,
	now,
	decision,
	go,
	focusMode,
}: {
	run: Run;
	step: Step;
	incident?: Incident;
	now: number;
	decision: Decision;
	go: (view: View, focus?: Focus) => void;
	focusMode: boolean; // the decision and its why, nothing else
}) {
	const st = STATUS[step.status];
	const sev = incident && SEVERITY[incident.severity];
	return (
		<div className="rise flex flex-col gap-[18px] p-5">
			<div className="flex flex-wrap items-center gap-2">
				<span
					className={`inline-flex h-6 items-center gap-[5px] border-[1.2px] px-2 font-medium font-mono text-xs ${TONE[st.tone]}`}
				>
					<st.Icon size={13} />
					{st.label}
				</span>
				{sev && (
					<span
						data-tip="Severity set by code: safety floor or trap key, critical; two legs confirmed, high."
						className={`chip h-6 px-2 ${TONE[sev.tone]}`}
					>
						<sev.Icon size={12} />
						{sev.label}
					</span>
				)}
				{!focusMode && (
					<span className="font-medium font-mono text-[12.5px]">
						#{step.n} {step.tool}
					</span>
				)}
			</div>
			{step.status === "held" ? (
				<>
					<Countdown step={step} incident={incident} now={now} />
					<div className="flex flex-col gap-2">
						<button
							type="button"
							onClick={decision.reject}
							disabled={decision.busy}
							className="btn btn-dark h-12 font-semibold text-base"
						>
							<X size={18} strokeWidth={2.5} />
							Reject
							<span className="font-mono font-normal text-[11px] opacity-70">
								R
							</span>
						</button>
						<button
							type="button"
							onClick={decision.approve}
							disabled={decision.busy}
							data-tip="No model can approve a call."
							className={`btn h-9 ${decision.armed ? "btn-dark" : ""}`}
						>
							<Check size={15} />
							{decision.armed ? "Confirm approval" : "Approve"}
							<span className="font-mono text-[11px] opacity-70">A</span>
						</button>
						{decision.error && (
							<span role="alert" className="text-[12.5px] text-held-fg">
								{decision.error}
							</span>
						)}
					</div>
				</>
			) : (
				<>
					<div
						className={`flex items-start gap-2.5 border-[1.2px] p-3 ${TONE[st.tone]}`}
					>
						<st.Icon size={18} className="flex-none" />
						<div className="flex flex-col gap-0.5">
							<span className="block font-semibold text-[15px] first-letter:uppercase">
								{st.label} at {time(step.decided_at)}
							</span>
							<span className="text-[13px] leading-[1.4]">{st.tip}</span>
						</div>
					</div>
					{incident && (
						<button
							type="button"
							onClick={() => go("inc", { incident: incident.id })}
							className="btn h-8 self-start px-3 text-[13px]"
						>
							Open incident
							<ArrowRight size={14} />
						</button>
					)}
				</>
			)}
			{!focusMode && (
				<Labeled label="attempted">
					<Code>{argsText(run, step.args, "\n") || "no arguments"}</Code>
				</Labeled>
			)}
			<div className="flex flex-col gap-[7px]">
				<span className="label">why it is held</span>
				{step.reason && (
					<span className="text-pretty font-medium text-sm leading-[1.4]">
						{step.reason}
					</span>
				)}
				<div className="flex flex-wrap gap-1">
					{LEGS.filter((g) => step.legs?.[g.k].confirmed).map((g) => (
						<span
							key={g.k}
							data-tip={`${g.name}: confirmed by the facts`}
							className={`chip text-[11px] ${TONE.warn}`}
						>
							<span
								className="font-pixel text-[17px] leading-none"
								style={{ color: g.color }}
							>
								{g.L}
							</span>
							confirmed
						</span>
					))}
				</div>
			</div>
			{!focusMode && (
				<div className="flex flex-col border-line border-t text-[13px]">
					<span
						data-tip={
							run.revoked
								? "Suspended as soon as the call was held: the run's next calls are refused."
								: "Run key active"
						}
						className="flex min-h-[34px] items-center gap-2 border-line border-b"
					>
						{run.revoked ? (
							<Lock size={14} className="text-held-strong" />
						) : (
							<KeyRound size={14} className="text-ok-strong" />
						)}
						Run key {run.revoked ? "suspended" : "active"}
					</span>
					{run.way_out_step ? (
						<span
							data-tip="Sent with the result of the call that confirmed the pressure, without a human."
							className="flex min-h-[34px] items-center gap-2 border-line border-b"
						>
							<DoorOpen size={14} className="text-info-fg" />
							Way out sent to the agent
							<span className="label ml-auto">step {run.way_out_step}</span>
						</span>
					) : null}
				</div>
			)}
		</div>
	);
}

function Countdown({
	step,
	incident,
	now,
}: {
	step: Step;
	incident?: Incident;
	now: number;
}) {
	const until = step.held_until ? Date.parse(step.held_until) : now;
	const left = Math.max(0, until - now);
	const s = Math.round(left / 1000);
	// The hold began as its incident opened: the bar drains from there to the safe cancel.
	const whole = incident ? until - Date.parse(incident.created_at) : 0;
	return (
		<div className="flex flex-col gap-1.5">
			<span
				data-tip="Without a decision, the call is safely cancelled."
				className="label self-start"
			>
				safe cancel in
			</span>
			<span className="font-pixel text-[72px] leading-[0.82] tracking-[0.02em]">
				{Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}
			</span>
			{whole > 0 && (
				<FitCells score={left / whole} color="var(--color-ink)" n={20} />
			)}
		</div>
	);
}
