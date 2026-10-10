import { Check, Info, Repeat, Wrench, X } from "lucide-react";
import { useState } from "react";
import { apiPost } from "@/api/client";
import { useLive } from "@/api/live";
import type { Fix, Incident, ReplayResult } from "@/api/types";
import { ROLE, TONE, time } from "@/lib/labels";
import { Keyed, useKeyed } from "./store";
import { Box, Pending, Tip } from "./ui";
import { LEG } from "./util";

const DECIDE_FIRST = "Decide on the held call first.";

const OUTCOME: Record<ReplayResult["outcome"], string> = {
	refused: "refused",
	stopped: "stopped on its own",
	completed: "completed",
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
				title="FIXES"
				aside={
					<span className="ml-auto font-mono text-[11px] text-mute-2 tracking-normal">
						{approved} of {i.fixes.length} approved
					</span>
				}
			>
				{i.fixes.map((f) => (
					<FixRow key={f.leg} id={i.id} fix={f} held={held} />
				))}
				{!i.fixes.length && (
					<p className="p-5 text-[13px] text-mute">
						No fixes proposed for this incident.
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
						approved
					</span>
				) : (
					<button
						type="button"
						onClick={approve}
						disabled={held || busy}
						data-tip={held ? DECIDE_FIRST : "A human approves; no model can."}
						className="btn h-[30px] gap-1.5 self-start px-[11px] text-[13px]"
					>
						<Check size={14} />
						Approve fix
					</button>
				)}
				{failed && (
					<p className="font-mono text-[11px] text-held-fg">
						The approval didn't go through.
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
			title="REPLAY ×5"
			aside={
				<>
					<span className="font-mono text-[11px] text-mute-2 tracking-normal">
						policy regression test
					</span>
					<Tip
						tip="Five scripted variants of the attack, replayed against the fixed policy. They test the policy, not a real agent. A replay never waits for a human: a call that would have been held fails the replay."
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
					{running ? "Replaying…" : "Replay ×5"}
				</button>
				{running && (
					<Pending>
						Each session replays on a fresh Cressey: up to a minute.
					</Pending>
				)}
				{state === "failed" && (
					<p className="font-mono text-[11px] text-held-fg">
						Replay interrupted: no answer from the server.
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
								{r.passed ? "passed" : "failed"}
							</span>
							<span className="text-mute">
								{r.fixes.length
									? `fixes: ${r.fixes.map((k) => LEG[k].name).join(", ")}`
									: "no fixes"}{" "}
								· {time(r.date)}
							</span>
						</div>
						{normal.length > 0 && (
							<Tip
								tip="The normal tasks, replayed against the fixed policy"
								className="self-start font-mono text-mute text-xs"
							>
								normal tasks: {normal.filter((x) => x.ok).length} /{" "}
								{normal.length} completed with no hold
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
					aria-label="passed"
					className="flex-none text-ok-strong"
				/>
			) : (
				<X size={14} aria-label="failed" className="flex-none text-held-fg" />
			)}
			<span className="flex min-w-0 flex-col">
				<span className="font-medium text-[13px]">{r.session}</span>
				{r.reason && (
					<span className="font-mono text-[11px] text-mute">{r.reason}</span>
				)}
			</span>
			<span className="ml-auto whitespace-nowrap font-mono text-[11.5px]">
				{OUTCOME[r.outcome]}
				{r.step !== null && ` at step ${r.step}`}
			</span>
		</div>
	);
}
