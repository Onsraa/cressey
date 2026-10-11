import { describe, expect, test } from "bun:test";
import type { Legs, Run, Step } from "@/api/types";
import { phaseOf } from "./Header";
import { layout, pos } from "./pixels";
import {
	agg,
	bar,
	callText,
	carried,
	originText,
	RAMP,
	rows,
	turnEvidence,
} from "./run";

const step = (
	n: number,
	tool: string,
	args: string,
	extra: Partial<Step> = {},
): Step => ({
	n,
	tool,
	args,
	risk: "read",
	status: "allowed",
	is_error: false,
	secrets: [],
	running: false,
	...extra,
});

const KEY = {
	kind: "Named secret",
	name: "DB_PROD_KEY",
	fingerprint: "0a1b2c3d4e5f",
	line: 1,
};

const run = (extra: Partial<Run> = {}): Run => ({
	id: "r1",
	task: "t",
	mandate: {
		may_destroy: [],
		may_send_to: [],
		may_read_secrets: [],
		protected: [],
		frozen: [],
	},
	visibility: "messages",
	kind: "live",
	started_at: "2026-10-10T18:00:00Z",
	revoked: false,
	refused: 0,
	stopped: false,
	steps: [
		step(1, "run_tests", "{}", { is_error: true }),
		step(2, "read_file", '{"path": ".env.prod"}', { secrets: [KEY] }),
		step(
			3,
			"run_sql",
			'{"query": "DELETE FROM users", "key": "[secret:0a1b2c3d4e5f]"}',
			{
				risk: "destructive",
			},
		),
	],
	messages: [],
	...extra,
});

describe("rows", () => {
	test("a message said after k calls comes before call #k+1, the report last", () => {
		const r = run({
			messages: [
				{ after: 0, text: "a" },
				{ after: 0, text: "b" },
				{ after: 2, text: "c" },
				{ after: 3, text: "d" },
			].map((m) => ({ ...m, role: "agent" as const, streaming: false })),
			report: "fin",
		});
		expect(rows(r).map((x) => x.id)).toEqual([
			"m0",
			"m1",
			"c1",
			"c2",
			"m2",
			"c3",
			"m3",
			"report",
		]);
	});
});

describe("a call as the design writes it", () => {
	const r = run();
	const as = (args: string) => callText(r, step(9, "tool", args));
	test("the tool, then its arguments, each secret by its name", () => {
		expect(callText(r, r.steps[2])).toBe(
			'run_sql {query: "DELETE FROM users", key: ‹DB_PROD_KEY›}',
		);
		expect(as('{"cmd": "echo [secret:0a1b2c3d4e5f]"}')).toBe(
			'tool {cmd: "echo ‹DB_PROD_KEY›"}',
		);
	});
	test("not a JSON object: as served, markers still named", () => {
		expect(as("[1, 2]")).toBe("tool [1, 2]");
		expect(as("rm [secret:0a1b2c3d4e5f]")).toBe("tool rm ‹DB_PROD_KEY›");
		expect(as("[secret:ffffffffffff]")).toBe("tool ‹secret›");
	});
	test("non-string values stay JSON", () => {
		expect(as('{"n": 2, "to": ["a@example.test"]}')).toBe(
			'tool {n: 2, to: ["a@example.test"]}',
		);
	});
});

describe("secrets", () => {
	const r = run();
	test("the origin is the call that read it, with its path", () => {
		expect(originText(r, KEY.fingerprint)).toBe(
			"DB_PROD_KEY (read in .env.prod, step 2)",
		);
		expect(originText(r, "ffffffffffff")).toBe("secret (unknown origin)");
	});
	test("an origin without a path names its tool", () => {
		const s = run({
			steps: [step(1, "run_sql", '{"query": "SELECT 1"}', { secrets: [KEY] })],
		});
		expect(originText(s, KEY.fingerprint)).toBe(
			"DB_PROD_KEY (read by run_sql, step 1)",
		);
	});
	test("a call carries what it read and what it uses, once each", () => {
		expect(carried(r.steps[1])).toEqual([KEY.fingerprint]);
		expect(carried(r.steps[2])).toEqual([KEY.fingerprint]);
		expect(carried(r.steps[0])).toEqual([]);
	});
});

describe("triangle", () => {
	const t = layout(600, 500);
	const centre = [
		(t.P[0] + t.O[0] + t.R[0]) / 3,
		(t.P[1] + t.O[1] + t.R[1]) / 3,
	];
	const at = (p: number, o: number, r: number) => pos(t, { p, o, r });
	test("an equilateral triangle, centred, with room for the labels", () => {
		expect(t.P[0]).toBe(300);
		expect(t.O[1]).toBe(t.R[1]);
		expect(t.R[0] - t.O[0]).toBeCloseTo(t.s);
		expect(t.P[1]).toBeGreaterThanOrEqual(62);
	});
	test("equal scores, or none at all, land in the centre", () => {
		for (const p of [at(0, 0, 0), at(0.4, 0.4, 0.4)]) {
			expect(p[0]).toBeCloseTo(centre[0]);
			expect(p[1]).toBeCloseTo(centre[1]);
		}
	});
	test("a call is pulled toward its strongest leg, never onto the vertex", () => {
		const [x, y] = at(0.7, 0, 0);
		expect(x).toBeCloseTo(t.P[0]);
		expect(y).toBeGreaterThan(t.P[1]);
		expect(y).toBeLessThan(centre[1]);
		expect(at(0, 0.5, 0.5)[1]).toBeGreaterThan(centre[1]);
	});
});

describe("the gauges", () => {
	const leg = (score: number, confirmed = false, facts: string[] = []) => ({
		score,
		confirmed,
		facts,
	});
	const scored = (n: number, l: Legs) => ({
		step: step(n, "t", "{}"),
		legs: l,
	});
	test("each leg's highest score, confirmed once, facts from their first step", () => {
		const a = agg([
			scored(1, {
				pressure: leg(0.8, true, ["deadline"]),
				opportunity: leg(0.2),
				rationalization: leg(0),
			}),
			scored(2, {
				pressure: leg(0.5, false, ["deadline", "2 failures"]),
				opportunity: leg(0.9),
				rationalization: leg(0),
			}),
		]);
		expect(a.pressure.score).toBe(0.8);
		expect(a.pressure.confirmed).toBe(true);
		expect(a.pressure.facts).toEqual([
			{ t: "deadline", at: "step 1" },
			{ t: "2 failures", at: "step 2" },
		]);
		expect(a.opportunity.score).toBe(0.9);
		expect(a.opportunity.confirmed).toBe(false);
	});
	test("a bar fills up to the score, darker toward its end", () => {
		const b = bar(0.5, 10);
		expect(b.filter(Boolean)).toHaveLength(5);
		expect(b[0]).toBe(RAMP[1]);
		expect(b[4]).toBe(RAMP[2]);
		expect(b[5]).toBeNull();
		expect(bar(1, 10)[9]).toBe(RAMP[4]);
	});
});

describe("Claude Code's turns", () => {
	test("your prompt is a row of its own, where you sent it", () => {
		const said = run({
			messages: [
				{ after: 1, text: "leave prod alone", role: "user", streaming: false },
			],
		});
		const got = rows(said);
		expect(got.map((r) => r.id)).toEqual(["c1", "m0", "c2", "c3"]);
		expect(got[1]).toMatchObject({ kind: "msg", role: "user" });
	});

	test("a turn's report shows once the turn is over", () => {
		expect(rows(run({ report: "done", turn: "working" })).at(-1)?.kind).toBe(
			"call",
		);
		expect(rows(run({ report: "done", turn: "waiting" })).at(-1)?.kind).toBe(
			"report",
		);
	});
});

describe("the run's status", () => {
	const quiet = (extra: Partial<Run> = {}) => run({ steps: [], ...extra });

	test("nothing has arrived: not connected", () => {
		expect(phaseOf(quiet())).toBe("offline");
	});

	test("Claude Code connected, or done answering: waiting for a prompt", () => {
		expect(phaseOf(quiet({ turn: "waiting" }))).toBe("prompt");
	});

	test("working on a prompt: thinking, writing, or running a tool", () => {
		expect(phaseOf(quiet({ turn: "working" }))).toBe("thinking");
		const writing = {
			after: 0,
			text: "I'll",
			role: "agent" as const,
			streaming: true,
		};
		expect(phaseOf(quiet({ turn: "working", messages: [writing] }))).toBe(
			"writing",
		);
		const tool = step(1, "Read", "{}", { running: true });
		expect(phaseOf(quiet({ turn: "working", steps: [tool] }))).toBe("tool");
	});

	test("a held call and the end come first", () => {
		const held = step(1, "Bash", "{}", { status: "held", running: true });
		expect(phaseOf(quiet({ turn: "working", steps: [held] }))).toBe("held");
		const ended = "2026-10-11T02:00:00Z";
		expect(phaseOf(quiet({ turn: "waiting", ended_at: ended }))).toBe("ended");
	});

	test("an MCP agent, with no turns, is running once it acts", () => {
		expect(phaseOf(run())).toBe("running");
	});

	test("a stopped run reads Stopped, after a held call and the end", () => {
		expect(phaseOf(run({ stopped: true }))).toBe("stopped");
		expect(phaseOf(run({ stopped: true, turn: "waiting" }))).toBe("stopped");
		const ended = "2026-10-11T02:00:00Z";
		expect(phaseOf(run({ stopped: true, ended_at: ended }))).toBe("ended");
		const held = step(1, "Bash", "{}", { status: "held" });
		expect(phaseOf(run({ stopped: true, steps: [held] }))).toBe("held");
	});
});

describe("turnEvidence", () => {
	const said = (after: number, text: string, role: "agent" | "user") => ({
		after,
		text,
		role,
		streaming: false,
	});
	const steps = [
		step(1, "run_tests", "{}", { is_error: true }),
		step(2, "run_sql", "{}", { status: "rejected" }),
		step(3, "run_tests", "{}", { is_error: true }),
		step(4, "run_sql", "{}", { status: "rejected" }),
		step(5, "run_sql", "{}", { status: "expired" }),
		step(6, "read_file", "{}"),
	];
	const scores = { impossible: 0.8, way_out: 0.2 };

	test("keeps what failed or was refused after the last prompt, and the last words", () => {
		const r = run({
			steps,
			preflight: { scores, facts: [] },
			messages: [
				said(0, "first prompt", "user"),
				said(1, "before", "agent"),
				said(2, "second prompt", "user"),
				said(3, "middle", "agent"),
				said(6, "no way through", "agent"),
			],
		});
		const out = turnEvidence(r);
		expect(out.refused.map((s) => s.n)).toEqual([4, 5]);
		expect(out.failed.map((s) => s.n)).toEqual([3]);
		expect(out.said).toBe("no way through");
		expect(out.estimate).toBe(0.8);
	});

	test("with no prompt, the turn is the whole run", () => {
		const out = turnEvidence(
			run({ steps, messages: [said(1, "alone", "agent")] }),
		);
		expect(out.refused.map((s) => s.n)).toEqual([2, 4, 5]);
		expect(out.failed.map((s) => s.n)).toEqual([1, 3]);
		expect(out.said).toBe("alone");
		expect(out.estimate).toBeUndefined();
	});

	test("the agent's last words are this turn's: none said, none shown", () => {
		const out = turnEvidence(
			run({
				steps,
				messages: [said(0, "old", "agent"), said(3, "prompt", "user")],
			}),
		);
		expect(out.said).toBeUndefined();
	});
});
