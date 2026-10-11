import { Copy, Terminal } from "lucide-react";
import { useEffect, useState } from "react";
import { useLive } from "@/api/live";

const COPIED_MS = 1500;

// Where an agent connects: the MCP URL to paste, and the run key it sends.
export function Waiting({ title }: { title: string }) {
	const { status } = useLive();
	const url = status ? `${window.location.origin}${status.mcp_path}` : "";
	const [copied, setCopied] = useState("");
	useEffect(() => {
		if (!copied) return;
		const t = setTimeout(() => setCopied(""), COPIED_MS);
		return () => clearTimeout(t);
	}, [copied]);
	// The clipboard API is missing outside a secure context: the rejection says so.
	const copy = () =>
		Promise.resolve()
			.then(() => navigator.clipboard.writeText(url))
			.then(
				() => setCopied("Copied"),
				() => setCopied("Copy failed"),
			);
	return (
		<div className="flex h-full flex-col items-center justify-center gap-2.5 p-6 text-center">
			<span className="inline-flex size-10 items-center justify-center border-[1.2px] border-ink">
				<Terminal size={20} />
			</span>
			<span className="font-medium text-[15px]">{title}</span>
			<span className="max-w-[260px] text-[13px] text-mute-2 leading-[1.45]">
				Paste this MCP URL into the agent's configuration.
			</span>
			<div className="flex w-full max-w-[320px] border-[1.2px] border-ink text-left">
				<code className="min-w-0 flex-1 select-all truncate px-2.5 py-2 font-mono text-[12.5px]">
					{url || "…"}
				</code>
				<button
					type="button"
					onClick={copy}
					disabled={!url}
					className="inline-flex flex-none items-center gap-1.5 border-ink border-l-[1.2px] px-3 font-medium text-[13px] hover:bg-paper"
				>
					<Copy size={14} />
					{copied || "Copy"}
				</button>
			</div>
			<span className="max-w-[280px] text-[12.5px] text-mute-2 leading-[1.45]">
				The agent sends{" "}
				<code className="whitespace-nowrap font-mono text-ink">
					Authorization: Bearer &lt;run key&gt;
				</code>
			</span>
			<span className="max-w-[280px] text-[12.5px] text-mute-2 leading-[1.45]">
				Or wire the Claude Code hook (shell, files and reasoning) — see
				Settings.
			</span>
		</div>
	);
}
