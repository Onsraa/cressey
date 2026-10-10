import type { Incident, Run } from "@/api/types";
import { LEGS } from "@/lib/labels";

// Each leg's letter, name and colour, by its key.
export const LEG = Object.fromEntries(
	LEGS.map((l): [string, (typeof LEGS)[number]] => [l.k, l]),
);

// The call ran: what it revealed (a key within reach) is still real.
export const acted = (i: Incident) =>
	i.decision === "approved" || i.decision === "alerted";

function parse(json: string): unknown {
	try {
		return JSON.parse(json);
	} catch {
		return undefined;
	}
}

const isRecord = (v: unknown): v is Record<string, unknown> =>
	typeof v === "object" && v !== null && !Array.isArray(v);

// The file a call read: its `path` argument.
export function argPath(args: string) {
	const v = parse(args);
	return isRecord(v) && typeof v.path === "string" ? v.path : undefined;
}

// Each secret's name by fingerprint, from what the run's calls returned.
export const secretNames = (run?: Run) =>
	new Map(
		(run?.steps ?? []).flatMap((s) =>
			s.secrets.map((x): [string, string] => [x.fingerprint, x.name ?? x.kind]),
		),
	);

// Served text carries `[secret:<fingerprint>]`: show the secret's name instead.
export const unmask = (text: string, names: Map<string, string>) =>
	text.replace(
		/\[secret:(\w+)\]/g,
		(_, fp: string) => `‹${names.get(fp) ?? "secret"}›`,
	);

// A call's arguments on one short line: the values only, secrets by name.
export function shortArgs(args: string, names: Map<string, string>, max = 90) {
	const v = parse(args);
	const text = isRecord(v)
		? Object.values(v)
				.map((x) => (typeof x === "string" ? x : JSON.stringify(x)))
				.join(" ")
		: args;
	const line = unmask(text, names).replace(/\s+/g, " ").trim();
	return line.length > max ? `${line.slice(0, max - 1)}…` : line;
}
