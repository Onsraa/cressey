import {
	ArrowDownWideNarrow,
	ArrowRight,
	Eye,
	SquareCheck,
} from "lucide-react";
import { useLive } from "@/api/live";
import type { Incident } from "@/api/types";
import { LIFE, stage } from "@/lib/incident";
import { SEVERITY, TONE, time } from "@/lib/labels";
import { Tip } from "./ui";
import { acted, OBSERVER_TIP } from "./util";

export function Queue({ selected }: { selected?: string }) {
	const { incidents, runs, go } = useLive();
	const control = new Set(
		runs.filter((r) => r.kind === "control").map((r) => r.id),
	);
	return (
		<section aria-label="Incident queue" className="panel rise">
			<div className="panel-head">
				<span>INCIDENTS</span>
				<span className="opacity-70">{incidents.length}</span>
				<div className="flex-1" />
				<Tip
					tip="One incident per root cause, sorted by severity, then by time"
					className="inline-flex"
				>
					<ArrowDownWideNarrow size={14} />
				</Tip>
			</div>
			<div className="min-h-0 flex-1 overflow-auto">
				{incidents.map((i) => (
					<Item
						key={i.id}
						incident={i}
						on={i.id === selected}
						observer={control.has(i.run_id)}
						pick={() => go("inc", { incident: i.id })}
					/>
				))}
				{!incidents.length && (
					<div className="flex flex-col gap-2 p-5 text-[13px] text-mute">
						<span>
							The live run's incident shows up here at its first hold.
						</span>
						<button
							type="button"
							onClick={() => go("live")}
							className="btn gap-1.5 self-start text-[13px]"
						>
							Go to live run
							<ArrowRight size={14} />
						</button>
					</div>
				)}
			</div>
		</section>
	);
}

function Item({
	incident: i,
	on,
	observer,
	pick,
}: {
	incident: Incident;
	on: boolean;
	observer: boolean;
	pick: () => void;
}) {
	const st = stage(i);
	const sev = SEVERITY[i.severity];
	return (
		<button
			type="button"
			onClick={pick}
			aria-current={on}
			className={`flex w-full flex-col gap-[7px] border-line border-b px-[18px] py-4 text-left -outline-offset-2 transition-colors hover:bg-paper active:bg-line ${on ? "bg-paper shadow-[inset_0_0_0_1.5px_var(--color-ink)]" : "bg-surface"}`}
		>
			<span className="flex items-center gap-1.5">
				<span
					className={`inline-flex h-5 items-center gap-1 border px-1.5 font-mono text-[11px] ${TONE[sev.tone]}`}
				>
					<sev.Icon size={11} />
					{sev.label}
				</span>
				<span className="font-medium font-mono text-xs">{i.id}</span>
				{acted(i) && (
					<span
						data-tip="The action took place: what it revealed is still real"
						className="inline-flex"
					>
						<SquareCheck size={13} aria-label="action approved" />
					</span>
				)}
				<span className="flex-1" />
				<span className="font-mono text-[11px] text-mute-2">
					{time(i.created_at)}
				</span>
			</span>
			<span className="text-pretty font-medium text-sm leading-[1.3]">
				{i.reason}
			</span>
			<span className="flex items-center gap-2">
				<span aria-hidden="true" className="flex gap-0.5">
					{LIFE.map((label, k) => (
						<span
							key={label}
							className={`size-2.5 border ${k <= st ? "border-ok-strong bg-ok-strong" : "border-line-2 bg-surface"}`}
						/>
					))}
				</span>
				<span className="font-mono text-[11px]">{LIFE[st]}</span>
				<span className="flex-1" />
				{observer && (
					<span
						data-tip={OBSERVER_TIP}
						className={`inline-flex h-5 items-center gap-1 border px-1.5 font-mono text-[11px] ${TONE.info}`}
					>
						<Eye size={11} />
						Observer
					</span>
				)}
			</span>
		</button>
	);
}
