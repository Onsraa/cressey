import type { ReactNode } from "react";
import type { Step } from "@/api/types";
import { MessageSquare } from "@/components/icons";
import {
	FROM_WORDS,
	type LEGS,
	RISK,
	type Shown,
	STATUS,
	TONE,
} from "@/lib/labels";
import { bar } from "./run";

export type LegLook = (typeof LEGS)[number];

// A leg's letter in its colour, filled once facts confirm the leg.
export function Letter({
	g,
	on,
	size,
}: {
	g: LegLook;
	on: boolean;
	size: number;
}) {
	return (
		<span
			className="inline-flex flex-none items-center justify-center border-[1.2px] font-pixel leading-none transition-[background-color,border-color,color] duration-300"
			style={{
				width: size,
				height: size,
				fontSize: size - 3,
				borderColor: g.color,
				background: on ? g.color : "var(--color-surface)",
				color: on ? "var(--color-surface)" : g.color,
			}}
		>
			{g.L}
		</span>
	);
}

const EMPTY = "#d6d6d3"; // an empty cell's outline

// The design's pixel bar: n cells up to the score, darker toward its end.
export function Bar({
	score,
	n,
	h,
	className = "",
}: {
	score: number;
	n: number;
	h: number;
	className?: string;
}) {
	return (
		<span
			aria-hidden="true"
			className={`grid gap-0.5 ${className}`}
			style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}
		>
			{bar(score, n).map((c, i) => (
				<span
					// biome-ignore lint/suspicious/noArrayIndexKey: a cell is its position
					key={i}
					className="transition-[background-color] duration-[350ms]"
					style={{
						height: h,
						background: c ?? "var(--color-surface)",
						boxShadow: `inset 0 0 0 1px ${c ? "transparent" : EMPTY}`,
					}}
				/>
			))}
		</span>
	);
}

const chip =
	"inline-flex flex-none items-center gap-1 whitespace-nowrap border font-mono text-[11px]";

export function StatusChip({
	status,
	tall,
}: {
	status: Shown;
	tall?: boolean;
}) {
	const { label, Icon, tone, tip } = STATUS[status];
	return (
		<span
			data-tip={tip}
			className={`${chip} ${tall ? "h-[22px] px-[7px]" : "h-5 px-1.5"} ${TONE[tone]}`}
		>
			<Icon size={11} />
			{label}
		</span>
	);
}

export function RiskChip({ risk }: { risk: Step["risk"] }) {
	const { label, Icon, tone } = RISK[risk];
	return (
		<span className={`${chip} h-[22px] px-[7px] ${TONE[tone]}`}>
			<Icon size={11} />
			{label}
		</span>
	);
}

// The tag on a level the agent's words lead, not the facts: display only.
export function FromWords({
	g,
	className = "",
}: {
	g: LegLook;
	className?: string;
}) {
	return (
		<span
			data-tip={`${g.name} read from what the agent said, not from the log.\nIt confirms nothing and holds nothing.`}
			className={`inline-flex min-h-[22px] max-w-full items-start gap-1 text-pretty border px-1.5 py-[3px] font-mono text-[11px] leading-[1.3] ${TONE.grey} ${className}`}
		>
			<span className="mt-px inline-flex flex-none">
				<MessageSquare size={11} />
			</span>
			<span className="min-w-0">{FROM_WORDS}</span>
		</span>
	);
}

// A small mono caption over a block: « arguments », « attempted »…
export function Labeled({
	label,
	tip,
	children,
}: {
	label: string;
	tip?: string;
	children: ReactNode;
}) {
	return (
		<div className="flex flex-col gap-1.5">
			<span data-tip={tip} className="label self-start">
				{label}
			</span>
			{children}
		</div>
	);
}

export function Code({ children }: { children: string }) {
	return (
		<code className="block whitespace-pre-wrap bg-paper px-2.5 py-2 font-mono text-xs leading-[1.45] wrap-anywhere">
			{children}
		</code>
	);
}
