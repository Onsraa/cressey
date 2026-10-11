import { useLive } from "@/api/live";
import { Detail } from "./Detail";
import { Queue } from "./Queue";

// The design's incL: the queue beside the detail, or above it, from a page width of 820 px
// less the sidebar and 40 px, so 804 px on this box inside its 28 px paddings.
export function IncidentsView() {
	const { incidents, focus } = useLive();
	const selected =
		incidents.find((i) => i.id === focus.incident) ?? incidents[0];
	return (
		<div
			data-slot="inc"
			className="@container flex min-h-0 flex-1 flex-col px-7 pt-6 pb-7"
		>
			<div className="grid min-h-[1212px] flex-1 grid-cols-1 grid-rows-[300px_900px] gap-4 @min-[804px]:min-h-[560px] @min-[804px]:grid-cols-[minmax(260px,320px)_minmax(0,1fr)] @min-[804px]:grid-rows-[minmax(0,1fr)]">
				<Queue selected={selected?.id} />
				<section data-anim aria-label="Incident detail" className="panel">
					{selected ? (
						<Detail incident={selected} />
					) : (
						<p className="p-6 font-mono text-[13px] text-mute">
							No open incidents.
						</p>
					)}
				</section>
			</div>
		</div>
	);
}
