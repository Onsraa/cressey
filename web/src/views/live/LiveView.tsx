import { useEffect, useState } from "react";
import { latestLive, useLive } from "@/api/live";
import type { Run } from "@/api/types";
import { Center, type CenterTab } from "./Center";
import { useDecision } from "./decide";
import { Header } from "./Header";
import { Inspector, type InspectorTab } from "./Inspector";
import { rows } from "./run";
import { Trace } from "./Trace";
import { Waiting } from "./Waiting";

const ROOT = "@container flex flex-[1_0_auto] flex-col gap-4 px-7 pt-6 pb-7";

// The design's live.cols: three columns, then two (the triangle spans both rows), then one.
// Its height grows from zero, not from its content: the panels scroll inside it.
const GRID =
	"grid h-0 min-h-[1584px] grow grid-cols-1 grid-rows-[400px_600px_560px] gap-4 @min-[760px]:min-h-[680px] @min-[760px]:grid-cols-[minmax(250px,310px)_minmax(0,1fr)] @min-[760px]:grid-rows-[minmax(0,1fr)_minmax(0,1fr)] @min-[1160px]:min-h-[540px] @min-[1160px]:grid-cols-[minmax(270px,330px)_minmax(0,1fr)_minmax(300px,350px)] @min-[1160px]:grid-rows-[minmax(0,1fr)]";
const AT = {
	trace: "col-start-1 row-start-1",
	center:
		"row-start-2 @min-[760px]:col-start-2 @min-[760px]:row-span-2 @min-[760px]:row-start-1 @min-[1160px]:row-span-1",
	inspector:
		"row-start-3 @min-[760px]:col-start-1 @min-[760px]:row-start-2 @min-[1160px]:col-start-3 @min-[1160px]:row-start-1",
};

// The latest live run, or the run another view linked to.
export function LiveView() {
	const { runs, focus } = useLive();
	const run = focus.run
		? runs.find((r) => r.id === focus.run)
		: latestLive(runs);
	if (run) return <RunView key={run.id} run={run} />;
	return (
		<div className={ROOT}>
			<header className="rise flex flex-col gap-[7px]">
				<span className="font-mono text-mute text-xs">Live run</span>
				<h1 className="m-0 font-medium text-[22px] leading-[1.15] tracking-[-0.02em]">
					Waiting for an agent
				</h1>
			</header>
			<section aria-label="Waiting for an agent" className="panel rise flex-1">
				<div className="panel-head">
					<span>WAITING FOR AN AGENT</span>
					<span className="blink h-3.5 w-2 bg-surface" />
				</div>
				<Waiting title="No runs yet" />
			</section>
		</div>
	);
}

function RunView({ run }: { run: Run }) {
	const { focus, refresh } = useLive();
	const all = rows(run);
	// The call on hold, else the last one that was.
	const held =
		run.steps.find((s) => s.status === "held") ??
		run.steps.findLast((s) => s.held_until);
	const pending = held?.status === "held" ? held : undefined;
	const tabFor = (n?: number): InspectorTab | null =>
		n === undefined
			? null
			: run.steps.find((s) => s.n === n)?.held_until
				? "hold"
				: "step";

	const [sel, setSel] = useState(focus.step ? `c${focus.step}` : null);
	// null: the hold, kept after the decision for its outcome, until a row is picked.
	const [tab, setTab] = useState(tabFor(focus.step));
	const [center, setCenter] = useState<CenterTab>("triangle");
	// A new hold opens its tab; a link from another view selects its step.
	const [seen, setSeen] = useState({ focus, hold: pending?.n });
	if (seen.focus !== focus || seen.hold !== pending?.n) {
		setSeen({ focus, hold: pending?.n });
		if (pending && seen.hold !== pending.n) setTab(null);
		if (seen.focus !== focus && focus.step) {
			setSel(`c${focus.step}`);
			setTab(tabFor(focus.step));
		}
	}
	const shown: InspectorTab =
		held && (tab ?? "hold") === "hold" ? "hold" : "step";
	const row = all.find((r) => r.id === sel);
	const decision = useDecision(run.id, pending?.n, refresh);

	// R rejects, A approves (twice), T switches the centre view. App handles 1–4.
	useEffect(() => {
		const key = (e: KeyboardEvent) => {
			const t = e.target;
			const typing =
				t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement;
			if (typing || e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
			const k = e.key.toLowerCase();
			if (k === "t") setCenter((c) => (c === "triangle" ? "time" : "triangle"));
			else if (k === "r" && pending) decision.reject();
			else if (k === "a" && pending) decision.approve();
			else return;
			e.preventDefault();
		};
		window.addEventListener("keydown", key);
		return () => window.removeEventListener("keydown", key);
	});

	return (
		<div className={ROOT}>
			<Header run={run} />
			<div className={GRID}>
				<Trace
					run={run}
					rows={all}
					sel={sel}
					onSelect={(id) => {
						setSel(sel === id ? null : id);
						setTab("step");
					}}
					className={AT.trace}
				/>
				<Center
					run={run}
					tab={center}
					setTab={setCenter}
					focus={row?.kind === "call" ? row.step.n : undefined}
					className={AT.center}
				/>
				<Inspector
					run={run}
					held={held}
					tab={shown}
					onTab={setTab}
					row={row}
					decision={decision}
					className={AT.inspector}
				/>
			</div>
		</div>
	);
}
