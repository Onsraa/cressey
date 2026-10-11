import { Chart, type ChartConfiguration, type ChartType } from "chart.js/auto";

// The design's chartSetup: Geist Mono, the dashboard's greys, square dark tooltips and bars.
const d = Chart.defaults;
d.font.family = "'Geist Mono Variable', ui-monospace, monospace";
d.font.size = 11;
d.color = "#4A4A4A";
d.borderColor = "#E4E4E2";
d.set("animation", { duration: 420 });
Object.assign(d.plugins.tooltip, {
	backgroundColor: "#1E1E1E",
	cornerRadius: 0,
	padding: 8,
	displayColors: false,
	titleFont: {
		family: "'Geist Mono Variable', monospace",
		size: 11,
		weight: 500,
	},
	bodyFont: { family: "'Geist Mono Variable', monospace", size: 11 },
});
d.elements.bar.borderRadius = 0;

export { Chart };

// A canvas ref that draws the chart on mount and destroys it on unmount. Keep it stable
// (useCallback): a new one each render would redraw the chart from scratch.
export const chartRef =
	<T extends ChartType>(make: () => ChartConfiguration<T>) =>
	(el: HTMLCanvasElement | null) => {
		if (!el) return;
		const c = new Chart(el, make());
		return () => c.destroy();
	};
