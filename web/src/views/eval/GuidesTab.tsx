import { Info } from "lucide-react";
import type { EvalFile } from "@/api/types";
import { Bars, type Group } from "./charts";
import { num, pct, sample, seconds } from "./format";
import type { Guides } from "./read";
import { Aside, Head, type Tile, Tiles } from "./ui";

export function GuidesTab({ file, g }: { file: EvalFile; g: Guides }) {
	const n = g.n_questions;
	const tiles: Tile[] = [
		{
			label: "Verified quotes",
			value: pct(g.citation_validity),
			sub: `${sample(g.n_incidents)} guides`,
			reading: "good, higher is better",
		},
		{
			label: "“I don't know” out of scope",
			value: `${g.unsure_correct} / ${g.n_out_of_scope}`,
			sub: `${sample(g.n_out_of_scope)} out-of-scope questions`,
			reading: "good, higher is better",
		},
		{
			label: "Latency · p50 / p95",
			value: `${seconds(g.latency_p50_ms)} / ${seconds(g.latency_p95_ms)} s`,
			sub: `${sample(g.n_incidents)} guides`,
			reading: "to watch, lower is better",
			watch: true,
		},
		{
			label: "hit@3 · re-ranked",
			value: num(g.hit_at_3_reranked, 2),
			sub: `BM25 ${num(g.hit_at_3_bm25, 2)} · hybrid ${num(g.hit_at_3_hybrid, 2)} · ${sample(n)}`,
			reading: "good, higher is better",
		},
	];
	const hit = (label: string, v: number, fill: string): Group => ({
		label,
		bars: [
			{
				key: label,
				value: v,
				text: num(v, 2),
				tip: `hit@3 ${label}: ${num(v, 2)} (${Math.round(v * n)} / ${n})`,
				fill,
			},
		],
	});

	return (
		<>
			<Tiles file={file} tiles={tiles} />
			<section className="panel rise min-h-[300px] flex-1">
				<Head>
					<span>HIT@3 · RETRIEVAL</span>
					<Aside>
						{file.split} · n = {n} questions
					</Aside>
					<div className="flex-1" />
					<span
						data-tip="This report doesn't list its misses yet."
						// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
						tabIndex={0}
						className="cursor-help"
					>
						<Aside>
							<Info size={13} />
							misses not listed
						</Aside>
					</span>
				</Head>
				<Bars
					groups={[
						hit("BM25", g.hit_at_3_bm25, "var(--color-mute-3)"),
						hit("hybrid", g.hit_at_3_hybrid, "var(--color-mute-2)"),
						hit("re-ranked", g.hit_at_3_reranked, "var(--color-ink)"),
					]}
					label="Retrieval hit@3: BM25, hybrid and re-ranked"
				/>
			</section>
		</>
	);
}
