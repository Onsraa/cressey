import { ArrowRight, Check, DoorOpen, KeyRound, Lock, X } from "lucide-react";
import type { Focus, View } from "@/api/live";
import type { Incident, Run, Step } from "@/api/types";
import { LEGS, SEVERITY, STATUS, TONE, time } from "@/lib/labels";
import type { Decision } from "./decide";
import { argsText } from "./run";
import { Code, FitCells, Labeled } from "./ui";

// The held call: the countdown and the decision while it waits, then the outcome.
export function Hold({
	run,
	step,
	incident,
	now,
	decision,
	go,
}: {
	run: Run;
	step: Step;
	incident?: Incident;
	now: number;
	decision: Decision;
	go: (view: View, focus?: Focus) => void;
}) {
	const st = STATUS[step.status];
	const sev = incident && SEVERITY[incident.severity];
	return (
		<div className="rise flex flex-col gap-[18px] p-5">
			<div className="flex flex-wrap items-center gap-2">
				<span
					className={`inline-flex h-6 items-center gap-[5px] border-[1.2px] px-2 font-medium font-mono text-xs ${TONE[st.tone]}`}
				>
					<st.Icon size={13} />
					{st.label}
				</span>
				{sev && (
					<span
						data-tip="Gravité fixée par le code : plancher de sécurité ou clé piège, critique ; deux côtés confirmés, haute."
						className={`chip h-6 px-2 ${TONE[sev.tone]}`}
					>
						<sev.Icon size={12} />
						{sev.label}
					</span>
				)}
				<span className="font-medium font-mono text-[12.5px]">
					#{step.n} {step.tool}
				</span>
			</div>
			{step.status === "held" ? (
				<>
					<Countdown step={step} incident={incident} now={now} />
					<div className="flex flex-col gap-2">
						<button
							type="button"
							onClick={decision.reject}
							disabled={decision.busy}
							className="btn btn-dark h-12 font-semibold text-base"
						>
							<X size={18} strokeWidth={2.5} />
							Rejeter
							<span className="font-mono font-normal text-[11px] opacity-70">
								R
							</span>
						</button>
						<button
							type="button"
							onClick={decision.approve}
							disabled={decision.busy}
							data-tip="Aucun modèle ne peut approuver un appel."
							className={`btn h-9 ${decision.armed ? "btn-dark" : ""}`}
						>
							<Check size={15} />
							{decision.armed ? "Confirmer l'approbation" : "Approuver"}
							<span className="font-mono text-[11px] opacity-70">A</span>
						</button>
						{decision.error && (
							<span role="alert" className="text-[12.5px] text-held-fg">
								{decision.error}
							</span>
						)}
					</div>
				</>
			) : (
				<>
					<div
						className={`flex items-start gap-2.5 border-[1.2px] p-3 ${TONE[st.tone]}`}
					>
						<st.Icon size={18} className="flex-none" />
						<div className="flex flex-col gap-0.5">
							<span className="block font-semibold text-[15px] first-letter:uppercase">
								{st.label} à {time(step.decided_at)}
							</span>
							<span className="text-[13px] leading-[1.4]">{st.tip}</span>
						</div>
					</div>
					{incident && (
						<button
							type="button"
							onClick={() => go("inc", { incident: incident.id })}
							className="btn h-8 self-start px-3 text-[13px]"
						>
							Ouvrir l'incident
							<ArrowRight size={14} />
						</button>
					)}
				</>
			)}
			<Labeled label="tenté">
				<Code>{argsText(run, step.args, "\n") || "aucun argument"}</Code>
			</Labeled>
			<div className="flex flex-col gap-[7px]">
				<span className="label">pourquoi il est retenu</span>
				{step.reason && (
					<span className="text-pretty font-medium text-sm leading-[1.4]">
						{step.reason}
					</span>
				)}
				<div className="flex flex-wrap gap-1">
					{LEGS.filter((g) => step.legs?.[g.k].confirmed).map((g) => (
						<span
							key={g.k}
							data-tip={`${g.name} : confirmée par les faits`}
							className={`chip text-[11px] ${TONE.warn}`}
						>
							<span
								className="font-pixel text-[17px] leading-none"
								style={{ color: g.color }}
							>
								{g.L}
							</span>
							confirmé
						</span>
					))}
				</div>
			</div>
			<div className="flex flex-col border-line border-t text-[13px]">
				<span
					data-tip={
						run.revoked
							? "Suspendue dès que l'appel a été retenu : les appels suivants du run sont refusés."
							: "Clé du run active"
					}
					className="flex min-h-[34px] items-center gap-2 border-line border-b"
				>
					{run.revoked ? (
						<Lock size={14} className="text-held-strong" />
					) : (
						<KeyRound size={14} className="text-ok-strong" />
					)}
					Clé du run {run.revoked ? "suspendue" : "active"}
				</span>
				{run.way_out_step ? (
					<span
						data-tip="Envoyée avec le résultat de l'appel qui a confirmé la pression, sans humain."
						className="flex min-h-[34px] items-center gap-2 border-line border-b"
					>
						<DoorOpen size={14} className="text-info-fg" />
						Porte de sortie envoyée à l'agent
						<span className="label ml-auto">étape {run.way_out_step}</span>
					</span>
				) : null}
			</div>
		</div>
	);
}

function Countdown({
	step,
	incident,
	now,
}: {
	step: Step;
	incident?: Incident;
	now: number;
}) {
	const until = step.held_until ? Date.parse(step.held_until) : now;
	const left = Math.max(0, until - now);
	const s = Math.round(left / 1000);
	// The hold began as its incident opened: the bar drains from there to the safe cancel.
	const whole = incident ? until - Date.parse(incident.created_at) : 0;
	return (
		<div className="flex flex-col gap-1.5">
			<span
				data-tip="Sans décision, l'appel est annulé sans risque."
				className="label self-start"
			>
				annulation sûre dans
			</span>
			<span className="font-pixel text-[72px] leading-[0.82] tracking-[0.02em]">
				{Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}
			</span>
			{whole > 0 && (
				<FitCells score={left / whole} color="var(--color-ink)" n={20} />
			)}
		</div>
	);
}
