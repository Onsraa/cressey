import { expect, test } from "bun:test";
import { readAblation, readDecision, readDetection, readGuides } from "./read";

// The reports /api/eval serves, as they sit in the backend.
const report = (name: string) =>
	Bun.file(
		new URL(`../../../../backend/data/eval/${name}`, import.meta.url),
	).json();

test("the readers accept the reports the backend writes", async () => {
	expect(readDetection(await report("report-detection.json"))).not.toBeNull();
	expect(readGuides(await report("report-dev.json"))).not.toBeNull();
	expect(readAblation(await report("report-ablation.json"))).not.toBeNull();
	const decision = readDecision(await report("decision-model.json"));
	expect(decision?.latency.map((l) => l.call)).toEqual([
		"label",
		"judgment",
		"report",
	]);
});

test("a report missing a field is refused, not shown in part", () => {
	expect(readDetection({ incident_held: 6, misses: [] })).toBeNull();
	expect(readGuides({ split: "dev" })).toBeNull();
	expect(readDecision({ decision_model: "jev", mode: "live" })).toBeNull();
});

test("a detection report keeps the model mode it was measured in", async () => {
	const shipped = await report("report-detection.json");
	expect(readDetection(shipped)?.mode).toBe(shipped.model_mode);
	expect(readDetection({ ...shipped, model_mode: "live" })?.mode).toBe("live");
	// Unlabelled, its times can't say what they measured: the report is refused.
	expect(readDetection({ ...shipped, model_mode: undefined })).toBeNull();
});
