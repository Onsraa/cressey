import type { Legs, Run, Secret, Step } from "@/api/types";

// What the trace lists, in order.
export type Row =
	| { id: string; kind: "call"; step: Step }
	| { id: string; kind: "msg"; text: string }
	| { id: string; kind: "report"; text: string };

// A message said after k calls goes just before call #k+1; the report comes last.
export function rows(run: Run): Row[] {
	const calls = run.steps.map((step): [number, Row] => [
		step.n,
		{ id: `c${step.n}`, kind: "call", step },
	]);
	const said = run.messages.map((m, i): [number, Row] => [
		m.after + 0.5,
		{ id: `m${i}`, kind: "msg", text: m.text },
	]);
	const all = [...calls, ...said]
		.sort((a, b) => a[0] - b[0])
		.map(([, row]) => row);
	return run.report
		? [...all, { id: "report", kind: "report", text: run.report }]
		: all;
}

const MARK = /\[secret:([0-9a-f]+)\]/g;

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

// The arguments as `name: value` pairs, each secret marker shown as ‹NAME›.
export function argsText(run: Run, args: string, sep = ", "): string {
	const obj = parsed(args);
	const text = obj
		? Object.entries(obj)
				.map(
					([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`,
				)
				.join(sep)
		: args;
	return text.replace(MARK, (_, fp: string) => `‹${secretName(run, fp)}›`);
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

export const tipOf = ({ step, legs }: Scored) =>
	`#${step.n} ${step.tool} · P ${fmt(legs.pressure.score)} · O ${fmt(legs.opportunity.score)} · R ${fmt(legs.rationalization.score)}`;

// The design's grey ramp: a darker cell is a higher score.
const STOPS = [0.3, 0.46, 0.62, 0.78];
export const RAMP = ["#f3f3f1", "#d6d6d3", "#a3a3a0", "#5c5c5a", "#1e1e1e"];
export const band = (v: number) => STOPS.filter((t) => v >= t).length;

// The floor's reason for a call carrying a trap key (core/floor.py).
export const TRAP = "trap key used";
