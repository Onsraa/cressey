// A score from 0 to 1 as a row of pixel cells: the design's leg meter.
export function Cells({
	score,
	color,
	n = 20,
	size = 6,
}: {
	score: number;
	color: string;
	n?: number;
	size?: number;
}) {
	const on = Math.round(score * n);
	const cells = Array.from({ length: n }, (_, i) => i);
	return (
		<span aria-hidden="true" className="inline-flex gap-px">
			{cells.map((i) => (
				<span
					key={i}
					style={{
						width: size,
						height: size,
						background: i < on ? color : "var(--color-line)",
					}}
				/>
			))}
		</span>
	);
}
