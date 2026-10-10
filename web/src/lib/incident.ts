import type { Incident } from "@/api/types";

// An incident's lifecycle (dashboard.md): held → decided → fix approved → replay passed.
export const LIFE = [
	"held",
	"decided",
	"fix approved",
	"replay passed",
] as const;

// How far along the lifecycle an incident is, 0 to 3. The decision is the held call's
// status: « held » while it waits. One approved fix is enough when its replay passes.
export function stage(i: Incident): number {
	if (i.decision === "held") return 0;
	if (!(i.fixes ?? []).some((f) => f.approved)) return 1;
	return i.replay?.passed ? 3 : 2;
}
