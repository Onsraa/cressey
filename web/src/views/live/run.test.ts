import { describe, expect, test } from "bun:test";
import type {
	CaseEvent,
	Indicator,
	LegName,
	Legs,
	Run,
	Step,
	Thread,
} from "@/api/types";
import { phaseOf } from "./Header";
import { layout, mix, pos } from "./pixels";
import {
	agg,
	bar,
	callText,
	carried,
	indicatorsOn,
	legEvidence,
	legThreads,
	originText,
	RAMP,
	rows,
	shadowOf,
	shownLegs,
	strongestEvent,
	thoughtLegs,
	turnEvidence,
} from "./run";

// A message's fields beyond its text, role and streaming: where the words come from, and the thoughts cut from them.
const words = {
	source: "narration" as const,
	thoughts: [],
	read: 0,
	scores: {},
};

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
	reasons: [],
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
			].map((m) => ({
				...m,
				...words,
				role: "agent" as const,
				streaming: false,
			})),
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
	test("a resized triangle glides to its new place, equilateral all the way", () => {
		const to = layout(600, 380); // shorter: smaller and higher
		for (const k of [0, 0.5, 1]) {
			const g = mix(t, to, k);
			expect(g.P[1]).toBeCloseTo(t.P[1] + (to.P[1] - t.P[1]) * k);
			expect(g.s).toBeCloseTo(t.s + (to.s - t.s) * k);
			expect(g.R[0] - g.O[0]).toBeCloseTo(g.s);
			expect(g.O[1] - g.P[1]).toBeCloseTo((g.s * Math.sqrt(3)) / 2);
		}
		expect(mix(t, to, 1).O[1]).toBeCloseTo(to.O[1]);
	});
	test("a call is pulled toward its strongest leg, never onto the vertex", () => {
		const [x, y] = at(0.7, 0, 0);
		expect(x).toBeCloseTo(t.P[0]);
		expect(y).toBeGreaterThan(t.P[1]);
		expect(y).toBeLessThan(centre[1]);
		expect(at(0, 0.5, 0.5)[1]).toBeGreaterThan(centre[1]);
	});
});

describe("a thought on the triangle", () => {
	const said = run({
		messages: [
			{
				...words,
				after: 1,
				text: "Still failing. Nobody checks scripts. We can modify it! But no.",
				role: "agent",
				streaming: false,
				thoughts: [
					"Still failing.",
					"Nobody checks scripts.",
					"We can modify it! But no.",
				],
				scores: {
					0: { P1: 0.97, O1: 0.1, R: 0.2, N1: 0.9 },
					1: { O2: 0.95, R: 0.7, C1: 0.68 },
					2: { O3: 0.39, R: 0.1, C1: 0.57 },
				},
			},
		],
		case: {
			events: (["toward", "away"] as const).map(
				(direction, i): CaseEvent => ({
					indicator: "C1",
					p: 0.6,
					quote: "",
					source: "narration",
					after: 1,
					objects: [],
					message: 0,
					thought: i + 1,
					direction,
				}),
			),
			threads: [],
			approved: [],
		},
	});
	test("each leg is its strongest thought, each thought's score a fact", () => {
		const legs = thoughtLegs(said, 0);
		expect(legs?.pressure).toEqual({
			score: 0.97,
			confirmed: false,
			facts: ["“Still failing.” 0.97"],
		});
		expect(legs?.opportunity.score).toBe(0.95);
		expect(legs?.opportunity.facts[0]).toBe("“Nobody checks scripts.” 0.95");
	});
	test("a concealment going away from the crossing is no justification", () => {
		expect(thoughtLegs(said, 0)?.rationalization.facts).toEqual([
			"“Nobody checks scripts.” 0.70",
			"“Still failing.” 0.20",
			"“We can modify it! But no.” 0.10",
		]);
	});
	test("a message read by nobody yet has no score, and its row carries them", () => {
		expect(
			thoughtLegs(run({ messages: [{ ...said.messages[0], scores: {} }] }), 0),
		).toBeUndefined();
		const row = rows(said).find((x) => x.kind === "msg");
		expect(row?.kind === "msg" && row.legs?.pressure.score).toBe(0.97);
	});
	test("the thought whose excuse stopped the agent carries the call it stopped", () => {
		const held = step(2, "read_file", "{}", { stopped_by: 0, status: "held" });
		const stopped = rows({ ...said, steps: [step(1, "t", "{}"), held] });
		const msg = stopped.find((x) => x.kind === "msg");
		expect(msg?.kind === "msg" && msg.stops?.n).toBe(2);
		const quiet = rows(said).find((x) => x.kind === "msg");
		expect(quiet?.kind === "msg" && quiet.stops).toBeUndefined();
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
	test("a call's scores rise to what the agent's thoughts held, and only facts confirm", () => {
		const legs = {
			pressure: leg(0.2, true, ["2 failed calls"]),
			opportunity: leg(0),
			rationalization: leg(0.7),
		};
		const shadow = {
			decision: "allow" as const,
			why: [],
			uses: [],
			words_read: true,
			legs: { pressure: 0.9, opportunity: 0.85, rationalization: 0.4 },
		};
		const shown = shownLegs(step(1, "t", "{}", { legs, shadow }));
		expect(shown?.pressure).toEqual(
			leg(0.9, true, ["2 failed calls", "from the agent's thoughts: 0.90"]),
		);
		expect(shown?.opportunity.score).toBe(0.85);
		expect(shown?.opportunity.confirmed).toBe(false);
		expect(shown?.rationalization).toEqual(legs.rationalization);
		expect(shownLegs(step(1, "t", "{}", { legs }))).toEqual(legs);
		expect(shownLegs(step(1, "t", "{}"))).toBeUndefined();
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

describe("the case", () => {
	const event = (
		indicator: Indicator,
		p: number,
		extra: Partial<CaseEvent> = {},
	): CaseEvent => ({
		indicator,
		p,
		quote: `${indicator} at ${p}`,
		source: "narration",
		after: 0,
		objects: [],
		...extra,
	});
	const thread = (
		leg: LegName,
		events: number[],
		state: Thread["state"] = "open",
	): Thread => ({ leg, state, outside: false, events });
	const withCase = (events: CaseEvent[], threads: Thread[] = []) =>
		run({ case: { events, threads, approved: [] } });

	test("a leg's thread is the strongest open one, as strong as its strongest event", () => {
		const r = withCase(
			[
				event("P1", 0.5, { objects: ["a"] }),
				event("P1", 0.9, { objects: ["a"] }),
				event("P1", 0.7, { objects: ["b"] }),
				event("P3", 0.95, { objects: ["c"] }),
				event("O1", 0.4, { objects: ["d"] }),
				event("O1", 0.6, { objects: ["e"] }),
			],
			[
				thread("pressure", [0, 1]),
				thread("pressure", [2]),
				thread("pressure", [3], "shared"),
				thread("opportunity", [4]),
				thread("opportunity", [5]),
			],
		);
		const got = legThreads(r);
		expect(got.pressure).toBe(r.case?.threads[0]);
		expect(got.opportunity).toBe(r.case?.threads[4]);
		// Rationalization has no thread; a closed thread never leads.
		expect(got.rationalization).toBeUndefined();
		const lead = got.pressure;
		expect(lead && strongestEvent(r, lead)?.quote).toBe("P1 at 0.9");
	});

	test("rationalization shows its strongest justification that goes toward the crossing", () => {
		const r = withCase([
			event("R", 0.9, { direction: "away", quote: "I should pause" }),
			event("R", 0.5, { direction: "toward", quote: "weak" }),
			event("C1", 0.7, { direction: "toward", quote: "hide the trace" }),
			event("R", 0.95, { quote: "no direction" }),
			event("P1", 0.99, { direction: "toward", quote: "not a justification" }),
		]);
		expect(legEvidence(r).rationalization?.quote).toBe("hide the trace");
		// Away from the crossing, or neither: not evidence.
		const away = withCase([
			event("R", 0.9, { direction: "away" }),
			event("R", 0.8, { direction: "neither" }),
			event("C1", 0.8),
		]);
		expect(legEvidence(away).rationalization).toBeUndefined();
		expect(legEvidence(run()).rationalization).toBeUndefined();
	});

	test("pressure and opportunity keep the strongest open thread's strongest event", () => {
		const r = withCase(
			[
				event("P1", 0.5, { objects: ["a"] }),
				event("P1", 0.9, { objects: ["a"] }),
				event("P3", 0.99, { objects: ["b"] }),
				event("O1", 0.6, { objects: ["c"] }),
			],
			[
				thread("pressure", [0, 1]),
				thread("pressure", [2], "shared"),
				thread("opportunity", [3]),
			],
		);
		const got = legEvidence(r);
		expect(got.pressure?.quote).toBe("P1 at 0.9");
		expect(got.opportunity?.quote).toBe("O1 at 0.6");
	});

	test("no case yet: no thread on any leg", () => {
		expect(legThreads(run())).toEqual({
			pressure: undefined,
			opportunity: undefined,
			rationalization: undefined,
		});
	});

	test("a message lists the indicators its thoughts raised, once each", () => {
		const r = withCase([
			event("P1", 0.9, { message: 0, thought: 0 }),
			event("O1", 0.8, { message: 0, thought: 1 }),
			event("P1", 0.7, { message: 0, thought: 2 }),
			event("R", 0.6, { message: 1, thought: 0 }),
			event("O4", 1, { source: "code" }),
		]);
		expect(indicatorsOn(r, 0)).toEqual(["P1", "O1"]);
		expect(indicatorsOn(r, 1)).toEqual(["R"]);
		expect(indicatorsOn(r, 2)).toEqual([]);
		expect(indicatorsOn(run(), 0)).toEqual([]);
	});

	test("a message row carries its indicators", () => {
		const r = withCase([event("N1", 0.8, { message: 1 })]);
		const said = {
			...r,
			messages: ["a", "b"].map((text, i) => ({
				...words,
				after: i,
				text,
				role: "agent" as const,
				streaming: false,
			})),
		};
		expect(
			rows(said).flatMap((x) => (x.kind === "msg" ? [x.indicators] : [])),
		).toEqual([[], ["N1"]]);
	});

	test("a step's shadow, or none yet", () => {
		const shadow = {
			decision: "hold" as const,
			why: ["Uses: secret:0a1b2c3d4e5f"],
			uses: [],
			words_read: true,
			legs: {},
		};
		expect(shadowOf(step(1, "t", "{}", { shadow }))).toEqual(shadow);
		expect(shadowOf(step(1, "t", "{}", { shadow: null }))).toBeUndefined();
		expect(shadowOf(step(1, "t", "{}"))).toBeUndefined();
	});
});

describe("Claude Code's turns", () => {
	test("your prompt is a row of its own, where you sent it", () => {
		const said = run({
			messages: [
				{
					...words,
					after: 1,
					text: "leave prod alone",
					role: "user",
					streaming: false,
				},
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
			...words,
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
		...words,
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
