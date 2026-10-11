import { useLayoutEffect, useRef } from "react";
import { useLive } from "@/api/live";
import type { Run, Step } from "@/api/types";
import {
	Check,
	FileText,
	KeySquare,
	MessageSquare,
	Terminal,
	TriangleAlert,
	UserRound,
} from "@/components/icons";
import { LEGS, STATUS, shown } from "@/lib/labels";
import { revealRow, scrollToEnd } from "@/lib/motion";
import {
	band,
	callText,
	carried,
	fmt,
	originText,
	RAMP,
	type Row,
	reportLabel,
} from "./run";
import { StatusChip } from "./ui";

// The statuses whose reason the row shows: Cressey acted on the call.
const REASONED = new Set<Step["status"]>([
	"held",
	"denied",
	"would_hold",
	"alerted",
]);

// The design's held-call chips: salmon, outlined by an inset line.
const CHIP_HELD =
	"inline-flex h-[18px] flex-none items-center gap-1 whitespace-nowrap bg-held px-[5px] font-mono text-[10.5px] text-held-fg shadow-[inset_0_0_0_1px_var(--color-held-bd)]";

export function Trace({
	run,
	rows,
	sel,
	onSelect,
	onHover,
	onFresh,
	className,
}: {
	run?: Run;
	rows: Row[];
	sel: string | null;
	onSelect: (id: string) => void;
	onHover: (id: string | null) => void;
	onFresh: (added: Row[]) => void; // rows that arrived since the last render
	className: string;
}) {
	const box = useRef<HTMLDivElement>(null);
	const seen = useRef<Set<string> | null>(null);
	// Each new row slides in and the trace glides to it; the rows already there on mount
	// just show, scrolled to the latest.
	useLayoutEffect(() => {
		const el = box.current;
		if (!el) return;
		if (!seen.current) {
			seen.current = new Set(rows.map((r) => r.id));
			el.scrollTop = el.scrollHeight;
			return;
		}
		const known = seen.current;
		const fresh = rows.filter((r) => !known.has(r.id));
		if (!fresh.length) return;
		for (const r of fresh) {
			known.add(r.id);
			const row = el.querySelector(`[data-row="${r.id}"]`);
			if (row) revealRow(row);
		}
		scrollToEnd(el);
		onFresh(fresh);
	});
	return (
		<section data-anim aria-label="Trace" className={`panel ${className}`}>
			<div className="panel-head">
				<span>TRACE</span>
				<span className="opacity-70">{rows.length || ""}</span>
				<div className="flex-1" />
				<span
					data-tip="Scores per call: Pressure · Opportunity · Rationalization (calls only)"
					// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
					tabIndex={0}
					className="font-mono text-[11px] tracking-normal opacity-80"
				>
					P O R
				</span>
			</div>
			<div ref={box} className="min-h-0 flex-1 overflow-auto">
				{rows.length === 0 && (
					<div className="flex h-full flex-col items-center justify-center gap-2.5 p-6 text-center">
						<span className="inline-flex size-10 items-center justify-center border-[1.2px] border-ink">
							<Terminal size={20} />
						</span>
						<span className="font-medium text-[15px]">No calls yet</span>
						<span className="max-w-[230px] text-[13px] text-mute-2 leading-[1.45]">
							Every call, thought and report lands here; calls are scored on the
							three legs.
						</span>
					</div>
				)}
				{rows.map((row) => (
					<button
						key={row.id}
						data-row={row.id}
						type="button"
						aria-pressed={sel === row.id}
						onClick={() => onSelect(row.id)}
						onMouseEnter={() => onHover(row.id)}
						onMouseLeave={() => onHover(null)}
						className={`fade grid w-full cursor-pointer grid-cols-[30px_minmax(0,1fr)_auto] items-start gap-2.5 border-line border-b px-[18px] py-3.5 text-left -outline-offset-2 hover:bg-paper active:bg-[#ededeb] ${sel === row.id ? "bg-paper shadow-[inset_0_0_0_1.5px_var(--color-ink)]" : "bg-surface"}`}
					>
						{row.kind === "call" ? (
							run && <CallRow run={run} step={row.step} />
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
	const secrets = carried(step);
	const status = shown(step);
	const Why = STATUS[step.status].Icon;
	return (
		<>
			<span className="pt-px">
				<span className="font-pixel text-[21px] leading-none">#{step.n}</span>
			</span>
			<span className="flex min-w-0 flex-col gap-[3px]">
				{/* Wraps only when the chips don't fit: the design's row runs under the cells. */}
				<span className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1">
					<span className="truncate font-medium font-mono text-[12.5px]">
						{step.tool}
					</span>
					{secrets.length > 0 && (
						<span
							data-tip={secrets.map((fp) => originText(run, fp)).join("\n")}
							className="inline-flex flex-none text-[#b07a0c]"
						>
							<KeySquare size={13} />
						</span>
					)}
					{step.risk === "destructive" && (
						<span className={CHIP_HELD}>destructive</span>
					)}
					<span className="flex-1" />
					{status === "allowed" ? (
						<span
							data-tip={STATUS.allowed.tip}
							className="inline-flex flex-none text-ok-strong"
						>
							<Check size={14} />
						</span>
					) : (
						<StatusChip status={status} />
					)}
				</span>
				<span className="truncate font-mono text-[11.5px] text-mute leading-[1.4]">
					{callText(run, step)}
				</span>
				{step.reason && REASONED.has(step.status) && (
					<span className="mt-0.5 flex items-center gap-[5px] font-medium text-[12.5px] text-held-fg leading-[1.35]">
						<Why size={12} strokeWidth={2.5} />
						{step.reason}
					</span>
				)}
			</span>
			<Legs step={step} />
		</>
	);
}

function TextRow({
	run,
	row,
}: {
	run?: Run;
	row: Exclude<Row, { kind: "call" }>;
}) {
	const { focusMode } = useLive();
	const report = row.kind === "report";
	const you = row.kind === "msg" && row.role === "user";
	const check = report ? run?.report_check : undefined;
	const Icon = report ? FileText : you ? UserRound : MessageSquare;
	return (
		<>
			<span className="pt-px">
				<span className="inline-flex size-[22px] items-center justify-center border border-ink">
					<Icon size={13} />
				</span>
			</span>
			<span className="flex min-w-0 flex-col gap-[3px]">
				<span className="flex min-w-0 items-center gap-1.5">
					<span className="truncate font-medium font-mono text-[12.5px]">
						{report ? reportLabel(run) : you ? "You" : "Thought"}
					</span>
					{!focusMode && (
						<span
							data-tip={
								you
									? "Your prompt to Claude Code: shown, never scored as the agent's"
									: "Agent text: untrusted, shown as plain text"
							}
							className="whitespace-nowrap font-mono text-[10.5px] text-mute-2"
						>
							{you ? "your prompt" : "agent text"}
						</span>
					)}
					{check?.confirmed && (
						<span
							data-tip={[
								"The final report is contradicted by the call log",
								`score ${fmt(check.score)}`,
								...check.facts,
							].join("\n")}
							className={CHIP_HELD}
						>
							<TriangleAlert size={10} />
							report contradicted by the log
						</span>
					)}
				</span>
				<span className="line-clamp-2 text-[#3a3a3a] text-[13px] leading-[1.4]">
					{row.text}
				</span>
			</span>
			<span className="flex gap-[3px] pt-px" />
		</>
	);
}

// A call's three scores as pixel cells: darker is higher, ringed in the leg's colour once
// facts confirm it at this step.
function Legs({ step }: { step: Step }) {
	const legs = step.legs;
	return (
		<span
			role="img"
			aria-label={
				legs
					? LEGS.map((g) => `${g.name} ${fmt(legs[g.k].score)}`).join(", ")
					: "no score"
			}
			className="flex gap-[3px] pt-px"
		>
			{legs &&
				LEGS.map((g) => {
					const leg = legs[g.k];
					const b = band(leg.score);
					return (
						<span
							key={g.k}
							data-cell
							data-tip={`${g.name} ${fmt(leg.score)}${leg.confirmed ? "\nconfirmed by facts at this step" : ""}`}
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
