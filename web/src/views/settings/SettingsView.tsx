import { latestLive, useLive } from "@/api/live";
import { ConnectPanel } from "./ConnectPanel";
import { ResponsesPanel } from "./ResponsesPanel";

// The design's « Connect » view, renamed « Settings » (cressey-dashboard-v3-fixes.md, Add 1).
export function SettingsView() {
	const { runs } = useLive();
	const run = latestLive(runs);
	const calls = run?.calls ?? 0;
	// The run's calls come one way: through the MCP proxy, or through the hook.
	const via =
		run?.via === "hook" ? `0 MCP, ${calls} hook` : `${calls} MCP, 0 hook`;
	return (
		<div
			data-slot="connect"
			className="flex min-h-0 flex-1 flex-col gap-4 px-7 pt-6 pb-7"
		>
			<header data-anim className="flex flex-none flex-wrap items-end gap-4">
				<div className="flex min-w-0 flex-[1_1_360px] flex-col gap-[7px]">
					<div className="flex items-center gap-1.5 font-mono text-xs">
						<span className="text-mute">Settings</span>
						<span className="text-mute-3">/</span>
						<span className="font-medium">{run?.id ?? "no run yet"}</span>
					</div>
					<h1 className="m-0 font-medium text-[22px] leading-[1.15] tracking-[-0.02em]">
						Cressey settings
					</h1>
				</div>
				<span className="inline-flex h-7 items-center gap-[7px] border-[1.2px] border-ink bg-surface px-2.5 font-mono text-xs">
					<span
						className={`size-2 ${calls ? "bg-ok-strong" : "blink bg-warn-bd"}`}
					/>
					{calls
						? `connected · ${calls} ${calls > 1 ? "calls" : "call"} (${via})`
						: "waiting for the first call"}
				</span>
			</header>
			<ResponsesPanel />
			{/* The design's two columns, the second for the stretch goals (owner connector,
			    Slack), which the backend doesn't have: the panel keeps its column's width. */}
			<div className="grid min-h-0 flex-1 grid-cols-[repeat(auto-fill,minmax(max(340px,calc(50%-8px)),1fr))] items-start gap-4">
				<ConnectPanel />
			</div>
		</div>
	);
}
