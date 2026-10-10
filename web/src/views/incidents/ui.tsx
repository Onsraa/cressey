import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

// A tooltip a keyboard user can reach too: tooltips.ts opens it on focus.
export function Tip({
	tip,
	className,
	children,
}: {
	tip: string;
	className?: string;
	children: ReactNode;
}) {
	return (
		<span
			data-tip={tip}
			// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
			tabIndex={0}
			className={className}
		>
			{children}
		</span>
	);
}

// A titled box inside a tab: SOURCE, CORRECTIFS, REJOUER ×5…
export function Box({
	Icon,
	title,
	aside,
	children,
}: {
	Icon: LucideIcon;
	title: string;
	aside?: ReactNode;
	children: ReactNode;
}) {
	return (
		<div className="flex min-w-0 flex-col border-[1.2px] border-ink">
			<div className="flex min-h-[34px] flex-wrap items-center gap-2 border-line border-b px-3.5 py-1.5 font-pixel text-[19px] leading-none tracking-[0.04em]">
				<Icon size={14} />
				{title}
				{aside}
			</div>
			{children}
		</div>
	);
}

// Work in progress: a blinking square and what is happening.
export function Pending({ children }: { children: ReactNode }) {
	return (
		<span className="flex items-center gap-2 text-[13px] text-mute">
			<span className="blink size-[9px] flex-none bg-ink" />
			{children}
		</span>
	);
}
