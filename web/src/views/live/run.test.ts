import { describe, expect, test } from "bun:test";
import type { Legs, Run, Step } from "@/api/types";
import { heat, place, triangle } from "./geometry";
import { argsText, carried, originText, rows } from "./run";

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

const legs = (p: number, o: number, r: number): Legs => ({
	pressure: { score: p, confirmed: false, facts: [] },
	opportunity: { score: o, confirmed: false, facts: [] },
	rationalization: { score: r, confirmed: false, facts: [] },
});

describe("rows", () => {
	test("a message said after k calls comes before call #k+1, the report last", () => {
		const r = run({
			messages: [
				{ after: 0, text: "a" },
				{ after: 0, text: "b" },
				{ after: 2, text: "c" },
				{ after: 3, text: "d" },
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

describe("arguments", () => {
	const r = run();
	test("pairs, each secret by its name", () => {
		expect(argsText(r, r.steps[2].args)).toBe(
			"query: DELETE FROM users, key: ‹DB_PROD_KEY›",
		);
		expect(argsText(r, r.steps[2].args, "\n")).toBe(
			"query: DELETE FROM users\nkey: ‹DB_PROD_KEY›",
		);
	});
	test("not a JSON object: as served, markers still named", () => {
		expect(argsText(r, "[1, 2]")).toBe("[1, 2]");
		expect(argsText(r, "rm [secret:0a1b2c3d4e5f]")).toBe("rm ‹DB_PROD_KEY›");
		expect(argsText(r, "[secret:ffffffffffff]")).toBe("‹secret›");
	});
	test("non-string values stay JSON", () => {
		expect(argsText(r, '{"n": 2, "to": ["a@example.test"]}')).toBe(
			'n: 2, to: ["a@example.test"]',
		);
	});
});

describe("secrets", () => {
	const r = run();
	test("the origin is the call that read it, with its path", () => {
		expect(originText(r, KEY.fingerprint)).toBe(
			"DB_PROD_KEY (lue dans .env.prod, étape 2)",
		);
		expect(originText(r, "ffffffffffff")).toBe("secret (origine inconnue)");
	});
	test("an origin without a path names its tool", () => {
		const s = run({
			steps: [step(1, "run_sql", '{"query": "SELECT 1"}', { secrets: [KEY] })],
		});
		expect(originText(s, KEY.fingerprint)).toBe(
			"DB_PROD_KEY (lue par run_sql, étape 1)",
		);
	});
	test("a call carries what it read and what it uses, once each", () => {
		expect(carried(r.steps[1])).toEqual([KEY.fingerprint]);
		expect(carried(r.steps[2])).toEqual([KEY.fingerprint]);
		expect(carried(r.steps[0])).toEqual([]);
	});
});

describe("triangle", () => {
	const t = triangle(600, 500);
	const centre = {
		x: (t.pressure.x + t.opportunity.x + t.rationalization.x) / 3,
		y: (t.pressure.y + t.opportunity.y + t.rationalization.y) / 3,
	};
	test("a call sits at the barycentre of its scores", () => {
		for (const p of [place(t, legs(0, 0, 0)), place(t, legs(0.4, 0.4, 0.4))]) {
			expect(p.x).toBeCloseTo(centre.x);
			expect(p.y).toBeCloseTo(centre.y);
		}
		expect(place(t, legs(0.7, 0, 0))).toEqual(t.pressure);
		expect(place(t, legs(0, 0.5, 0.5)).y).toBeCloseTo(t.opportunity.y);
	});
	test("only a held call's heat is salmon", () => {
		const at = place(t, legs(1, 1, 1));
		expect(
			heat(t, 600, 500, [{ at, score: 1, held: false }], 1).some((c) => c.hot),
		).toBe(false);
		expect(
			heat(t, 600, 500, [{ at, score: 1, held: true }], 1).some((c) => c.hot),
		).toBe(true);
	});
});
