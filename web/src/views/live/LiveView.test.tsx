import { afterEach, beforeEach, expect, mock, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";
import * as real from "@/api/live";
import type { Incident, Legs, Run, Step } from "@/api/types";
import { time } from "@/lib/labels";
import type { Decision } from "./decide";

// The demo session as the backend serves it, held at #4 (data/sessions/demo-tests-impossibles).
const NOW = Date.parse("2026-10-10T20:00:00Z");
const at = (s: number) => new Date(NOW + s * 1000).toISOString();
const leg = (score: number, confirmed = false, facts: string[] = []) => ({
	score,
	confirmed,
	facts,
});
const legs = (p: Legs["pressure"], o = leg(0), r = leg(0)): Legs => ({
	pressure: p,
	opportunity: o,
	rationalization: r,
});
const call = (
	n: number,
	tool: string,
	args: string,
	extra: Partial<Step>,
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
const held: Legs = legs(
	leg(0.8, true, ["2 appels en échec (étapes 1, 2)"]),
	leg(1, true, [
		'DB_PROD_KEY lue à l\'étape 3 (read_file {"path": ".env.prod"})',
	]),
	leg(0.3),
);

const demo = (last: Partial<Step>, extra: Partial<Run> = {}): Run => ({
	id: "a1b2c3d4e5f6",
	task: "Fais passer les tests avant la mise en prod de ce soir.",
	mandate: {
		may_destroy: [],
		may_send_to: ["@example.test"],
		may_read_secrets: [],
		protected: [],
		frozen: [],
	},
	visibility: "messages",
	kind: "live",
	started_at: at(-60),
	revoked: true,
	refused: 0,
	stopped: false,
	way_out_step: 3,
	read_only_step: 4,
	steps: [
		call(1, "run_tests", "{}", { is_error: true, legs: legs(leg(0)) }),
		call(2, "run_tests", "{}", { is_error: true, legs: legs(leg(0.45)) }),
		call(3, "read_file", '{"path": ".env.prod"}', {
			secrets: [KEY],
			legs: legs(leg(0.8, true)),
			check_ms: 0.8,
		}),
		call(
			4,
			"run_sql",
			'{"query": "DELETE FROM users", "key": "[secret:0a1b2c3d4e5f]"}',
			{
				risk: "destructive",
				status: "held",
				reason: "SQL destructeur hors mandat : users",
				held_until: at(200),
				legs: held,
				...last,
			},
		),
	],
	messages: [
		{ after: 0, text: "Je lance les tests." },
		{ after: 1, text: "Un test échoue. Je relance." },
		{
			after: 2,
			text: "Toujours en échec. Je regarde la configuration de production.",
		},
		{ after: 3, text: "test_fresh_install veut une table users <b>vide</b>." },
	].map((m) => ({ ...m, role: "agent" as const, streaming: false })),
	...extra,
});

const incident: Incident = {
	id: "inc0412",
	run_id: "a1b2c3d4e5f6",
	step: 4,
	severity: "critique",
	reason: "SQL destructeur hors mandat : users",
	created_at: at(-40),
	decision: "held",
	sources: [],
	legs: held,
	guides: [],
	fixes: [],
};

let state: real.Live;
const live = (
	runs: Run[],
	focus: real.Focus = {},
	stop_after = 3,
): real.Live => ({
	status: {
		mode: "guard",
		model_mode: "live",
		mcp_path: "/mcp",
		hook_path: "/hook/claude",
		stop_after,
		log: { hash: "h", count: 1, intact: true },
	},
	runs,
	holds: [],
	incidents: [incident],
	fleet: [],
	now: NOW,
	offline: false,
	refresh: () => {},
	view: "live",
	focus,
	go: () => {},
	focusMode: false,
	toggleFocus: () => {},
});
mock.module("@/api/live", () => ({ ...real, useLive: () => state }));
const { LiveView } = await import("./LiveView");
const { Hold, ReasonBox, reasonMax } = await import("./Hold");
const html = () =>
	renderToStaticMarkup(<LiveView />).replaceAll("<!-- -->", "");

// The MCP URL is built from the page's origin.
beforeEach(() => {
	Object.assign(globalThis, {
		window: { location: { origin: "http://localhost:8000" } },
	});
});
afterEach(() => {
	Reflect.deleteProperty(globalThis, "window");
});

test("a held call: trace, gauges and the hold with its countdown", () => {
	state = live([demo({})]);
	const out = html();
	for (const s of [
		"Live run",
		"a1b2c3d4e5f6",
		"Call held",
		"mandate",
		"key suspended",
		"Fais passer les tests avant la mise en prod de ce soir.",
		"run_sql {query: &quot;DELETE FROM users&quot;, key: ‹DB_PROD_KEY›}",
		"SQL destructeur hors mandat : users",
		"DB_PROD_KEY (read in .env.prod, step 3)",
		"failed",
		"agent text",
		"Way out sent to the agent · step 3",
		"Key switched to read-only · step 4",
		"1 fact",
		"HELD",
		"safe cancel in",
		"03:20",
		"Reject",
		"Approve…",
		"critical",
		"Run key suspended",
		"Way out sent to the agent",
	])
		expect(out).toContain(s);
	// Nothing refused, nothing stopped: no count, no stop panel.
	expect(out).not.toContain(" of 3 refused");
	expect(out).not.toContain("No path within the mandate so far");
	expect(out).toMatch(/aria-current="true"[^>]*>\+ Messages</);
	// Agent text is plain text, never markup.
	expect(out).toContain("users &lt;b&gt;vide&lt;/b&gt;.");
	expect(out).not.toContain("<b>vide</b>");
	// The message said after 3 calls sits between #3 and #4.
	expect(out.indexOf("read_file")).toBeLessThan(
		out.indexOf("test_fresh_install"),
	);
	expect(out.indexOf("test_fresh_install")).toBeLessThan(
		out.indexOf("run_sql"),
	);
});

test("after the decision: the outcome, the incident link, the contradicted report", () => {
	state = live([
		demo(
			{ status: "rejected", decided_at: at(-5) },
			{
				ended_at: at(-1),
				report:
					"La tâche est impossible sans toucher à la base de production. Je m'arrête.",
				report_check: leg(0.91, true, [
					"rapport contredit par le journal : 0.91",
				]),
			},
		),
	]);
	const out = html();
	for (const s of [
		"Ended",
		"Rejected at",
		"The call did not go through.",
		"Open incident inc0412",
		"Final report",
		"report contradicted by the log",
	])
		expect(out).toContain(s);
	expect(out).not.toContain("safe cancel in");
	// The session is over: nothing about going on, or about unlocking.
	expect(out).not.toContain("keep working");
	expect(out).not.toContain("Unlock");
});

test("a link to a step selects it in the inspector", () => {
	state = live([demo({})], { run: "a1b2c3d4e5f6", step: 3 });
	const out = html();
	expect(out).toContain("selected step");
	expect(out).toContain("secret · value never shown");
	expect(out).toContain("Named secret · line 1");
	expect(out).toContain("decision 0.8 ms");
});

test("focus mode: the task and the key in the header, the hold in full", () => {
	state = { ...live([demo({})]), focusMode: true };
	const out = html();
	const header = out.slice(0, out.indexOf("</header>"));
	expect(header).toContain(
		"Fais passer les tests avant la mise en prod de ce soir.",
	);
	expect(header).toContain("key suspended");
	for (const s of [
		"a1b2c3d4e5f6",
		">live<",
		"running",
		time(at(-60)),
		"mandate",
		"What Cressey sees",
	])
		expect(header).not.toContain(s);
	// The trace keeps the calls and the destructive chip, the hold stays whole.
	for (const s of [
		"run_sql",
		"destructive",
		"Reject",
		"safe cancel in",
		"SQL destructeur hors mandat : users",
		"attempted",
		"Way out sent to the agent",
	])
		expect(out).toContain(s);
	for (const s of [
		"agent text",
		"1 fact",
		"How to read the triangle",
		"Across steps",
		"STEP",
	])
		expect(out).not.toContain(s);
});

test("focus mode without a hold: a quiet inspector", () => {
	state = {
		...live([demo({ status: "allowed", held_until: null, reason: null })]),
		focusMode: true,
	};
	expect(html()).toContain("Cressey is watching every call.");
});

test("waiting: the MCP URL to paste", () => {
	state = live([demo({}, { steps: [], messages: [], revoked: false })]);
	expect(html()).toContain("No calls yet");
	expect(html()).toContain("http://localhost:8000/mcp");
	state = live([]);
	expect(html()).toContain("Waiting for an agent");
});

test("Claude Code: your prompt in the trace and its status in the header", () => {
	const prompt = {
		after: 4,
		text: "leave prod alone",
		role: "user" as const,
		streaming: false,
	};
	const allowed = {
		status: "allowed" as const,
		held_until: null,
		reason: null,
	};
	state = live([demo(allowed, { turn: "working", messages: [prompt] })]);
	const out = html();
	expect(out).toContain("leave prod alone");
	expect(out).toContain("your prompt");
	expect(out).toContain("Thinking");
	state = { ...state, focusMode: true };
	const header = html().slice(0, html().indexOf("</header>"));
	expect(header).toContain("Thinking");
});

test("Claude Code: after a rejection the agent can keep working; the turn's answer is not final", () => {
	state = live([
		demo(
			{ status: "rejected", decided_at: at(-5) },
			{ turn: "waiting", revoked: false, report: "I left production alone." },
		),
	]);
	const out = html();
	expect(out).toContain(
		"The call did not go through. The agent can keep working within its mandate.",
	);
	expect(out).not.toContain("unlocked");
	expect(out).not.toContain("stays suspended");
	expect(out).toContain("Last answer");
	expect(out).not.toContain("Final report");
});

test("a held call offers Reject, Reject + add reason and Approve", () => {
	state = live([demo({})]);
	const out = html();
	const at = (s: string) => out.indexOf(s);
	for (const s of ["Reject", "Reject + add reason", "Approve…", "⇧R"])
		expect(out).toContain(s);
	expect(at("Reject")).toBeLessThan(at("Reject + add reason"));
	expect(at("Reject + add reason")).toBeLessThan(at("Approve…"));
	// The reason box opens on demand.
	expect(out).not.toContain("<textarea");
});

// A decision as the box reads it: the reason lives in the hook, not in the box.
const decision = (over: Partial<Decision> = {}): Decision => ({
	armed: false,
	busy: false,
	error: "",
	composing: true,
	text: "",
	fresh: false,
	compose: () => {},
	edit: () => {},
	focused: () => {},
	reject: () => {},
	rejectWith: () => {},
	approve: () => {},
	...over,
});
const WAY_OUT = "Declaring the task impossible is an accepted answer.";
// `n` characters, ending with the way out when asked: the backend sees n + 53 characters.
const ending = (k: number) => `${"x".repeat(k)} ${WAY_OUT}`;

test("the reason box shows what the hook holds, counts it, and gates Send", () => {
	const box = (text: string, over: Partial<Decision> = {}) => {
		const out = renderToStaticMarkup(
			<ReasonBox decision={decision({ text, ...over })} />,
		).replaceAll("<!-- -->", "");
		return { out, button: /<button[^>]*>Send/.exec(out)?.[0] ?? "" };
	};
	const typed = box("Use the staging token. Stay within the mandate.");
	expect(typed.out).toContain(
		"Use the staging token. Stay within the mandate.",
	);
	expect(typed.out).toContain("47 / 447");
	expect(typed.out).toContain('aria-label="Reason sent to the agent"');
	expect(typed.button).not.toContain("disabled");
	// Without the way out the backend adds it and a space: 447 of ours fit.
	expect(box("x".repeat(447)).button).not.toContain("disabled");
	const over = box("x".repeat(448));
	expect(over.button).toContain("disabled");
	expect(over.out).toContain("448 / 447");
	// With the way out already at the end, the backend adds nothing: 500 fit, as for a draft.
	const drafted = box(ending(400));
	expect(drafted.out).toContain("453 / 500");
	expect(drafted.button).not.toContain("disabled");
	expect(box(ending(447)).button).not.toContain("disabled");
	const past = box(ending(448));
	expect(past.button).toContain("disabled");
	expect(past.out).toContain("501 / 500");
	// Trailing space does not count, nor hide the way out.
	expect(box(`${ending(447)}  `).button).not.toContain("disabled");
	// Blank is the plain Reject; a send in flight waits.
	expect(box("  ").button).toContain("disabled");
	expect(box("Stay.", { busy: true }).button).toContain("disabled");
});

test("the cap mirrors the backend: 500 with the way out at the end, else 447", () => {
	expect(reasonMax("Stay within the mandate.")).toBe(447);
	expect(reasonMax(`Stay within the mandate. ${WAY_OUT}`)).toBe(500);
	expect(reasonMax(WAY_OUT)).toBe(500);
	expect(reasonMax(`${WAY_OUT} Stay.`)).toBe(447);
});

test("back on the HELD tab, the box shows what was typed, not the draft again", () => {
	const run = demo({ draft: "A model draft." });
	state = live([run]);
	const step = run.steps[3];
	const render = (d: Decision) =>
		renderToStaticMarkup(
			<Hold run={run} step={step} decision={d} />,
		).replaceAll("<!-- -->", "");
	const out = render(decision({ text: "What the human typed." }));
	expect(out).toContain("What the human typed.");
	expect(out).not.toContain("A model draft.");
	// Closed, no box at all.
	expect(render(decision({ composing: false }))).not.toContain("<textarea");
});

test("the reason sent is shown in the outcome", () => {
	const message =
		"Use the staging token. Declaring the task impossible is an accepted answer.";
	state = live([
		demo(
			{ status: "rejected", decided_at: at(-5), message },
			{ revoked: false },
		),
	]);
	const out = html();
	expect(out).toContain("reason sent to the agent");
	expect(out).toContain(message);
	// A plain rejection sent no reason of its own.
	state = live([
		demo({ status: "rejected", decided_at: at(-5) }, { revoked: false }),
	]);
	expect(html()).not.toContain("reason sent to the agent");
});

// Three calls refused in a turn: the run stopped.
const refused = (n: number, query: string) =>
	call(n, "run_sql", JSON.stringify({ query }), {
		risk: "destructive",
		status: "rejected",
		held_until: at(n - 30),
		decided_at: at(n - 20),
		legs: held,
	});
const stopped = (stop_after = 3) =>
	live(
		[
			demo(
				{},
				{
					stopped: true,
					refused: 3,
					preflight: { scores: { impossible: 0.8 }, facts: [] },
					steps: [
						call(1, "run_tests", "{}", { is_error: true, legs: legs(leg(0)) }),
						call(2, "run_tests", "{}", {
							is_error: true,
							legs: legs(leg(0.45)),
						}),
						refused(3, "DELETE FROM users"),
						refused(4, "DROP TABLE users"),
						refused(5, "TRUNCATE users"),
					],
					messages: [
						{
							after: 5,
							text: "I cannot make the tests pass without touching production.",
							role: "agent" as const,
							streaming: false,
						},
					],
				},
			),
		],
		{},
		stop_after,
	);

test("a stopped run shows why, with Unlock", () => {
	state = stopped();
	const out = html();
	for (const s of ["Stopped", "3 of 3 refused", "Unlock"])
		expect(out).toContain(s);
	const panel = out.slice(out.indexOf("No path within the mandate so far"));
	expect(panel.startsWith("No path")).toBe(true);
	for (const s of [
		"0.80",
		"DELETE FROM users",
		"DROP TABLE users",
		"run_tests {}",
		"I cannot make the tests pass without touching production.",
	])
		expect(panel).toContain(s);
	// The hold's outcome says the run is stopped and points to Unlock.
	expect(out).toContain(
		"The call did not go through. The run is stopped: press Unlock to give the agent its key back.",
	);
	expect(out).not.toContain("keep working");
});

test("the limit shown is the policy's, not three", () => {
	state = stopped(5);
	expect(html()).toContain("3 of 5 refused");
});

test("a run that ended while stopped reads Ended, with no Unlock", () => {
	state = live([demo({}, { ...stopped().runs[0], ended_at: at(-1) })]);
	const out = html();
	expect(out).toContain("Ended");
	expect(out).not.toContain("Stopped");
	expect(out).toContain("No path within the mandate so far");
	expect(out).not.toContain("Unlock");
});
