import {
	Activity,
	BellRing,
	ChartColumn,
	Cpu,
	Hash,
	Inbox,
	Keyboard,
	type LucideIcon,
	PanelLeftClose,
	PanelLeftOpen,
	Pause,
	Radar,
	ShieldCheck,
	SlidersHorizontal,
	Triangle,
	Unplug,
} from "lucide-react";
import { useEffect, useState } from "react";
import { LiveProvider, useLive, type View } from "@/api/live";
import { useTooltips } from "@/components/tooltips";
import { stage } from "@/lib/incident";
import { CHECK, onAlert, time } from "@/lib/labels";
import { EvalView } from "@/views/eval/EvalView";
import { IncidentsView } from "@/views/incidents/IncidentsView";
import { LiveView } from "@/views/live/LiveView";
import { SettingsView } from "@/views/settings/SettingsView";

const NAV: { k: View; label: string; Icon: LucideIcon }[] = [
	{ k: "live", label: "Live run", Icon: Activity },
	{ k: "inc", label: "Incidents", Icon: Inbox },
	{ k: "eval", label: "Evaluation", Icon: ChartColumn },
	{ k: "connect", label: "Settings", Icon: SlidersHorizontal },
];

const SHORTCUTS =
	"Shortcuts\n1–4: switch view\nR: reject the held call\nA: approve (twice)\nT: triangle or chart";

export default function App() {
	return (
		<LiveProvider>
			<Shell />
		</LiveProvider>
	);
}

function Shell() {
	useTooltips();
	const { view, go, holds } = useLive();
	const [collapsed, setCollapsed] = useState(() => window.innerWidth < 1180);
	const hold = holds[0];

	useEffect(() => {
		const key = (e: KeyboardEvent) => {
			const t = e.target;
			const typing =
				t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement;
			if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
			const to = NAV[Number(e.key) - 1];
			if (!to) return;
			e.preventDefault();
			go(to.k);
		};
		window.addEventListener("keydown", key);
		return () => window.removeEventListener("keydown", key);
	}, [go]);

	useEffect(() => {
		document.title = hold ? `Held · ${hold.step.tool} · Cressey` : "Cressey";
	}, [hold]);

	return (
		<div className="flex h-screen overflow-hidden bg-paper font-sans text-ink">
			<Sidebar collapsed={collapsed} toggle={() => setCollapsed((c) => !c)} />
			<div className="flex min-w-0 flex-1 flex-col overflow-hidden">
				<HoldBanner />
				<AlertBanner />
				<FleetBanner />
				<main className="flex min-h-0 flex-1 flex-col overflow-auto">
					{view === "live" && <LiveView />}
					{view === "inc" && <IncidentsView />}
					{view === "eval" && <EvalView />}
					{view === "connect" && <SettingsView />}
				</main>
			</div>
		</div>
	);
}

function Sidebar({
	collapsed,
	toggle,
}: {
	collapsed: boolean;
	toggle: () => void;
}) {
	const { view, go, holds, incidents, status, responses, offline } = useLive();
	const open = !collapsed;
	const pending = incidents.filter((i) => stage(i) < 3).length;
	const alerting = onAlert(responses);
	const mode = status?.model_mode;
	const items = [
		{
			Icon: ShieldCheck,
			label: "Guard",
			value: alerting.length ? "alert" : "active",
			dot: alerting.length ? "var(--color-warn-bd)" : "var(--color-ok-strong)",
			tip: alerting.length
				? `Protection mode: Guard\nOn alert: ${alerting.map((k) => CHECK[k]).join(", ")}`
				: "Protection mode: Guard\nRisky calls wait for a human decision.",
		},
		{
			Icon: Cpu,
			label: "Model",
			// replay and fallback answer from the recording: “recorded answers”.
			value: mode === "live" || mode === "record" ? mode : "recorded",
			dot: mode === "live" ? "var(--color-ok-strong)" : "var(--color-warn-bd)",
			tip:
				mode === "live" || mode === "record"
					? `Model mode: ${mode}`
					: `Model mode: recorded answers (${mode ?? "?"})`,
		},
		{
			Icon: Hash,
			label: "Log",
			value: !status
				? "…"
				: status.log.count
					? `${status.log.hash.slice(0, 12)} · ${status.log.count}`
					: "empty",
			dot: status?.log.intact
				? "var(--color-ok-strong)"
				: "var(--color-held-strong)",
			tip: status
				? `Event log\nlast hash ${status.log.hash.slice(0, 12)}\n${status.log.count} records · chain ${status.log.intact ? "intact" : "broken"}`
				: "",
		},
	];
	return (
		<aside
			aria-label="Navigation"
			className="flex flex-none flex-col overflow-hidden border-ink border-r-[1.2px] bg-surface transition-[width] duration-200"
			style={{ width: open ? 224 : 60 }}
		>
			<div className="flex h-16 flex-none items-center gap-2.5 overflow-hidden whitespace-nowrap border-line border-b px-[19px]">
				<Triangle size={22} strokeWidth={2.25} />
				{open && (
					<span className="font-semibold text-[19px] leading-none tracking-[-0.03em]">
						Cressey
					</span>
				)}
			</div>
			<nav className="flex min-h-0 flex-1 flex-col gap-1 overflow-auto px-2.5 py-3.5">
				{NAV.map(({ k, label, Icon }) => {
					const on = view === k;
					const badge =
						k === "inc" && pending
							? String(pending)
							: k === "live" && holds.length
								? "held"
								: "";
					const red = k === "live" || (k === "inc" && holds.length > 0);
					return (
						<button
							key={k}
							type="button"
							onClick={() => go(k)}
							aria-current={on ? "page" : undefined}
							aria-label={label}
							data-tip={open ? "" : label + (badge ? ` · ${badge}` : "")}
							className={`flex h-10 flex-none items-center gap-2.5 overflow-hidden whitespace-nowrap px-3 text-left font-medium text-sm transition-colors ${on ? "bg-ink text-surface" : "bg-surface hover:bg-paper"}`}
						>
							<Icon size={17} />
							{open && <span className="min-w-0 flex-1 truncate">{label}</span>}
							{open && badge && (
								<span
									className={`inline-flex h-5 min-w-5 items-center justify-center border px-[5px] font-pixel text-[17px] leading-none ${red ? "border-held-bd bg-held text-held-fg" : "border-warn-bd bg-warn text-warn-fg"}`}
								>
									{badge}
								</span>
							)}
						</button>
					);
				})}
			</nav>
			<div className="flex flex-none flex-col gap-1 border-line border-t px-2.5 pt-3 pb-3.5">
				{offline && (
					<div
						data-tip="The backend isn't answering: the screen shows its last answer."
						className="flex h-8 items-center gap-2.5 overflow-hidden whitespace-nowrap px-3 font-medium text-held-fg text-xs"
					>
						<Unplug size={15} />
						{open && "API unreachable"}
					</div>
				)}
				{items.map(({ Icon, label, value, dot, tip }) => (
					<div
						key={label}
						data-tip={tip}
						// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
						tabIndex={0}
						className="flex h-8 items-center gap-2 overflow-hidden whitespace-nowrap px-2"
					>
						<Icon size={15} />
						{open && (
							<>
								<span className="text-[12.5px] text-mute">{label}</span>
								<span className="ml-auto inline-flex items-center gap-1.5 font-medium font-mono text-[11px]">
									<span className="size-[7px]" style={{ background: dot }} />
									{value}
								</span>
							</>
						)}
					</div>
				))}
				<div className={`flex gap-1 pt-1.5 ${open ? "flex-row" : "flex-col"}`}>
					<button
						type="button"
						aria-label="Keyboard shortcuts"
						data-tip={SHORTCUTS}
						className="btn h-8 min-w-8 flex-auto cursor-help px-1.5 text-[12.5px]"
					>
						<Keyboard size={15} />
						{open && "Shortcuts"}
					</button>
					<button
						type="button"
						aria-label={open ? "Collapse the menu" : "Expand the menu"}
						data-tip={open ? "Collapse the menu" : "Expand the menu"}
						onClick={toggle}
						className="btn h-8 w-8 flex-none p-0"
					>
						{open ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
					</button>
				</div>
			</div>
		</aside>
	);
}

// m:ss to the safe cancel.
const clock = (until: string | null | undefined, now: number) => {
	const s = until
		? Math.max(0, Math.round((Date.parse(until) - now) / 1000))
		: 0;
	return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

function HoldBanner() {
	const { holds, now, go } = useLive();
	const hold = holds[0];
	if (!hold) return null;
	return (
		<div
			role="alert"
			className="flex min-h-[54px] flex-none flex-wrap items-center gap-[18px] border-held-bd border-b bg-held px-7 py-2"
		>
			<span className="inline-flex size-7 items-center justify-center bg-held-strong text-surface">
				<Pause size={16} strokeWidth={2.5} />
			</span>
			<strong className="font-semibold text-[15px]">Call held</strong>
			<span className="font-mono text-[13px]">
				{hold.run_id} · #{hold.step.n} {hold.step.tool}
				{holds.length > 1 && ` · and ${holds.length - 1} more`}
			</span>
			<span
				data-tip="Without a decision, the call is safely cancelled when the countdown ends."
				className="inline-flex items-baseline gap-2"
			>
				<span className="font-mono text-xs">safe cancel in</span>
				<span className="font-pixel text-[30px] leading-none">
					{clock(hold.step.held_until, now)}
				</span>
			</span>
			<div className="flex-1" />
			<button
				type="button"
				onClick={() => go("live", { run: hold.run_id, step: hold.step.n })}
				className="btn btn-dark"
			>
				Go to hold
			</button>
		</div>
	);
}

function AlertBanner() {
	const { responses, go } = useLive();
	const alerting = onAlert(responses);
	if (!alerting.length) return null;
	return (
		<div
			role="status"
			className="flex min-h-[46px] flex-none flex-wrap items-center gap-3.5 border-warn-bd border-b bg-warn px-7 py-2 text-warn-fg"
		>
			<BellRing size={17} />
			<strong className="font-semibold">
				Alert mode: Cressey isn't blocking
			</strong>
			<span className="font-mono text-[13px]">
				{alerting.map((k) => CHECK[k]).join(" · ")}
			</span>
			<div className="flex-1" />
			<button type="button" onClick={() => go("connect")} className="btn">
				What does Cressey do when…?
			</button>
		</div>
	);
}

function FleetBanner() {
	const { fleet, responses } = useLive();
	if (!fleet.length) return null;
	return (
		<div
			role="status"
			className="flex flex-none flex-col gap-1 border-info-bd border-b bg-info px-7 py-2 text-info-fg"
		>
			{fleet.map((f) => (
				<div key={f.target} className="flex flex-wrap items-center gap-3">
					<Radar size={17} />
					<strong className="font-semibold">Signal across runs</strong>
					<span className="font-mono text-[13px]">
						{f.runs.length} runs target {f.target} outside their mandate, from{" "}
						{time(f.first_at)} to {time(f.last_at)}
					</span>
					{responses?.fleet === "stop" && (
						<span className="chip border-info-bd">their calls are refused</span>
					)}
				</div>
			))}
		</div>
	);
}
