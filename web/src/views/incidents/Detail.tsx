import {
	BookOpen,
	Check,
	ChevronRight,
	Eye,
	Gavel,
	LayoutDashboard,
	type LucideIcon,
	Minus,
	Wrench,
} from "lucide-react";
import { useState } from "react";
import { useLive } from "@/api/live";
import type { Incident, StepStatus } from "@/api/types";
import { LIFE, stage } from "@/lib/incident";
import { SEVERITY, STATUS, TONE, time } from "@/lib/labels";
import { Fixes } from "./Fixes";
import { Guides } from "./Guides";
import { Observer } from "./Observer";
import { Overview } from "./Overview";
import { Tip } from "./ui";
import { acted, OBSERVER_TIP } from "./util";

type Tab = "overview" | "guides" | "fixes" | "observer";

const TABS: { k: Tab; label: string; Icon: LucideIcon }[] = [
	{ k: "overview", label: "Overview", Icon: LayoutDashboard },
	{ k: "guides", label: "Guides", Icon: BookOpen },
	{ k: "fixes", label: "Fixes & replay", Icon: Wrench },
	{ k: "observer", label: "Observer", Icon: Eye },
];

const isStatus = (s: string): s is StepStatus => Object.hasOwn(STATUS, s);
// The held call's status, named as in the step timeline.
const decision = (d: string) => (isStatus(d) ? STATUS[d].label : d);

export function Detail({ incident: i }: { incident: Incident }) {
	const { runs, focusMode } = useLive();
	const [tab, setTab] = useState<Tab>("overview");
	const run = runs.find((r) => r.id === i.run_id);
	// The same task in “Observer” mode: logged, never held.
	const control = runs
		.filter((r) => r.kind === "control" && r.task === run?.task)
		.toSorted((a, b) => a.started_at.localeCompare(b.started_at))
		.at(-1);
	const tabs = TABS.filter((t) => t.k !== "observer" || control);
	const shown = tabs.some((t) => t.k === tab) ? tab : "overview";
	const approved = i.fixes.filter((f) => f.approved).length;
	const count: Partial<Record<Tab, string>> = {
		guides: String(i.guides.length),
		fixes: `${approved}/${i.fixes.length}`,
	};
	const sev = SEVERITY[i.severity];
	return (
		<>
			<div className="flex flex-none flex-col gap-4 px-6 pt-[22px]">
				<div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
					<span className="font-medium">{i.id}</span>
					{!focusMode && (
						<>
							<span className="text-mute-3">·</span>
							<span className="text-mute">{i.run_id}</span>
							<span className="text-mute-3">·</span>
							<span className="mr-1.5 text-mute">
								opened at {time(i.created_at)}
							</span>
						</>
					)}
					<span className={`chip ${TONE[sev.tone]}`}>
						<sev.Icon size={11} />
						{sev.label}
					</span>
					{!focusMode && (
						<Tip tip="Decision on the held call" className="chip">
							<Gavel size={11} />
							{i.decision === "held"
								? "awaiting a decision"
								: decision(i.decision)}
						</Tip>
					)}
					{run?.kind === "control" && (
						<Tip tip={OBSERVER_TIP} className={`chip ${TONE.info}`}>
							<Eye size={11} />
							Observer
						</Tip>
					)}
					{acted(i) && (
						<Tip
							tip="The action took place: what it revealed is still real"
							className={`chip ${TONE.warn}`}
						>
							action approved
						</Tip>
					)}
				</div>
				<h2 className="text-balance font-medium text-[28px] leading-[1.05] tracking-[-0.03em]">
					{i.reason}
				</h2>
				<Lifecycle incident={i} />
				<div
					role="tablist"
					aria-label="Incident sections"
					className="-mx-6 flex flex-wrap border-ink border-b-[1.2px] px-6"
				>
					{tabs.map(({ k, label, Icon }) => {
						const on = k === shown;
						return (
							<button
								key={k}
								type="button"
								role="tab"
								aria-selected={on}
								onClick={() => setTab(k)}
								className={`-mb-[1.2px] inline-flex h-9 items-center gap-[7px] whitespace-nowrap border-[1.2px] px-3.5 text-[13.5px] transition-colors active:scale-[.985] ${on ? "border-ink border-b-surface bg-surface font-semibold" : "border-transparent font-medium hover:bg-paper"}`}
							>
								<Icon size={14} />
								{label}
								{count[k] && (
									<span className="font-mono text-[11px] text-mute-2">
										{count[k]}
									</span>
								)}
							</button>
						);
					})}
				</div>
			</div>
			<div role="tabpanel" className="min-h-0 flex-1 overflow-auto p-6">
				<div key={`${i.id}-${shown}`} className="rise">
					{shown === "overview" && <Overview incident={i} run={run} />}
					{shown === "guides" && <Guides incident={i} />}
					{shown === "fixes" && <Fixes incident={i} />}
					{shown === "observer" && control && <Observer run={control} />}
				</div>
			</div>
		</>
	);
}

function Lifecycle({ incident: i }: { incident: Incident }) {
	const { focusMode } = useLive();
	const st = stage(i);
	const approved = i.fixes.filter((f) => f.approved).length;
	const sub = [
		`Opened at ${time(i.created_at)}`,
		i.decision === "held"
			? "Awaiting a decision"
			: `Decision: ${decision(i.decision)}`,
		i.fixes.length
			? `${approved} of ${i.fixes.length} fixes approved`
			: "no fixes proposed",
		i.replay
			? i.replay.passed
				? "replay passed"
				: "replay failed"
			: "not replayed yet",
	];
	return (
		<ol aria-label="Lifecycle" className="grid grid-cols-4">
			{LIFE.map((label, k) => {
				const done = k <= st;
				const Icon = done ? Check : k === st + 1 ? ChevronRight : Minus;
				return (
					<li key={label} className="flex min-w-0 flex-col gap-1.5">
						<span className="flex items-center">
							<span
								className={`inline-flex size-6 flex-none items-center justify-center border-[1.2px] transition-colors duration-300 ${done ? "border-ok-strong bg-ok-strong text-surface" : "border-ink bg-surface"}`}
							>
								<Icon size={13} strokeWidth={2.25} />
							</span>
							{k < LIFE.length - 1 && (
								<span
									className={`h-0 flex-1 border-t-2 ${k < st ? "border-ok-strong" : "border-ink border-dashed opacity-35"}`}
								/>
							)}
						</span>
						<span
							className={`truncate pr-2 text-[13px] ${k === st + 1 || (done && k === LIFE.length - 1) ? "font-semibold" : "font-medium"}`}
						>
							{label}
						</span>
						{!focusMode && (
							<span className="truncate pr-2 font-mono text-[11px] text-mute-2">
								{sub[k]}
							</span>
						)}
					</li>
				);
			})}
		</ol>
	);
}
