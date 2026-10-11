import { useRef } from "react";
import { useLive } from "@/api/live";
import type { Incident, Leg, Run, Step } from "@/api/types";
import {
	Check,
	Eye,
	type IconType,
	KeySquare,
	List,
	MousePointerClick,
	Pause,
} from "@/components/icons";
import { LEGS, SHADOW_TIP, shown, TONE, VIA } from "@/lib/labels";
import { animIn, useOnChange } from "@/lib/motion";
import { type Decision, useUnlock } from "./decide";
import { Hold } from "./Hold";
import {
	callText,
	carried,
	fmt,
	originText,
	type Row,
	reportLabel,
	shadowOf,
	turnEvidence,
} from "./run";
import {
	Bar,
	Code,
	Labeled,
	type LegLook,
	Letter,
	RiskChip,
	ShadowChip,
	StatusChip,
} from "./ui";

export type InspectorTab = "hold" | "step";

const ms = (v: number) => `${v < 10 ? v.toFixed(1) : Math.round(v)} ms`;

export function Inspector({
	run,
	held,
	incident,
	tab,
	onTab,
	row,
	pinned,
	watching,
	decision,
	className,
}: {
	run?: Run;
	held?: Step; // the call on hold, else the last one that was
	incident?: Incident;
	tab: InspectorTab;
	onTab: (t: InspectorTab) => void;
	row?: Row; // the selected row, else the latest
	pinned: boolean; // the row was selected, not just the latest
	watching: boolean; // the run is going: the watching dot blinks
	decision: Decision;
	className: string;
}) {
	const { focusMode } = useLive();
	const box = useRef<HTMLElement>(null);
	// Focus mode has no STEP tab: the hold, or a quiet line.
	const hold = run && held && (focusMode || tab === "hold") ? held : undefined;
	const pane = hold ? "hold" : focusMode ? "watch" : "step";
	useOnChange(pane, () => animIn(box.current, "[data-pane]"));
	return (
		<section
			ref={box}
			data-anim
			aria-label="Inspector"
			className={`panel ${className}`}
		>
			<div
				role="tablist"
				aria-label="Inspector"
				className="flex h-[34px] flex-none items-stretch bg-ink"
			>
				{held && (
					<Tab
						on={Boolean(hold)}
						onClick={() => onTab("hold")}
						Icon={Pause}
						label="HELD"
						dot={held.status === "held"}
					/>
				)}
				{!focusMode && (
					<Tab
						on={!hold}
						onClick={() => onTab("step")}
						Icon={List}
						label="STEP"
					/>
				)}
				{focusMode && !held && (
					<Tab on onClick={() => {}} Icon={Eye} label="WATCHING" />
				)}
			</div>
			<div className="min-h-0 flex-1 overflow-auto">
				{run?.stopped && <Stopped run={run} />}
				{run && hold ? (
					<Hold run={run} step={hold} incident={incident} decision={decision} />
				) : focusMode ? (
					<div
						data-pane
						className="flex h-full min-h-[200px] items-center justify-center p-6 text-center"
					>
						<span className="inline-flex items-center gap-[9px] text-mute-2 text-sm">
							<span
								className={`size-2 flex-none bg-ok-strong ${watching ? "blink" : ""}`}
							/>
							Cressey is watching every call.
						</span>
					</div>
				) : run && row ? (
					<div data-pane className="flex flex-col gap-[18px] p-5">
						{row.kind === "call" ? (
							<Call run={run} step={row.step} pinned={pinned} />
						) : (
							<Text run={run} row={row} pinned={pinned} />
						)}
					</div>
				) : (
					<div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2.5 p-6 text-center">
						<MousePointerClick size={22} />
						<span className="max-w-[220px] text-[13px] text-mute-2 leading-[1.45]">
							Click a call in the trace to see its arguments, secrets and
							scores.
						</span>
					</div>
				)}
			</div>
		</section>
	);
}

// Why the run stopped, from the turn that stopped it, and the way to let it go on.
function Stopped({ run }: { run: Run }) {
	const { refresh } = useLive();
	const { busy, error, unlock } = useUnlock(run.id, refresh);
	const { estimate, refused, failed, said } = turnEvidence(run);
	const calls = (steps: Step[]) => (
		<ul className="m-0 flex list-none flex-col gap-1 p-0">
			{steps.map((s) => (
				<li key={s.n} className="flex items-start gap-1.5">
					<StatusChip status={shown(s)} />
					<Code>{`#${s.n} ${callText(run, s)}`}</Code>
				</li>
			))}
		</ul>
	);
	return (
		<section
			aria-label="Why the run stopped"
			className="flex flex-col gap-3.5 border-held-bd border-b-[1.2px] bg-held p-5"
		>
			<h2 className="m-0 font-semibold text-[15px] leading-[1.3]">
				No path within the mandate so far
			</h2>
			{!run.ended_at && (
				<div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
					<button
						type="button"
						onClick={unlock}
						disabled={busy}
						className="btn btn-dark h-9 px-4"
					>
						Unlock
					</button>
					<span className="min-w-0 flex-1 text-[12.5px] leading-[1.4]">
						Gives the agent its key back and resets the count.
						{run.turn && " Your next prompt does the same."}
					</span>
				</div>
			)}
			{error && (
				<span role="alert" className="text-[12.5px] text-held-fg">
					{error}
				</span>
			)}
			{estimate !== undefined && (
				<Labeled label="estimated before the run">
					<span className="text-[13px] leading-[1.4]">
						The task can fail even when done honestly: {fmt(estimate)}
					</span>
				</Labeled>
			)}
			{refused.length > 0 && (
				<Labeled label="refused this turn">{calls(refused)}</Labeled>
			)}
			{failed.length > 0 && (
				<Labeled label="failed this turn">{calls(failed)}</Labeled>
			)}
			{said && (
				<Labeled
					label="the agent’s last words"
					tip="Untrusted: shown as plain text, never interpreted"
				>
					<p className="m-0 text-pretty text-[13px] leading-[1.4]">{said}</p>
				</Labeled>
			)}
		</section>
	);
}

function Tab({
	on,
	onClick,
	Icon,
	label,
	dot,
}: {
	on: boolean;
	onClick: () => void;
	Icon: IconType;
	label: string;
	dot?: boolean;
}) {
	return (
		<button
			type="button"
			role="tab"
			aria-selected={on}
			onClick={onClick}
			className={`press inline-flex items-center gap-[7px] border-mute border-r-[1px] px-3 font-pixel text-[19px] leading-none tracking-[0.04em] ${on ? "bg-surface text-ink" : "bg-ink text-surface"}`}
		>
			<Icon size={13} />
			{label}
			{dot && <span className="size-2 bg-[#e8553e]" />}
		</button>
	);
}

// What the pane shows first: the step pinned, or the latest one.
function Kicker({ pinned }: { pinned: boolean }) {
	return (
		<span className="label">
			{pinned ? "selected step" : "latest step · click a row to pin it"}
		</span>
	);
}

function Call({
	run,
	step,
	pinned,
}: {
	run: Run;
	step: Step;
	pinned: boolean;
}) {
	const legs = step.legs;
	const secrets = carried(step);
	const shadow = shadowOf(step);
	const timing = [
		typeof step.check_ms === "number" ? `decision ${ms(step.check_ms)}` : "",
		typeof step.scan_ms === "number" ? `secret scan ${ms(step.scan_ms)}` : "",
	]
		.filter(Boolean)
		.join(" · ");
	return (
		<>
			<div className="flex flex-col gap-2">
				<Kicker pinned={pinned} />
				<div className="flex min-w-0 items-baseline gap-2.5">
					<span className="font-pixel text-4xl leading-[0.8]">#{step.n}</span>
					<span className="truncate font-medium font-mono text-[15px]">
						{step.tool}
					</span>
				</div>
				<div className="flex flex-wrap gap-1">
					<RiskChip risk={step.risk} />
					<StatusChip status={shown(step)} tall />
					{shadow && <ShadowChip shadow={shadow} tall />}
					{run.via && (
						<span
							data-tip="How Cressey received this call"
							className="inline-flex h-[22px] items-center border border-line-2 px-[7px] font-mono text-[11px]"
						>
							{VIA[run.via]}
						</span>
					)}
				</div>
			</div>
			<Labeled label="arguments">
				<Code>{callText(run, step)}</Code>
			</Labeled>
			{step.reason && (
				<Labeled label="reason">
					<span className="text-pretty font-medium text-sm leading-[1.4]">
						{step.reason}
					</span>
				</Labeled>
			)}
			{shadow && (shadow.why.length > 0 || !shadow.words_read) && (
				<Labeled label="shadow decision" tip={SHADOW_TIP}>
					{shadow.why.map((line) => (
						<span key={line} className="text-pretty text-[13px] leading-[1.4]">
							{line}
						</span>
					))}
					{!shadow.words_read && (
						<span className="text-mute-2 text-[12.5px] leading-[1.4]">
							Some thoughts before this call were not read.
						</span>
					)}
				</Labeled>
			)}
			{secrets.length > 0 && (
				<div className="flex flex-col gap-1">
					<span className="label">secret · value never shown</span>
					{secrets.map((fp) => {
						const own = step.secrets.find((s) => s.fingerprint === fp);
						return (
							<span
								key={fp}
								className="flex items-start gap-1.5 text-[13px] leading-[1.4]"
							>
								<span className="inline-flex text-[#b07a0c]">
									<KeySquare size={14} />
								</span>
								{originText(run, fp)}
								{own && ` · ${own.kind} · line ${own.line}`}
							</span>
						);
					})}
				</div>
			)}
			{timing && <span className="label">{timing}</span>}
			{legs && (
				<div className="flex flex-col gap-0.5">
					<span className="label mb-1">scores for this call</span>
					{LEGS.map((g) => (
						<LegRow key={g.k} g={g} leg={legs[g.k]} />
					))}
				</div>
			)}
		</>
	);
}

function LegRow({ g, leg }: { g: LegLook; leg: Leg }) {
	return (
		<div className="flex flex-col gap-[5px] border-line border-t py-2">
			<div className="flex items-center gap-2">
				<Letter g={g} on={leg.confirmed} size={20} />
				<span className="font-medium text-[13px]">{g.name}</span>
				<Bar score={leg.score} n={10} h={8} className="mx-1.5 flex-1" />
				<span className="font-pixel text-[22px] leading-[0.8]">
					{fmt(leg.score)}
				</span>
			</div>
			<Facts facts={leg.facts} />
		</div>
	);
}

function Facts({ facts }: { facts: string[] }) {
	return facts.map((f) => (
		<span
			key={f}
			className="flex items-baseline gap-2 pl-7 text-[12.5px] leading-[1.4]"
		>
			<Check size={11} />
			{f}
		</span>
	));
}

function Text({
	run,
	row,
	pinned,
}: {
	run: Run;
	row: Exclude<Row, { kind: "call" }>;
	pinned: boolean;
}) {
	const check = row.kind === "report" ? run.report_check : undefined;
	const you = row.kind === "msg" && row.role === "user";
	return (
		<>
			<div className="flex flex-col gap-2">
				<Kicker pinned={pinned} />
				<div className="flex min-w-0 items-baseline gap-2.5">
					<span className="truncate font-medium font-mono text-[15px]">
						{row.kind === "report" ? reportLabel(run) : you ? "You" : "Thought"}
					</span>
				</div>
			</div>
			<div className="flex flex-col gap-1.5">
				<span
					data-tip={
						you
							? "Your prompt to Claude Code: shown, never scored as the agent's"
							: "Untrusted: shown as plain text, never interpreted"
					}
					className="label self-start"
				>
					{you ? "your prompt" : "agent text"}
				</span>
				<p className="m-0 text-pretty text-[15px] leading-normal">{row.text}</p>
			</div>
			{check && (
				<div className="flex flex-col gap-[5px] border-line border-t py-2">
					<span className="label">the report against the log</span>
					{/* Unconfirmed can also mean unchecked: the facts say which. */}
					<div className="flex items-center gap-2">
						{check.confirmed && (
							<span
								className={`inline-flex h-[22px] items-center border px-[7px] font-mono text-[11px] ${TONE.held}`}
							>
								report contradicted by the log
							</span>
						)}
						<span className="flex-1" />
						<span className="font-pixel text-[22px] leading-[0.8]">
							{fmt(check.score)}
						</span>
					</div>
					<Facts facts={check.facts} />
				</div>
			)}
		</>
	);
}
