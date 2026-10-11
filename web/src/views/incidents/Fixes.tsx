import { useLayoutEffect, useRef, useState } from "react";
import { apiPost } from "@/api/client";
import { useLive } from "@/api/live";
import type { Fix, Incident, ReplayResult } from "@/api/types";
import { Ban, Check, Info, Repeat, Wrench, X } from "@/components/icons";
import { ROLE, TONE } from "@/lib/labels";
import { stepIn } from "@/lib/motion";
import { Keyed, useKeyed } from "./store";
import { Box, Pending, Tip } from "./ui";
import { LEG } from "./util";

const DECIDE_FIRST = "Decide the held call first";

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
		<div
			data-anim
			className="grid grid-cols-[repeat(auto-fit,minmax(320px,1fr))] items-start gap-4"
		>
			<Box
				Icon={Wrench}
				title="FIXES"
				aside={
					<>
						<div className="flex-1" />
						<Tip
							tip="One fix per leg, for pressure and opportunity only. Only a human approves a fix or closes an incident."
							className="cursor-help font-mono text-[11px] text-mute-2 tracking-normal"
						>
							{approved} / {i.fixes.length} approved
						</Tip>
					</>
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
		<div className="grid grid-cols-[26px_minmax(0,1fr)] gap-4 border-line border-b px-[18px] py-4">
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
						{g.name} · {ROLE[fix.owner_role].toLowerCase()}
					</span>
				</div>
				{fix.approved ? (
					<span
						className={`inline-flex h-[26px] items-center gap-[5px] self-start border px-[9px] font-mono text-[11.5px] ${TONE.ok}`}
					>
						<Check size={12} />
						approved
					</span>
				) : (
					<button
						type="button"
						onClick={approve}
						disabled={held || busy}
						data-tip={held ? DECIDE_FIRST : "A human approves every fix"}
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
	const variants = r?.results.filter((x) => x.expect === "held") ?? [];
	const stopped = variants.filter((x) => x.ok).length;
	const normal = r?.results.filter((x) => x.expect === "free") ?? [];
	// A new replay's results come in one after the other, as the design's.
	const list = useRef<HTMLDivElement>(null);
	const shown = useRef(r?.date);
	useLayoutEffect(() => {
		if (shown.current === r?.date) return;
		shown.current = r?.date;
		if (list.current) stepIn([...list.current.children], 0.42);
	});
	return (
		<Box
			Icon={Repeat}
			title="REPLAY ×5"
			aside={
				<>
					<span className="font-mono text-[11px] text-mute-2 tracking-normal">
						policy regression test
					</span>
					<div className="flex-1" />
					<Tip
						tip="Five scripted variants of the attack, replayed against the fixed policy. They test the policy, not a real agent. A variant passes only if it stops on its own; “refused” means Cressey still had to block."
						className="inline-flex cursor-help"
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
					{running ? "Replaying…" : r ? "Replay ×5 again" : "Replay ×5"}
				</button>
				{running && (
					<Pending small>
						Each session replays on a fresh Cressey: up to a minute.
					</Pending>
				)}
				{state === "failed" && (
					<p className="font-mono text-[11px] text-held-fg">
						Replay interrupted: no answer from the server.
					</p>
				)}
				{r && (
					<>
						<div ref={list} className="flex flex-col border-line border-t">
							{variants.map((x) => (
								<Result key={x.session} result={x} />
							))}
						</div>
						<div className="flex flex-wrap items-center gap-2.5">
							<span
								className={`inline-flex h-7 items-center gap-1.5 border-[1.2px] px-2.5 font-mono text-xs ${TONE[r.passed ? "ok" : "held"]}`}
							>
								{r.passed ? <Check size={13} /> : <X size={13} />}
								{r.passed
									? `replay passed · ${stopped} / ${variants.length} stopped on their own`
									: `${stopped} / ${variants.length} stopped on their own · replay failed`}
							</span>
							{normal.length > 0 && (
								<Tip
									tip="Counted from the replay results"
									className="font-mono text-mute text-xs"
								>
									normal tasks: {normal.filter((x) => x.ok).length} /{" "}
									{normal.length} completed with no hold
								</Tip>
							)}
						</div>
					</>
				)}
			</div>
		</Box>
	);
}

function Result({ result: r }: { result: ReplayResult }) {
	const at = r.step !== null ? ` at step ${r.step}` : "";
	return (
		<div
			data-tip={
				r.ok
					? "The variant stops by itself: the fix held."
					: `Cressey had to block${r.reason ? `: ${r.reason}` : ""}`
			}
			className={`flex min-h-9 items-center gap-2.5 border-line border-b px-2.5 ${r.ok ? "bg-surface" : "bg-held"}`}
		>
			<span
				className={`inline-flex ${r.ok ? "text-ok-strong" : "text-held-fg"}`}
			>
				{r.ok ? <Check size={14} /> : <Ban size={14} />}
			</span>
			<span className="font-medium text-[13px]">{r.session}</span>
			<span className="ml-auto whitespace-nowrap font-mono text-[11.5px]">
				{OUTCOME[r.outcome]}
				{at}
			</span>
		</div>
	);
}
