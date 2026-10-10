import { ArrowRight, Check, Search, Triangle } from "lucide-react";
import { useLive } from "@/api/live";
import type { Incident, Run, Source } from "@/api/types";
import { Cells } from "@/components/Cells";
import { LEGS } from "@/lib/labels";
import { Box } from "./ui";
import { argPath, secretNames, unmask } from "./util";

const HOW: { k: Source["how"]; label: string; tip: string }[] = [
	{ k: "exact", label: "exacte", tip: "Valeur trouvée telle quelle" },
	{ k: "lowercase", label: "minuscules", tip: "Valeur trouvée en minuscules" },
	{ k: "base64", label: "base64", tip: "Valeur trouvée encodée en base64" },
	{ k: "hex", label: "hex", tip: "Valeur trouvée encodée en hexadécimal" },
	{ k: "url", label: "url", tip: "Valeur trouvée encodée pour une URL" },
];

export function Overview({
	incident: i,
	run,
}: {
	incident: Incident;
	run?: Run;
}) {
	const { go } = useLive();
	const names = secretNames(run);
	return (
		<div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] items-start gap-4">
			<Box Icon={Search} title="SOURCE">
				<div className="flex flex-col divide-y divide-line px-5">
					{i.sources.map((s) => {
						const path = argPath(s.args);
						// The secret's line in what that call returned.
						const line = run?.steps
							.find((x) => x.n === s.step)
							?.secrets.find((x) => (x.name ?? x.kind) === s.secret)?.line;
						const where = path ? `dans ${path} ` : "";
						return (
							<div
								key={`${s.step}-${s.how}-${s.value}`}
								className="flex flex-col gap-4 py-5"
							>
								<span className="text-pretty font-medium text-lg leading-[1.3] tracking-[-0.01em]">
									{`${s.secret ?? unmask(s.value, names)} lue ${where}à l'étape ${s.step}`}
								</span>
								<dl className="grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-3.5 gap-y-1.5 font-mono text-[12.5px]">
									<dt className="text-[11px] text-mute-2">outil</dt>
									<dd>{s.tool}</dd>
									{path && (
										<>
											<dt className="text-[11px] text-mute-2">fichier</dt>
											<dd>{line ? `${path}, ligne ${line}` : path}</dd>
										</>
									)}
									{!path && line !== undefined && (
										<>
											<dt className="text-[11px] text-mute-2">ligne</dt>
											<dd>{line}</dd>
										</>
									)}
									<dt className="text-[11px] text-mute-2">correspondance</dt>
									<dd className="flex flex-wrap gap-[3px]">
										{HOW.map((h) => {
											const on = h.k === s.how;
											return (
												<span
													key={h.k}
													data-tip={
														on ? `${h.tip} · cette correspondance` : h.tip
													}
													className={`inline-flex h-5 items-center gap-1 border px-1.5 text-[11px] ${on ? "border-ink bg-ink text-surface" : "border-line-2 bg-surface text-mute-3"}`}
												>
													{on && <Check size={10} />}
													{h.label}
												</span>
											);
										})}
									</dd>
								</dl>
								<button
									type="button"
									onClick={() => go("live", { run: i.run_id, step: s.step })}
									className="btn btn-dark h-8 gap-1.5 self-start px-3 text-[13px]"
								>
									Aller à l'étape {s.step}
									<ArrowRight size={14} />
								</button>
							</div>
						);
					})}
					{!i.sources.length && (
						<p className="py-5 text-[13px] text-mute">
							Aucune valeur de l'appel retenu ne vient d'une lecture antérieure.
						</p>
					)}
				</div>
			</Box>
			<Box Icon={Triangle} title="LÉGS IMPLIQUÉES">
				{LEGS.map((g) => {
					const leg = i.legs[g.k];
					return (
						<div
							key={g.k}
							className={`grid grid-cols-[24px_minmax(0,1fr)] gap-2.5 border-line border-b px-[18px] py-3.5 last:border-b-0 ${leg.confirmed ? "" : "opacity-55"}`}
						>
							<span
								className="inline-flex size-6 items-center justify-center border-[1.2px] font-pixel text-[19px] leading-none"
								style={
									leg.confirmed
										? {
												background: g.color,
												borderColor: g.color,
												color: "var(--color-surface)",
											}
										: {
												borderColor: "var(--color-line-2)",
												color: "var(--color-mute-3)",
											}
								}
							>
								{g.L}
							</span>
							<div className="flex min-w-0 flex-col gap-1">
								<span className="flex flex-wrap items-baseline gap-2">
									<span className="font-medium text-sm">{g.name}</span>
									<span className="font-mono text-[11px] text-mute-2">
										{leg.confirmed ? "confirmée" : "non confirmée"}
									</span>
								</span>
								<span className="flex items-center gap-2">
									<Cells score={leg.score} color={g.color} />
									<span className="font-mono text-[11px]">
										{leg.score.toFixed(2)}
									</span>
								</span>
								{leg.facts.map((f) => (
									<span
										key={f}
										className="grid grid-cols-[8px_minmax(0,1fr)] items-baseline gap-2 text-[12.5px] leading-[1.4]"
									>
										<span className="size-1.5 bg-ink" />
										{f}
									</span>
								))}
							</div>
						</div>
					);
				})}
			</Box>
		</div>
	);
}
