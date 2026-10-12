import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { LiveProvider, shownRun, useLive, type View } from "@/api/live";
import type { FleetSignal } from "@/api/types";
import {
	Activity,
	ArrowRight,
	Bell,
	ChartColumn,
	Cpu,
	Focus,
	GitMerge,
	Hash,
	type IconType,
	Inbox,
	Keyboard,
	PanelLeftClose,
	PanelLeftOpen,
	Pause,
	ShieldCheck,
	SlidersHorizontal,
	Unplug,
	X,
} from "@/components/icons";
import { useTooltips } from "@/components/tooltips";
import { stage } from "@/lib/incident";
import { CHECK, clock, onAlert, time } from "@/lib/labels";
import { animIn, arrive, closePops, usePopovers } from "@/lib/motion";
import { EvalView } from "@/views/eval/EvalView";
import { IncidentsView } from "@/views/incidents/IncidentsView";
import { LiveView } from "@/views/live/LiveView";
import { SettingsView } from "@/views/settings/SettingsView";

const NAV: { k: View; label: string; Icon: IconType }[] = [
	{ k: "live", label: "Live run", Icon: Activity },
	{ k: "inc", label: "Incidents", Icon: Inbox },
	{ k: "eval", label: "Evaluation", Icon: ChartColumn },
	{ k: "connect", label: "Settings", Icon: SlidersHorizontal },
];

const SHORTCUTS =
	"Keyboard shortcuts\n1–4   switch page\nF     focus mode\nT     triangle / across steps\nR     reject the held call\nA A   approve the held call\nEsc   clear the selection";

export default function App() {
	return (
		<LiveProvider>
			<Shell />
		</LiveProvider>
	);
}

function Shell() {
	useTooltips();
	usePopovers();
	const { view, go, holds, now, toggleFocus } = useLive();
	const [collapsed, setCollapsed] = useState(() => window.innerWidth < 1180);
	const main = useRef<HTMLElement>(null);
	const hold = holds[0];

	useEffect(() => {
		const key = (e: KeyboardEvent) => {
			const t = e.target;
			const typing =
				t instanceof HTMLInputElement ||
				t instanceof HTMLTextAreaElement ||
				(t instanceof HTMLElement && t.isContentEditable);
			if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
			const k = e.key.toLowerCase();
			if (k === "f") {
				e.preventDefault();
				if (!e.repeat) toggleFocus();
			} else if (k === "escape") closePops();
			else if (NAV[Number(k) - 1]) {
				e.preventDefault();
				go(NAV[Number(k) - 1].k);
			}
		};
		window.addEventListener("keydown", key);
		return () => window.removeEventListener("keydown", key);
	}, [go, toggleFocus]);

	// A page's blocks rise in when it opens, as on the first load.
	// biome-ignore lint/correctness/useExhaustiveDependencies: replayed on each page switch
	useLayoutEffect(() => animIn(main.current), [view]);

	const label = NAV.find((n) => n.k === view)?.label;
	const title = hold
		? `‖ Held · ${hold.step.tool} · ${clock(hold.step.held_until, now)} — Cressey`
		: `Cressey · ${label}`;
	useEffect(() => {
		document.title = title;
	}, [title]);

	return (
		<div className="flex h-screen overflow-hidden bg-paper font-sans text-ink">
			<Sidebar collapsed={collapsed} toggle={() => setCollapsed((c) => !c)} />
			<div className="flex min-w-0 flex-1 flex-col overflow-hidden">
				<HoldBanner />
				<AlertBanner />
				<SignalBanner />
				<main ref={main} className="flex min-h-0 flex-1 flex-col overflow-auto">
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
	const {
		view,
		go,
		holds,
		incidents,
		status,
		responses,
		offline,
		focusMode,
		toggleFocus,
	} = useLive();
	const open = !collapsed;
	const pending = incidents.filter((i) => stage(i) < 3).length;
	const alerting = onAlert(responses);
	const mode = status?.model_mode;
	const live = mode === "live" || mode === "record";
	const items = [
		{
			Icon: ShieldCheck,
			label: "Guard",
			value: alerting.length ? "alert" : "on",
			dot: alerting.length ? "var(--color-warn-bd)" : "var(--color-ok-strong)",
			tip: alerting.length
				? `Protection mode: Guard\nOn alert: ${alerting.map((k) => CHECK[k]).join(", ")}`
				: "Protection mode: Guard\nRisky calls wait for a human decision.",
		},
		{
			Icon: Cpu,
			label: "Model",
			// replay and fallback answer from the recording: “recorded answers”.
			value: live ? mode : "recorded",
			dot: live ? "var(--color-ok-strong)" : "var(--color-warn-bd)",
			tip: live ? `Model: ${mode}` : `Model: recorded answers (${mode ?? "?"})`,
		},
		{
			Icon: Hash,
			label: "Log",
			value: !status
				? "…"
				: `${status.log.hash.slice(0, 12)} · ${status.log.count.toLocaleString("en-GB")}`,
			dot: status?.log.intact
				? "var(--color-ok-strong)"
				: "var(--color-held-strong)",
			tip: status
				? `Event log\nlast hash ${status.log.hash.slice(0, 12)}\n${status.log.count.toLocaleString("en-GB")} records · chain ${status.log.intact ? "intact" : "broken"}`
				: "",
		},
	];
	return (
		<aside
			aria-label="Main navigation"
			className="flex flex-none flex-col overflow-hidden border-ink border-r-[1.2px] bg-surface transition-[width] duration-[220ms] ease-[cubic-bezier(.2,.7,.2,1)]"
			style={{ width: open ? 224 : 60 }}
		>
			<div className="flex h-16 flex-none items-center gap-2.5 overflow-hidden whitespace-nowrap border-line border-b px-[19px]">
				{/* The logo: the deck's pixel triangle (deck/index.html .mark), favicon too. */}
				<svg
					viewBox="0 0 11 10"
					width={22}
					height={20}
					aria-hidden="true"
					className="flex-none"
				>
					<path
						d="M5 0h1v1h1v2h1v2h1v2h1v3H0V7h1V5h1V3h1V1h1V0z M5 3v1H4v2H3v2h5V6H7V4H6V3z"
						fill="currentColor"
						fillRule="evenodd"
					/>
				</svg>
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
							className={`fade shade flex h-10 flex-none items-center gap-2.5 overflow-hidden whitespace-nowrap px-3 text-left font-medium text-sm active:bg-[#e9e9e7] ${on ? "bg-ink text-surface" : "bg-surface text-ink"}`}
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
						className="flex h-8 items-center gap-2.5 overflow-hidden whitespace-nowrap px-3 font-medium text-[12.5px] text-held-fg"
					>
						<Unplug size={15} />
						{open && "API unreachable"}
					</div>
				)}
				{!focusMode &&
					items.map(({ Icon, label, value, dot, tip }) => (
						<div
							key={label}
							data-tip={tip}
							// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
							tabIndex={0}
							className="flex h-8 cursor-default items-center gap-2.5 overflow-hidden whitespace-nowrap px-3"
						>
							<Icon size={15} />
							{open && (
								<>
									<span className="text-[12.5px] text-mute">{label}</span>
									<span className="ml-auto inline-flex items-center gap-1.5 font-medium font-mono text-[11.5px]">
										<span className="size-[7px]" style={{ background: dot }} />
										{value}
									</span>
								</>
							)}
						</div>
					))}
				<button
					type="button"
					onClick={toggleFocus}
					aria-pressed={focusMode}
					aria-label="Focus mode"
					data-tip={open ? "" : "Focus · F"}
					className={`press mt-1 flex h-9 flex-none items-center gap-2.5 overflow-hidden whitespace-nowrap border-[1.2px] border-ink px-[11px] font-medium text-[13.5px] hover:shadow-[inset_0_0_0_999px_rgba(127,127,127,.14)] ${open ? "justify-start" : "justify-center"} ${focusMode ? "bg-ink text-surface" : "bg-surface text-ink"}`}
				>
					<Focus size={16} />
					{open && (
						<>
							<span className="flex-1 text-left">Focus</span>
							<span className="font-mono text-[11px] opacity-70">F</span>
						</>
					)}
				</button>
				<div
					className={`flex items-stretch gap-1 pt-1.5 ${open ? "flex-row" : "flex-col"}`}
				>
					{!focusMode && (
						<button
							type="button"
							aria-label="Keyboard shortcuts"
							data-tip={SHORTCUTS}
							className="btn h-8 min-h-8 min-w-8 flex-[1_1_auto] cursor-help px-1.5 font-normal text-[12.5px]"
						>
							<Keyboard size={15} />
							{open && <span>Shortcuts</span>}
						</button>
					)}
					<button
						type="button"
						aria-label={open ? "Collapse the panel" : "Expand the panel"}
						data-tip={open ? "Collapse the panel" : "Expand the panel"}
						onClick={toggle}
						className="btn h-8 min-w-8 flex-none p-0"
					>
						{open ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
					</button>
				</div>
			</div>
		</aside>
	);
}

// The hold banner slides down from under the top edge when a call is held.
const slideDown = (el: HTMLDivElement | null) =>
	arrive(el, { yPercent: -100 }, 0.35);

function HoldBanner() {
	const { holds, now, go, view, runs, focus } = useLive();
	// The Live page shows its run's hold in full: a banner there only pushes the page down.
	const watched = view === "live" ? shownRun(runs, focus)?.id : undefined;
	const others = holds.filter((h) => h.run_id !== watched);
	const hold = others[0];
	if (!hold) return null;
	return (
		<div
			key={`${hold.run_id}-${hold.step.n}`}
			ref={slideDown}
			role="alert"
			className="flex min-h-[54px] flex-none flex-wrap items-center gap-[18px] border-held-bd border-b bg-held px-7 py-2"
		>
			<span className="inline-flex size-7 items-center justify-center bg-held-strong text-surface">
				<Pause size={16} strokeWidth={2.5} />
			</span>
			<strong className="font-semibold text-[15px]">Call held</strong>
			<span className="font-mono text-[13px]">
				#{hold.step.n} {hold.step.tool} · {hold.step.risk}
				{others.length > 1 && ` · and ${others.length - 1} more`}
			</span>
			<span
				data-tip="With no decision, the call is safely cancelled when the countdown ends."
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
				View the call
				<ArrowRight size={15} />
			</button>
		</div>
	);
}

function AlertBanner() {
	const alerting = onAlert(useLive().responses);
	// Keyed by the checks on alert: a closed banner comes back when they change, or when
	// alert mode is switched off and on again.
	return alerting.length ? (
		<AlertBar key={alerting.join()} alerting={alerting} />
	) : null;
}

function AlertBar({ alerting }: { alerting: ReturnType<typeof onAlert> }) {
	const { go, view } = useLive();
	const [closed, setClosed] = useState(false);
	// The Live page shows alert mode in its header (the banner keeps its closed state).
	if (closed || view === "live") return null;
	return (
		<div
			role="alert"
			className="flex min-h-11 flex-none items-center gap-3.5 overflow-hidden whitespace-nowrap border-warn-bd border-b bg-warn px-7 py-1.5"
		>
			<span className="inline-flex size-6 flex-none items-center justify-center bg-warn-fg text-surface">
				<Bell size={14} strokeWidth={2.25} />
			</span>
			<strong className="font-semibold text-[#5a3a00] text-sm">
				Alert mode: Cressey does not block
			</strong>
			<span className="min-w-0 truncate font-mono text-[12.5px] text-warn-fg">
				on alert: {alerting.map((k) => CHECK[k]).join(", ")}
			</span>
			<div className="flex-1" />
			<button
				type="button"
				onClick={() => go("connect")}
				className="press inline-flex h-[30px] flex-none items-center gap-1.5 border-[1.2px] border-warn-fg bg-surface px-3 font-medium text-[13px] text-ink hover:shadow-[inset_0_0_0_999px_rgba(122,78,0,.08)]"
			>
				Settings
				<ArrowRight size={14} />
			</button>
			<button
				type="button"
				aria-label="Close this banner"
				onClick={() => setClosed(true)}
				className="press inline-flex size-[30px] flex-none items-center justify-center text-warn-fg opacity-70 hover:opacity-100"
			>
				<X size={16} />
			</button>
		</div>
	);
}

function SignalBanner() {
	const { fleet, responses, go, view } = useLive();
	// A closed signal comes back when another run is held on its target.
	const [closed, setClosed] = useState<string[]>([]);
	const id = (f: FleetSignal) => `${f.target}@${f.last_at}`;
	// The Live page shows a signal on its run's calls, and nothing to decide comes with one:
	// a banner there only pushes the page down (the banner keeps its closed signals).
	if (view === "live") return null;
	return fleet
		.filter((f) => !closed.includes(id(f)))
		.map((f) => (
			<div
				key={f.target}
				role="alert"
				className="flex min-h-11 flex-none items-center gap-3.5 overflow-hidden whitespace-nowrap border-black border-b bg-ink px-7 py-1.5 text-surface"
			>
				<span className="inline-flex size-6 flex-none items-center justify-center bg-surface text-ink">
					<GitMerge size={14} strokeWidth={2.25} />
				</span>
				<strong className="font-semibold text-sm">Cross-run signal</strong>
				<span className="min-w-0 truncate font-mono text-[12.5px] opacity-90">
					{f.target}
				</span>
				<span
					data-tip={`${f.runs.length} runs held outside the mandate:\n${f.runs.join("\n")}`}
					// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
					tabIndex={0}
					className="cursor-help font-mono text-[11.5px] opacity-70"
				>
					{f.runs.length} runs · {time(f.first_at)} → {time(f.last_at)}
				</span>
				<div className="flex-1" />
				<span className="inline-flex h-[22px] items-center border border-surface px-[7px] font-mono text-[11px]">
					{responses?.fleet === "stop"
						? "Stop: calls refused"
						: "Alert: calls let through"}
				</span>
				<button
					type="button"
					onClick={() => go("connect")}
					className="press inline-flex h-[30px] flex-none items-center gap-1.5 border-[1.2px] border-surface bg-surface px-3 font-medium text-[13px] text-ink"
				>
					Settings
					<ArrowRight size={14} />
				</button>
				<button
					type="button"
					aria-label="Close this signal"
					onClick={() => setClosed((c) => [...c, id(f)])}
					className="press inline-flex size-[30px] flex-none items-center justify-center opacity-70 hover:opacity-100"
				>
					<X size={16} />
				</button>
			</div>
		));
}
