import { type ReactNode, useRef } from "react";
import { useLive } from "@/api/live";
import type { CaseEvent, LegName, Run } from "@/api/types";
import {
	Check,
	ChevronUp,
	DoorOpen,
	type IconType,
	Info,
	KeySquare,
	Lock,
	Minus,
	Pause,
	Triangle,
	X,
} from "@/components/icons";
import { INDICATOR, LEGS, TONE } from "@/lib/labels";
import { animIn, useGlide, useOnChange } from "@/lib/motion";
import { Chart } from "./Chart";
import { Field, type Hover } from "./Field";
import type { Phase } from "./Header";
import type { Scene } from "./pixels";
import { type Agg, fmt, type Scored } from "./run";
import { Bar, type LegLook, Letter } from "./ui";
import { Waiting } from "./Waiting";

export type CenterTab = "triangle" | "time";

const TABS: { k: CenterTab; label: string; tip: string }[] = [
	{ k: "triangle", label: "Triangle", tip: "Where each step lands (T)" },
	{ k: "time", label: "Across steps", tip: "Leg scores step by step (T)" },
];

const STATUS: Record<Phase, string> = {
	waiting: "idle",
	offline: "idle",
	prompt: "idle",
	thinking: "live scoring",
	writing: "live scoring",
	tool: "live scoring",
	running: "live scoring",
	held: "triangle closed · call held",
	stopped: "run stopped",
	ended: "run ended",
};

const LEGEND = [
	"How to read",
	"Each call (ink square) and each thought (coloured pixel) lands where its three scores pull it, further out when stronger.",
	"A thought takes its strongest leg's colour; grey = every score low.",
	"The marker follows the latest call; its three lines show its scores.",
	"Darker grey heat = higher score (0.30 to 0.78+).",
	"Salmon = the held call.",
	"Hover a trace row to locate it. Click the field for a pulse.",
].join("\n");

const SIDES: [LegName, LegName][] = [
	["pressure", "opportunity"],
	["opportunity", "rationalization"],
	["rationalization", "pressure"],
];

type Auto = { Icon: IconType; t: string; tip: string };

// What Cressey did on its own, by leg: the way out and the read-only key on pressure, a
// decoy key in use on opportunity.
function autos(run: Run | undefined, g: LegLook): Auto[] {
	if (!run) return [];
	const trap = run.steps.find((s) =>
		s.reasons.some((r) => r.check === "trap_key"),
	);
	if (g.k === "pressure")
		return [
			...(run.way_out_step
				? [
						{
							Icon: DoorOpen,
							t: `Way out sent to the agent · step ${run.way_out_step}`,
							tip: `Sent to the agent at step ${run.way_out_step}, no human involved`,
						},
					]
				: []),
			...(run.way_out_prompt
				? [
						{
							Icon: DoorOpen,
							t: `Way out sent with your prompt · before step ${run.way_out_prompt}`,
							tip: "Added to your first prompt once the agent had ended a turn, whatever you typed",
						},
					]
				: []),
			...(run.read_only_step
				? [
						{
							Icon: Lock,
							t: `Key switched to read-only · step ${run.read_only_step}`,
							tip: `Run key switched to read-only at step ${run.read_only_step}, no human involved`,
						},
					]
				: []),
		];
	if (g.k === "opportunity" && trap)
		return [
			{
				Icon: KeySquare,
				t: `Decoy key used · step ${trap.n}`,
				tip: `${trap.reason} (step ${trap.n})`,
			},
		];
	return [];
}

// The event the case serves as a leg's evidence: what its gauge quotes.
function evidence(run: Run | undefined, k: LegName): CaseEvent | undefined {
	const i = run?.case?.evidence[k];
	return i === undefined ? undefined : run?.case?.events[i];
}

export function Center({
	run,
	phase,
	calls,
	agg,
	scene,
	hover,
	tab,
	setTab,
	hold,
	className,
}: {
	run?: Run;
	phase: Phase;
	calls: Scored[];
	agg: Agg;
	scene: Scene;
	hover?: Hover;
	tab: CenterTab;
	setTab: (t: CenterTab) => void;
	// The call on hold, else the last one that was: shown over the triangle, or hidden.
	hold?: {
		open: boolean;
		pending: boolean;
		onToggle: () => void;
		pane: ReactNode;
	};
	className: string;
}) {
	const { focusMode } = useLive();
	const box = useRef<HTMLElement>(null);
	// Focus mode shows the triangle only.
	const shown = focusMode ? "triangle" : tab;
	useOnChange(shown, () => animIn(box.current, "[data-pane]"));
	const glide = useGlide(
		agg.pressure.score,
		agg.opportunity.score,
		agg.rationalization.score,
	);
	const score: Record<LegName, number> = {
		pressure: glide.p,
		opportunity: glide.o,
		rationalization: glide.r,
	};
	const closed = SIDES.filter(
		([a, b]) => agg[a].confirmed && agg[b].confirmed,
	).length;
	return (
		<section
			ref={box}
			data-anim
			aria-label="Fraud triangle"
			className={`panel relative ${className}`}
		>
			<div className="panel-head pr-1.5">
				<span className="min-w-0 flex-[0_1_auto] truncate">FRAUD TRIANGLE</span>
				<span className="min-w-0 truncate font-mono text-[11.5px] tracking-normal opacity-75">
					{STATUS[phase]}
				</span>
				<div className="flex-1" />
				<span
					data-tip={`${closed} of 3 sides closed\nA side closes when both its legs are confirmed by facts.`}
					// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
					tabIndex={0}
					className="inline-flex flex-none items-center gap-[5px] font-mono text-[11px] tracking-normal opacity-85"
				>
					<Triangle size={11} />
					{closed}/3
				</span>
				{hold && (
					<button
						type="button"
						aria-pressed={hold.open}
						data-tip={hold.open ? "Hide the hold" : "Show the hold"}
						onClick={hold.onToggle}
						className={`press inline-flex h-[22px] flex-none items-center gap-[5px] border border-surface px-[7px] font-mono text-[11.5px] tracking-normal ${hold.open ? "bg-surface text-ink" : "bg-ink text-surface"}`}
					>
						<Pause size={11} />
						HELD
						{hold.pending && <span className="size-2 bg-[#e8553e]" />}
					</button>
				)}
				{!focusMode && (
					<>
						<div
							role="tablist"
							aria-label="Center view"
							className="flex flex-none border border-surface"
						>
							{TABS.map((x) => (
								<button
									key={x.k}
									type="button"
									role="tab"
									aria-selected={tab === x.k}
									data-tip={x.tip}
									onClick={() => setTab(x.k)}
									className={`press h-[22px] px-[9px] font-mono text-[11.5px] tracking-normal ${tab === x.k ? "bg-surface text-ink" : "bg-ink text-surface"}`}
								>
									{x.label}
								</button>
							))}
						</div>
						<span
							data-tip={LEGEND}
							// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
							tabIndex={0}
							role="img"
							aria-label="How to read the triangle"
							className="inline-flex size-6 flex-none cursor-help items-center justify-center"
						>
							<Info size={15} />
						</span>
					</>
				)}
			</div>
			<div className="relative min-h-0 flex-1 overflow-hidden">
				{shown === "triangle" ? (
					<>
						<Field
							run={run?.id ?? ""}
							scene={scene}
							agg={agg}
							score={score}
							hover={hover}
						/>
						{(phase === "waiting" || phase === "offline") && <Waiting />}
					</>
				) : (
					<div data-pane className="absolute inset-[20px_22px_14px]">
						<Chart calls={calls} />
					</div>
				)}
			</div>
			{hold?.open && (
				// Over the field and the gauges, see-through: the triangle stays in sight.
				<div className="absolute inset-x-0 top-[34px] bottom-0 z-10 overflow-auto bg-surface/85">
					<button
						type="button"
						aria-label="Hide the hold"
						onClick={hold.onToggle}
						className="press absolute top-3 right-3 z-10 inline-flex size-7 items-center justify-center border-[1.2px] border-ink bg-surface"
					>
						<X size={14} />
					</button>
					<div className="mx-auto max-w-[460px]">{hold.pane}</div>
				</div>
			)}
			<div
				data-gauges
				className="grid flex-none grid-cols-3 border-ink border-t-[1.2px]"
			>
				{LEGS.map((g) => (
					<Gauge
						key={g.k}
						g={g}
						agg={agg}
						score={score[g.k]}
						said={evidence(run, g.k)}
						auto={autos(run, g)}
					/>
				))}
			</div>
		</section>
	);
}

// A leg: its highest score so far, gliding to each new one, whether facts confirm it, the
// facts in a popover, what the case says of it, and what Cressey did about it on
// its own.
function Gauge({
	g,
	agg,
	score,
	said,
	auto,
}: {
	g: LegLook;
	agg: Agg;
	score: number;
	said?: CaseEvent;
	auto: Auto[];
}) {
	const { focusMode } = useLive();
	const { confirmed, facts } = agg[g.k];
	const n = facts.length;
	return (
		<div className="relative flex min-w-0 flex-col gap-[7px] border-line border-r-[1px] px-[18px] py-4">
			<div className="flex min-w-0 items-center gap-2">
				<Letter g={g} on={confirmed} size={22} />
				<span className="truncate font-medium text-sm">{g.name}</span>
				<div className="flex-1" />
				<span className="font-pixel text-[34px] leading-[0.8]">
					{fmt(score)}
				</span>
			</div>
			<Bar score={score} n={20} h={9} />
			<div className="flex min-h-[22px] flex-col items-start gap-[5px]">
				<span
					className={`inline-flex h-[22px] items-center gap-1 whitespace-nowrap border px-1.5 font-mono text-[11px] ${TONE[confirmed ? "warn" : "grey"]}`}
				>
					{confirmed ? <Check size={11} /> : <Minus size={11} />}
					{confirmed ? "confirmed" : "not confirmed"}
				</span>
				{n > 0 && !focusMode && (
					<details data-pop>
						<summary className="inline-flex h-[22px] items-center gap-1 whitespace-nowrap border border-ink bg-surface px-1.5 font-mono text-[11px]">
							{n} fact{n > 1 ? "s" : ""}
							<ChevronUp size={11} />
						</summary>
						<div
							data-pop-body
							className="absolute right-2 bottom-[calc(100%+8px)] left-2 z-[5] flex origin-bottom flex-col gap-1.5 border-[1.2px] border-ink bg-surface px-3 py-2.5 shadow-[0_18px_40px_-16px_rgba(30,30,30,.32),0_2px_6px_rgba(30,30,30,.06)]"
						>
							<span className="label">{g.name} · facts from the log</span>
							{facts.map((f) => (
								<div
									key={f.t}
									className="grid grid-cols-[8px_minmax(0,1fr)_auto] items-baseline gap-2 text-[12.5px] leading-[1.4]"
								>
									<span className="size-1.5 bg-ink" />
									<span>{f.t}</span>
									<span className="whitespace-nowrap font-mono text-[11px] text-mute-2">
										{f.at}
									</span>
								</div>
							))}
						</div>
					</details>
				)}
			</div>
			{said && (
				<span
					data-tip={`${INDICATOR[said.indicator]}\n“${said.quote}”`}
					className="line-clamp-2 text-pretty text-[12.5px] leading-[1.4]"
				>
					“{said.quote}”{" "}
					<span className="font-mono text-[11px] text-mute-2">
						{said.source}
					</span>
				</span>
			)}
			{auto.length > 0 && (
				<div className="flex flex-col items-start gap-1">
					{auto.map((a) => (
						<span
							key={a.t}
							data-tip={a.tip}
							// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
							tabIndex={0}
							className={`inline-flex min-h-[22px] max-w-full items-start gap-1 text-pretty border px-1.5 py-[3px] font-mono text-[11px] leading-[1.3] ${TONE.info}`}
						>
							<span className="mt-px inline-flex flex-none">
								<a.Icon size={11} />
							</span>
							<span className="min-w-0">{a.t}</span>
						</span>
					))}
				</div>
			)}
		</div>
	);
}
