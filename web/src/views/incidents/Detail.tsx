import { useRef, useState } from "react";
import { useLive, useRun } from "@/api/live";
import type { Incident, StepStatus } from "@/api/types";
import {
	BookOpen,
	Check,
	ChevronRight,
	Eye,
	Gavel,
	type IconType,
	LayoutDashboard,
	Minus,
	Wrench,
} from "@/components/icons";
import { LIFE, stage } from "@/lib/incident";
import { SEVERITY, STATUS, TONE, time } from "@/lib/labels";
import { animIn, useOnChange } from "@/lib/motion";
import { Fixes } from "./Fixes";
import { Guides } from "./Guides";
import { Observer } from "./Observer";
import { Overview } from "./Overview";
import { Tip } from "./ui";
import { acted, OBSERVER_TIP } from "./util";

type Tab = "overview" | "guides" | "fixes" | "observer";

const TABS: { k: Tab; label: string; Icon: IconType }[] = [
	{ k: "overview", label: "Overview", Icon: LayoutDashboard },
	{ k: "guides", label: "Guides", Icon: BookOpen },
	{ k: "fixes", label: "Fixes & replay", Icon: Wrench },
	{ k: "observer", label: "Observer run", Icon: Eye },
];

const isStatus = (s: string): s is StepStatus => Object.hasOwn(STATUS, s);
// The held call's status, named as in the step timeline.
const decision = (d: string) => (isStatus(d) ? STATUS[d].label : d);

export function Detail({ incident: i }: { incident: Incident }) {
	const { runs, focusMode } = useLive();
	const [tab, setTab] = useState<Tab>("overview");
	const body = useRef<HTMLDivElement>(null);
	const run = useRun(i.run_id);
	const task = runs.find((r) => r.id === i.run_id)?.task;
	// The same task in « Observer » mode: logged, never held.
	const control = runs
		.filter((r) => r.kind === "control" && r.task === task)
		.toSorted((a, b) => a.started_at.localeCompare(b.started_at))
		.at(-1);
	const observed = useRun(control?.id);
	const tabs = TABS.filter((t) => t.k !== "observer" || control);
	const shown = tabs.some((t) => t.k === tab) ? tab : "overview";
	// Another tab or another incident: its blocks rise in.
	useOnChange(`${i.id}:${shown}`, () => animIn(body.current, "[data-anim]"));
	const approved = i.fixes.filter((f) => f.approved).length;
	const count: Partial<Record<Tab, string>> = {
		guides: String(i.guides.length),
		fixes: `${approved}/${i.fixes.length}`,
	};
	const sev = SEVERITY[i.severity];
	const decidedAt = run?.steps.find((s) => s.n === i.step)?.decided_at;
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
								opened {time(i.created_at)}
							</span>
						</>
					)}
					<span
						className={`inline-flex h-[22px] items-center gap-1 border px-[7px] ${TONE[sev.tone]}`}
					>
						<sev.Icon size={11} />
						{sev.label}
					</span>
					<Tip
						tip="Decision on the held call"
						className="inline-flex h-[22px] items-center gap-1 border border-line-2 px-[7px]"
					>
						<Gavel size={11} />
						{i.decision === "held"
							? "awaiting decision"
							: `${decision(i.decision)} ${time(decidedAt)}`.trim()}
					</Tip>
					{run?.kind === "control" && (
						<Tip
							tip={OBSERVER_TIP}
							className={`inline-flex h-[22px] items-center gap-1 border px-[7px] ${TONE.info}`}
						>
							<Eye size={11} />
							Observer
						</Tip>
					)}
					{acted(i) && (
						<Tip
							tip="The call went through, but what it revealed (a key within reach) is still real."
							className={`inline-flex h-[22px] items-center border px-[7px] ${TONE.warn}`}
						>
							action approved
						</Tip>
					)}
				</div>
				<h2 className="m-0 text-balance font-medium text-[28px] leading-[1.05] tracking-[-0.03em]">
					{i.reason}
				</h2>
				<Lifecycle incident={i} decidedAt={decidedAt} />
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
								className={`press -mb-[1.2px] inline-flex h-9 items-center gap-[7px] whitespace-nowrap border-[1.2px] px-3.5 text-[13.5px] hover:bg-paper ${on ? "border-ink border-b-surface bg-surface font-semibold" : "border-transparent font-medium"}`}
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
			<div
				ref={body}
				role="tabpanel"
				data-slot="inctab"
				className="min-h-0 flex-1 overflow-auto p-6"
			>
				{shown === "overview" && <Overview incident={i} run={run} />}
				{shown === "guides" && <Guides incident={i} />}
				{shown === "fixes" && <Fixes incident={i} />}
				{shown === "observer" && observed && <Observer run={observed} />}
			</div>
		</>
	);
}

// Held → decided → fix approved → replay passed, each stage's detail in its tooltip.
function Lifecycle({
	incident: i,
	decidedAt,
}: {
	incident: Incident;
	decidedAt?: string | null;
}) {
	const { focusMode } = useLive();
	const st = stage(i);
	const approved = i.fixes.filter((f) => f.approved).length;
	const sub = [
		`Opened ${time(i.created_at)}`,
		i.decision === "held"
			? "Awaiting a decision"
			: `Decision: ${decision(i.decision)} ${time(decidedAt)}`.trim(),
		`${approved} / ${i.fixes.length} fixes approved`,
		i.replay
			? `${i.replay.results.filter((r) => r.expect === "held" && r.ok).length} / ${i.replay.results.filter((r) => r.expect === "held").length} variants stopped on their own`
			: "Not replayed yet",
	];
	return (
		<ol aria-label="Lifecycle" className="m-0 grid list-none grid-cols-4 p-0">
			{LIFE.map((label, k) => {
				const done = k <= st;
				const Icon = done ? Check : k === st + 1 ? ChevronRight : Minus;
				return (
					<li
						key={label}
						data-tip={focusMode ? "" : sub[k]}
						className="flex min-w-0 flex-col gap-1.5"
					>
						<span className="flex items-center">
							<span
								className={`inline-flex size-6 flex-none items-center justify-center border-[1.2px] transition-[background-color,border-color,color] duration-300 ${done ? "border-ok-strong bg-ok-strong text-surface" : "border-ink bg-surface"}`}
							>
								<Icon size={13} strokeWidth={2.25} />
							</span>
							<span
								className={`h-0 flex-1 border-t-2 transition-[border-color,opacity] duration-300 ${k < st ? "border-ok-strong" : "border-ink border-dashed"} ${k === LIFE.length - 1 ? "opacity-0" : k < st ? "" : "opacity-35"}`}
							/>
						</span>
						<span
							className={`truncate pr-2 text-[13px] first-letter:uppercase ${k === st + 1 || (k === LIFE.length - 1 && st === k) ? "font-semibold" : "font-medium"}`}
						>
							{label}
						</span>
					</li>
				);
			})}
		</ol>
	);
}
