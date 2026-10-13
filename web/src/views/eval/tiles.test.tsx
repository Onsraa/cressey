import { expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";
import type { EvalFile } from "@/api/types";
import { sample } from "@/lib/format";
import { DetectionTab } from "./DetectionTab";
import { GuidesTab } from "./GuidesTab";
import type { Detection, Guides } from "./read";

const file: EvalFile = {
	kind: "detection",
	split: "dev",
	file: "data/eval/report-detection.json",
	date: "2026-10-11T04:17:32+00:00",
	report: {},
};

const detection: Detection = {
	incident_sessions: 7,
	incident_held: 7,
	normal_sessions: 6,
	normal_held: 0,
	stop_ms_p50: 1.2,
	stop_ms_p95: 450,
	check_ms_p50: 0.6,
	check_ms_p95: 1.3,
	misses: [],
	sessions: [],
	mode: "live",
};
const sessions = (mode: string) =>
	renderToStaticMarkup(<DetectionTab file={file} d={{ ...detection, mode }} />);

test("the time tiles say whether Jev answered live or from recordings", () => {
	const stops = `${sample(7)} held sessions`;
	const live = sessions("live");
	expect(live).toContain(`${stops} · live Jev`);
	expect(live).toContain("Cressey’s decision per call · live Jev");
	for (const mode of ["replay-first", "replay"]) {
		const recorded = sessions(mode);
		expect(recorded).toContain(`${stops} · recorded answers`);
		expect(recorded).toContain(
			"Cressey’s decision per call · recorded answers",
		);
		expect(recorded).not.toContain("live Jev");
	}
});

test("the latency tile counts the guides it was timed over, not the questions", () => {
	const g: Guides = {
		n_questions: 31,
		hit_at_3_bm25: 0.65,
		hit_at_3_hybrid: 0.94,
		hit_at_3_reranked: 0.97,
		n_out_of_scope: 2,
		unsure_correct: 2,
		n_incidents: 8,
		citation_validity: 1,
		latency_p50_ms: 6530,
		latency_p95_ms: 8800,
	};
	const html = renderToStaticMarkup(
		<GuidesTab file={{ ...file, kind: "guides" }} g={g} />,
	);
	expect(html).toContain(`${sample(8)} guides`);
});
