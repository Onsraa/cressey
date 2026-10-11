import { useLive } from "@/api/live";
import type { Mandate, Run } from "@/api/types";
import {
	Clock,
	FileCheck,
	type IconType,
	KeySquare,
	Lock,
} from "@/components/icons";
import { KIND, TONE, type Tone, time, VISIBILITY } from "@/lib/labels";

export type Phase =
	| "waiting"
	| "offline"
	| "prompt"
	| "thinking"
	| "writing"
	| "tool"
	| "running"
	| "held"
	| "ended";

// The design's run status: no run yet, nothing arrived, a call held, or ended. Claude Code's
// hooks tell its turn: waiting for a prompt, or working on one (thinking, writing, running a
// tool). An MCP agent has no turns: it is running once it acts.
export function phaseOf(run?: Run): Phase {
	if (!run) return "waiting";
	if (run.steps.some((s) => s.status === "held")) return "held";
	if (run.ended_at) return "ended";
	if (run.turn === "waiting") return "prompt";
	if (run.turn === "working") {
		if (run.steps.some((s) => s.running)) return "tool";
		return run.messages.some((m) => m.streaming) ? "writing" : "thinking";
	}
	return run.steps.length || run.messages.length ? "running" : "offline";
}

// The agent is at work: the dot blinks and the inspector follows the newest row.
export const busy = (p: Phase) =>
	p === "running" || p === "thinking" || p === "writing" || p === "tool";

// The chip keeps the ink text: only its fill and its outline change.
const WORKING = { look: "border-ok-bd bg-ok", dot: "var(--color-ok-strong)" };
const PHASE: Record<Phase, { label: string; look: string; dot: string }> = {
	waiting: { label: "Waiting", look: "border-grey-bd bg-grey", dot: "#a3a3a0" },
	offline: {
		label: "Not connected",
		look: "border-grey-bd bg-grey",
		dot: "#a3a3a0",
	},
	prompt: {
		label: "Waiting for prompt",
		look: "border-grey-bd bg-grey",
		dot: "var(--color-ok-strong)",
	},
	thinking: { label: "Thinking", ...WORKING },
	writing: { label: "Writing", ...WORKING },
	tool: { label: "Running tool", ...WORKING },
	running: { label: "Running", ...WORKING },
	held: { label: "Call held", look: "border-held-bd bg-held", dot: "#d9452b" },
	ended: { label: "Ended", look: "border-grey-bd bg-grey", dot: "#5c5c5a" },
};

const LEVELS: Run["visibility"][] = ["tools", "messages", "reasoning"];
const SEES: Record<Run["visibility"], string> = {
	tools: "Cressey scores tool calls only",
	messages: "Tool calls, agent text and final report",
	reasoning: "Everything, including the agent’s reasoning",
};

const list = (xs: string[]) => (xs.length ? xs.join(", ") : "none");

const mandateTip = (m: Mandate) =>
	[
		"Mandate",
		`may_destroy: ${list(m.may_destroy)}`,
		`may_send_to: ${list(m.may_send_to)}`,
		`may_read_secrets: ${list(m.may_read_secrets)}`,
		`protected: ${list(m.protected)} (no read, no write)`,
		`frozen: ${list(m.frozen)} (read-only)`,
	].join("\n");

function keyLook(run: Run): {
	Icon: IconType;
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
			label: `read-only since step ${run.read_only_step}`,
			tip: `Run key switched to read-only at step ${run.read_only_step} (pressure and opportunity confirmed)`,
		};
	return {
		Icon: KeySquare,
		tone: "ok",
		label: "key active",
		tip: "Run key active",
	};
}

const CHIP = "inline-flex h-[22px] items-center gap-[5px] px-[7px]";
const VIS_TIP = "What Cressey sees: set when the run starts";

export function Header({ run, phase }: { run?: Run; phase: Phase }) {
	const { focusMode } = useLive();
	const st = PHASE[phase];
	const key = run && keyLook(run);
	// A Claude Code run ends with its session; an MCP agent's, with its final report.
	const startedTip = run?.ended_at
		? `Started ${time(run.started_at)}\nEnded ${time(run.ended_at)}${run.turn ? ", session closed" : ", final report received"}`
		: run?.turn
			? "The run ends when the Claude Code session ends."
			: "The run ends when the agent sends its final report.";
	// Shown in focus mode too: the demo watches it.
	const chip = (
		<span className={`${CHIP} gap-1.5 border ${st.look}`}>
			<span
				className={`size-[7px] ${busy(phase) ? "blink" : ""}`}
				style={{ background: st.dot }}
			/>
			{st.label}
		</span>
	);
	return (
		<header data-anim className="flex flex-none flex-wrap items-end gap-4">
			<div className="flex min-w-0 flex-[1_1_420px] flex-col gap-[7px]">
				<div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
					{!focusMode && (
						<>
							<span className="text-mute">Live run</span>
							{run && (
								<>
									<span className="text-mute-3">/</span>
									<span className="mr-1.5 font-medium">{run.id}</span>
									<span
										data-tip="Run kind: live / replay / Observer"
										// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
										tabIndex={0}
										className={`${CHIP} bg-ink text-surface`}
									>
										{KIND[run.kind]}
									</span>
								</>
							)}
							{chip}
							{run && (
								<>
									<span
										data-tip={startedTip}
										// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
										tabIndex={0}
										className={`${CHIP} border border-line-2`}
									>
										<Clock size={12} />
										{time(run.started_at)}
									</span>
									<span
										data-tip={mandateTip(run.mandate)}
										// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
										tabIndex={0}
										className={`${CHIP} cursor-help border border-line-2`}
									>
										<FileCheck size={12} />
										mandate
									</span>
								</>
							)}
						</>
					)}
					{focusMode && chip}
					{key && (
						<span
							data-tip={key.tip}
							// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
							tabIndex={0}
							className={`${CHIP} border ${TONE[key.tone]}`}
						>
							<key.Icon size={12} />
							{key.label}
						</span>
					)}
				</div>
				<h1 className="m-0 text-balance font-medium text-[22px] leading-[1.15] tracking-[-0.02em]">
					{run?.task ?? "Waiting for an agent"}
				</h1>
			</div>
			{run && !focusMode && (
				<div className="flex flex-wrap items-end gap-4">
					<div className="flex flex-col gap-1">
						<span
							data-tip={VIS_TIP}
							// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
							tabIndex={0}
							className="inline-flex cursor-help items-center gap-[5px] font-mono text-[11px] text-mute-2"
						>
							What Cressey sees
							<Lock size={11} />
						</span>
						<fieldset
							aria-label="What Cressey sees (set when the run starts)"
							data-tip={VIS_TIP}
							className="flex min-w-0 border-[1.2px] border-ink bg-surface"
						>
							{LEVELS.map((k) => {
								const on = k === run.visibility;
								return (
									<span
										key={k}
										aria-current={on || undefined}
										data-tip={`${SEES[k]}\nset when the run starts`}
										className={`inline-flex h-8 cursor-default items-center whitespace-nowrap border-ink border-r-[1px] px-[11px] font-medium text-[13px] ${on ? "bg-ink text-surface" : "bg-surface text-mute-3"}`}
									>
										{VISIBILITY[k]}
									</span>
								);
							})}
						</fieldset>
					</div>
				</div>
			)}
		</header>
	);
}
