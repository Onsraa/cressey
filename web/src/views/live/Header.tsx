import {
	Clock,
	FileCheck,
	KeyRound,
	Lock,
	type LucideIcon,
} from "lucide-react";
import type { Mandate, Run } from "@/api/types";
import { KIND, TONE, type Tone, time, VISIBILITY } from "@/lib/labels";

const list = (xs: string[]) => (xs.length ? xs.join(", ") : "aucun");

const mandateTip = (m: Mandate) =>
	[
		"Mandat",
		`peut détruire : ${list(m.may_destroy)}`,
		`peut envoyer à : ${list(m.may_send_to)}`,
		`peut lire les secrets : ${list(m.may_read_secrets)}`,
		`protégé (ni lecture ni écriture) : ${list(m.protected)}`,
		`gelé (lecture seule) : ${list(m.frozen)}`,
	].join("\n");

function keyLook(run: Run): {
	Icon: LucideIcon;
	tone: Tone;
	label: string;
	tip: string;
} {
	if (run.revoked)
		return {
			Icon: Lock,
			tone: "held",
			label: "clé suspendue",
			tip: "Clé du run suspendue : ses appels sont refusés",
		};
	if (run.read_only_step)
		return {
			Icon: Lock,
			tone: "warn",
			label: `clé en lecture seule depuis l'étape ${run.read_only_step}`,
			tip: "Pression et opportunité confirmées, sans humain : les appels destructifs sont refusés",
		};
	return {
		Icon: KeyRound,
		tone: "ok",
		label: "clé active",
		tip: "Clé du run active",
	};
}

export function Header({ run }: { run: Run }) {
	const ended = Boolean(run.ended_at);
	const key = keyLook(run);
	const startedTip = ended
		? `Lancé à ${time(run.started_at)}\nTerminé à ${time(run.ended_at)} : rapport final reçu`
		: `Lancé à ${time(run.started_at)}\nLe run se termine quand l'agent envoie son rapport final.`;
	return (
		<header className="rise flex flex-none flex-wrap items-end gap-4">
			<div className="flex min-w-0 flex-[1_1_420px] flex-col gap-[7px]">
				<div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
					<span className="text-mute">Run en direct</span>
					<span className="text-mute-3">/</span>
					<span className="mr-1.5 font-medium">{run.id}</span>
					<span
						data-tip="Type de run : live, rejeu ou Observateur"
						className="chip border-ink bg-ink text-surface"
					>
						{KIND[run.kind]}
					</span>
					<span
						className={`chip gap-1.5 ${ended ? "border-grey-bd bg-grey" : "border-ok-bd bg-ok"}`}
					>
						<span
							className={`size-[7px] ${ended ? "bg-mute" : "blink bg-ok-strong"}`}
						/>
						{ended ? "terminé" : "en cours"}
					</span>
					<button
						type="button"
						data-tip={startedTip}
						className="chip cursor-help"
					>
						<Clock size={12} />
						{time(run.started_at)}
					</button>
					<button
						type="button"
						data-tip={mandateTip(run.mandate)}
						className="chip cursor-help"
					>
						<FileCheck size={12} />
						mandat
					</button>
					<span data-tip={key.tip} className={`chip ${TONE[key.tone]}`}>
						<key.Icon size={12} />
						{key.label}
					</span>
				</div>
				<h1 className="m-0 text-balance font-medium text-[22px] leading-[1.15] tracking-[-0.02em]">
					{run.task}
				</h1>
			</div>
			<div className="flex flex-col gap-1">
				<span className="label">Ce que voit Cressey</span>
				<div
					data-tip="fixé au lancement du run"
					className="flex border-[1.2px] border-ink bg-surface"
				>
					{Object.entries(VISIBILITY).map(([k, label]) => (
						<span
							key={k}
							aria-current={k === run.visibility || undefined}
							className={`flex h-8 items-center whitespace-nowrap border-ink border-r-[1px] px-[11px] font-medium text-[13px] last:border-r-0 ${k === run.visibility ? "bg-ink text-surface" : ""}`}
						>
							{label}
						</span>
					))}
				</div>
			</div>
		</header>
	);
}
