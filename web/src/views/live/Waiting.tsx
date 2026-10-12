import { useEffect, useState } from "react";
import { useLive } from "@/api/live";
import { ArrowRight, Copy } from "@/components/icons";
import { COPIED_MS } from "@/lib/labels";

// The design's waiting card, over the empty triangle: the MCP URL to paste, and the way to
// the other connection, the hook.
export function Waiting() {
	const { status, go } = useLive();
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
		<div className="absolute top-1/2 left-1/2 w-[min(420px,calc(100%-32px))] -translate-x-1/2 -translate-y-1/2 border-[1.2px] border-ink bg-surface shadow-[0_18px_40px_-16px_rgba(30,30,30,.32),0_2px_6px_rgba(30,30,30,.06)]">
			<div className="panel-head gap-2">
				<span>WAITING FOR AN AGENT</span>
				<span className="blink h-3.5 w-2 bg-surface" />
			</div>
			<div className="flex flex-col gap-4 p-5">
				<span className="text-sm leading-[1.4]">
					Paste this MCP URL into the agent’s config. The run starts from a
					terminal.
				</span>
				<div className="flex border-[1.2px] border-ink">
					<code className="min-w-0 flex-1 select-all truncate px-2.5 py-2 font-mono text-[12.5px]">
						{url || "…"}
					</code>
					<button
						type="button"
						onClick={copy}
						disabled={!url}
						className="press shade inline-flex flex-none items-center gap-1.5 border-ink border-l-[1.2px] bg-surface px-3 font-medium text-[13px]"
					>
						<Copy size={14} />
						{copied || "Copy"}
					</button>
				</div>
				<div className="flex flex-wrap gap-2">
					<button
						type="button"
						onClick={() => go("connect")}
						className="btn h-9"
					>
						Connect an agent
						<ArrowRight size={15} />
					</button>
				</div>
			</div>
		</div>
	);
}
