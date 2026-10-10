import {
	Check,
	CircleQuestionMark,
	FileText,
	Hourglass,
	type LucideIcon,
	X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/api/client";
import type { Guide, Incident, OwnerGuide, WhyAnswer } from "@/api/types";
import { GUIDE_STATUS, ROLE, TONE, type Tone } from "@/lib/labels";
import { Keyed, useKeyed } from "./store";
import { Pending, Tip } from "./ui";
import { LEG } from "./util";

type Status = OwnerGuide["status"];

const LOOK: Record<Status, { Icon: LucideIcon; tone: Tone; tip: string }> = {
	pending: {
		Icon: Hourglass,
		tone: "info",
		tip: "Le guide démarre à l'ouverture de l'incident, avant la décision.",
	},
	ok: {
		Icon: Check,
		tone: "ok",
		tip: "Chaque étape cite une source vérifiée.",
	},
	unsure: {
		Icon: CircleQuestionMark,
		tone: "warn",
		tip: "Aucune source vérifiée ne couvre ce cas.",
	},
	unavailable: {
		Icon: X,
		tone: "grey",
		tip: "Guide indisponible ; les sources restent affichées.",
	},
};

const guides = new Keyed<Guide | "failed">();
type Why = { q: string; busy?: boolean; answer?: WhyAnswer; failed?: boolean };
const whys = new Keyed<Why>();

export function Guides({ incident }: { incident: Incident }) {
	return (
		<div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] items-stretch gap-4">
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
			<div className="flex min-h-11 flex-wrap items-center gap-2 border-line border-b px-4 py-3">
				<div className="flex min-w-0 flex-1 flex-col">
					<span className="font-semibold text-sm leading-[1.2]">
						{ROLE[owner.owner_role]}
					</span>
					<span className="truncate text-mute-2 text-xs">
						{owner.owner_role === "soc"
							? "boîte de repli"
							: LEG[owner.leg].name}
					</span>
				</div>
				<Tip
					tip={look.tip}
					className={`chip h-auto min-h-[22px] whitespace-normal text-[11px] ${TONE[look.tone]}`}
				>
					<look.Icon size={11} className="flex-none" />
					{GUIDE_STATUS[owner.status]}
				</Tip>
			</div>
			<div className="flex flex-1 flex-col gap-4 p-4">
				{owner.status === "pending" && <Pending>Rédaction du guide…</Pending>}
				{owner.guide_id ? (
					<>
						<GuideBody id={owner.guide_id} status={owner.status} />
						<Why id={owner.guide_id} />
					</>
				) : (
					owner.status === "unavailable" && (
						<p className="text-sm leading-[1.45]">
							Guide indisponible. Les sources restent listées.
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
	if (guide === undefined) return <Pending>Chargement du guide…</Pending>;
	if (guide === "failed")
		return (
			<p className="text-[13px] text-held-fg">
				Le guide n'a pas pu être chargé.
			</p>
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
								<span className="text-pretty bg-paper px-[9px] py-1.5 text-[12.5px] leading-[1.45]">
									« {x.quote} »
								</span>
								<span className="font-mono text-[11px] text-mute">
									{x.source_title} · {x.source_id}
								</span>
							</div>
						</li>
					))}
				</ol>
			)}
			{guide.status === "unsure" && (
				<>
					<p className="text-sm leading-[1.45]">
						Aucune source vérifiée ne couvre ce cas. Voir l'équipe sécurité.
					</p>
					{guide.message && (
						<p className="font-mono text-[11px] text-mute">{guide.message}</p>
					)}
				</>
			)}
			{guide.status === "unavailable" && (
				<p className="text-sm leading-[1.45]">
					Guide indisponible. Les sources restent listées.
				</p>
			)}
			{dropped > 0 && (
				<span className="inline-flex items-center gap-[5px] self-start font-mono text-[11px] text-mute">
					<X size={11} />
					{dropped} étape{s} écartée{s} : citation introuvable
				</span>
			)}
			{guide.status !== "ok" && guide.passages.length > 0 && (
				<ul className="flex flex-col gap-1">
					{guide.passages.map((p) => (
						<li
							key={p.id}
							className="inline-flex items-center gap-[5px] font-mono text-[11.5px] text-mute"
						>
							<FileText size={12} className="flex-none" />
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
				className="flex"
				onSubmit={(e) => {
					e.preventDefault();
					ask(id, q.trim());
				}}
			>
				<input
					type="text"
					aria-label="Question sur ce guide"
					placeholder="Pourquoi cette étape ?"
					maxLength={500}
					value={q}
					onChange={(e) => setQ(e.target.value)}
					className="h-[34px] min-w-0 flex-1 border-[1.2px] border-ink border-r-0 bg-surface px-2.5 text-[13px] -outline-offset-2"
				/>
				<button
					type="submit"
					// The API asks for 3 characters at least.
					disabled={why?.busy || q.trim().length < 3}
					className="btn btn-dark px-[11px] text-[13px]"
				>
					Pourquoi ?
				</button>
			</form>
			{why?.busy && <Pending>Recherche dans les sources vérifiées…</Pending>}
			{why?.failed && (
				<p className="font-mono text-[11px] text-held-fg">
					La question n'a pas pu être posée.
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
									tip={`« ${c.quote} »`}
									className="inline-flex min-h-5 cursor-help items-center bg-ink px-1.5 py-0.5 font-mono text-[11px] text-surface"
								>
									[{n + 1}] {c.source_title} · {c.source_id}
								</Tip>
							))}
						</span>
					)}
				</div>
			)}
		</div>
	);
}
