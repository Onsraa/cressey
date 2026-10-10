import type { EvalFile } from "@/api/types";
import { Cells } from "@/components/Cells";
import { ms, share, signed } from "./format";
import type { Ablation } from "./read";
import { Aside, Head, type Tile, Tiles } from "./ui";

type Cell = { value: string; score?: number }; // a score draws the pixel cells

const held = (k: number, n: number): Cell => ({
	value: `${k} / ${n}`,
	score: share(k, n),
});

function Ids({
	title,
	note,
	ids,
}: {
	title: string;
	note: string;
	ids: string[];
}) {
	return (
		<section className="panel">
			<Head>
				<span>{title}</span>
				<Aside>{ids.length}</Aside>
			</Head>
			<p className="px-[18px] pt-3 text-[13px] text-mute leading-[1.4]">
				{note}
			</p>
			<ul className="px-[18px] pb-2">
				{ids.map((id) => (
					<li key={id} className="border-line border-b py-2 font-mono text-xs">
						{id}
					</li>
				))}
				{ids.length === 0 && (
					<li className="py-2 font-mono text-mute-2 text-xs">aucune</li>
				)}
			</ul>
		</section>
	);
}

export function AblationTab({ file, a }: { file: EvalFile; a: Ablation }) {
	const { floor: f, both: b } = a;
	const incidents = new Set(
		b.sessions.filter((s) => s.expect === "held").map((s) => s.session),
	);
	const gained = a.only_triangle.filter((id) => incidents.has(id)).length;
	const stop =
		f.stop_ms_p50 === null || b.stop_ms_p50 === null
			? "—"
			: `${signed(b.stop_ms_p50 - f.stop_ms_p50)} ms`;
	const tiles: Tile[] = [
		{
			label: "Incidents retenus par le triangle seul",
			value: signed(gained),
			sub: `${f.incident_held} → ${b.incident_held} sur ${b.incident_sessions}`,
			reading: "bon, plus haut est mieux",
		},
		{
			label: "Retenues en trop",
			value: signed(b.normal_held - f.normal_held),
			sub: `${f.normal_held} → ${b.normal_held} sur ${b.normal_sessions}`,
			reading: "à surveiller, le coût du triangle",
			watch: true,
		},
		{
			label: "Arrêt · p50",
			value: stop,
			sub: `${ms(f.stop_ms_p50)} → ${ms(b.stop_ms_p50)} ms`,
			reading: "bon, plus bas est mieux",
		},
	];
	const rows: { label: string; floor: Cell; both: Cell }[] = [
		{
			label: "Sessions d'incident retenues",
			floor: held(f.incident_held, f.incident_sessions),
			both: held(b.incident_held, b.incident_sessions),
		},
		{
			label: "Sessions normales retenues par erreur",
			floor: held(f.normal_held, f.normal_sessions),
			both: held(b.normal_held, b.normal_sessions),
		},
		{
			label: "Temps d'arrêt · p50",
			floor: { value: `${ms(f.stop_ms_p50)} ms` },
			both: { value: `${ms(b.stop_ms_p50)} ms` },
		},
	];
	const grid = "grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]";

	return (
		<>
			<Tiles file={file} tiles={tiles} />
			<div className="rise grid grid-cols-[repeat(auto-fit,minmax(320px,1fr))] items-start gap-4">
				<section className="panel">
					<div
						className={`${grid} border-ink border-b-[1.2px] font-mono text-xs`}
					>
						<span className="px-3.5 py-2.5 text-mute-2">{file.split}</span>
						<span className="border-line border-l px-3.5 py-2.5">
							plancher seul
						</span>
						<span className="bg-ink px-3.5 py-2.5 text-surface">
							plancher + triangle
						</span>
					</div>
					{rows.map((r) => (
						<div key={r.label} className={`${grid} border-line border-b`}>
							<span className="p-5 text-[13.5px] leading-[1.35]">
								{r.label}
							</span>
							{(["floor", "both"] as const).map((k) => {
								const { value, score } = r[k];
								return (
									<div
										key={k}
										className="flex flex-col gap-[7px] border-line border-l p-5"
									>
										<span className="whitespace-nowrap font-pixel text-[34px] leading-[0.8]">
											{value}
										</span>
										{/* 10 cells: 20 would overflow the column on a 1280 px screen */}
										{score !== undefined && (
											<Cells
												score={score}
												color="var(--color-ink)"
												n={10}
												size={7}
											/>
										)}
									</div>
								);
							})}
						</div>
					))}
				</section>
				<div className="flex flex-col gap-4">
					<Ids
						title="TRIANGLE SEUL"
						note="Sessions retenues seulement quand le triangle peut retenir."
						ids={a.only_triangle}
					/>
					<Ids
						title="PLANCHER SEUL"
						note="Sessions retenues par le plancher seul, mais pas quand le triangle s'y ajoute."
						ids={a.only_floor}
					/>
				</div>
			</div>
		</>
	);
}
