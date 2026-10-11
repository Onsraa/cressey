import type { ChartConfiguration } from "chart.js";
import { useCallback, useEffect, useRef } from "react";
import { Chart as ChartJS } from "@/lib/chart";
import { fmt, levels, type Scored } from "./run";

type Line = ChartJS<"line", number[], string>;

// The design's legsCfg: one line per leg, each with its own dash and point so colour is
// never the only signal, and the held call marked with a salmon band.
function config(hold: {
	at: number;
}): ChartConfiguration<"line", number[], string> {
	const line = (label: string, color: string, more: object) => ({
		label,
		data: [],
		borderColor: color,
		borderWidth: 1.8,
		pointStyle: "rect" as const,
		pointRadius: 3.5,
		pointHoverRadius: 5,
		pointBackgroundColor: color,
		pointBorderColor: color,
		tension: 0,
		fill: false,
		...more,
	});
	return {
		type: "line",
		data: {
			labels: [],
			datasets: [
				line("P · Pressure", "#3D64D8", {}),
				line("O · Opportunity", "#0E8F86", {
					borderDash: [6, 4],
					pointBackgroundColor: "#FEFEFE",
				}),
				line("R · Rationalization", "#8A55D1", {
					borderDash: [2, 3],
					borderWidth: 2,
					pointStyle: "triangle",
					pointRadius: 4.5,
				}),
			],
		},
		options: {
			responsive: true,
			maintainAspectRatio: false,
			interaction: { mode: "index", intersect: false },
			scales: {
				y: {
					min: 0,
					max: 1,
					ticks: { stepSize: 0.25 },
					grid: { color: "#EDEDEB" },
					border: { color: "#1E1E1E" },
				},
				x: { grid: { display: false }, border: { color: "#1E1E1E" } },
			},
			plugins: {
				legend: {
					display: true,
					position: "top",
					align: "end",
					labels: { boxWidth: 18, boxHeight: 2, font: { size: 11 } },
				},
				tooltip: {
					callbacks: {
						label: (c) => `${c.dataset.label}: ${fmt(c.parsed.y ?? 0)}`,
					},
				},
			},
		},
		plugins: [
			{
				id: "holdMark",
				beforeDatasetsDraw: (ch) => {
					if (hold.at < 0) return;
					const x = ch.scales.x.getPixelForValue(hold.at);
					const a = ch.chartArea;
					const k = ch.ctx;
					k.save();
					k.fillStyle = "#FFD6CE";
					k.fillRect(x - 8, a.top, 16, a.bottom - a.top);
					k.fillStyle = "#1E1E1E";
					k.font = "17px VT323, monospace";
					k.textBaseline = "top";
					k.fillText("HELD", Math.min(x + 11, a.right - 36), a.top + 2);
					k.restore();
				},
			},
		],
	};
}

// Pressure, opportunity and rationalization at each scored call; new calls slide in.
export function Chart({ calls }: { calls: Scored[] }) {
	const chart = useRef<Line | null>(null);
	const hold = useRef({ at: -1 });
	const drawn = useRef("");
	const ref = useCallback((el: HTMLCanvasElement | null) => {
		if (!el) return;
		const c = new ChartJS(el, config(hold.current));
		chart.current = c;
		drawn.current = "";
		return () => {
			c.destroy();
			chart.current = null;
		};
	}, []);
	useEffect(() => {
		const c = chart.current;
		const at = calls.map((x) => levels(x.legs));
		const now = calls
			.map(
				({ step }, i) =>
					`${step.n}:${at[i].p},${at[i].o},${at[i].r}:${Boolean(step.held_until)}`,
			)
			.join();
		if (!c || now === drawn.current) return;
		drawn.current = now;
		c.data.labels = calls.map((x) => `#${x.step.n}`);
		c.data.datasets[0].data = at.map((x) => x.p);
		c.data.datasets[1].data = at.map((x) => x.o);
		c.data.datasets[2].data = at.map((x) => x.r);
		hold.current.at = calls.findIndex((x) => x.step.held_until);
		c.update();
	});
	return (
		<canvas
			ref={ref}
			role="img"
			aria-label="Leg scores for each call, with the held call marked"
		/>
	);
}
