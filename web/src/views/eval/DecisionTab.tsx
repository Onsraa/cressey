import type { EvalFile } from "@/api/types";
import { Strip } from "./charts";
import { num, sample, signed } from "./format";
import type { Decision, JudgedSet, Latency } from "./read";
import { Aside, Head, type Tile, Tiles } from "./ui";

const CALL: Record<Latency["call"], string> = {
	label: "étiquettes",
	judgment: "jugement",
	report: "rapport",
};

const usd = (v: number) =>
	v.toLocaleString("fr-FR", {
		style: "currency",
		currency: "USD",
		maximumFractionDigits: 3,
	});

// Accuracy at the threshold, with the margin and the calibration error.
const judged = (s: JudgedSet) => ({
	value: s.accuracy.replace("/", " / "),
	sub: `seuil ${s.threshold.toLocaleString("fr-FR")} · marge ${signed(s.margin, 2)} · ECE ${num(s.ece, 3)}`,
});

function SetStrip({ title, set }: { title: string; set: JudgedSet }) {
	return (
		<div className="flex min-w-0 flex-col gap-1">
			<span className="font-mono text-[11px] text-mute">
				{title} · n = {set.n}
			</span>
			<Strip
				scores={set.scores}
				threshold={set.threshold}
				label={`${title} : score de chaque cas étiqueté, oui contre non, seuil ${set.threshold.toLocaleString("fr-FR")}`}
			/>
		</div>
	);
}

export function DecisionTab({ file, d }: { file: EvalFile; d: Decision }) {
	// The largest shift the injected text caused, with its sign.
	const shift = d.attack
		.flatMap((a) => a.deltas)
		.reduce((m, x) => (Math.abs(x) > Math.abs(m) ? x : m), 0);
	const held = d.attack.filter((a) => a.floorHeld).length;
	const p50 = d.latency.map((l) => l.p50_ms);
	const tiles: Tile[] = [
		{
			label: "Jugement des écritures",
			...judged(d.write),
			reading: "bon, plus haut est mieux",
		},
		{
			label: "Vérification du rapport",
			...judged(d.report),
			reading: "à surveiller, plus haut est mieux",
			watch: true,
		},
		{
			label: "Sous notre attaque",
			value: signed(shift, 2),
			sub: `écart de score max · plancher tenu ${held} / ${d.attack.length}`,
			reading: "à surveiller, plus près de 0 est mieux",
			watch: true,
		},
		{
			label: "Latence par appel · p50",
			value: `${num(Math.min(...p50))}–${num(Math.max(...p50))} ms`,
			sub: `${d.latency.map((l) => `${CALL[l.call]} ${num(l.p50_ms)}`).join(" · ")} · ${sample([...new Set(d.latency.map((l) => l.n))].join(" / "))}`,
			reading: "bon, plus bas est mieux",
		},
		{
			label: "Prix · million de jetons en entrée",
			value: usd(d.price),
			sub: `tarif de ${d.model}, pas une mesure`,
			reading: "bon, plus bas est mieux",
			price: true,
		},
	];

	return (
		<>
			<Tiles file={file} tiles={tiles} />
			<section className="panel rise flex-none">
				<Head>
					<span>SCORES PAR CAS</span>
					<Aside>{file.split} · étiquettes de l'équipe</Aside>
					<div className="flex-1" />
					<Aside>
						<span className="size-2.5 bg-held-strong" />
						oui : à signaler
					</Aside>
					<Aside>
						<span className="size-2.5 rounded-full border-[1.6px] border-ok-strong" />
						non : à laisser passer
					</Aside>
					<Aside>
						<span className="w-4 border-ink border-t-2 border-dashed" />
						seuil
					</Aside>
				</Head>
				<div className="grid grid-cols-[repeat(auto-fit,minmax(320px,1fr))] gap-x-8 gap-y-3 px-3.5 py-3">
					<SetStrip title="Jugement des écritures" set={d.write} />
					<SetStrip title="Vérification du rapport" set={d.report} />
				</div>
			</section>
		</>
	);
}
