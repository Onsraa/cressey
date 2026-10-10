import {
	Check,
	KeyRound,
	List,
	type LucideIcon,
	MousePointerClick,
	Pause,
} from "lucide-react";
import { useLive } from "@/api/live";
import type { Leg, Run, Step } from "@/api/types";
import { Cells } from "@/components/Cells";
import { LEGS, TONE } from "@/lib/labels";
import type { Decision } from "./decide";
import { Hold } from "./Hold";
import { argsText, carried, fmt, originText, type Row } from "./run";
import {
	AgentText,
	Code,
	Labeled,
	type LegLook,
	Letter,
	RiskChip,
	StatusChip,
} from "./ui";

export type InspectorTab = "hold" | "step";

const ms = (v: number) => `${v < 10 ? v.toFixed(1) : Math.round(v)} ms`;

export function Inspector({
	run,
	held,
	tab,
	onTab,
	row,
	decision,
	className,
}: {
	run: Run;
	held?: Step;
	tab: InspectorTab;
	onTab: (t: InspectorTab) => void;
	row?: Row;
	decision: Decision;
	className: string;
}) {
	const { incidents, now, go } = useLive();
	return (
		<section aria-label="Inspector" className={`panel rise ${className}`}>
			<div
				role="tablist"
				aria-label="Inspector"
				className="flex h-[34px] flex-none items-stretch bg-ink"
			>
				{held && (
					<Tab
						on={tab === "hold"}
						onClick={() => onTab("hold")}
						Icon={Pause}
						label="HOLD"
						dot={held.status === "held"}
					/>
				)}
				<Tab
					on={tab === "step"}
					onClick={() => onTab("step")}
					Icon={List}
					label="STEP"
				/>
			</div>
			<div className="min-h-0 flex-1 overflow-auto">
				{tab === "hold" && held ? (
					<Hold
						run={run}
						step={held}
						incident={incidents.find(
							(i) => i.run_id === run.id && i.step === held.n,
						)}
						now={now}
						decision={decision}
						go={go}
					/>
				) : row?.kind === "call" ? (
					<Call run={run} step={row.step} />
				) : row ? (
					<Text run={run} row={row} />
				) : (
					<div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2.5 p-6 text-center">
						<MousePointerClick size={22} />
						<span className="max-w-[220px] text-[13px] text-mute-2 leading-[1.45]">
							Select a step in the trace to see its arguments, its secrets and
							its scores.
						</span>
					</div>
				)}
			</div>
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
	Icon: LucideIcon;
	label: string;
	dot?: boolean;
}) {
	return (
		<button
			type="button"
			role="tab"
			aria-selected={on}
			onClick={onClick}
			className={`inline-flex items-center gap-[7px] border-mute border-r-[1px] px-3 font-pixel text-[19px] leading-none tracking-[0.04em] ${on ? "bg-surface text-ink" : "bg-ink text-surface"}`}
		>
			<Icon size={13} />
			{label}
			{dot && <span className="size-2 bg-held-bd" />}
		</button>
	);
}

function Call({ run, step }: { run: Run; step: Step }) {
	const legs = step.legs;
	const secrets = carried(step);
	const timing = [
		typeof step.check_ms === "number" ? `decision ${ms(step.check_ms)}` : "",
		typeof step.scan_ms === "number" ? `secret scan ${ms(step.scan_ms)}` : "",
	]
		.filter(Boolean)
		.join(" · ");
	return (
		<div className="rise flex flex-col gap-[18px] p-5">
			<div className="flex flex-col gap-2">
				<span className="label">selected step</span>
				<div className="flex min-w-0 items-baseline gap-2.5">
					<span className="font-pixel text-4xl leading-[0.8]">#{step.n}</span>
					<span className="truncate font-medium font-mono text-[15px]">
						{step.tool}
					</span>
				</div>
				<div className="flex flex-wrap gap-1">
					<RiskChip risk={step.risk} tall />
					<StatusChip status={step.status} tall />
					{step.is_error && (
						<span className={`chip text-[11px] ${TONE.held}`}>failed</span>
					)}
				</div>
			</div>
			<Labeled label="arguments">
				<Code>{argsText(run, step.args, "\n") || "no arguments"}</Code>
			</Labeled>
			{step.reason && (
				<Labeled label="reason">
					<span className="font-medium text-sm leading-[1.4]">
						{step.reason}
					</span>
				</Labeled>
			)}
			{secrets.length > 0 && (
				<Labeled label="secret · value never shown">
					{secrets.map((fp) => {
						const own = step.secrets.find((s) => s.fingerprint === fp);
						return (
							<span
								key={fp}
								className="flex items-start gap-1.5 text-[13px] leading-[1.4]"
							>
								<KeyRound size={14} className="mt-0.5 flex-none text-warn-fg" />
								{originText(run, fp)}
								{own && ` · ${own.kind} · line ${own.line}`}
							</span>
						);
					})}
				</Labeled>
			)}
			{timing && <span className="label">{timing}</span>}
			{legs && (
				<div className="flex flex-col">
					<span className="label mb-1">scores at this step</span>
					{LEGS.map((g) => (
						<LegRow key={g.k} g={g} leg={legs[g.k]} />
					))}
				</div>
			)}
		</div>
	);
}

function LegRow({ g, leg }: { g: LegLook; leg: Leg }) {
	return (
		<div className="flex flex-col gap-[5px] border-line border-t py-2">
			<div className="flex items-center gap-2">
				<Letter g={g} on={leg.confirmed} size={20} />
				<span className="min-w-0 flex-1 truncate font-medium text-[13px]">
					{g.name}
				</span>
				<Cells score={leg.score} color={g.color} n={10} size={7} />
				<span className="w-10 text-right font-pixel text-[22px] leading-[0.8]">
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
			<Check size={11} className="flex-none" />
			{f}
		</span>
	));
}

function Text({ run, row }: { run: Run; row: Exclude<Row, { kind: "call" }> }) {
	const check = row.kind === "report" ? run.report_check : undefined;
	return (
		<div className="rise flex flex-col gap-[18px] p-5">
			<div className="flex flex-col gap-2">
				<span className="label">selected step</span>
				<span className="font-medium font-mono text-[15px]">
					{row.kind === "report" ? "final report" : "message"}
				</span>
			</div>
			<div className="flex flex-col items-start gap-1.5">
				<AgentText />
				<p className="m-0 text-pretty text-[15px] leading-normal">{row.text}</p>
			</div>
			{check && (
				<div className="flex flex-col gap-[5px] border-line border-t py-2">
					<span className="label">the report against the log</span>
					{/* Unconfirmed can also mean unchecked: the facts say which. */}
					<div className="flex items-center gap-2">
						{check.confirmed && (
							<span className={`chip text-[11px] ${TONE.held}`}>
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
		</div>
	);
}
