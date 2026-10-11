import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/api/client";
import type { Guide, Incident, OwnerGuide, WhyAnswer } from "@/api/types";
import {
	Check,
	CircleHelp,
	FileText,
	Hourglass,
	type IconType,
	X,
} from "@/components/icons";
import { GUIDE_STATUS, ROLE, TONE, type Tone } from "@/lib/labels";
import { Keyed, useKeyed } from "./store";
import { Pending, Tip } from "./ui";
import { LEG } from "./util";

type Status = OwnerGuide["status"];

const LOOK: Record<Status, { Icon: IconType; tone: Tone; tip: string }> = {
	pending: {
		Icon: Hourglass,
		tone: "info",
		tip: "The guide starts as soon as the incident opens, before the decision.",
	},
	ok: {
		Icon: Check,
		tone: "ok",
		tip: "Every step quotes a verified source.",
	},
	unsure: {
		Icon: CircleHelp,
		tone: "warn",
		tip: "No verified source covers this case.",
	},
	unavailable: {
		Icon: X,
		tone: "grey",
		tip: "Guide unavailable; sources still listed.",
	},
};

const guides = new Keyed<Guide | "failed">();
type Why = { q: string; busy?: boolean; answer?: WhyAnswer; failed?: boolean };
const whys = new Keyed<Why>();

export function Guides({ incident }: { incident: Incident }) {
	return (
		<div
			data-anim
			className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] items-stretch gap-4"
		>
			{incident.guides.map((g) => (
				<Inbox key={`${g.leg}-${g.owner_role}`} owner={g} />
			))}
		</div>
	);
}

function Inbox({ owner }: { owner: OwnerGuide }) {
	const look = LOOK[owner.status];
	return (
		<div className="flex min-w-0 flex-col border-[1.2px] border-ink">
			<div className="flex min-h-11 items-center gap-2 border-line border-b px-4 py-3">
				<div className="flex min-w-0 flex-1 flex-col">
					<span className="font-semibold text-sm leading-[1.2]">
						{ROLE[owner.owner_role]}
					</span>
					<span className="truncate text-mute-2 text-xs">
						{owner.owner_role === "soc"
							? "fallback inbox"
							: LEG[owner.leg].name}
					</span>
				</div>
				<Tip
					tip={look.tip}
					className={`inline-flex h-[22px] items-center gap-1 whitespace-nowrap border px-[7px] font-mono text-[11px] ${TONE[look.tone]}`}
				>
					<look.Icon size={11} />
					{GUIDE_STATUS[owner.status]}
				</Tip>
			</div>
			<div className="flex flex-1 flex-col gap-4 p-4">
				{owner.status === "pending" && <Pending>Writing the guide…</Pending>}
				{owner.guide_id ? (
					<>
						<GuideBody id={owner.guide_id} status={owner.status} />
						<Why id={owner.guide_id} />
					</>
				) : (
					owner.status === "unavailable" && (
						<p className="text-sm leading-[1.45]">
							Guide unavailable. The sources are still listed.
						</p>
					)
				)}
			</div>
		</div>
	);
}

// Fetched once per guide, and again if its owner's status changes.
function useGuide(id: string, status: Status) {
	const guide = useKeyed(guides, id);
	useEffect(() => {
		const hit = guides.get(id);
		if (typeof hit === "object" && hit.status === status) return;
		apiGet<Guide>(`/guides/${id}`).then(
			(g) => guides.set(id, g),
			() => guides.set(id, "failed"),
		);
	}, [id, status]);
	return guide;
}

function GuideBody({ id, status }: { id: string; status: Status }) {
	const guide = useGuide(id, status);
	if (guide === undefined) return <Pending>Loading the guide…</Pending>;
	if (guide === "failed")
		return (
			<p className="text-[13px] text-held-fg">The guide couldn't be loaded.</p>
		);
	const dropped = guide.dropped_steps;
	const s = dropped > 1 ? "s" : "";
	return (
		<>
			{guide.status === "ok" && (
				<ol className="flex flex-col gap-4">
					{guide.steps.map((x, n) => (
						<li
							key={`${x.source_id}-${x.quote}`}
							className="grid grid-cols-[22px_minmax(0,1fr)] gap-2.5"
						>
							<span className="inline-flex size-[22px] items-center justify-center bg-ink font-pixel text-[18px] text-surface leading-none">
								{n + 1}
							</span>
							<div className="flex min-w-0 flex-col gap-[5px]">
								<span className="text-pretty font-medium text-sm leading-[1.35]">
									{x.action}
								</span>
								<Tip
									tip={`${x.source_title} · ${x.source_id}\nverified quote`}
									className="text-pretty bg-paper px-[9px] py-1.5 text-[12.5px] leading-[1.45]"
								>
									“{x.quote}”
								</Tip>
								<span className="font-mono text-[11px] text-mute">
									{x.source_id}
								</span>
							</div>
						</li>
					))}
				</ol>
			)}
			{guide.status === "unsure" && (
				<>
					<p className="text-sm leading-[1.45]">
						I don’t know — ask the security team.
					</p>
					{guide.message && (
						<p className="font-mono text-[11px] text-mute">{guide.message}</p>
					)}
				</>
			)}
			{guide.status === "unavailable" && (
				<p className="text-sm leading-[1.45]">
					Guide unavailable. The sources are still listed.
				</p>
			)}
			{dropped > 0 && (
				<Tip
					tip="Dropped because the quote could not be verified."
					className="inline-flex cursor-help items-center gap-[5px] self-start font-mono text-[11px] text-mute"
				>
					<X size={11} />
					{dropped} step{s} dropped
				</Tip>
			)}
			{guide.status !== "ok" && guide.passages.length > 0 && (
				<ul className="flex flex-col gap-1">
					{guide.passages.map((p) => (
						<li
							key={p.id}
							className="inline-flex items-center gap-[5px] font-mono text-[11.5px] text-mute"
						>
							<FileText size={12} />
							{p.title} · {p.id}
						</li>
					))}
				</ul>
			)}
		</>
	);
}

function ask(id: string, q: string) {
	whys.set(id, { q, busy: true });
	apiPost<WhyAnswer>(`/guides/${id}/why`, { question: q }).then(
		(answer) => whys.set(id, { q, answer }),
		() => whys.set(id, { q, failed: true }),
	);
}

function Why({ id }: { id: string }) {
	const [q, setQ] = useState("");
	const why = useKeyed(whys, id);
	return (
		<div className="mt-auto flex flex-col gap-2 border-line border-t pt-2.5">
			<form
				className="flex border-[1.2px] border-ink"
				onSubmit={(e) => {
					e.preventDefault();
					ask(id, q.trim());
				}}
			>
				<input
					type="text"
					aria-label="Ask a question"
					placeholder="Why this step?"
					maxLength={500}
					value={q}
					onChange={(e) => setQ(e.target.value)}
					className="h-[34px] min-w-0 flex-1 bg-surface px-2.5 text-[13px] -outline-offset-2"
				/>
				<button
					type="submit"
					// The API asks for 3 characters at least.
					disabled={why?.busy || q.trim().length < 3}
					className="press inline-flex items-center gap-1.5 whitespace-nowrap border-ink border-l-[1.2px] bg-ink px-[11px] font-medium text-[13px] text-surface hover:bg-[#3a3a38] disabled:opacity-45"
				>
					Why?
				</button>
			</form>
			{why?.busy && <Pending small>Searching the verified sources…</Pending>}
			{why?.failed && (
				<p className="font-mono text-[11px] text-held-fg">
					The question couldn't be asked.
				</p>
			)}
			{why?.answer && (
				<div className="flex flex-col gap-1.5 border border-ink px-2.5 py-[9px]">
					<span className="font-mono text-[11px] text-mute-2">{why.q}</span>
					<span className="whitespace-pre-line text-pretty text-[13px] leading-normal">
						{why.answer.text}
					</span>
					{why.answer.citations.length > 0 && (
						<span className="flex flex-wrap gap-1">
							{why.answer.citations.map((c, n) => (
								<Tip
									key={`${c.source_id}-${c.quote}`}
									tip={`${c.source_title} · ${c.source_id}\n“${c.quote}”`}
									className="inline-flex h-5 cursor-help items-center bg-ink px-1.5 font-mono text-[11px] text-surface"
								>
									[{n + 1}] {c.source_id}
								</Tip>
							))}
						</span>
					)}
				</div>
			)}
		</div>
	);
}
