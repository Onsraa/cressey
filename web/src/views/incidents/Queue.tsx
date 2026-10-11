import { latestLive, useLive } from "@/api/live";
import type { Incident } from "@/api/types";
import {
	ArrowDownWideNarrow,
	ArrowRight,
	Eye,
	SquareCheck,
} from "@/components/icons";
import { LIFE, stage } from "@/lib/incident";
import { SEVERITY, TONE, time } from "@/lib/labels";
import { Tip } from "./ui";
import { acted, OBSERVER_TIP } from "./util";

export function Queue({ selected }: { selected?: string }) {
	const { incidents, runs, go } = useLive();
	const control = new Set(
		runs.filter((r) => r.kind === "control").map((r) => r.id),
	);
	// The live run's incident shows here at its first hold: until then, say so.
	const live = latestLive(runs);
	const current = incidents.some((i) => i.run_id === live?.id);
	return (
		<section data-anim aria-label="Incident queue" className="panel">
			<div className="panel-head">
				<span>INCIDENTS</span>
				<span className="opacity-70">{incidents.length}</span>
				<div className="flex-1" />
				<Tip
					tip="One incident per root cause, sorted by severity, then time"
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
				{!current && (
					<div className="flex flex-col gap-2 p-5 text-[13px] text-mute leading-[1.45]">
						<span>The live run’s incident appears here at its first hold.</span>
						<button
							type="button"
							onClick={() => go("live")}
							className="btn h-[34px] gap-1.5 self-start text-[13px]"
						>
							Go to the live run
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
	const { focusMode } = useLive();
	const st = stage(i);
	const sev = SEVERITY[i.severity];
	return (
		<button
			type="button"
			onClick={pick}
			aria-current={on || undefined}
			className={`fade flex w-full flex-col items-stretch gap-[7px] border-line border-b px-[18px] py-4 text-left -outline-offset-2 hover:bg-paper active:bg-[#e9e9e7] ${on ? "bg-paper shadow-[inset_0_0_0_1.5px_var(--color-ink)]" : "bg-surface"}`}
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
						data-tip="Action let through: what it revealed is still real"
						role="img"
						aria-label="action approved"
						className="inline-flex"
					>
						<SquareCheck size={13} />
					</span>
				)}
				<span className="flex-1" />
				{!focusMode && (
					<span className="font-mono text-[11px] text-mute-2">
						{time(i.created_at)}
					</span>
				)}
			</span>
			<span className="text-pretty font-medium text-sm leading-[1.3]">
				{i.reason}
			</span>
			<span className="flex items-center gap-2">
				{!focusMode && (
					<span aria-hidden="true" className="flex gap-0.5">
						{LIFE.map((label, k) => (
							<span
								key={label}
								className={`size-2.5 border ${k <= st ? "border-ok-strong bg-ok-strong" : "border-ink bg-surface"}`}
							/>
						))}
					</span>
				)}
				<span className="font-mono text-[11px]">{LIFE[st]}</span>
				{observer && (
					<span
						data-tip={OBSERVER_TIP}
						className={`ml-auto inline-flex h-5 items-center gap-1 border px-1.5 font-mono text-[11px] ${TONE.info}`}
					>
						<Eye size={11} />
						Observer
					</span>
				)}
			</span>
		</button>
	);
}
