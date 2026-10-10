import {
	Check,
	ChevronUp,
	DoorOpen,
	Info,
	KeyRound,
	Lock,
	type LucideIcon,
	Minus,
} from "lucide-react";
import type { Leg, Run } from "@/api/types";
import { LEGS, TONE } from "@/lib/labels";
import { Chart } from "./Chart";
import { Field } from "./Field";
import { fmt, scored, TRAP } from "./run";
import { FitCells, type LegLook, Letter } from "./ui";

export type CenterTab = "triangle" | "time";

const TABS: { k: CenterTab; label: string; tip: string }[] = [
	{ k: "triangle", label: "Triangle", tip: "Où chaque appel se place (T)" },
	{
		k: "time",
		label: "Au fil des étapes",
		tip: "Les scores appel par appel (T)",
	},
];

const LEGEND = [
	"Comment le lire",
	"Chaque appel se place selon ses trois scores : plus un score est haut, plus il tire vers son sommet.",
	"Gris plus foncé : scores plus hauts.",
	"Saumon : l'appel retenu.",
	"Un côté devient plein quand ses deux sommets sont confirmés par les faits.",
	"Le cadre suit le dernier appel, ou l'appel sélectionné.",
].join("\n");

const NONE: Leg = { score: 0, confirmed: false, facts: [] };

type Auto = { Icon: LucideIcon; t: string; tip: string };

export function Center({
	run,
	tab,
	setTab,
	focus,
	className,
}: {
	run: Run;
	tab: CenterTab;
	setTab: (t: CenterTab) => void;
	focus?: number;
	className: string;
}) {
	const legs = scored(run).at(-1)?.legs;
	const trap = run.steps.find((s) => s.reason?.startsWith(TRAP));
	const auto = (g: LegLook): Auto[] => {
		if (g.k === "pressure")
			return [
				...(run.way_out_step
					? [
							{
								Icon: DoorOpen,
								t: `porte de sortie envoyée · étape ${run.way_out_step}`,
								tip: `Envoyée à l'agent avec le résultat de l'étape ${run.way_out_step}, sans humain : la pression est confirmée.`,
							},
						]
					: []),
				...(run.read_only_step
					? [
							{
								Icon: Lock,
								t: `clé en lecture seule · étape ${run.read_only_step}`,
								tip: `Depuis l'étape ${run.read_only_step}, sans humain : pression et opportunité confirmées, les appels destructifs sont refusés.`,
							},
						]
					: []),
			];
		if (g.k === "opportunity" && trap)
			return [
				{
					Icon: KeyRound,
					t: TRAP,
					tip: `${trap.reason} (étape ${trap.n})`,
				},
			];
		return [];
	};
	return (
		<section
			aria-label="Triangle de la fraude"
			className={`panel rise ${className}`}
		>
			<div className="panel-head pr-1.5">
				<span className="min-w-0 truncate">TRIANGLE DE LA FRAUDE</span>
				<div className="flex-1" />
				<div
					role="tablist"
					aria-label="Vue du triangle"
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
							className={`h-[22px] px-[7px] font-mono text-[11.5px] tracking-normal ${tab === x.k ? "bg-surface text-ink" : "bg-ink text-surface"}`}
						>
							{x.label}
						</button>
					))}
				</div>
			</div>
			<div className="relative min-h-0 flex-1 overflow-hidden">
				{tab === "triangle" ? (
					<>
						<Field run={run} focus={focus} />
						<button
							type="button"
							data-tip={LEGEND}
							aria-label="Comment lire le triangle"
							className="absolute top-2 right-2 inline-flex size-6 cursor-help items-center justify-center bg-surface"
						>
							<Info size={15} />
						</button>
					</>
				) : (
					<Chart run={run} />
				)}
			</div>
			<div className="grid flex-none grid-cols-3 border-ink border-t-[1.2px]">
				{LEGS.map((g) => (
					<Gauge key={g.k} g={g} leg={legs?.[g.k] ?? NONE} auto={auto(g)} />
				))}
			</div>
		</section>
	);
}

// A leg as the latest scored call left it: its score, whether facts confirm it, and those
// facts.
function Gauge({ g, leg, auto }: { g: LegLook; leg: Leg; auto: Auto[] }) {
	const n = leg.facts.length;
	return (
		<div className="@container relative flex min-w-0 flex-col gap-[7px] border-line border-r-[1px] px-[18px] py-4 last:border-r-0">
			{/* In a narrow gauge the name takes its own line, under the letter and the score. */}
			<div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
				<Letter g={g} on={leg.confirmed} size={22} />
				<span className="min-w-0 truncate font-medium text-sm @max-[190px]:order-last @max-[190px]:basis-full">
					{g.name}
				</span>
				<span className="ml-auto font-pixel text-[34px] leading-[0.8]">
					{fmt(leg.score)}
				</span>
			</div>
			<FitCells score={leg.score} color={g.color} n={20} />
			<div className="flex min-h-[22px] flex-wrap items-center gap-[5px]">
				<span
					className={`chip h-[22px] gap-1 px-1.5 text-[11px] ${TONE[leg.confirmed ? "warn" : "grey"]}`}
				>
					{leg.confirmed ? <Check size={11} /> : <Minus size={11} />}
					{leg.confirmed ? "confirmé" : "non confirmé"}
				</span>
				{auto.map((a) => (
					<span
						key={a.t}
						data-tip={a.tip}
						className={`inline-flex min-h-[22px] items-center gap-1 border px-1.5 py-0.5 font-mono text-[11px] leading-[1.3] ${TONE.info}`}
					>
						<a.Icon size={11} className="flex-none" />
						{a.t}
					</span>
				))}
				{n > 0 && (
					<details className="ml-auto">
						<summary className="inline-flex min-h-[22px] items-center gap-1 border border-ink bg-surface px-1.5 py-0.5 font-mono text-[11px] leading-[1.3]">
							{n} fait{n > 1 ? "s" : ""} du journal
							<ChevronUp size={11} />
						</summary>
						<div className="absolute right-2 bottom-[calc(100%+8px)] left-2 z-[5] flex flex-col gap-1.5 border-[1.2px] border-ink bg-surface px-3 py-2.5 shadow-[0_18px_40px_-16px_rgba(30,30,30,0.32),0_2px_6px_rgba(30,30,30,0.06)]">
							<span className="label">{g.name} · faits du journal</span>
							{leg.facts.map((f) => (
								<span
									key={f}
									className="grid grid-cols-[8px_minmax(0,1fr)] items-baseline gap-2 text-[12.5px] leading-[1.4]"
								>
									<span className="size-1.5 bg-ink" />
									{f}
								</span>
							))}
						</div>
					</details>
				)}
			</div>
		</div>
	);
}
