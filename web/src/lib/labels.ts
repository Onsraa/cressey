import type { LucideIcon } from "lucide-react";
import {
	Ban,
	BellRing,
	Check,
	ChevronsUp,
	CirclePause,
	Eye,
	Hourglass,
	Pause,
	Pencil,
	Plug,
	SquareCheck,
	Trash,
	TriangleAlert,
	Webhook,
	X,
} from "lucide-react";
import type {
	Incident,
	LegName,
	OwnerGuide,
	Responses,
	Run,
	Step,
	StepStatus,
} from "@/api/types";

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

type Look = { label: string; Icon: LucideIcon; tone: Tone; tip: string };

// A step's status. Rejected and refused are safe outcomes, hence green, as in the design.
export const STATUS: Record<StepStatus, Look> = {
	allowed: {
		label: "allowed",
		Icon: Check,
		tone: "ok",
		tip: "Allowed: passed through as is",
	},
	alerted: {
		label: "alerted",
		Icon: BellRing,
		tone: "warn",
		tip: "Alerted: the response is “Alert”, the call went through and an incident is open",
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
		tip: "Approved by a human, then run",
	},
	rejected: {
		label: "rejected",
		Icon: X,
		tone: "ok",
		tip: "Rejected by a human: not run",
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
		tip: "Refused by Cressey, without waiting",
	},
	would_hold: {
		label: "would have been held",
		Icon: CirclePause,
		tone: "held",
		tip: "Replay: this call would have been held, and the replay fails",
	},
};

export const RISK: Record<Step["risk"], Omit<Look, "tip">> = {
	read: { label: "read", Icon: Eye, tone: "grey" },
	write: { label: "write", Icon: Pencil, tone: "warn" },
	destructive: { label: "destructive", Icon: Trash, tone: "held" },
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
	pending: "writing the guide…",
	ok: "ok",
	unsure: "I don't know — ask the security team",
	unavailable: "unavailable",
};

export const KIND: Record<Run["kind"], string> = {
	live: "live",
	replay: "replay",
	control: "Observer",
};

// How a run's calls reach Cressey: the MCP proxy, or the Claude Code hook.
export const VIA: Record<
	"mcp" | "hook",
	{ label: string; Icon: LucideIcon; tip: string }
> = {
	mcp: {
		label: "via MCP",
		Icon: Plug,
		tip: "Calls reach Cressey through the MCP proxy",
	},
	hook: {
		label: "via hook",
		Icon: Webhook,
		tip: "Calls reach Cressey through the Claude Code hook (shell, files, reasoning)",
	},
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
	trap_key: "Trap key",
	triangle: "Triangle",
	fleet: "Signal across runs",
};

export const time = (iso?: string | null) =>
	iso ? new Date(iso).toLocaleTimeString("en-GB") : ""; // 24-hour, shorter on a projector

// The checks currently on “Alert”: Cressey lets their calls through.
export const onAlert = (r?: Responses) =>
	r
		? (["floor", "trap_key", "triangle"] as const).filter(
				(k) => r[k] === "alert",
			)
		: [];
