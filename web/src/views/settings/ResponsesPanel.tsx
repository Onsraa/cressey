import { useState } from "react";
import { apiPut } from "@/api/client";
import { useLive } from "@/api/live";
import type { Responses } from "@/api/types";
import { Hash, SlidersHorizontal } from "@/components/icons";
import { CHECK, RESPONSE } from "@/lib/labels";

type Response = Responses["floor"];

const ALL: readonly Response[] = ["alert", "review", "stop"];
const NO_REVIEW: readonly Responses["fleet"][] = ["alert", "stop"];

// What each response does, as the design's POLOPT.
const EFFECT: Record<Response, string> = {
	alert: "the call goes through and an incident opens",
	review: "the call waits for a human",
	stop: "refused outright, run key suspended",
};

// What each check watches for.
// shortcut: 3 runs and 15 min mirror policy.yaml's fleet defaults, which the API doesn't
// serve; read them from /api/status once it does.
const WHAT: Record<keyof Responses, string> = {
	floor: "destructive outside the mandate · protected or frozen path",
	trap_key: "a decoy key was used",
	trap_key_read: "a decoy key was used in a call that only reads",
	triangle: "pressure + opportunity + rationalization",
	fleet: "3 runs held on the same target within 15 min",
};

function Row<T extends Response>({
	check,
	value,
	options,
	pick,
}: {
	check: keyof Responses;
	value: T;
	options: readonly T[];
	pick: (v: T) => void;
}) {
	return (
		<div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-6 gap-y-4 border-line border-b px-[18px] py-4">
			<div className="flex min-w-0 flex-col gap-[3px]">
				<span className="font-medium text-[14.5px]">{CHECK[check]}</span>
				<span className="font-mono text-[11.5px] text-mute-2">
					{WHAT[check]}
				</span>
				<span className="text-[12.5px] text-mute leading-[1.4]">
					→ {EFFECT[value]}
				</span>
			</div>
			<fieldset
				aria-label={CHECK[check]}
				className="flex flex-none border-[1.2px] border-ink"
			>
				{options.map((o) => (
					<button
						key={o}
						type="button"
						aria-pressed={o === value}
						data-tip={EFFECT[o]}
						onClick={() => pick(o)}
						className={`press shade h-[34px] whitespace-nowrap border-ink border-r-[1px] px-[13px] font-medium text-[13px] ${o === value ? "bg-ink text-surface" : "bg-surface text-ink"}`}
					>
						{RESPONSE[o]}
					</button>
				))}
			</fieldset>
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
		<section
			data-anim
			aria-label="What does Cressey do when…?"
			className="flex-none border-[1.2px] border-ink bg-surface shadow-[0_1px_2px_rgba(30,30,30,.04),0_12px_28px_-18px_rgba(30,30,30,.22)]"
		>
			<div className="panel-head gap-2">
				<SlidersHorizontal size={14} />
				WHAT DOES CRESSEY DO WHEN…?
			</div>
			<div className="flex flex-col">
				{r ? (
					<>
						<Row
							check="floor"
							value={r.floor}
							options={ALL}
							pick={(floor) => save({ ...r, floor })}
						/>
						<Row
							check="trap_key"
							value={r.trap_key}
							options={ALL}
							pick={(trap_key) => save({ ...r, trap_key })}
						/>
						<Row
							check="trap_key_read"
							value={r.trap_key_read}
							options={ALL}
							pick={(trap_key_read) => save({ ...r, trap_key_read })}
						/>
						<Row
							check="triangle"
							value={r.triangle}
							options={ALL}
							pick={(triangle) => save({ ...r, triangle })}
						/>
						<Row
							check="fleet"
							value={r.fleet}
							options={NO_REVIEW}
							pick={(fleet) => save({ ...r, fleet })}
						/>
					</>
				) : (
					<p className="px-[18px] py-4 font-mono text-[13px] text-mute">
						Reading the responses…
					</p>
				)}
				{error && (
					<p
						role="alert"
						className="mx-[18px] mt-3 border border-held-bd bg-held px-2.5 py-1.5 text-[13px] text-held-fg"
					>
						The change wasn't saved: {error}
					</p>
				)}
				<span className="flex items-center gap-[7px] px-[18px] py-3 font-mono text-[11.5px] text-mute">
					<Hash size={12} />A change applies live and is written to the event
					log.
				</span>
			</div>
		</section>
	);
}
