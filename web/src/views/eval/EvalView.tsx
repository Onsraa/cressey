import {
	BookOpen,
	Columns2,
	Cpu,
	FileText,
	type LucideIcon,
	ShieldCheck,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { apiGet } from "@/api/client";
import type { EvalFile } from "@/api/types";
import { AblationTab } from "./AblationTab";
import { DecisionTab } from "./DecisionTab";
import { DetectionTab } from "./DetectionTab";
import { GuidesTab } from "./GuidesTab";
import { readAblation, readDecision, readDetection, readGuides } from "./read";
import { Notice, source } from "./ui";

type Kind = EvalFile["kind"];

const TABS: { k: Kind; label: string; Icon: LucideIcon; question: string }[] = [
	{
		k: "detection",
		label: "Detection",
		Icon: ShieldCheck,
		question: "Are incidents stopped without blocking normal work?",
	},
	{
		k: "guides",
		label: "Guides",
		Icon: BookOpen,
		question:
			"Do the owner guides quote real sources and admit what they don't know?",
	},
	{
		k: "ablation",
		label: "Ablation",
		Icon: Columns2,
		question: "What does the triangle add to the safety floor?",
	},
	{
		k: "decision",
		label: "Decision model",
		Icon: Cpu,
		question:
			"Is the decision model calibrated, and does it hold under attack?",
	},
];

// A tab's body, and what its header line adds; no body when the report is unreadable.
function read(file: EvalFile): { body: ReactNode; detail?: string } {
	const r = file.report;
	switch (file.kind) {
		case "detection": {
			const d = readDetection(r);
			return { body: d && <DetectionTab file={file} d={d} /> };
		}
		case "guides": {
			const g = readGuides(r);
			return { body: g && <GuidesTab file={file} g={g} /> };
		}
		case "ablation": {
			const a = readAblation(r);
			return { body: a && <AblationTab file={file} a={a} /> };
		}
		case "decision": {
			const d = readDecision(r);
			return {
				body: d && <DecisionTab file={file} d={d} />,
				detail: d ? `${d.model} · ${d.mode}` : undefined,
			};
		}
	}
}

export function EvalView() {
	const [files, setFiles] = useState<EvalFile[]>();
	const [error, setError] = useState("");
	const [t, setTab] = useState(TABS[0]);

	useEffect(() => {
		apiGet<EvalFile[]>("/eval")
			.then(setFiles)
			.catch((e: unknown) =>
				setError(e instanceof Error ? e.message : String(e)),
			);
	}, []);

	const file = files?.find((f) => f.kind === t.k);
	const { body, detail } = file
		? read(file)
		: { body: null, detail: undefined };

	let content = body;
	if (error) content = <Notice>The reports couldn't be loaded: {error}</Notice>;
	else if (!files) content = <Notice>Loading the reports…</Notice>;
	else if (!file)
		content = <Notice>/api/eval serves no “{t.label}” report.</Notice>;
	else if (!body) content = <Notice>Unreadable report: {file.file}</Notice>;

	return (
		<div className="flex min-h-0 flex-1 flex-col gap-4 px-7 pt-6 pb-7">
			<header className="rise flex flex-none flex-wrap items-end gap-4">
				<div className="flex min-w-0 flex-[1_1_360px] flex-col gap-[7px]">
					<div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
						<span className="text-mute">Evaluation</span>
						<span className="text-mute-3">/</span>
						<span className="font-medium">{t.label}</span>
						{detail && <span className="text-mute">· {detail}</span>}
					</div>
					<h1 className="m-0 text-balance font-medium text-[22px] leading-[1.15] tracking-[-0.02em]">
						{t.question}
					</h1>
				</div>
				{file && (
					<span
						data-tip="The source file and the date of every number on this page"
						// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
						tabIndex={0}
						className="inline-flex h-6 items-center gap-[5px] border border-ink bg-surface px-2 font-mono text-xs"
					>
						<FileText size={12} />
						{source(file)}
					</span>
				)}
			</header>
			<div
				role="tablist"
				aria-label="Evaluation sections"
				className="flex flex-none overflow-x-auto border-ink border-b-[1.2px] [scrollbar-width:none]"
			>
				{TABS.map((x) => {
					const on = x === t;
					return (
						<button
							key={x.k}
							type="button"
							role="tab"
							aria-selected={on}
							onClick={() => setTab(x)}
							className={`-mb-[1.2px] inline-flex h-9 items-center gap-[7px] whitespace-nowrap border-[1.2px] px-3.5 text-[13.5px] transition-[background-color,box-shadow] hover:shadow-[inset_0_0_0_999px_rgba(30,30,30,.05)] active:translate-y-px active:scale-[.985] ${on ? "border-ink border-b-surface bg-surface font-semibold" : "border-transparent font-medium"}`}
						>
							<x.Icon size={14} />
							{x.label}
						</button>
					);
				})}
			</div>
			<div
				key={t.k}
				role="tabpanel"
				aria-label={t.label}
				className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto"
			>
				{content}
			</div>
		</div>
	);
}
