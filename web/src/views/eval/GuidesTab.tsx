import type { EvalFile } from "@/api/types";
import { Info } from "@/components/icons";
import { num, pct, sample, seconds } from "@/lib/format";
import { HitChart } from "./charts";
import type { Guides } from "./read";
import { Aside, Panel, type Tile, Tiles } from "./ui";

export function GuidesTab({ file, g }: { file: EvalFile; g: Guides }) {
	const n = g.n_questions;
	const tiles: Tile[] = [
		{
			label: "Verified quotes",
			value: pct(g.citation_validity),
			sub: `across ${g.n_incidents} guides`,
			reading: "good, higher is better",
		},
		{
			label: "“I don’t know” out of scope",
			value: `${g.unsure_correct} / ${g.n_out_of_scope}`,
			sub: "questions with no source",
			reading: "good, higher is better",
		},
		{
			label: "Latency · p50 / p95",
			value: `${seconds(g.latency_p50_ms)} / ${seconds(g.latency_p95_ms)} s`,
			sub: `${sample(n)} questions`,
			reading: "watch, lower is better",
			watch: true,
		},
		{
			label: "hit@3 · re-ranked",
			value: num(g.hit_at_3_reranked, 2),
			sub: `BM25 ${num(g.hit_at_3_bm25, 2)} · hybrid ${num(g.hit_at_3_hybrid, 2)}`,
			reading: "good, higher is better",
		},
	];
	return (
		<>
			<Tiles file={file} tiles={tiles} />
			<Panel
				anim
				className="min-h-[300px] flex-1"
				head={
					<>
						<span>HIT@3 · RETRIEVAL</span>
						<Aside>
							{file.split} · {sample(n)} questions
						</Aside>
						<div className="flex-1" />
						<span
							data-tip={`Quotes verified at ${pct(g.citation_validity)} across ${g.n_incidents} guides`}
							// biome-ignore lint/a11y/noNoninteractiveTabindex: the tooltip opens on keyboard focus too
							tabIndex={0}
							className="cursor-help"
						>
							<Aside>
								<Info size={13} />
								{pct(g.citation_validity)} verified
							</Aside>
						</span>
					</>
				}
			>
				<HitChart
					hits={[
						{ label: "BM25", v: g.hit_at_3_bm25, n },
						{ label: "hybrid", v: g.hit_at_3_hybrid, n },
						{ label: "re-ranked", v: g.hit_at_3_reranked, n },
					]}
				/>
			</Panel>
		</>
	);
}
