import { Bot, Copy, Terminal, Webhook } from "lucide-react";
import { useState } from "react";
import { useLive } from "@/api/live";

// The hook settings an agent drops into .claude/settings.json. The run key is sent on every
// event; the dashboard only shows the shape, with <run key> left to fill.
function hookSettings(origin: string, hookPath: string): string {
	const one = (timeout: number, extra: object = {}) => ({
		matcher: "*",
		hooks: [
			{
				type: "http",
				url: `${origin}${hookPath}`,
				headers: { Authorization: "Bearer <run key>" },
				timeout,
				...extra,
			},
		],
	});
	return JSON.stringify(
		{
			hooks: {
				MessageDisplay: [one(10)],
				PreToolUse: [one(300, { onFailure: "block" })],
				PostToolUse: [one(60, { onFailure: "block" })],
				PostToolUseFailure: [one(60)],
				Stop: [one(60)],
			},
		},
		null,
		2,
	);
}

function CopyBlock({
	title,
	Icon,
	body,
	note,
}: {
	title: string;
	Icon: typeof Terminal;
	body: string;
	note: string;
}) {
	const [copied, setCopied] = useState("");
	const copy = () => {
		// Inside the promise: without a secure context, navigator.clipboard is missing.
		Promise.resolve()
			.then(() => navigator.clipboard.writeText(body))
			.then(
				() => setCopied("Copied"),
				() => setCopied("Copy blocked"),
			);
		setTimeout(() => setCopied(""), 1500);
	};
	return (
		<div className="flex flex-col gap-2">
			<div className="border-[1.2px] border-ink bg-paper">
				<div className="flex h-[38px] items-center justify-between gap-2.5 border-line border-b bg-surface pr-1.5 pl-3.5">
					<span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-mute-2">
						<Icon size={12} />
						{title}
					</span>
					<button
						type="button"
						onClick={copy}
						disabled={!body}
						className="btn h-[30px] px-2.5 text-[13px]"
					>
						<Copy size={14} />
						{copied || "Copy"}
					</button>
				</div>
				<pre className="m-0 max-h-[280px] overflow-auto whitespace-pre bg-paper p-3.5 font-mono text-xs leading-[1.5]">
					{body || "…"}
				</pre>
			</div>
			<span className="text-[13px] text-mute leading-[1.45]">{note}</span>
		</div>
	);
}

export function ConnectPanel() {
	const { status } = useLive();
	const origin = window.location.origin;
	const mcp = status
		? `claude mcp add --transport http cressey \\\n  ${origin}${status.mcp_path} \\\n  --header "Authorization: Bearer <run key>"`
		: "";
	const hook = status ? hookSettings(origin, status.hook_path) : "";

	return (
		<section aria-label="Connect an agent" className="panel rise">
			<div className="panel-head">
				<Bot size={14} />
				CONNECT AN AGENT
			</div>
			<div className="flex flex-col gap-5 p-5">
				<span className="text-[13.5px] leading-[1.45]">
					Create the run first (POST /api/runs); it returns the run key, once.
					Then connect the agent one of two ways.
				</span>
				<div className="flex flex-col gap-2">
					<span className="label">
						Via MCP — the agent calls Cressey's tools
					</span>
					<CopyBlock
						title="agent's terminal"
						Icon={Terminal}
						body={mcp}
						note="Run once in the agent's terminal. Cressey sees the MCP tool calls."
					/>
				</div>
				<div className="flex flex-col gap-2">
					<span className="label">
						Via hook — Claude Code posts every tool call
					</span>
					<CopyBlock
						title=".claude/settings.json"
						Icon={Webhook}
						body={hook}
						note="Merge into the workspace's .claude/settings.json. Cressey also sees the shell, the files and the reasoning (MessageDisplay streams it live). Needs Claude Code ≥ 2.1.295 for onFailure: block."
					/>
				</div>
			</div>
		</section>
	);
}
