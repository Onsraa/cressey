import { useEffect, useState } from "react";
import { ApiError, apiPost } from "@/api/client";

const ARMED_MS = 4000; // the design's window for the second click

export type Decision = ReturnType<typeof useDecision>;

// « Rejeter », and « Approuver » behind a second click, for the held call #n of a run.
export function useDecision(
	run: string,
	n: number | undefined,
	refresh: () => void,
) {
	const [armed, setArmed] = useState(false);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState("");
	useEffect(() => {
		if (!armed) return;
		const t = setTimeout(() => setArmed(false), ARMED_MS);
		return () => clearTimeout(t);
	}, [armed]);

	const decide = (verb: "approve" | "reject") => {
		if (n === undefined || busy) return;
		setBusy(true);
		setArmed(false);
		setError("");
		apiPost(`/runs/${encodeURIComponent(run)}/steps/${n}/${verb}`, {})
			.catch((e: unknown) =>
				setError(
					e instanceof ApiError && e.status === 404
						? "Cette retenue n'attend plus de décision."
						: "Décision non enregistrée : réessayez.",
				),
			)
			.finally(() => {
				setBusy(false);
				refresh();
			});
	};

	return {
		armed,
		busy,
		error,
		reject: () => decide("reject"),
		approve: () => {
			if (n === undefined) return;
			if (armed) decide("approve");
			else setArmed(true);
		},
	};
}
