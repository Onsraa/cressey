import type {
	Incident,
	Leg,
	LegName,
	OwnerGuide,
	Responses,
	Run,
	Step,
	StepStatus,
} from "@/api/types";
import {
	Ban,
	Bell,
	Check,
	ChevronsUp,
	CirclePause,
	CircleX,
	Eye,
	Hourglass,
	type IconType,
	Pause,
	Pencil,
	SquareCheck,
	Trash2,
	TriangleAlert,
	X,
} from "@/components/icons";

// The interface is in English; every label the views show lives here.

export type Tone = "ok" | "held" | "warn" | "info" | "grey";

// Background, text and border of a chip in each tone.
export const TONE: Record<Tone, string> = {
	ok: "bg-ok text-ok-fg border-ok-bd",
	held: "bg-held text-held-fg border-held-bd",
	warn: "bg-warn text-warn-fg border-warn-bd",
	info: "bg-info text-info-fg border-info-bd",
	grey: "bg-grey text-mute border-grey-bd",
};

export const LEGS: {
	k: LegName;
	L: "P" | "O" | "R";
	name: string;
	color: string;
}[] = [
	{ k: "pressure", L: "P", name: "Pressure", color: "var(--color-p)" },
	{ k: "opportunity", L: "O", name: "Opportunity", color: "var(--color-o)" },
	{
		k: "rationalization",
		L: "R",
		name: "Rationalization",
		color: "var(--color-r)",
	},
];

// What a leg shows: its score, or what the agent's words say of it when that is higher.
// The words are display only: they confirm nothing and hold nothing.
type Said = Pick<Leg, "score" | "words">;
export const level = (leg: Said) => Math.max(leg.score, leg.words ?? 0);
export const byWords = (leg: Said) => (leg.words ?? 0) > leg.score;
export const FROM_WORDS = "from the agent's words";

// What the decision model reads in an agent message, by the key it is served under.
// Manipulation counts as rationalization.
export const MESSAGE_LABEL = {
	pressure: "Pressure",
	rationalization: "Rationalization",
	manipulation: "Manipulation",
};

type Look = { label: string; Icon: IconType; tone: Tone; tip: string };

// A step's status, as the design's ST map. Rejected and refused are safe outcomes, hence
// green. « failed » is no status of its own: an allowed call that returned an error.
export type Shown = StepStatus | "failed";

export const STATUS: Record<Shown, Look> = {
	allowed: {
		label: "allowed",
		Icon: Check,
		tone: "ok",
		tip: "Allowed: went straight through",
	},
	alerted: {
		label: "alerted",
		Icon: Bell,
		tone: "warn",
		tip: "Alerted: the call went through, an incident is open",
	},
	held: {
		label: "held",
		Icon: Pause,
		tone: "held",
		tip: "Held: waiting for a human decision",
	},
	approved: {
		label: "approved",
		Icon: SquareCheck,
		tone: "warn",
		tip: "Approved by a human, then executed",
	},
	rejected: {
		label: "rejected",
		Icon: X,
		tone: "ok",
		tip: "Rejected by a human: not executed",
	},
	expired: {
		label: "expired",
		Icon: Hourglass,
		tone: "warn",
		tip: "No decision in time: safely cancelled",
	},
	denied: {
		label: "refused",
		Icon: Ban,
		tone: "ok",
		tip: "Refused outright by Cressey, without waiting",
	},
	would_hold: {
		label: "would have been held",
		Icon: CirclePause,
		tone: "grey",
		tip: "Replay: would have been held against the real policy",
	},
	failed: {
		label: "failed",
		Icon: CircleX,
		tone: "grey",
		tip: "Failed: the call returned an error",
	},
};

export const shown = (s: Step): Shown =>
	s.status === "allowed" && s.is_error ? "failed" : s.status;

export const RISK: Record<Step["risk"], Omit<Look, "tip">> = {
	read: { label: "read", Icon: Eye, tone: "grey" },
	write: { label: "write", Icon: Pencil, tone: "warn" },
	destructive: { label: "destructive", Icon: Trash2, tone: "held" },
};

export const SEVERITY: Record<Incident["severity"], Omit<Look, "tip">> = {
	critique: { label: "critical", Icon: TriangleAlert, tone: "held" },
	haute: { label: "high", Icon: ChevronsUp, tone: "warn" },
};

export const ROLE: Record<OwnerGuide["owner_role"], string> = {
	key_owner: "Key owner",
	task_author: "Task author",
	platform_owner: "Platform owner",
	soc: "SOC",
};

export const GUIDE_STATUS: Record<OwnerGuide["status"], string> = {
	pending: "writing…",
	ok: "ready",
	unsure: "I don’t know",
	unavailable: "unavailable",
};

export const KIND: Record<Run["kind"], string> = {
	live: "live",
	replay: "replay",
	control: "Observer",
};

// How a run's calls reach Cressey: the MCP proxy, or the Claude Code hook.
export const VIA: Record<"mcp" | "hook", string> = {
	mcp: "via MCP",
	hook: "via hook",
};

export const VISIBILITY: Record<Run["visibility"], string> = {
	tools: "Tool calls",
	messages: "+ Messages",
	reasoning: "+ Reasoning",
};

export const RESPONSE: Record<Responses["floor"], string> = {
	alert: "Alert",
	review: "Human review",
	stop: "Stop",
};

export const CHECK: Record<keyof Responses, string> = {
	floor: "Safety floor",
	trap_key: "Decoy key",
	triangle: "Triangle",
	fleet: "Cross-run signal",
};

export const time = (iso?: string | null) =>
	iso ? new Date(iso).toLocaleTimeString("en-GB") : ""; // 24-hour, shorter on a projector

// The countdown to `until`, as the design's clock: “03:20”, rounded up.
export function clock(until: string | null | undefined, now: number) {
	const v = until
		? Math.max(0, Math.ceil((Date.parse(until) - now) / 1000))
		: 0;
	return `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}`;
}

// The checks currently on “Alert”: Cressey lets their calls through.
export const onAlert = (r?: Responses) =>
	r
		? (["floor", "trap_key", "triangle"] as const).filter(
				(k) => r[k] === "alert",
			)
		: [];
