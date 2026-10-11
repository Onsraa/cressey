import { describe, expect, test } from "bun:test";
import type { Legs, Run, Step } from "@/api/types";
import { byWords, level } from "@/lib/labels";
import { layout, pos } from "./pixels";
import {
	agg,
	bar,
	callText,
	carried,
	levels,
	originText,
	RAMP,
	rows,
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
				{ after: 0, text: "a", flagged: [] },
				{ after: 0, text: "b", flagged: [] },
				{ after: 2, text: "c", flagged: [] },
				{ after: 3, text: "d", flagged: [] },
			],
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
	const leg = (
		score: number,
		confirmed = false,
		facts: string[] = [],
		words: number | null = null,
	) => ({
		score,
		confirmed,
		facts,
		words,
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
	test("each leg's highest words, kept apart from its score and never lowered", () => {
		const a = agg([
			scored(1, {
				pressure: leg(0, false, [], 0.4),
				opportunity: leg(0),
				rationalization: leg(0, false, [], 0.7),
			}),
			scored(2, {
				pressure: leg(0, false, [], 0.9),
				opportunity: leg(0),
				rationalization: leg(0),
			}),
			scored(3, {
				pressure: leg(0.1, false, [], 0.2),
				opportunity: leg(0),
				rationalization: leg(0),
			}),
		]);
		expect(a.pressure.words).toBe(0.9);
		expect(a.pressure.score).toBe(0.1);
		expect(a.rationalization.words).toBe(0.7);
		expect(a.opportunity.words).toBe(0);
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

describe("what a leg shows", () => {
	const of = (score: number, words?: number | null) => ({ score, words });
	test("the higher of its score and the agent's words, tagged only when the words lead", () => {
		expect(level(of(0, 0.9))).toBe(0.9);
		expect(level(of(0.8, 0.2))).toBe(0.8);
		expect(level(of(0.3))).toBe(0.3);
		expect(level(of(0.3, null))).toBe(0.3);
		expect(byWords(of(0, 0.9))).toBe(true);
		expect(byWords(of(0.8, 0.2))).toBe(false);
		expect(byWords(of(0.5, 0.5))).toBe(false); // a tie is the facts'
		expect(byWords(of(0.3))).toBe(false);
		expect(byWords(of(0, null))).toBe(false);
	});
	test("a call lands and is charted at those levels", () => {
		const leg = (score: number, words?: number | null) => ({
			score,
			confirmed: false,
			facts: [],
			words,
		});
		expect(
			levels({
				pressure: leg(0, 0.9),
				opportunity: leg(0.1),
				rationalization: leg(0.6, 0.4),
			}),
		).toEqual({ p: 0.9, o: 0.1, r: 0.6 });
	});
});
