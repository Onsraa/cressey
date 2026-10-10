import { Check, Info, Repeat, Wrench, X } from "lucide-react";
import { useState } from "react";
import { apiPost } from "@/api/client";
import { useLive } from "@/api/live";
import type { Fix, Incident, ReplayResult } from "@/api/types";
import { ROLE, TONE, time } from "@/lib/labels";
import { Keyed, useKeyed } from "./store";
import { Box, Pending, Tip } from "./ui";
import { LEG } from "./util";

const DECIDE_FIRST = "Décidez d'abord l'appel retenu.";

const OUTCOME: Record<ReplayResult["outcome"], string> = {
	refused: "refusé",
	stopped: "s'est arrêté seul",
	completed: "terminé",
};

const replays = new Keyed<"running" | "failed" | "done">();

function replay(id: string, refresh: () => void) {
	replays.set(id, "running");
	apiPost(`/incidents/${id}/replay`, {})
		.then(
			() => replays.set(id, "done"),
			() => replays.set(id, "failed"),
		)
		.finally(refresh);
}

export function Fixes({ incident: i }: { incident: Incident }) {
	const held = i.decision === "held";
	const approved = i.fixes.filter((f) => f.approved).length;
	return (
		<div className="grid grid-cols-[repeat(auto-fit,minmax(320px,1fr))] items-start gap-4">
			<Box
				Icon={Wrench}
				title="CORRECTIFS"
				aside={
					<span className="ml-auto font-mono text-[11px] text-mute-2 tracking-normal">
						{approved} sur {i.fixes.length} approuvés
					</span>
				}
			>
				{i.fixes.map((f) => (
					<FixRow key={f.leg} id={i.id} fix={f} held={held} />
				))}
				{!i.fixes.length && (
					<p className="p-5 text-[13px] text-mute">
						Aucun correctif proposé pour cet incident.
					</p>
				)}
			</Box>
			<ReplayBox incident={i} held={held} />
		</div>
	);
}

function FixRow({ id, fix, held }: { id: string; fix: Fix; held: boolean }) {
	const { refresh } = useLive();
	const [busy, setBusy] = useState(false);
	const [failed, setFailed] = useState(false);
	const g = LEG[fix.leg];
	const approve = () => {
		setBusy(true);
		setFailed(false);
		// On success the button stays disabled until the poll shows the fix approved.
		apiPost(`/incidents/${id}/fixes/${fix.leg}/approve`, {}).then(
			refresh,
			() => {
				setBusy(false);
				setFailed(true);
			},
		);
	};
	return (
		<div className="grid grid-cols-[26px_minmax(0,1fr)] gap-4 border-line border-b px-[18px] py-4 last:border-b-0">
			<span
				className="inline-flex size-[26px] items-center justify-center font-pixel text-[20px] text-surface leading-none"
				style={{ background: g.color }}
			>
				{g.L}
			</span>
			<div className="flex min-w-0 flex-col gap-2">
				<div className="flex flex-col gap-0.5">
					<span className="text-pretty font-medium text-sm leading-[1.35]">
						{fix.text}
					</span>
					<span className="font-mono text-[11px] text-mute-2">
						{g.name} · {ROLE[fix.owner_role]}
					</span>
				</div>
				{fix.approved ? (
					<span className={`chip self-start ${TONE.ok}`}>
						<Check size={12} />
						approuvé
					</span>
				) : (
					<button
						type="button"
						onClick={approve}
						disabled={held || busy}
						data-tip={
							held
								? DECIDE_FIRST
								: "Un humain approuve ; aucun modèle ne le peut."
						}
						className="btn h-[30px] gap-1.5 self-start px-[11px] text-[13px]"
					>
						<Check size={14} />
						Approuver le correctif
					</button>
				)}
				{failed && (
					<p className="font-mono text-[11px] text-held-fg">
						L'approbation n'a pas abouti.
					</p>
				)}
			</div>
		</div>
	);
}

function ReplayBox({
	incident: i,
	held,
}: {
	incident: Incident;
	held: boolean;
}) {
	const { refresh } = useLive();
	const state = useKeyed(replays, i.id);
	const running = state === "running";
	const r = i.replay;
	const normal = r?.results.filter((x) => x.expect === "free") ?? [];
	return (
		<Box
			Icon={Repeat}
			title="REJOUER ×5"
			aside={
				<>
					<span className="font-mono text-[11px] text-mute-2 tracking-normal">
						test de régression de la politique
					</span>
					<Tip
						tip="Cinq variantes scriptées de l'attaque, rejouées sur la politique corrigée. Elles testent la politique, pas un vrai agent. Un rejeu n'attend jamais d'humain : un appel qui aurait été retenu fait échouer le rejeu."
						className="ml-auto inline-flex cursor-help"
					>
						<Info size={14} />
					</Tip>
				</>
			}
		>
			<div className="flex flex-col gap-4 p-5">
				<button
					type="button"
					onClick={() => replay(i.id, refresh)}
					disabled={held || running}
					data-tip={held ? DECIDE_FIRST : undefined}
					className="btn btn-dark h-[38px] self-start px-4"
				>
					<Repeat size={15} />
					{running ? "Rejeu en cours…" : "Rejouer ×5"}
				</button>
				{running && (
					<Pending>
						Chaque session rejoue sur un Cressey neuf : jusqu'à une minute.
					</Pending>
				)}
				{state === "failed" && (
					<p className="font-mono text-[11px] text-held-fg">
						Rejeu interrompu : pas de réponse du serveur.
					</p>
				)}
				{r && (
					<div className={`flex flex-col gap-4 ${running ? "opacity-50" : ""}`}>
						<div className="flex flex-col border-line border-t">
							{r.results
								.filter((x) => x.expect === "held")
								.map((x) => (
									<Result key={x.session} result={x} />
								))}
						</div>
						<div className="flex flex-wrap items-center gap-2.5 font-mono text-xs">
							<span
								className={`inline-flex h-7 items-center gap-1.5 border-[1.2px] px-2.5 ${TONE[r.passed ? "ok" : "held"]}`}
							>
								{r.passed ? <Check size={13} /> : <X size={13} />}
								{r.passed ? "validé" : "échoué"}
							</span>
							<span className="text-mute">
								{r.fixes.length
									? `correctifs : ${r.fixes.map((k) => LEG[k].name).join(", ")}`
									: "aucun correctif"}{" "}
								· {time(r.date)}
							</span>
						</div>
						{normal.length > 0 && (
							<Tip
								tip="Les tâches normales, rejouées sur la politique corrigée"
								className="self-start font-mono text-mute text-xs"
							>
								tâches normales : {normal.filter((x) => x.ok).length} /{" "}
								{normal.length} terminées sans retenue
							</Tip>
						)}
					</div>
				)}
			</div>
		</Box>
	);
}

function Result({ result: r }: { result: ReplayResult }) {
	return (
		<div
			className={`flex min-h-9 items-center gap-2.5 border-line border-b px-2.5 py-1.5 ${r.ok ? "bg-surface" : "bg-held"}`}
		>
			{r.ok ? (
				<Check
					size={14}
					aria-label="réussi"
					className="flex-none text-ok-strong"
				/>
			) : (
				<X size={14} aria-label="échoué" className="flex-none text-held-fg" />
			)}
			<span className="flex min-w-0 flex-col">
				<span className="font-medium text-[13px]">{r.session}</span>
				{r.reason && (
					<span className="font-mono text-[11px] text-mute">{r.reason}</span>
				)}
			</span>
			<span className="ml-auto whitespace-nowrap font-mono text-[11.5px]">
				{OUTCOME[r.outcome]}
				{r.step !== null && ` à l'étape ${r.step}`}
			</span>
		</div>
	);
}
