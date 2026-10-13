// The eval reports arrive as free-form JSON (EvalFile.report). Each reader checks the
// shape its tab needs and returns null when the report doesn't have it.

type Obj = { [key: string]: unknown };

const isObj = (v: unknown): v is Obj =>
	typeof v === "object" && v !== null && !Array.isArray(v);

const hasNumbers = <K extends string>(
	o: Obj,
	keys: readonly K[],
): o is Obj & Record<K, number> => keys.every((k) => typeof o[k] === "number");

const isStrings = (v: unknown): v is string[] =>
	Array.isArray(v) && v.every((s) => typeof s === "string");

const numOrNull = (v: unknown) => (typeof v === "number" ? v : null);

// Every item read, or null: a report with one bad item is not shown in part.
function all<T>(items: unknown, read: (v: unknown) => T | null): T[] | null {
	if (!Array.isArray(items)) return null;
	const out = items.map(read).filter((x) => x !== null);
	return out.length === items.length ? out : null;
}

export type Session = {
	session: string;
	expect: string; // « held » or « free »
	held_at: number | null;
	expected_at: number | null; // the call an incident must be held at, when it names one
	reason: string | null;
};

const COUNTS = [
	"incident_sessions",
	"incident_held",
	"normal_sessions",
	"normal_held",
	"check_ms_p50",
	"check_ms_p95",
] as const;

export type Detection = Record<(typeof COUNTS)[number], number> & {
	mode: string; // the report's model_mode: live Jev, or recorded answers
	stop_ms_p50: number | null; // null when no session was held
	stop_ms_p95: number | null;
	misses: string[];
	sessions: Session[];
};

function readSession(v: unknown): Session | null {
	if (!isObj(v) || typeof v.session !== "string") return null;
	if (typeof v.expect !== "string") return null;
	const reason = typeof v.reason === "string" ? v.reason : null;
	return {
		session: v.session,
		expect: v.expect,
		held_at: numOrNull(v.held_at),
		expected_at: numOrNull(v.expected_at),
		reason,
	};
}

export function readDetection(r: unknown): Detection | null {
	if (!isObj(r) || !hasNumbers(r, COUNTS) || !isStrings(r.misses)) return null;
	if (typeof r.model_mode !== "string") return null;
	const sessions = all(r.sessions, readSession);
	if (!sessions) return null;
	return {
		...r,
		mode: r.model_mode,
		stop_ms_p50: numOrNull(r.stop_ms_p50),
		stop_ms_p95: numOrNull(r.stop_ms_p95),
		misses: r.misses,
		sessions,
	};
}

const GUIDES = [
	"n_questions",
	"hit_at_3_bm25",
	"hit_at_3_hybrid",
	"hit_at_3_reranked",
	"n_out_of_scope",
	"unsure_correct",
	"n_incidents",
	"citation_validity",
	"latency_p50_ms",
	"latency_p95_ms",
] as const;

export type Guides = Record<(typeof GUIDES)[number], number>;

export const readGuides = (r: unknown): Guides | null =>
	isObj(r) && hasNumbers(r, GUIDES) ? r : null;

export type Ablation = {
	floor: Detection;
	both: Detection;
	only_triangle: string[]; // sessions held only when the triangle may hold
	only_floor: string[];
};

export function readAblation(r: unknown): Ablation | null {
	if (!isObj(r) || !isStrings(r.only_triangle) || !isStrings(r.only_floor))
		return null;
	const floor = readDetection(r.floor);
	const both = readDetection(r.both);
	if (!floor || !both) return null;
	return {
		floor,
		both,
		only_triangle: r.only_triangle,
		only_floor: r.only_floor,
	};
}

export type Scored = { id: string; label: "yes" | "no"; score: number };

export type JudgedSet = {
	n: number;
	threshold: number;
	accuracy: string; // « 30/30 », as the report writes it
	margin: number;
	ece: number;
	scores: Scored[];
};

export type Attack = { id: string; deltas: number[]; floorHeld: boolean };

const CALLS = ["label", "judgment", "report"] as const;

export type Latency = {
	call: (typeof CALLS)[number];
	n: number;
	p50_ms: number;
};

export type Decision = {
	model: string;
	mode: string;
	price: number; // USD per million input tokens
	write: JudgedSet;
	report: JudgedSet;
	attack: Attack[];
	latency: Latency[];
};

function readScored(v: unknown): Scored | null {
	if (!isObj(v) || typeof v.id !== "string" || typeof v.score !== "number")
		return null;
	if (v.label !== "yes" && v.label !== "no") return null;
	return { id: v.id, label: v.label, score: v.score };
}

function readSet(v: unknown): JudgedSet | null {
	if (!isObj(v) || !isObj(v.calibration)) return null;
	const c = v.calibration;
	if (!hasNumbers(c, ["n", "threshold", "margin", "ece"])) return null;
	if (typeof c.accuracy_overall !== "string") return null;
	const scores = all(v.scores, readScored);
	if (!scores) return null;
	const { n, threshold, margin, ece } = c;
	return { n, threshold, accuracy: c.accuracy_overall, margin, ece, scores };
}

function readAttack(v: unknown): Attack | null {
	if (!isObj(v) || typeof v.id !== "string" || !isObj(v.variants)) return null;
	const deltas = all(Object.values(v.variants), (x) =>
		isObj(x) && typeof x.delta === "number" ? x.delta : null,
	);
	if (!deltas) return null;
	// The floor held when its verdict didn't depend on the injected text.
	const floorHeld = isObj(v.floor) && v.floor.depends_on_text === false;
	return { id: v.id, deltas, floorHeld };
}

export function readDecision(r: unknown): Decision | null {
	if (!isObj(r) || typeof r.decision_model !== "string") return null;
	if (typeof r.mode !== "string" || !isObj(r.latency_per_call)) return null;
	const per = r.latency_per_call;
	const latency = CALLS.map((call) => {
		const l = per[call];
		return isObj(l) && hasNumbers(l, ["n", "p50_ms"])
			? { call, n: l.n, p50_ms: l.p50_ms }
			: null;
	}).filter((l) => l !== null);
	const price = r.price_per_million_input_tokens_usd;
	const write = readSet(r.write_judgment);
	const report = readSet(r.report_check);
	const attack = all(r.attack, readAttack);
	if (typeof price !== "number" || !write || !report || !attack) return null;
	if (latency.length < CALLS.length) return null;
	return {
		model: r.decision_model,
		mode: r.mode,
		price,
		write,
		report,
		attack,
		latency,
	};
}
