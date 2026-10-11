import { useEffect, useState } from "react";
import { useLive } from "@/api/live";
import { ArrowRight, Bot, Copy, Shield, Terminal } from "@/components/icons";

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

type Method = "mcp" | "hook";

const METHODS: { k: Method; label: string }[] = [
	{ k: "mcp", label: "MCP server" },
	{ k: "hook", label: "HTTP hook" },
];

const COPIED_MS = 1500;

export function ConnectPanel() {
	const { status, go } = useLive();
	const [method, setMethod] = useState<Method>("mcp");
	const [copied, setCopied] = useState("");
	useEffect(() => {
		if (!copied) return;
		const t = setTimeout(() => setCopied(""), COPIED_MS);
		return () => clearTimeout(t);
	}, [copied]);
	const origin = window.location.origin;
	const mcp = method === "mcp";
	const code = !status
		? ""
		: mcp
			? `claude mcp add --transport http cressey \\\n  ${origin}${status.mcp_path} \\\n  --header "Authorization: Bearer <run key>"`
			: hookSettings(origin, status.hook_path);
	// Inside the promise: without a secure context, navigator.clipboard is missing.
	const copy = () =>
		Promise.resolve()
			.then(() => navigator.clipboard.writeText(code))
			.then(
				() => setCopied("Copied"),
				() => setCopied("Copy blocked"),
			);
	return (
		<section
			data-anim
			aria-label="Connect an agent"
			className="border-[1.2px] border-ink bg-surface shadow-[0_1px_2px_rgba(30,30,30,.04),0_12px_28px_-18px_rgba(30,30,30,.22)]"
		>
			<div className="panel-head gap-2">
				<Bot size={14} />
				CONNECT AN AGENT
			</div>
			<div className="flex flex-col gap-4 p-5">
				<div
					role="tablist"
					aria-label="Connection method"
					className="flex self-start border-[1.2px] border-ink"
				>
					{METHODS.map((m) => (
						<button
							key={m.k}
							type="button"
							role="tab"
							aria-selected={m.k === method}
							onClick={() => setMethod(m.k)}
							className={`press shade h-8 border-ink border-r-[1px] px-3 font-medium text-[13px] ${m.k === method ? "bg-ink text-surface" : "bg-surface text-ink"}`}
						>
							{m.label}
						</button>
					))}
				</div>
				<span className="text-[13.5px] leading-[1.45]">
					{mcp
						? "Run once in the agent’s terminal. Cressey sees the MCP tool calls. The run key comes from POST /api/runs, given once."
						: "Merge into the workspace’s .claude/settings.json. Cressey also sees the shell, the files and the reasoning. Needs Claude Code ≥ 2.1.295 for onFailure: block."}
				</span>
				{!mcp && (
					<span className="inline-flex h-6 items-center gap-1.5 self-start border border-held-bd bg-held px-2 font-mono text-[11.5px] text-held-fg">
						<Shield size={12} />a hook failure blocks the call
					</span>
				)}
				<div className="border-[1.2px] border-ink bg-paper">
					<div className="flex h-[38px] items-center justify-between gap-2.5 border-line border-b bg-surface pr-1.5 pl-3.5">
						<span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-mute-2">
							<Terminal size={12} />
							{mcp ? "agent terminal" : ".claude/settings.json"}
						</span>
						<button
							type="button"
							onClick={copy}
							disabled={!code}
							data-tip="Copies it as shown: replace <run key> with the key you received."
							className="btn h-[30px] px-2.5 text-[13px]"
						>
							<Copy size={14} />
							{copied || "Copy"}
						</button>
					</div>
					<pre className="m-0 max-h-[280px] overflow-auto whitespace-pre bg-paper p-3.5 font-mono text-xs leading-[1.5]">
						{code || "…"}
					</pre>
				</div>
				<button
					type="button"
					onClick={() => go("live")}
					className="btn btn-dark h-[34px] gap-1.5 self-start px-[13px] text-[13.5px]"
				>
					Open the live run
					<ArrowRight size={14} />
				</button>
			</div>
		</section>
	);
}
