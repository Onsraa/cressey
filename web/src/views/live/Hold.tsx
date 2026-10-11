import { useLayoutEffect, useRef } from "react";
import { useLive } from "@/api/live";
import type { Incident, Run, Step, StepStatus } from "@/api/types";
import { ArrowRight, Check, DoorOpen, Lock, X } from "@/components/icons";
import { clock, LEGS, SEVERITY, STATUS, TONE, time } from "@/lib/labels";
import { animIn } from "@/lib/motion";
import type { Decision } from "./decide";
import { callText } from "./run";
import { Code, Labeled } from "./ui";

// The decided hold: its title and what it means, as the design's OUT map.
const OUTCOME: Partial<Record<StepStatus, { title: string; text: string }>> = {
	approved: {
		title: "Approved",
		text: "The call went through. The incident stays open, marked “action approved”.",
	},
	rejected: {
		title: "Rejected",
		text: "The call did not go through. The run key stays suspended.",
	},
	expired: {
		title: "Expired",
		text: "Safely cancelled: the call did not go through.",
	},
};

const CELLS = 40; // the countdown bar

const keyState = (run: Run) =>
	run.revoked ? "suspended" : run.read_only_step ? "read-only" : "active";

// The held call: the countdown and the decision while it waits, then the outcome.
export function Hold({
	run,
	step,
	incident,
	decision,
}: {
	run: Run;
	step: Step;
	incident?: Incident;
	decision: Decision;
}) {
	const { now, go } = useLive();
	const box = useRef<HTMLDivElement>(null);
	const pending = step.status === "held";
	const out = OUTCOME[step.status];
	const st = STATUS[step.status];
	const sev = incident && SEVERITY[incident.severity];
	const state = keyState(run);
	// Once decided, the pane's blocks rise in again (the design's decide).
	const was = useRef(pending);
	useLayoutEffect(() => {
		if (was.current === pending) return;
		was.current = pending;
		if (!pending) animIn(box.current, ":scope > *");
	});
	return (
		<div ref={box} data-hold data-pane className="flex flex-col gap-[18px] p-5">
			<div className="flex flex-wrap items-center gap-2">
				<span
					className={`inline-flex h-6 items-center gap-[5px] border-[1.2px] px-2 font-medium font-mono text-xs ${pending ? "border-held-bd bg-held text-ink" : TONE[st.tone]}`}
				>
					<st.Icon size={13} />
					{out?.title ?? st.label}
				</span>
				{sev && (
					<span
						data-tip="Severity is set by code: a safety-floor hit is always critical."
						// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
						tabIndex={0}
						className={`inline-flex h-6 items-center border px-2 font-mono text-xs ${TONE[sev.tone]}`}
					>
						{sev.label}
					</span>
				)}
				<span className="font-medium font-mono text-[12.5px]">
					#{step.n} {step.tool}
				</span>
			</div>
			{pending ? (
				<>
					<Countdown step={step} incident={incident} now={now} />
					<div className="flex flex-col gap-2">
						<button
							type="button"
							onClick={decision.reject}
							disabled={decision.busy}
							className="btn btn-dark h-12 gap-2.5 font-semibold text-base"
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
							data-tip="Needs a second click. No model can approve a call."
							className={`btn h-9 ${decision.armed ? "btn-dark" : ""}`}
						>
							<Check size={15} />
							{decision.armed ? "Confirm approval" : "Approve…"}
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
						<st.Icon size={18} />
						<div className="flex flex-col gap-0.5">
							<span className="font-semibold text-[15px]">
								{out?.title ?? st.label} at {time(step.decided_at)}
							</span>
							<span className="text-[13px] leading-[1.4]">
								{out?.text ?? st.tip}
							</span>
						</div>
					</div>
					{incident && (
						<button
							type="button"
							onClick={() => go("inc", { incident: incident.id })}
							className="btn h-8 gap-1.5 self-start px-3 text-[13px]"
						>
							Open incident {incident.id}
							<ArrowRight size={14} />
						</button>
					)}
				</>
			)}
			<Labeled label="attempted">
				<Code>{callText(run, step)}</Code>
			</Labeled>
			<div className="flex flex-col gap-[7px]">
				<span className="label">why it was held</span>
				{step.reason && (
					<span className="text-pretty font-medium text-sm leading-[1.4]">
						{step.reason}
					</span>
				)}
				<div className="flex flex-wrap gap-1">
					{LEGS.map((g) => {
						const on = Boolean(step.legs?.[g.k].confirmed);
						return (
							<span
								key={g.k}
								data-tip={`${g.name} ${on ? "confirmed by facts" : "not confirmed"}`}
								className={`inline-flex h-[22px] items-center gap-[5px] border px-[7px] font-mono text-[11px] transition-[background-color,border-color,color] duration-300 ${TONE[on ? "warn" : "grey"]}`}
							>
								<span
									className="font-pixel text-[17px] leading-none"
									style={{ color: g.color }}
								>
									{g.L}
								</span>
								{on ? "confirmed" : "not confirmed"}
							</span>
						);
					})}
				</div>
			</div>
			<div className="flex flex-col border-line border-t">
				<span
					data-tip={
						state === "suspended"
							? "Suspended automatically when the call was held"
							: `Run key: ${state}`
					}
					// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
					tabIndex={0}
					className="flex min-h-[34px] items-center gap-2 border-line border-b text-[13px]"
				>
					<span className="inline-flex text-[#c33a22]">
						<Lock size={14} />
					</span>
					Run key {state}
					<span className="ml-auto font-mono text-[11px] text-mute-2">
						{time(incident?.created_at)}
					</span>
				</span>
				{run.way_out_step ? (
					<span
						data-tip={
							"Sent automatically when pressure was confirmed:\n“Declaring the task impossible is an accepted answer.”"
						}
						// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
						tabIndex={0}
						className="flex min-h-[34px] items-center gap-2 border-line border-b text-[13px]"
					>
						<span className="inline-flex text-info-fg">
							<DoorOpen size={14} />
						</span>
						Way out sent to the agent
						<span className="ml-auto font-mono text-[11px] text-mute-2">
							step {run.way_out_step}
						</span>
					</span>
				) : null}
			</div>
		</div>
	);
}

// The safe cancel: the time left, and a bar of 40 cells draining from when the call was held.
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
	// The hold began as its incident opened: the whole wait runs from there to the cancel.
	const whole = incident ? until - Date.parse(incident.created_at) : 0;
	const on = whole > 0 ? Math.ceil((left / whole) * CELLS) : CELLS;
	return (
		<div className="flex flex-col gap-1.5">
			<span
				data-tip="With no decision, the call is safely cancelled."
				// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
				tabIndex={0}
				className="label self-start"
			>
				safe cancel in{whole > 0 && ` · ${Math.round(whole / 1000)} s`}
			</span>
			<span className="font-pixel text-[72px] leading-[0.82] tracking-[0.02em]">
				{clock(step.held_until, now)}
			</span>
			<div
				aria-hidden="true"
				className="grid gap-px"
				style={{ gridTemplateColumns: `repeat(${CELLS}, minmax(0, 1fr))` }}
			>
				{Array.from({ length: CELLS }, (_, i) => (
					<span
						// biome-ignore lint/suspicious/noArrayIndexKey: a cell is its position
						key={i}
						className={`h-2 transition-[background-color] duration-[350ms] ${i < on ? "bg-ink" : "bg-line"}`}
					/>
				))}
			</div>
		</div>
	);
}
