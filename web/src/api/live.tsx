import {
	createContext,
	type ReactNode,
	useCallback,
	useContext,
	useEffect,
	useRef,
	useState,
} from "react";
import { ApiError, apiGet } from "./client";
import type {
	FleetSignal,
	Hold,
	Incident,
	Responses,
	Run,
	RunSummary,
	Status,
} from "./types";

export type View = "live" | "inc" | "eval" | "connect";
// Where a link from another view lands: an incident, or a step of a run.
export type Focus = { incident?: string; run?: string; step?: number };

type Polled = {
	status?: Status;
	runs: RunSummary[];
	holds: Hold[];
	incidents: Incident[];
	responses?: Responses;
	fleet: FleetSignal[];
	shown: Run[]; // the runs the views show, with their steps
};

export type Live = Polled & {
	now: number; // ticks with each poll, for the countdowns
	offline: boolean; // the backend didn't answer the last poll
	locked: boolean; // the backend refused the dashboard's admin key (or it has none)
	refresh: () => void; // poll now, after a decision or a change
	view: View;
	focus: Focus;
	go: (view: View, focus?: Focus) => void;
	focusMode: boolean; // for the demo: the views hide their secondary contents
	toggleFocus: () => void;
	show: (run: string) => () => void; // poll this run's steps until the returned call
};

const LiveContext = createContext<Live | null>(null);

const EMPTY: Polled = {
	runs: [],
	holds: [],
	incidents: [],
	fleet: [],
	shown: [],
};
const FOCUS_KEY = "cressey.focus";

// A run a view shows, in the same poll as its holds; one that is gone (an old link) is none.
const runOf = (id: string) =>
	apiGet<Run>(`/runs/${encodeURIComponent(id)}`).catch((e: unknown) => {
		if (e instanceof ApiError && e.status === 404) return undefined;
		throw e;
	});

async function poll(shown: string[]): Promise<Polled> {
	const [status, runs, holds, incidents, responses, fleet, details] =
		await Promise.all([
			apiGet<Status>("/status"),
			apiGet<RunSummary[]>("/runs"),
			apiGet<Hold[]>("/holds"),
			apiGet<Incident[]>("/incidents"),
			apiGet<Responses>("/policy/responses"),
			apiGet<FleetSignal[]>("/fleet"),
			Promise.all(shown.map(runOf)),
		]);
	const found = details.filter((r): r is Run => r !== undefined);
	return { status, runs, holds, incidents, responses, fleet, shown: found };
}

// The dashboard polls about once a second (dashboard.md, Data); it keeps the last answer
// when a poll fails, and says so.
export function LiveProvider({ children }: { children: ReactNode }) {
	const [data, setData] = useState<Polled>(EMPTY);
	const [now, setNow] = useState(() => Date.now());
	const [offline, setOffline] = useState(false);
	const [locked, setLocked] = useState(false);
	const [view, setView] = useState<View>("live");
	const [focus, setFocus] = useState<Focus>({});
	const busy = useRef(false);
	const showing = useRef(new Map<string, number>()); // run id -> views showing it

	const refresh = useCallback(() => {
		setNow(Date.now());
		if (busy.current) return;
		busy.current = true;
		poll([...showing.current.keys()])
			.then((d) => {
				setData(d);
				setOffline(false);
				setLocked(false);
			})
			.catch((e: unknown) => {
				if (e instanceof ApiError && e.status === 401) setLocked(true);
				else setOffline(true);
			})
			.finally(() => {
				busy.current = false;
			});
	}, []);

	useEffect(() => {
		refresh();
		const id = setInterval(refresh, 1000);
		return () => clearInterval(id);
	}, [refresh]);

	const show = useCallback(
		(id: string) => {
			const views = showing.current;
			views.set(id, (views.get(id) ?? 0) + 1);
			refresh();
			return () => {
				const left = (views.get(id) ?? 1) - 1;
				if (left) views.set(id, left);
				else views.delete(id);
			};
		},
		[refresh],
	);

	const go = useCallback((v: View, f: Focus = {}) => {
		setView(v);
		setFocus(f);
	}, []);

	// Focus mode outlives a reload; where storage is blocked it starts off.
	const [focusMode, setFocusMode] = useState(() => {
		try {
			return localStorage.getItem(FOCUS_KEY) === "on";
		} catch {
			return false;
		}
	});
	useEffect(() => {
		try {
			localStorage.setItem(FOCUS_KEY, focusMode ? "on" : "off");
		} catch {
			// blocked storage: the mode lasts until the page closes
		}
	}, [focusMode]);
	const toggleFocus = useCallback(() => setFocusMode((f) => !f), []);

	return (
		<LiveContext.Provider
			value={{
				...data,
				now,
				offline,
				locked,
				refresh,
				view,
				focus,
				go,
				focusMode,
				toggleFocus,
				show,
			}}
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
export function latestLive(runs: RunSummary[]): RunSummary | undefined {
	return runs
		.filter((r) => r.kind === "live")
		.sort((a, b) => a.started_at.localeCompare(b.started_at))
		.at(-1);
}

// The run the Live view shows: the one another view linked to, else the latest live run.
export const shownRun = (runs: RunSummary[], focus: Focus) =>
	focus.run ? runs.find((r) => r.id === focus.run) : latestLive(runs);

// A run with its steps, polled while a view shows it: the poll itself carries summaries.
export function useRun(id: string | undefined): Run | undefined {
	const { show, shown } = useLive();
	useEffect(() => (id ? show(id) : undefined), [id, show]);
	return shown.find((r) => r.id === id);
}
