import { type ReactNode, useCallback, useState } from "react";
import type { Step, StepStatus } from "@/api/types";
import { Cells } from "@/components/Cells";
import { type LEGS, RISK, STATUS, TONE } from "@/lib/labels";

export type LegLook = (typeof LEGS)[number];

// The element's content box, kept up to date.
export function useSize() {
	const [size, setSize] = useState({ w: 0, h: 0 });
	const ref = useCallback((el: HTMLElement | null) => {
		if (!el) return;
		const ro = new ResizeObserver(([e]) =>
			setSize({ w: e.contentRect.width, h: e.contentRect.height }),
		);
		ro.observe(el);
		return () => ro.disconnect();
	}, []);
	return { ref, ...size };
}

// Cells as wide as their box: n cells and Cells' n - 1 one-pixel gaps.
export function FitCells({
	score,
	color,
	n,
}: {
	score: number;
	color: string;
	n: number;
}) {
	const { ref, w } = useSize();
	return (
		<div ref={ref} className="flex">
			{w > 0 && (
				<Cells
					score={score}
					color={color}
					n={n}
					size={Math.floor((w - (n - 1)) / n)}
				/>
			)}
		</div>
	);
}

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
			className="inline-flex flex-none items-center justify-center border-[1.2px] font-pixel leading-none"
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

const chip =
	"inline-flex flex-none items-center gap-1 whitespace-nowrap border font-mono";

export function StatusChip({
	status,
	tall,
}: {
	status: StepStatus;
	tall?: boolean;
}) {
	const { label, Icon, tone, tip } = STATUS[status];
	return (
		<span
			data-tip={tip}
			className={`${chip} text-[11px] ${tall ? "h-[22px] px-[7px]" : "h-5 px-1.5"} ${TONE[tone]}`}
		>
			<Icon size={11} />
			{label}
		</span>
	);
}

export function RiskChip({
	risk,
	tall,
}: {
	risk: Step["risk"];
	tall?: boolean;
}) {
	const { label, Icon, tone } = RISK[risk];
	return (
		<span
			className={`${chip} ${tall ? "h-[22px] px-[7px] text-[11px]" : "h-[18px] px-[5px] text-[10.5px]"} ${TONE[tone]}`}
		>
			<Icon size={tall ? 11 : 10} />
			{label}
		</span>
	);
}

export function AgentText() {
	return (
		<span
			data-tip="Texte de l'agent : non fiable, affiché en texte brut"
			className={`${chip} h-[18px] border-line-2 px-[5px] text-[10.5px] text-mute-2`}
		>
			texte de l'agent
		</span>
	);
}

export function Labeled({
	label,
	children,
}: {
	label: string;
	children: ReactNode;
}) {
	return (
		<div className="flex flex-col gap-1.5">
			<span className="label">{label}</span>
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
