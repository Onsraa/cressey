import type {
	Indicator,
	Leg,
	LegName,
	Legs,
	Message,
	Run,
	Secret,
	Shadow,
	Step,
} from "@/api/types";
import { isRecord } from "@/lib/utils";

// What the trace lists, in order. A message carries the indicators its thoughts raised.
export type Row =
	| { id: string; kind: "call"; step: Step }
	| ({
			id: string;
			kind: "msg";
			indicators: Indicator[];
			stops?: Step; // the call this thought's excuse stopped (CRESSEY_THOUGHT_HOLDS)
	  } & Message)
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
		{
			...m,
			id: `m${i}`,
			kind: "msg",
			indicators: indicatorsOn(run, i),
			stops: run.steps.find(
				(s) =>
					s.stopped_by != null && run.case?.events[s.stopped_by]?.message === i,
			),
		},
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

// A call's scores as shown: each leg raised to what the case held from the agent's thoughts
// when the call came in (its shadow). Display only: `confirmed`, and so every hold, stays
// the code's.
export function shownLegs(step: Step): Legs | undefined {
	const legs = step.legs ?? undefined;
	const held = step.shadow?.legs;
	if (!legs || !held) return legs;
	const raise = (k: LegName): Leg => {
		const v = held[k] ?? 0; // a shadow recorded before the case kept legs has none
		const leg = legs[k];
		return v > leg.score
			? {
					...leg,
					score: v,
					facts: [...leg.facts, `from the agent's thoughts: ${fmt(v)}`],
				}
			: leg;
	};
	return {
		pressure: raise("pressure"),
		opportunity: raise("opportunity"),
		rationalization: raise("rationalization"),
	};
}

// The questions each leg asks of a thought (engine/case/case.py LEG); the counters and the
// plan belong to no leg.
const ASKS: Record<LegName, string[]> = {
	pressure: ["P1"],
	opportunity: ["O1", "O2", "O3"],
	rationalization: ["R", "C1"],
};

// One read thought of message `message` on each leg: its strongest question. A justification
// or concealment whose conclusion goes away from the crossing counts for nothing, as in the
// case (engine/case/case.py, thought_legs).
function thoughtScores(run: Run, message: number) {
	const away = (run.case?.events ?? []).filter(
		(e) => e.message === message && e.direction === "away",
	);
	return Object.entries(run.messages[message].scores).map(([t, p]) => {
		const leg = (k: LegName) =>
			Math.max(
				0,
				...ASKS[k].map((q) =>
					away.some((e) => e.thought === Number(t) && e.indicator === q)
						? 0
						: (p[q] ?? 0),
				),
			);
		return {
			thought: Number(t),
			legs: {
				pressure: leg("pressure"),
				opportunity: leg("opportunity"),
				rationalization: leg("rationalization"),
			},
		};
	});
}

// Every read thought of the run, in the order said, as its own point on the triangle; `at`
// places it among the calls, as `rows` does. Display only, like the scores it is drawn from.
export const thoughtDots = (run: Run) =>
	run.messages.flatMap((m, i) =>
		thoughtScores(run, i).map(({ thought, legs }) => ({
			id: `m${i}.${thought}`,
			at: m.after + 0.5,
			legs: {
				p: legs.pressure,
				o: legs.opportunity,
				r: legs.rationalization,
			},
		})),
	);

// The calls the triangle scored: a call refused on a suspended key has no legs.
export const scored = (run: Run): Scored[] =>
	run.steps.flatMap((step) => {
		const legs = shownLegs(step);
		return legs ? [{ step, legs }] : [];
	});

export const fmt = (v: number) => v.toFixed(2);

// What the stopped run shows: since the user's last prompt (a message said after k calls
// sits before call #k+1), or since its start, the calls refused or expired by a human and
// those that failed, the agent's last words, and the pre-run estimate that the task can
// fail even when done honestly.
export function turnEvidence(run: Run): {
	estimate?: number;
	refused: Step[];
	failed: Step[];
	said?: string;
} {
	const prompt = run.messages.findLastIndex((m) => m.role === "user");
	const since = run.messages[prompt]?.after ?? 0;
	const turn = run.steps.filter((s) => s.n > since);
	return {
		estimate: run.preflight?.scores.impossible,
		refused: turn.filter(
			(s) => s.status === "rejected" || s.status === "expired",
		),
		failed: turn.filter((s) => s.is_error),
		said: run.messages.slice(prompt + 1).findLast((m) => m.role === "agent")
			?.text,
	};
}

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

// The indicators raised by the thoughts of message `message` (an index in run.messages),
// each once, in the order they came.
export const indicatorsOn = (run: Run, message: number): Indicator[] => [
	...new Set(
		(run.case?.events ?? [])
			.filter((e) => e.message === message)
			.map((e) => e.indicator),
	),
];
