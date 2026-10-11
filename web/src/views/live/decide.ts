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
	// The call whose reason box is open: it closes with the decision, or on the next hold.
	const [composing, setComposing] = useState<number>();
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
		composing: n !== undefined && composing === n,
		compose: (open: boolean) => setComposing(open ? n : undefined),
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
