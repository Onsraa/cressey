import type {
	CaseEvent,
	Indicator,
	LegName,
	Legs,
	Message,
	Run,
	Secret,
	Shadow,
	Step,
	Thread,
} from "@/api/types";

// What the trace lists, in order. A message carries the indicators its thoughts raised.
export type Row =
	| { id: string; kind: "call"; step: Step }
	| ({ id: string; kind: "msg"; indicators: Indicator[] } & Message)
	| { id: string; kind: "report"; text: string };

// A message said after k calls goes just before call #k+1; the report comes last, once
// Claude Code's turn is over (while it works, the report is the last turn's).
export function rows(run: Run): Row[] {
	const calls = run.steps.map((step): [number, Row] => [
		step.n,
		{ id: `c${step.n}`, kind: "call", step },
	]);
	const said = run.messages.map((m, i): [number, Row] => [
		m.after + 0.5,
		{ ...m, id: `m${i}`, kind: "msg", indicators: indicatorsOn(run, i) },
	]);
	const all = [...calls, ...said]
		.sort((a, b) => a[0] - b[0])
		.map(([, row]) => row);
	return run.report && run.turn !== "working"
		? [...all, { id: "report", kind: "report", text: run.report }]
		: all;
}

// A Claude Code run's report is its last turn's answer: the session goes on.
export const reportLabel = (run?: Run) =>
	run?.turn ? "Last answer" : "Final report";

const MARK = /\[secret:([0-9a-f]+)\]/g;
const MARK_ONLY = /^\[secret:[0-9a-f]+\]$/;

const isRecord = (v: unknown): v is Record<string, unknown> =>
	typeof v === "object" && v !== null && !Array.isArray(v);

// step.args, when it parses to a JSON object.
function parsed(args: string): Record<string, unknown> | undefined {
	try {
		const v: unknown = JSON.parse(args);
		return isRecord(v) ? v : undefined;
	} catch {
		return undefined; // not JSON: shown as served
	}
}

// A call as the design writes it: `run_sql {query: "DELETE FROM users", key: ‹DB_PROD_KEY›}`,
// each secret marker shown as ‹NAME›.
export function callText(run: Run, step: Step): string {
	const name = (fp: string) => `‹${secretName(run, fp)}›`;
	const value = (v: unknown) =>
		typeof v !== "string"
			? JSON.stringify(v)
			: MARK_ONLY.test(v)
				? v.replace(MARK, (_, fp: string) => name(fp))
				: `"${v.replace(MARK, (_, fp: string) => name(fp))}"`;
	const obj = parsed(step.args);
	const body = obj
		? `{${Object.entries(obj)
				.map(([k, v]) => `${k}: ${value(v)}`)
				.join(", ")}}`
		: step.args.replace(MARK, (_, fp: string) => name(fp));
	return `${step.tool} ${body}`;
}

// Where a secret was first read: the earliest call whose result carried it.
function origin(run: Run, fp: string) {
	for (const step of run.steps) {
		const secret = step.secrets.find((s) => s.fingerprint === fp);
		if (secret) return { step, secret };
	}
}

const nameOf = (s: Secret) => s.name ?? s.kind;

function secretName(run: Run, fp: string) {
	const o = origin(run, fp);
	return o ? nameOf(o.secret) : "secret";
}

// “DB_PROD_KEY (read in .env.prod, step 3)”
export function originText(run: Run, fp: string): string {
	const o = origin(run, fp);
	if (!o) return "secret (unknown origin)";
	const path = parsed(o.step.args)?.path;
	const where = typeof path === "string" ? `in ${path}` : `by ${o.step.tool}`;
	return `${nameOf(o.secret)} (read ${where}, step ${o.step.n})`;
}

// The secrets a call carries: read in its result, or used in its arguments.
export const carried = (step: Step) => [
	...new Set([
		...step.secrets.map((s) => s.fingerprint),
		...Array.from(step.args.matchAll(MARK), (m) => m[1]),
	]),
];

export type Scored = { step: Step; legs: Legs };

// The calls the triangle scored: a call refused on a suspended key has no legs.
export const scored = (run: Run): Scored[] =>
	run.steps.flatMap((step) => (step.legs ? [{ step, legs: step.legs }] : []));

export const fmt = (v: number) => v.toFixed(2);

// The design's grey ramp: a darker cell is a higher score.
const STOPS = [0.3, 0.46, 0.62, 0.78];
export const RAMP = ["#f3f3f1", "#d6d6d3", "#a3a3a0", "#5c5c5a", "#1e1e1e"];
export const band = (v: number) => STOPS.filter((t) => v >= t).length;

// The design's bar: n cells filled up to the score, each as dark as the score it stands
// for; null for an empty cell.
export const bar = (v: number, n: number) =>
	Array.from({ length: n }, (_, i) =>
		i < Math.round(v * n) ? RAMP[Math.max(1, band((i + 1) / n))] : null,
	);

const KEYS: LegName[] = ["pressure", "opportunity", "rationalization"];

type AggLeg = {
	score: number;
	confirmed: boolean;
	facts: { t: string; at: string }[];
};
export type Agg = Record<LegName, AggLeg>;

// The design's agg over the scored calls: each leg's highest score so far, confirmed once
// a call confirmed it, and its facts, each with the step that first gave it.
export function agg(calls: Scored[]): Agg {
	const leg = (): AggLeg => ({ score: 0, confirmed: false, facts: [] });
	const out: Agg = {
		pressure: leg(),
		opportunity: leg(),
		rationalization: leg(),
	};
	for (const { step, legs } of calls)
		for (const k of KEYS) {
			const a = out[k];
			a.score = Math.max(a.score, legs[k].score);
			a.confirmed ||= legs[k].confirmed;
			for (const t of legs[k].facts)
				if (!a.facts.some((f) => f.t === t))
					a.facts.push({ t, at: `step ${step.n}` });
		}
	return out;
}

// A call's shadow decision, once there is one.
export const shadowOf = (step: Step): Shadow | undefined =>
	step.shadow ?? undefined;

// A thread is as strong as its strongest event, which also gives its quote.
export function strongestEvent(run: Run, t: Thread): CaseEvent | undefined {
	let best: CaseEvent | undefined;
	for (const i of t.events) {
		const e = run.case?.events[i];
		if (e && (!best || e.p > best.p)) best = e;
	}
	return best;
}

// Each leg's strongest open thread: what the leg shows.
export function legThreads(run: Run): Record<LegName, Thread | undefined> {
	const out: Record<LegName, Thread | undefined> = {
		pressure: undefined,
		opportunity: undefined,
		rationalization: undefined,
	};
	const strength = (t: Thread) => strongestEvent(run, t)?.p ?? 0;
	for (const t of run.case?.threads ?? []) {
		const lead = out[t.leg];
		if (t.state === "open" && (!lead || strength(t) > strength(lead)))
			out[t.leg] = t;
	}
	return out;
}

// What each leg shows: the strongest event of its strongest open thread. Rationalization
// has no threads (R and C1 are events, core/case.py), so it shows the strongest justification
// or concealment whose conclusion goes toward the crossing; one that goes away from it
// (a pause, a question, a refusal) is not evidence.
export function legEvidence(run: Run): Record<LegName, CaseEvent | undefined> {
	const open = legThreads(run);
	const lead = (events: CaseEvent[]) =>
		events.reduce<CaseEvent | undefined>(
			(best, e) => (!best || e.p > best.p ? e : best),
			undefined,
		);
	const pick = (t?: Thread) => t && strongestEvent(run, t);
	return {
		pressure: pick(open.pressure),
		opportunity: pick(open.opportunity),
		rationalization: lead(
			(run.case?.events ?? []).filter(
				(e) =>
					(e.indicator === "R" || e.indicator === "C1") &&
					e.direction === "toward",
			),
		),
	};
}

// The indicators raised by the thoughts of message `message` (an index in run.messages),
// each once, in the order they came.
export const indicatorsOn = (run: Run, message: number): Indicator[] => [
	...new Set(
		(run.case?.events ?? [])
			.filter((e) => e.message === message)
			.map((e) => e.indicator),
	),
];

// The floor's reason for a call carrying a trap key (core/floor.py).
export const TRAP = "trap key used";
