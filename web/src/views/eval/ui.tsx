import type { ReactNode } from "react";
import type { EvalFile } from "@/api/types";
import { day } from "@/lib/format";
import { TONE } from "@/lib/labels";

// « report-detection.json · dev · 2026-10-10 »
export const source = (f: EvalFile) =>
	`${f.file.split("/").at(-1)} · ${f.split} · ${day(f.date)}`;

export const Split = ({ split }: { split: string }) => (
	<span
		className={`border px-1.5 py-px ${TONE[split === "held-out" ? "info" : "grey"]}`}
	>
		{split}
	</span>
);

export type Tile = {
	label: string;
	value: string;
	sub: string; // n/N or the sample size
	reading: string; // how to read it, the design's TT map
	watch?: boolean; // a cost or a weak spot: amber, not green
};

const PANEL =
	"border-[1.2px] border-ink bg-surface shadow-[0_1px_2px_rgba(30,30,30,.04),0_12px_28px_-18px_rgba(30,30,30,.22)]";

export function Tiles({ file, tiles }: { file: EvalFile; tiles: Tile[] }) {
	return (
		<div
			data-anim
			className={`grid flex-none grid-cols-[repeat(auto-fit,minmax(180px,1fr))] ${PANEL}`}
		>
			{tiles.map((t) => (
				<div
					key={t.label}
					data-tip={`${t.label}: ${t.value}\nReading: ${t.reading}\n${file.split} · ${t.sub}\n${source(file)}`}
					// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
					tabIndex={0}
					className="flex min-w-0 flex-col gap-2 border-line border-r-[1px] px-[22px] py-5"
				>
					<span className="flex min-h-[34px] items-start gap-2 text-[13px] text-mute leading-[1.3]">
						<span
							className={`mt-[5px] size-2 flex-none ${t.watch ? "bg-warn-bd" : "bg-ok-strong"}`}
						/>
						{t.label}
					</span>
					<span className="whitespace-nowrap font-pixel text-[clamp(34px,3.2vw,50px)] leading-[0.8]">
						{t.value}
					</span>
					<span className="flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-mute leading-[1.4]">
						<Split split={file.split} />
						{t.sub}
					</span>
					{/* shortcut: one report per kind, as /api/eval serves today; show a held-out file's numbers once it serves one */}
					{file.split !== "held-out" && (
						<span className="font-mono text-[11px] text-mute-2">
							held-out: not measured yet
						</span>
					)}
				</div>
			))}
		</div>
	);
}

// A chart or list panel: VT323 head on white, as in the design's eval blocks.
export function Panel({
	head,
	anim,
	className = "",
	children,
}: {
	head: ReactNode;
	anim?: boolean; // a block of its own: it rises in with the tab
	className?: string;
	children: ReactNode;
}) {
	return (
		<div data-anim={anim} className={`flex flex-col ${PANEL} ${className}`}>
			<div className="flex h-[34px] flex-none items-center gap-2 overflow-hidden whitespace-nowrap border-line border-b px-3.5 font-pixel text-[19px] leading-none tracking-[0.04em]">
				{head}
			</div>
			{children}
		</div>
	);
}

// Mono text inside a head, without the VT323 letter spacing.
export const Aside = ({ children }: { children: ReactNode }) => (
	<span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-mute-2 tracking-normal">
		{children}
	</span>
);

// One listed session: its split, its id and why.
export const Miss = ({
	split,
	id,
	children,
}: {
	split: string;
	id: string;
	children?: ReactNode;
}) => (
	<div className="flex flex-col gap-1 border-line border-b px-[18px] py-3.5">
		<span className="flex items-center gap-1.5 font-mono text-[11px]">
			<Split split={split} />
			{id}
		</span>
		{children && <span className="text-[13px] leading-[1.4]">{children}</span>}
	</div>
);

export const Notice = ({ children }: { children: ReactNode }) => (
	<p data-anim className={`px-5 py-4 font-mono text-[13px] text-mute ${PANEL}`}>
		{children}
	</p>
);
