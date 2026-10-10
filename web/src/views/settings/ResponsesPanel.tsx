import { SlidersHorizontal } from "lucide-react";
import { type ReactNode, useState } from "react";
import { apiPut } from "@/api/client";
import { useLive } from "@/api/live";
import type { Responses } from "@/api/types";
import { CHECK, RESPONSE } from "@/lib/labels";

type Response = Responses["floor"];

const ALL: readonly Response[] = ["alert", "review", "stop"];
const NO_REVIEW: readonly Responses["fleet"][] = ["alert", "stop"];

// shortcut: 240 s, 3 runs and 15 min mirror the backend defaults (CRESSEY_HOLD_TIMEOUT,
// policy.yaml fleet), which the API doesn't serve; read them from /api/status once it does.
const EFFECT: Record<Response, string> = {
	alert: "the call goes through and an incident opens",
	review: "the call waits for a human, safely cancelled after 240 s",
	stop: "refused at once, run key suspended",
};

function Choice<T extends Response>({
	label,
	value,
	options,
	pick,
}: {
	label: string;
	value: T;
	options: readonly T[];
	pick: (v: T) => void;
}) {
	return (
		<fieldset
			aria-label={label}
			className="flex flex-none border-[1.2px] border-ink"
		>
			{options.map((o) => (
				<button
					key={o}
					type="button"
					aria-pressed={o === value}
					onClick={() => pick(o)}
					className={`h-8 border-ink border-r-[1px] px-3 font-medium text-[13px] transition-[background-color,box-shadow] last:border-r-0 active:translate-y-px ${o === value ? "bg-ink text-surface" : "bg-surface hover:shadow-[inset_0_0_0_999px_rgba(30,30,30,.07)]"}`}
				>
					{RESPONSE[o]}
				</button>
			))}
		</fieldset>
	);
}

function Row({
	check,
	what,
	children,
}: {
	check: keyof Responses;
	what: string;
	children: ReactNode;
}) {
	return (
		<div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-line border-b py-3.5">
			<div className="flex min-w-[180px] flex-1 flex-col gap-0.5">
				<span className="font-medium text-sm">{CHECK[check]}</span>
				<span className="text-[13px] text-mute leading-[1.4]">{what}</span>
			</div>
			{children}
		</div>
	);
}

export function ResponsesPanel() {
	const { responses: r, refresh } = useLive();
	const [error, setError] = useState("");

	const save = (next: Responses) => {
		setError("");
		apiPut<Responses>("/policy/responses", next)
			.then(refresh)
			.catch((e: unknown) =>
				setError(e instanceof Error ? e.message : String(e)),
			);
	};

	return (
		<section aria-label="What does Cressey do when…?" className="panel rise">
			<div className="panel-head">
				<SlidersHorizontal size={14} />
				WHAT DOES CRESSEY DO WHEN…?
			</div>
			<div className="flex flex-col gap-4 px-5 pt-1.5 pb-5">
				{r ? (
					<div className="flex flex-col">
						<Row
							check="floor"
							what="destructive outside the mandate, protected or frozen path"
						>
							<Choice
								label={CHECK.floor}
								value={r.floor}
								options={ALL}
								pick={(floor) => save({ ...r, floor })}
							/>
						</Row>
						<Row
							check="trap_key"
							what="a call carries a decoy key, even encoded"
						>
							<Choice
								label={CHECK.trap_key}
								value={r.trap_key}
								options={ALL}
								pick={(trap_key) => save({ ...r, trap_key })}
							/>
						</Row>
						<Row
							check="triangle"
							what="a write, with rationalization confirmed alongside pressure or opportunity"
						>
							<Choice
								label={CHECK.triangle}
								value={r.triangle}
								options={ALL}
								pick={(triangle) => save({ ...r, triangle })}
							/>
						</Row>
						<Row
							check="fleet"
							what="3 runs held for the same target outside their mandate within 15 min. Alert: the banner shows; Stop: their calls to that target are refused"
						>
							<Choice
								label={CHECK.fleet}
								value={r.fleet}
								options={NO_REVIEW}
								pick={(fleet) => save({ ...r, fleet })}
							/>
						</Row>
					</div>
				) : (
					<p className="py-3 font-mono text-[13px] text-mute">
						Reading the responses…
					</p>
				)}
				<ul className="flex flex-col gap-1 text-[13px] leading-[1.4]">
					{ALL.map((o) => (
						<li key={o}>
							<span className="font-medium">{RESPONSE[o]}</span>
							<span className="text-mute">: {EFFECT[o]}</span>
						</li>
					))}
				</ul>
				<p className="font-mono text-[12px] text-mute-2 leading-[1.5]">
					Every change is written to the log. Replays never stop for a human.
				</p>
				{error && (
					<p
						role="alert"
						className="border border-held-bd bg-held px-2.5 py-1.5 text-[13px] text-held-fg"
					>
						The change wasn't saved: {error}
					</p>
				)}
			</div>
		</section>
	);
}
