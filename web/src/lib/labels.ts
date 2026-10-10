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
	SquareCheck,
	Trash,
	TriangleAlert,
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

// The interface is in French (dashboard.md); every label the views show lives here.

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
	{ k: "pressure", L: "P", name: "Pression", color: "var(--color-p)" },
	{ k: "opportunity", L: "O", name: "Opportunité", color: "var(--color-o)" },
	{
		k: "rationalization",
		L: "R",
		name: "Rationalisation",
		color: "var(--color-r)",
	},
];

type Look = { label: string; Icon: LucideIcon; tone: Tone; tip: string };

// A step's status. Rejected and refused are safe outcomes, hence green, as in the design.
export const STATUS: Record<StepStatus, Look> = {
	allowed: {
		label: "autorisé",
		Icon: Check,
		tone: "ok",
		tip: "Autorisé : passé tel quel",
	},
	alerted: {
		label: "alerté",
		Icon: BellRing,
		tone: "warn",
		tip: "Alerté : la réponse est « alerte », l'appel est passé et un incident est ouvert",
	},
	held: {
		label: "retenu",
		Icon: Pause,
		tone: "held",
		tip: "Retenu : en attente d'une décision humaine",
	},
	approved: {
		label: "approuvé",
		Icon: SquareCheck,
		tone: "warn",
		tip: "Approuvé par un humain, puis exécuté",
	},
	rejected: {
		label: "rejeté",
		Icon: X,
		tone: "ok",
		tip: "Rejeté par un humain : non exécuté",
	},
	expired: {
		label: "expiré",
		Icon: Hourglass,
		tone: "warn",
		tip: "Pas de décision à temps : annulé sans risque",
	},
	denied: {
		label: "refusé",
		Icon: Ban,
		tone: "ok",
		tip: "Refusé par Cressey, sans attendre",
	},
	would_hold: {
		label: "aurait été retenu",
		Icon: CirclePause,
		tone: "held",
		tip: "Rejeu : cet appel aurait été retenu, et le rejeu échoue",
	},
};

export const RISK: Record<Step["risk"], Omit<Look, "tip">> = {
	read: { label: "lecture", Icon: Eye, tone: "grey" },
	write: { label: "écriture", Icon: Pencil, tone: "warn" },
	destructive: { label: "destructive", Icon: Trash, tone: "held" },
};

export const SEVERITY: Record<Incident["severity"], Omit<Look, "tip">> = {
	critique: { label: "critique", Icon: TriangleAlert, tone: "held" },
	haute: { label: "haute", Icon: ChevronsUp, tone: "warn" },
};

export const ROLE: Record<OwnerGuide["owner_role"], string> = {
	key_owner: "Propriétaire de la clé",
	task_author: "Auteur de la tâche",
	platform_owner: "Responsable de la plateforme",
	soc: "SOC",
};

export const GUIDE_STATUS: Record<OwnerGuide["status"], string> = {
	pending: "guide en cours…",
	ok: "ok",
	unsure: "je ne sais pas, voir l'équipe sécurité",
	unavailable: "indisponible",
};

export const KIND: Record<Run["kind"], string> = {
	live: "live",
	replay: "rejeu",
	control: "Observateur",
};

export const VISIBILITY: Record<Run["visibility"], string> = {
	tools: "Appels d'outils",
	messages: "+ Messages",
	reasoning: "+ Raisonnement",
};

export const RESPONSE: Record<Responses["floor"], string> = {
	alert: "Alerte",
	review: "Revue humaine",
	stop: "Arrêt",
};

export const CHECK: Record<keyof Responses, string> = {
	floor: "Plancher de sécurité",
	trap_key: "Clé piège",
	triangle: "Triangle",
	fleet: "Signal entre runs",
};

export const time = (iso?: string | null) =>
	iso ? new Date(iso).toLocaleTimeString("fr-FR") : "";

// The checks currently on « alerte »: Cressey lets their calls through.
export const onAlert = (r?: Responses) =>
	r
		? (["floor", "trap_key", "triangle"] as const).filter(
				(k) => r[k] === "alert",
			)
		: [];
