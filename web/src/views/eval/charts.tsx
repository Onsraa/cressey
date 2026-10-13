import type { ChartConfiguration, ChartType, Plugin } from "chart.js";
import { useMemo } from "react";
import { chartRef } from "@/lib/chart";
import { num } from "@/lib/format";
import { inkColor } from "@/lib/utils";
import type { JudgedSet } from "./read";

// The design's hatch: the normal sessions' bar, a diagonal every 6 px.
function hatch(): CanvasPattern | string {
	const c = document.createElement("canvas");
	c.width = c.height = 6;
	const x = c.getContext("2d");
	if (!x) return inkColor();
	x.fillStyle = "#FEFEFE";
	x.fillRect(0, 0, 6, 6);
	x.fillStyle = inkColor();
	for (let i = 0; i < 6; i++) x.fillRect(i, 5 - i, 1, 1);
	return x.createPattern(c, "repeat") ?? inkColor();
}

const axes = (pct: boolean) => ({
	x: { grid: { display: false }, border: { color: inkColor() } },
	y: {
		min: 0,
		max: pct ? 100 : 1,
		ticks: {
			stepSize: pct ? 25 : 0.25,
			callback: (v: string | number) => (pct ? `${v} %` : v),
		},
		grid: { color: "#EDEDEB" },
		border: { color: inkColor() },
	},
});

// Each bar's value printed on top of it, in the pixel type.
const valTop = (label: (i: number) => string): Plugin<"bar"> => ({
	id: "valTop",
	afterDatasetsDraw: (ch) => {
		const k = ch.ctx;
		k.save();
		k.fillStyle = inkColor();
		k.font = "19px VT323, monospace";
		k.textAlign = "center";
		k.textBaseline = "bottom";
		ch.getDatasetMeta(0).data.forEach((bar, i) => {
			k.fillText(label(i), bar.x, bar.y - 3);
		});
		k.restore();
	},
});

function Canvas<T extends ChartType>({
	cfg,
	label,
}: {
	cfg: () => ChartConfiguration<T>;
	label: string;
}) {
	// biome-ignore lint/correctness/useExhaustiveDependencies: the chart is drawn once per mount
	const ref = useMemo(() => chartRef(cfg), []);
	return (
		<div className="relative m-[12px_14px_10px] min-h-0 flex-1">
			<canvas ref={ref} role="img" aria-label={label} />
		</div>
	);
}

// Sessions held: the incidents against the normal ones, each as k of n.
export function HeldChart({
	incidents,
	normal,
	split,
}: {
	incidents: [number, number];
	normal: [number, number];
	split: string;
}) {
	const nn = [incidents, normal];
	return (
		<Canvas
			label={`Held sessions: incidents vs normal (${split})`}
			cfg={() => ({
				type: "bar",
				data: {
					labels: ["incidents", "normal"],
					datasets: [
						{
							label: "held",
							data: nn.map(([k, n]) => (n ? (k / n) * 100 : 0)),
							backgroundColor: [inkColor(), hatch()],
							borderColor: inkColor(),
							borderWidth: 1.2,
							barPercentage: 0.6,
							categoryPercentage: 0.7,
						},
					],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					layout: { padding: { top: 20 } },
					scales: axes(true),
					plugins: {
						legend: { display: false },
						tooltip: {
							callbacks: {
								label: (c) =>
									`${nn[c.dataIndex][0]} / ${nn[c.dataIndex][1]} held (${split})`,
							},
						},
					},
				},
				plugins: [valTop((i) => `${nn[i][0]}/${nn[i][1]}`)],
			})}
		/>
	);
}

// Retrieval hit@3 for each retriever, lighter to darker.
export function HitChart({
	hits,
}: {
	hits: { label: string; v: number; n: number }[];
}) {
	return (
		<Canvas
			label={`hit@3 for ${hits.map((h) => h.label).join(", ")}`}
			cfg={() => ({
				type: "bar",
				data: {
					labels: hits.map((h) => h.label),
					datasets: [
						{
							label: "hit@3",
							data: hits.map((h) => h.v),
							backgroundColor: ["#A3A3A0", "#5C5C5A", inkColor()],
							borderColor: inkColor(),
							borderWidth: 1.2,
							barPercentage: 0.5,
						},
					],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					layout: { padding: { top: 20 } },
					scales: axes(false),
					plugins: {
						legend: { display: false },
						tooltip: {
							callbacks: {
								label: (c) => {
									const h = hits[c.dataIndex];
									return `hit@3: ${num(h.v, 2)} (${Math.round(h.v * h.n)} / ${h.n})`;
								},
							},
						},
					},
				},
				plugins: [valTop((i) => num(hits[i].v, 2))],
			})}
		/>
	);
}

// The design's cfgCal: every labelled case at its score, writes above, reports below,
// each lane spread a little so close scores don't hide each other; harmful as ink squares,
// benign as hollow circles; each set's threshold as a dashed red line.
export function BandChart({
	write,
	report,
}: {
	write: JudgedSet;
	report: JudgedSet;
}) {
	const jit = (i: number) => (((i * 2654435761) % 1000) / 1000 - 0.5) * 0.3;
	const lane = (set: JudgedSet, y: number, label: "yes" | "no") =>
		set.scores
			.filter((s) => s.label === label)
			.map((s, i) => ({
				x: s.score,
				y: y + jit(i + (label === "yes" ? 0 : 50)),
			}));
	return (
		<Canvas
			label="Decision band: the score of each labelled case from 0 to 1, yes vs no, with the threshold"
			cfg={() => ({
				type: "scatter",
				data: {
					datasets: [
						{
							label: "harmful (yes)",
							data: [...lane(write, 1, "yes"), ...lane(report, 0, "yes")],
							backgroundColor: inkColor(),
							pointStyle: "rect",
							pointRadius: 4,
							pointHoverRadius: 6,
						},
						{
							label: "benign (no)",
							data: [...lane(write, 1, "no"), ...lane(report, 0, "no")],
							backgroundColor: "#FEFEFE",
							borderColor: "#A3A3A0",
							borderWidth: 1.4,
							pointStyle: "circle",
							pointRadius: 3.5,
							pointHoverRadius: 5.5,
						},
					],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					layout: { padding: { right: 8 } },
					scales: {
						x: {
							type: "linear",
							min: 0,
							max: 1,
							grid: { color: "#EDEDEB" },
							border: { color: inkColor() },
							ticks: { stepSize: 0.25 },
							title: { display: true, text: "decision score" },
						},
						y: {
							type: "linear",
							min: -0.6,
							max: 1.6,
							grid: { display: false },
							border: { color: inkColor() },
							ticks: {
								stepSize: 1,
								callback: (v) =>
									v === 1
										? `writes n=${write.n}`
										: v === 0
											? `reports n=${report.n}`
											: "",
							},
						},
					},
					plugins: {
						legend: { display: false },
						tooltip: {
							callbacks: {
								label: (c) =>
									`${c.datasetIndex === 0 ? "harmful" : "benign"} · score ${num(c.parsed.x ?? 0, 2)}`,
							},
						},
					},
				},
				plugins: [
					{
						id: "thr",
						afterDatasetsDraw: (ch) => {
							const k = ch.ctx;
							const sx = ch.scales.x;
							const sy = ch.scales.y;
							const line = (xv: number, y0: number, y1: number) => {
								const px = sx.getPixelForValue(xv);
								k.save();
								k.strokeStyle = "#B8331C";
								k.lineWidth = 1.4;
								k.setLineDash([5, 4]);
								k.beginPath();
								k.moveTo(px, sy.getPixelForValue(y0));
								k.lineTo(px, sy.getPixelForValue(y1));
								k.stroke();
								k.setLineDash([]);
								k.fillStyle = "#B8331C";
								k.font = "11px 'Geist Mono Variable', monospace";
								k.textAlign = "center";
								k.fillText(
									`threshold ${xv.toLocaleString("en-US")}`,
									px,
									sy.getPixelForValue(y1) - 4,
								);
								k.restore();
							};
							line(write.threshold, 0.45, 1.55);
							line(report.threshold, -0.55, 0.45);
						},
					},
				],
			})}
		/>
	);
}
