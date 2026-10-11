import { useEffect, useState } from "react";
import { ApiError, apiPost } from "@/api/client";

const ARMED_MS = 4000; // the design's window for the second click

export type Decision = ReturnType<typeof useDecision>;

// What the human reads when a decision didn't save. A reason that breaks a rule comes
// back with the rule named.
export function failure(e: unknown): string {
	if (e instanceof ApiError) {
		if (e.status === 404)
			return "This hold is no longer waiting for a decision.";
		const b = e.body;
		if (
			e.status === 422 &&
			typeof b === "object" &&
			b !== null &&
			"detail" in b &&
			typeof b.detail === "string"
		)
			return `Reason not sent: ${b.detail}`;
	}
	return "Decision not saved: try again.";
}

// The reason being written for the held call #n. It lives in the hook, not in the box, so
// it survives the inspector leaving the HELD tab. `fresh`: the box was just opened and
// wants the focus, once.
type Reason = { n: number; text: string; fresh: boolean };

// Opening the box seeds it from the draft once; opening it again for the same hold keeps
// what was typed.
export const opened = (
	r: Reason | undefined,
	n: number,
	draft?: string | null,
): Reason =>
	r?.n === n ? { ...r, fresh: true } : { n, text: draft ?? "", fresh: true };

// “Reject”, “Reject + add reason”, and “Approve” behind a second click, for the held call
// #n of a run.
export function useDecision(
	run: string,
	n: number | undefined,
	refresh: () => void,
) {
	const [armed, setArmed] = useState(false);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState("");
	// The reason box is open for the call it was written for: it closes with the decision,
	// or on the next hold.
	const [reason, setReason] = useState<Reason>();
	const mine = reason?.n === n ? reason : undefined;
	useEffect(() => {
		if (!armed) return;
		const t = setTimeout(() => setArmed(false), ARMED_MS);
		return () => clearTimeout(t);
	}, [armed]);

	const decide = (
		verb: "approve" | "reject",
		body: { message?: string } = {},
	) => {
		if (n === undefined || busy) return;
		setBusy(true);
		setArmed(false);
		setError("");
		apiPost(`/runs/${encodeURIComponent(run)}/steps/${n}/${verb}`, body)
			.catch((e: unknown) => setError(failure(e)))
			.finally(() => {
				setBusy(false);
				refresh();
			});
	};

	return {
		armed,
		busy,
		error,
		composing: mine !== undefined,
		text: mine?.text ?? "",
		fresh: mine?.fresh ?? false,
		compose: (open: boolean, draft?: string | null) => {
			if (open && n !== undefined) setReason((r) => opened(r, n, draft));
			else setReason(undefined);
		},
		edit: (text: string) => setReason((r) => r && { ...r, text }),
		focused: () => setReason((r) => r && { ...r, fresh: false }),
		reject: () => decide("reject"),
		rejectWith: (message: string) => decide("reject", { message }),
		approve: () => {
			if (n === undefined) return;
			if (armed) decide("approve");
			else setArmed(true);
		},
	};
}

// “Unlock” on a stopped run: its key back, its count of refused calls reset.
export function useUnlock(run: string, refresh: () => void) {
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState("");
	const unlock = () => {
		if (busy) return;
		setBusy(true);
		setError("");
		apiPost(`/runs/${encodeURIComponent(run)}/unlock`, {})
			.catch(() => setError("Unlock not saved: try again."))
			.finally(() => {
				setBusy(false);
				refresh();
			});
	};
	return { busy, error, unlock };
}
