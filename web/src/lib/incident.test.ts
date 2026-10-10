import { expect, test } from "bun:test";
import type { Fix, Incident, Replay } from "@/api/types";
import { stage } from "./incident";

const fix = (leg: Fix["leg"], approved: boolean): Fix => ({
	leg,
	owner_role: leg === "pressure" ? "task_author" : "key_owner",
	text: "",
	move_out: [],
	add_to_task: null,
	approved,
});
const replay = (passed: boolean): Replay => ({
	date: "2026-10-10T20:42:00Z",
	fixes: ["opportunity"],
	results: [],
	passed,
});
const leg = { score: 1, confirmed: true, facts: [] };
const incident = (over: Partial<Incident>): Incident => ({
	id: "i",
	run_id: "r",
	step: 4,
	severity: "critique",
	reason: "SQL destructeur hors mandat : users",
	created_at: "2026-10-10T20:41:43Z",
	decision: "rejected",
	sources: [],
	legs: { pressure: leg, opportunity: leg, rationalization: leg },
	guides: [],
	fixes: [fix("pressure", false), fix("opportunity", false)],
	replay: null,
	...over,
});

test("the lifecycle: held, decided, a fix approved, the replay passed", () => {
	expect(stage(incident({ decision: "held" }))).toBe(0);
	expect(stage(incident({}))).toBe(1);
	const one = [fix("pressure", false), fix("opportunity", true)];
	expect(stage(incident({ fixes: one }))).toBe(2);
	// The demo approves the key fix alone, and that replay already passes.
	expect(stage(incident({ fixes: one, replay: replay(true) }))).toBe(3);
	expect(stage(incident({ fixes: one, replay: replay(false) }))).toBe(2);
});
