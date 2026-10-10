import {
	Check,
	CircleX,
	FileText,
	KeyRound,
	MessageSquare,
	TriangleAlert,
} from "lucide-react";
import { useEffect, useRef } from "react";
import { useLive } from "@/api/live";
import type { Legs, Run, Step } from "@/api/types";
import { LEGS, STATUS } from "@/lib/labels";
import {
	argsText,
	band,
	carried,
	fmt,
	originText,
	RAMP,
	type Row,
} from "./run";
import { AgentText, RiskChip, StatusChip } from "./ui";
import { Waiting } from "./Waiting";

// The statuses whose reason the row shows: Cressey acted on the call.
const REASONED = new Set<Step["status"]>([
	"held",
	"denied",
	"would_hold",
	"alerted",
]);

export function Trace({
	run,
	rows,
	sel,
	onSelect,
	className,
}: {
	run: Run;
	rows: Row[];
	sel: string | null;
	onSelect: (id: string) => void;
	className: string;
}) {
	const box = useRef<HTMLDivElement>(null);
	const count = rows.length;
	// Follow the run: each new row scrolls into view.
	useEffect(() => {
		const el = box.current;
		if (!el || !count) return;
		const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		el.scrollTo({ top: el.scrollHeight, behavior: still ? "auto" : "smooth" });
	}, [count]);
	return (
		<section aria-label="Trace" className={`panel rise ${className}`}>
			<div className="panel-head">
				<span>TRACE</span>
				<span className="opacity-70">{count || ""}</span>
				<div className="flex-1" />
				<span
					data-tip="Scores per step: Pressure · Opportunity · Rationalization"
					className="font-mono text-[11px] tracking-normal opacity-80"
				>
					P O R
				</span>
			</div>
			<div ref={box} className="min-h-0 flex-1 overflow-auto">
				{count === 0 && <Waiting title="No steps yet" />}
				{rows.map((row) => (
					<button
						key={row.id}
						type="button"
						aria-pressed={sel === row.id}
						onClick={() => onSelect(row.id)}
						className={`rise grid w-full grid-cols-[30px_minmax(0,1fr)_auto] items-start gap-2.5 border-line border-b px-[18px] py-3.5 text-left transition-colors hover:bg-paper ${sel === row.id ? "bg-paper shadow-[inset_0_0_0_1.5px_var(--color-ink)]" : "bg-surface"}`}
					>
						{row.kind === "call" ? (
							<CallRow run={run} step={row.step} />
						) : (
							<TextRow run={run} row={row} />
						)}
					</button>
				))}
			</div>
		</section>
	);
}

function CallRow({ run, step }: { run: Run; step: Step }) {
	const { focusMode } = useLive();
	const secrets = carried(step);
	// Focus mode keeps the one risk that tells the story: destructive.
	const risky = focusMode ? step.risk === "destructive" : step.risk !== "read";
	const args = argsText(run, step.args);
	return (
		<>
			<span className="pt-px font-pixel text-[21px] leading-none">
				#{step.n}
			</span>
			<span className="flex min-w-0 flex-col gap-[3px]">
				{/* Wraps in a narrow column, so the tool name always shows. */}
				<span className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1">
					<span className="truncate font-medium font-mono text-[12.5px]">
						{step.tool}
					</span>
					{secrets.length > 0 && (
						<span
							data-tip={secrets.map((fp) => originText(run, fp)).join("\n")}
							className="inline-flex flex-none text-warn-fg"
						>
							<KeyRound size={13} />
						</span>
					)}
					{risky && <RiskChip risk={step.risk} />}
					<span className="ml-auto inline-flex">
						{step.status === "allowed" ? (
							<span data-tip={STATUS.allowed.tip} className="text-ok-strong">
								<Check size={14} />
							</span>
						) : (
							<StatusChip status={step.status} />
						)}
					</span>
				</span>
				{args && (
					<span className="truncate font-mono text-[11.5px] text-mute leading-[1.4]">
						{args}
					</span>
				)}
				{step.reason && REASONED.has(step.status) && (
					<span className="font-medium text-[12.5px] leading-[1.4]">
						{step.reason}
					</span>
				)}
				{step.is_error && (
					<span className="inline-flex items-center gap-1 font-mono text-[11px] text-held-fg">
						<CircleX size={11} />
						failed
					</span>
				)}
			</span>
			{step.legs ? <Mini legs={step.legs} /> : <span />}
		</>
	);
}

function TextRow({
	run,
	row,
}: {
	run: Run;
	row: Exclude<Row, { kind: "call" }>;
}) {
	const { focusMode } = useLive();
	const report = row.kind === "report";
	const check = report ? run.report_check : undefined;
	const Icon = report ? FileText : MessageSquare;
	return (
		<>
			<span className="inline-flex size-[22px] items-center justify-center border border-ink">
				<Icon size={13} />
			</span>
			<span className="flex min-w-0 flex-col gap-[3px]">
				<span className="flex min-w-0 flex-wrap items-center gap-1.5">
					<span className="font-medium font-mono text-[12.5px]">
						{report ? "final report" : "message"}
					</span>
					{!focusMode && <AgentText />}
					{check?.confirmed && (
						<span
							data-tip={[`score ${fmt(check.score)}`, ...check.facts].join(
								"\n",
							)}
							className="inline-flex h-5 items-center gap-1 border border-held-bd bg-held px-1.5 font-mono text-[11px] text-held-fg"
						>
							<TriangleAlert size={11} />
							report contradicted by the log
						</span>
					)}
				</span>
				<span className="line-clamp-2 text-[13px] text-mute leading-[1.4]">
					{row.text}
				</span>
			</span>
			<span />
		</>
	);
}

// A call's three scores as pixel cells: darker is higher, ringed in the leg's colour once
// facts confirm it.
function Mini({ legs }: { legs: Legs }) {
	return (
		<span
			role="img"
			aria-label={LEGS.map((g) => `${g.name} ${fmt(legs[g.k].score)}`).join(
				", ",
			)}
			className="flex gap-[3px] pt-px"
		>
			{LEGS.map((g) => {
				const leg = legs[g.k];
				const b = band(leg.score);
				return (
					<span
						key={g.k}
						data-tip={`${g.name} ${fmt(leg.score)}${leg.confirmed ? "\nconfirmed by the facts at this step" : ""}`}
						className="inline-flex size-5 items-center justify-center font-pixel text-base leading-none"
						style={{
							background: RAMP[b],
							color: b >= 3 ? "var(--color-surface)" : "var(--color-ink)",
							boxShadow: leg.confirmed
								? `inset 0 0 0 2px ${g.color}, inset 0 0 0 3px var(--color-surface)`
								: b
									? "none"
									: `inset 0 0 0 1px ${RAMP[1]}`,
						}}
					>
						{g.L}
					</span>
				);
			})}
		</span>
	);
}
