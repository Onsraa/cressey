import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { shownRun, useLive, useRun } from "@/api/live";
import type { Run } from "@/api/types";
import { arrive, still } from "@/lib/motion";
import { Center, type CenterTab } from "./Center";
import { useDecision } from "./decide";
import type { Hover } from "./Field";
import { busy, Header, phaseOf } from "./Header";
import { Hold } from "./Hold";
import { Inspector } from "./Inspector";
import type { Scene } from "./pixels";
import { agg, type Row, rows, scored, thoughtDots } from "./run";
import { Trace } from "./Trace";

const ROOT = "@container flex flex-[1_0_auto] flex-col gap-4 px-7 pt-6 pb-7";

// The design's liveLayout: three columns, then two (the triangle spans both rows), then
// one. Its breakpoints are on the page width less the sidebar and 40 px: 1160 and 760, so
// 1144 and 744 on this box, inside its 28 px paddings. Its height grows from zero, not from
// its content: the panels scroll inside it.
const GRID =
	"grid h-0 min-h-[1584px] grow grid-cols-1 grid-rows-[400px_600px_560px] gap-4 @min-[744px]:min-h-[680px] @min-[744px]:grid-cols-[minmax(250px,310px)_minmax(0,1fr)] @min-[744px]:grid-rows-[minmax(0,1fr)_minmax(0,1fr)] @min-[1144px]:min-h-[540px] @min-[1144px]:grid-cols-[minmax(270px,330px)_minmax(0,1fr)_minmax(300px,350px)] @min-[1144px]:grid-rows-[minmax(0,1fr)]";
const AT = {
	trace: "col-start-1 row-start-1",
	center:
		"row-start-2 @min-[744px]:col-start-2 @min-[744px]:row-span-2 @min-[744px]:row-start-1 @min-[1144px]:row-span-1",
	inspector:
		"row-start-3 @min-[744px]:col-start-1 @min-[744px]:row-start-2 @min-[1144px]:col-start-3 @min-[1144px]:row-start-1",
};

// The latest live run, or the run another view linked to; before any, the same page,
// waiting for an agent.
export function LiveView() {
	const { runs, focus } = useLive();
	const run = useRun(shownRun(runs, focus)?.id);
	return <RunView key={run?.id ?? ""} run={run} />;
}

function RunView({ run }: { run?: Run }) {
	const { focus, refresh, focusMode, incidents } = useLive();
	const root = useRef<HTMLDivElement>(null);
	const all = run ? rows(run) : [];
	const calls = run ? scored(run) : [];
	const legs = agg(calls);
	const phase = phaseOf(run);
	// The call on hold, else the last one that was.
	const held =
		run?.steps.find((s) => s.status === "held") ??
		run?.steps.findLast((s) => s.held_until);
	const pending = held?.status === "held" ? held : undefined;
	// The hold is shown over the triangle, or hidden ("step") to see the triangle under it.
	const tabFor = (n?: number): "hold" | "step" | null =>
		n === undefined
			? null
			: run?.steps.find((s) => s.n === n)?.held_until
				? "hold"
				: "step";

	const [sel, setSel] = useState(focus.step ? `c${focus.step}` : null);
	const [hover, setHover] = useState<string | null>(null);
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
	const holdOpen = Boolean(held) && (tab ?? "hold") === "hold";
	const picked = all.find((r) => r.id === sel);
	const decision = useDecision(run?.id ?? "", pending?.n, refresh);

	// The design's showInsp: on a narrow page, bring the inspector (or, for the hold, the
	// triangle it sits over) into view.
	const showInspector = (top: boolean) => {
		const insp = root.current?.querySelector(
			top ? "[aria-label='Fraud triangle']" : "[aria-label=Inspector]",
		);
		const sc = root.current?.parentElement;
		if (!insp || !sc) return;
		if (top) {
			const h = insp.querySelector("[data-hold]");
			if (h?.parentElement) h.parentElement.scrollTop = 0;
		}
		const b = insp.getBoundingClientRect();
		const sb = sc.getBoundingClientRect();
		if (b.top >= sb.top && b.top + Math.min(b.height, 260) <= sb.bottom) return;
		sc.scrollTo({
			top: Math.max(0, b.top - sb.top + sc.scrollTop - 12),
			behavior: still() ? "auto" : "smooth",
		});
	};
	// A link from the hold banner lands on the hold.
	const linked = useRef(focus);
	useLayoutEffect(() => {
		if (linked.current === focus) return;
		linked.current = focus;
		if (focus.step) setTimeout(() => showInspector(true), 60);
	});

	// T switches the centre view (not in focus mode, which shows the triangle only), R
	// rejects, Shift+R opens the reason box, A approves (twice), Esc clears the selection.
	// App handles 1–4 and F.
	useEffect(() => {
		const key = (e: KeyboardEvent) => {
			const t = e.target;
			const typing =
				t instanceof HTMLInputElement ||
				t instanceof HTMLTextAreaElement ||
				(t instanceof HTMLElement && t.isContentEditable);
			if (typing || e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
			const k = e.key.toLowerCase();
			if (k === "t" && !focusMode)
				setCenter((c) => (c === "triangle" ? "time" : "triangle"));
			else if (k === "r" && pending) {
				if (e.shiftKey) {
					decision.compose(true, pending.draft);
					setTab(null); // the hold
				} else decision.reject();
			} else if (k === "a" && pending) decision.approve();
			else if (k === "escape") setSel(null);
			else return;
			if (k !== "escape") e.preventDefault();
		};
		window.addEventListener("keydown", key);
		return () => window.removeEventListener("keydown", key);
	});

	const id = (n: number) => `c${n}`;
	const scene: Scene = {
		calls: calls.map(({ step, legs: l }) => ({
			id: id(step.n),
			legs: {
				p: l.pressure.score,
				o: l.opportunity.score,
				r: l.rationalization.score,
			},
			hold: Boolean(step.held_until),
			at: step.n,
		})),
		thoughts: (run ? thoughtDots(run) : []).map((d) => ({ ...d, hold: false })),
		confirmed: {
			p: legs.pressure.confirmed,
			o: legs.opportunity.confirmed,
			r: legs.rationalization.confirmed,
		},
		held: Boolean(pending),
		holdId: held && id(held.n),
		pin: hover ?? sel ?? undefined,
	};
	const hovered = calls.find((c) => id(c.step.n) === hover);
	const tip: Hover | undefined = hovered && {
		n: hovered.step.n,
		tool: hovered.step.tool,
		legs: {
			p: hovered.legs.pressure.score,
			o: hovered.legs.opportunity.score,
			r: hovered.legs.rationalization.score,
		},
	};
	// A call held as it arrives slides the hold pane in, as the banner comes down.
	const fresh = (added: Row[]) => {
		if (added.some((r) => r.kind === "call" && r.step.status === "held"))
			arrive(
				root.current?.querySelector("[data-hold]") ?? null,
				{ x: 20 },
				0.4,
			);
	};

	return (
		<div ref={root} data-slot="live" className={ROOT}>
			<Header run={run} phase={phase} />
			<div className={GRID}>
				<Trace
					run={run}
					rows={all}
					sel={sel}
					onSelect={(r) => {
						setSel(sel === r ? null : r);
						if (sel !== r) showInspector(false);
					}}
					onHover={setHover}
					onFresh={fresh}
					className={AT.trace}
				/>
				<Center
					run={run}
					phase={phase}
					calls={calls}
					agg={legs}
					scene={scene}
					hover={tip}
					tab={center}
					setTab={setCenter}
					hold={
						run &&
						held && {
							open: holdOpen,
							pending: Boolean(pending),
							onToggle: () => setTab(holdOpen ? "step" : "hold"),
							pane: (
								<Hold
									run={run}
									step={held}
									incident={incidents.find(
										(i) => i.run_id === run.id && i.step === held.n,
									)}
									decision={decision}
								/>
							),
						}
					}
					className={AT.center}
				/>
				<Inspector
					run={run}
					row={picked ?? all.at(-1)}
					pinned={Boolean(picked)}
					watching={busy(phase)}
					className={AT.inspector}
				/>
			</div>
		</div>
	);
}
