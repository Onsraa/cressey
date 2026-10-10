import { ConnectPanel } from "./ConnectPanel";
import { ResponsesPanel } from "./ResponsesPanel";

// The design's “Connect” view, renamed “Settings” (cressey-dashboard-v3-fixes.md, Add 1).
export function SettingsView() {
	return (
		<div className="flex min-h-0 flex-1 flex-col gap-4 px-7 pt-6 pb-7">
			<header className="rise flex flex-none flex-col gap-[7px]">
				<div className="flex items-center gap-1.5 font-mono text-xs">
					<span className="text-mute">Settings</span>
					<span className="text-mute-3">/</span>
					<span className="font-medium">Guard</span>
				</div>
				<h1 className="m-0 font-medium text-[22px] leading-[1.15] tracking-[-0.02em]">
					What Cressey does, and how to connect an agent to it
				</h1>
			</header>
			<div className="grid grid-cols-[repeat(auto-fit,minmax(340px,1fr))] items-start gap-4">
				<ResponsesPanel />
				<ConnectPanel />
			</div>
		</div>
	);
}
