import {
	Clock,
	FileCheck,
	KeyRound,
	Lock,
	type LucideIcon,
} from "lucide-react";
import { useLive } from "@/api/live";
import type { Mandate, Run } from "@/api/types";
import { KIND, TONE, type Tone, time, VISIBILITY } from "@/lib/labels";

const list = (xs: string[]) => (xs.length ? xs.join(", ") : "none");

const mandateTip = (m: Mandate) =>
	[
		"Mandate",
		`may destroy: ${list(m.may_destroy)}`,
		`may send to: ${list(m.may_send_to)}`,
		`may read secrets: ${list(m.may_read_secrets)}`,
		`protected (no read, no write): ${list(m.protected)}`,
		`frozen (read-only): ${list(m.frozen)}`,
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
			label: "key suspended",
			tip: "Run key suspended: its calls are refused",
		};
	if (run.read_only_step)
		return {
			Icon: Lock,
			tone: "warn",
			label: `key read-only since step ${run.read_only_step}`,
			tip: "Pressure and opportunity confirmed, without a human: destructive calls are refused",
		};
	return {
		Icon: KeyRound,
		tone: "ok",
		label: "key active",
		tip: "Run key active",
	};
}

export function Header({ run }: { run: Run }) {
	const { focusMode } = useLive();
	const ended = Boolean(run.ended_at);
	const key = keyLook(run);
	const startedTip = ended
		? `Started at ${time(run.started_at)}\nFinished at ${time(run.ended_at)}: final report received`
		: `Started at ${time(run.started_at)}\nThe run ends when the agent sends its final report.`;
	return (
		<header className="rise flex flex-none flex-wrap items-end gap-4">
			<div className="flex min-w-0 flex-[1_1_420px] flex-col gap-[7px]">
				<div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
					<span className="text-mute">Live run</span>
					{!focusMode && (
						<>
							<span className="text-mute-3">/</span>
							<span className="mr-1.5 font-medium">{run.id}</span>
							<span
								data-tip="Run kind: live, replay or Observer"
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
								{ended ? "finished" : "running"}
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
								mandate
							</button>
						</>
					)}
					<span data-tip={key.tip} className={`chip ${TONE[key.tone]}`}>
						<key.Icon size={12} />
						{key.label}
					</span>
				</div>
				<h1 className="m-0 text-balance font-medium text-[22px] leading-[1.15] tracking-[-0.02em]">
					{run.task}
				</h1>
			</div>
			{!focusMode && (
				<div className="flex flex-col gap-1">
					<span className="label">What Cressey sees</span>
					<div
						data-tip="set when the run starts"
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
			)}
		</header>
	);
}
