import {
	createContext,
	type ReactNode,
	useCallback,
	useContext,
	useEffect,
	useRef,
	useState,
} from "react";
import { apiGet } from "./client";
import type {
	FleetSignal,
	Hold,
	Incident,
	Responses,
	Run,
	Status,
} from "./types";

export type View = "live" | "inc" | "eval" | "connect";
// Where a link from another view lands: an incident, or a step of a run.
export type Focus = { incident?: string; run?: string; step?: number };

type Polled = {
	status?: Status;
	runs: Run[];
	holds: Hold[];
	incidents: Incident[];
	responses?: Responses;
	fleet: FleetSignal[];
};

export type Live = Polled & {
	now: number; // ticks with each poll, for the countdowns
	offline: boolean; // the backend didn't answer the last poll
	refresh: () => void; // poll now, after a decision or a change
	view: View;
	focus: Focus;
	go: (view: View, focus?: Focus) => void;
};

const LiveContext = createContext<Live | null>(null);

const EMPTY: Polled = { runs: [], holds: [], incidents: [], fleet: [] };

async function poll(): Promise<Polled> {
	const [status, runs, holds, incidents, responses, fleet] = await Promise.all([
		apiGet<Status>("/status"),
		apiGet<Run[]>("/runs"),
		apiGet<Hold[]>("/holds"),
		apiGet<Incident[]>("/incidents"),
		apiGet<Responses>("/policy/responses"),
		apiGet<FleetSignal[]>("/fleet"),
	]);
	return { status, runs, holds, incidents, responses, fleet };
}

// The dashboard polls about once a second (dashboard.md, Data); it keeps the last answer
// when a poll fails, and says so.
export function LiveProvider({ children }: { children: ReactNode }) {
	const [data, setData] = useState<Polled>(EMPTY);
	const [now, setNow] = useState(() => Date.now());
	const [offline, setOffline] = useState(false);
	const [view, setView] = useState<View>("live");
	const [focus, setFocus] = useState<Focus>({});
	const busy = useRef(false);

	const refresh = useCallback(() => {
		setNow(Date.now());
		if (busy.current) return;
		busy.current = true;
		poll()
			.then((d) => {
				setData(d);
				setOffline(false);
			})
			.catch(() => setOffline(true))
			.finally(() => {
				busy.current = false;
			});
	}, []);

	useEffect(() => {
		refresh();
		const id = setInterval(refresh, 1000);
		return () => clearInterval(id);
	}, [refresh]);

	const go = useCallback((v: View, f: Focus = {}) => {
		setView(v);
		setFocus(f);
	}, []);

	return (
		<LiveContext.Provider
			value={{ ...data, now, offline, refresh, view, focus, go }}
		>
			{children}
		</LiveContext.Provider>
	);
}

export function useLive(): Live {
	const live = useContext(LiveContext);
	if (!live) throw new Error("useLive outside LiveProvider");
	return live;
}

// The Run view follows the latest live run.
export function latestLive(runs: Run[]): Run | undefined {
	return runs
		.filter((r) => r.kind === "live")
		.sort((a, b) => a.started_at.localeCompare(b.started_at))
		.at(-1);
}
